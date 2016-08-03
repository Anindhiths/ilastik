import warnings
import numpy as np

from lazyflow.graph import Operator, InputSlot, OutputSlot
from lazyflow.roi import roiToSlice
from lazyflow.operators import OpBlockedArrayCache, OpValueCache
from lazyflow.utility import Timer

import logging
logger = logging.getLogger(__name__)

##
## Check for OpenGM
##
try:
    import opengm_with_cplex as opengm
    OPENGM_SOLVER_NAMES = ['Opengm_IntersectionBased', 'Opengm_Cgc', 'Opengm_Exact']
except ImportError:
    # Are there any multicut solvers in OpenGM that work without CPLEX?
    # If not, there's no point in importing it at all.
    # import opengm
    OPENGM_SOLVER_NAMES = []

##
## Select Nifty implementation (if any)
##

# Nifty first choice: With-CPLEX
try:
    import nifty_with_cplex as nifty
    MulticutObjectiveUndirectedGraph = nifty.graph.multicut.MulticutObjectiveUndirectedGraph
    NIFTY_SOLVER_NAMES = ['Nifty_FmGreedy',
                          'Nifty_FmCplex',
                          'Nifty_ExactCplex']
except ImportError:
    NIFTY_SOLVER_NAMES = []

# Nifty second choice: With-Gurobi
if not NIFTY_SOLVER_NAMES:
    try:
        import nifty_with_gurobi as nifty
        MulticutObjectiveUndirectedGraph = nifty.graph.multicut.MulticutObjectiveUndirectedGraph
        NIFTY_SOLVER_NAMES = ['Nifty_FmGreedy',
                              'Nifty_FmGurobi',
                              'Nifty_ExactGurobi']
    except ImportError:
        NIFTY_SOLVER_NAMES = []

# Nifty third choice: No exact optimizer
if not NIFTY_SOLVER_NAMES:
    try:
        import nifty
        MulticutObjectiveUndirectedGraph = nifty.graph.multicut.MulticutObjectiveUndirectedGraph
        NIFTY_SOLVER_NAMES = ['Nifty_FmGreedy']
    except ImportError:
        # Nifty isn't available at all
        NIFTY_SOLVER_NAMES = []



AVAILABLE_SOLVER_NAMES = NIFTY_SOLVER_NAMES + OPENGM_SOLVER_NAMES

class OpMulticut(Operator):
    Beta = InputSlot(value=0.5)
    SolverName = InputSlot(value='Nifty_FmGreedy')
    FreezeCache = InputSlot(value=True)

    Rag = InputSlot() # value slot.  Rag object.
    Superpixels = InputSlot()
    EdgeProbabilities = InputSlot()
    EdgeProbabilitiesDict = InputSlot() # A dict of id_pair -> probabilities (used by the GUI)
    RawData = InputSlot(optional=True) # Used by the GUI for display only

    Output = OutputSlot() # Pixelwise output (not RAG, etc.)

    def __init__(self, *args, **kwargs):
        super( OpMulticut, self ).__init__(*args, **kwargs)

        self.opMulticutAgglomerator = OpMulticutAgglomerator(parent=self)
        self.opMulticutAgglomerator.Superpixels.connect( self.Superpixels )
        self.opMulticutAgglomerator.Beta.connect( self.Beta )
        self.opMulticutAgglomerator.SolverName.connect( self.SolverName )
        self.opMulticutAgglomerator.Rag.connect( self.Rag )
        self.opMulticutAgglomerator.EdgeProbabilities.connect( self.EdgeProbabilities )

        self.opSegmentationCache = OpBlockedArrayCache(parent=self)
        self.opSegmentationCache.fixAtCurrent.connect( self.FreezeCache )
        self.opSegmentationCache.Input.connect( self.opMulticutAgglomerator.Output )
        self.Output.connect( self.opSegmentationCache.Output )

    def setupOutputs(self):
        pass

    def execute(self, slot, subindex, roi, result):
        assert False, "Unknown or unconnected output slot: {}".format( slot )

    def propagateDirty(self, slot, subindex, roi):
        pass

class OpMulticutAgglomerator(Operator):
    SolverName = InputSlot()
    Beta = InputSlot()

    Rag = InputSlot()
    Superpixels = InputSlot() # Just needed for slot metadata
    EdgeProbabilities = InputSlot()
    Output = OutputSlot()

    def setupOutputs(self):
        self.Output.meta.assignFrom(self.Superpixels.meta)
        self.Output.meta.display_mode = 'random-colortable'

    def execute(self, slot, subindex, roi, result):
        edge_probabilities = self.EdgeProbabilities.value
        rag = self.Rag.value
        beta = self.Beta.value
        solver_name = self.SolverName.value

        with Timer() as timer:
            agglomerated_labels = self.agglomerate_with_multicut(rag, edge_probabilities, beta, solver_name)
        logger.info("'{}' Multicut took {} seconds".format( solver_name, timer.seconds() ))

        result[:] = agglomerated_labels[...,None]

        # FIXME: Is it okay to produce 0-based supervoxels?
        #result[:] += 1 # RAG labels are 0-based, but we want 1-based

    def propagateDirty(self, slot, subindex, roi):
        self.Output.setDirty()

    @classmethod
    def agglomerate_with_multicut(cls, rag, edge_probabilities, beta, solver_name):
        """
        rag: ilastikrag.Rag

        edge_probabilities: 1D array, same order as rag.edge_ids.
                            Should indicate probability of each edge being ON.

        beta: The multicut 'beta' parameter (0.0 < beta < 1.0)

        solver_name: The multicut solver used. Format: library_solver (e.g. opengm_Exact, nifty_Exact)

        Returns: A label image of the same shape as rag.label_img, type uint32
        """
        #
        # Check parameters
        #
        assert rag.edge_ids.shape == (rag.num_edges, 2)
        assert solver_name in AVAILABLE_SOLVER_NAMES, \
            "'{}' is not a valid solver name.".format(solver_name)

        # The Rag is allowed to contain non-consecutive superpixel labels,
        # but for OpenGM, we require node_count > max_id
        # Therefore, use max_sp, not num_sp
        node_count = rag.max_sp+1
        if rag.num_sp != rag.max_sp+1:
            warnings.warn( "Superpixel IDs are not consecutive. GM will contain excess variables to fill the gaps."
                           " (num_sp = {}, max_sp = {})".format( rag.num_sp, rag.max_sp ) )
        #
        # Solve
        #        
        edge_weights = compute_edge_weights(edge_probabilities, beta)
        assert edge_weights.shape == (rag.num_edges,)

        solver_library, solver_method = solver_name.split('_')
        if solver_library == 'Nifty':
            mapping_index_array = solve_with_nifty(rag.edge_ids, edge_weights, node_count, solver_method)
        elif solver_library == 'Opengm':
            mapping_index_array = solve_with_opengm(rag.edge_ids, edge_weights, node_count, solver_method)
        else:
            raise RuntimeError("Unknown solver library: '{}'".format(solver_library))

        #
        # Project solution onto supervoxels, return segmentation image
        #            
        agglomerated_labels = mapping_index_array[rag.label_img]
        assert agglomerated_labels.shape == rag.label_img.shape
        return agglomerated_labels

def compute_edge_weights( edge_probabilities, beta ):
    """
    Convert edge probabilities to energies for the multicut problem.
    
    edge_probabilities: 1-D, float
    beta: scalar, float
    """
    p1 = edge_probabilities # P(Edge=ON)
    p1 = np.clip(p1, 0.001, 0.999)
    p0 = 1.0 - p1 # P(Edge=OFF)

    edge_weights = np.log(p0/p1) + np.log( (1-beta)/(beta) )
    return edge_weights
    

def solve_with_nifty(edge_ids, edge_weights, node_count, solver_method):
    """
    Solve the given multicut problem with the 'Nifty' library and return an
    index array that maps node IDs to segment IDs.
    
    edge_ids: The list of edges in the graph. shape=(N, 2)

    edge_weights: Edge energies. shape=(N,)

    node_count: Number of nodes in the model.
                Note: Must be greater than the max ID found in edge_ids.
                      If your superpixel IDs are not consecutive, node_count should be max_sp_id+1

    solver_method: One of 'ExactCplex', 'FmGreedy', etc. 
    """
    # TODO: I don't know if this handles non-consecutive sp-ids properly
    g = nifty.graph.UndirectedGraph( int(node_count) )
    g.insertEdges(edge_ids)
    obj = nifty.graph.multicut.multicutObjective(g, edge_weights)

    moug = MulticutObjectiveUndirectedGraph

    def getIlpFac(ilpSolver):
        return moug.multicutIlpFactory(
                   ilpSolver=ilpSolver,
                   verbose=0,
                   addThreeCyclesConstraints=True,
                   addOnlyViolatedThreeCyclesConstraints=True)

    def getFmFac(subFac):
        return moug.fusionMoveBasedFactory(
            verbose=1,
            fusionMove=moug.fusionMoveSettings(mcFactory=subFac),
            proposalGen=moug.watershedProposals(sigma=1,seedFraction=0.01),
            numberOfIterations=500,
            numberOfParallelProposals=8,
            stopIfNoImprovement=20,
            fuseN=2
        )
    
     # TODO finetune parameters
    ret = None
    if solver_method == 'ExactCplex':
        inf = getIlpFac('cplex').create(obj)

    elif solver_method == 'ExactGurobi':
        inf = getIlpFac('gurobi').create(obj)

    elif solver_method == 'FmCplex':
        greedy=moug.greedyAdditiveFactory().create(obj)
        ret = greedy.optimize()
        inf = getFmFac(getIlpFac('cplex')).create(obj)

    elif solver_method == 'FmGurobi':
        greedy=moug.greedyAdditiveFactory().create(obj)
        ret = greedy.optimize()
        inf = getFmFac(getIlpFac('gurobi')).create(obj)

    elif solver_method == 'FmGreedy':
        greedy=moug.greedyAdditiveFactory().create(obj)
        ret = greedy.optimize()
        inf = getFmFac(moug.greedyAdditiveFactory()).create(obj)

    else:
        assert False, "Unknown solver method: {}".format( solver_method )

    if ret is None:
        ret = inf.optimize(visitor=moug.multicutVerboseVisitor())
    else:
        ret = inf.optimize(visitor=moug.multicutVerboseVisitor(), nodeLabels=ret)

    mapping_index_array = ret.astype(np.uint32)
    return mapping_index_array

def solve_with_opengm(edge_ids, edge_weights, node_count, solver_method):
    """
    Solve the given multicut problem with OpenGM and return an
    index array that maps node IDs to segment IDs.
    
    edge_ids: The list of edges in the graph. shape=(N, 2)

    edge_weights: Edge energies. shape=(N,)

    node_count: Number of nodes in the model.
                Note: Must be greater than the max ID found in edge_ids.
                      If your superpixel IDs are not consecutive, node_count should be max_sp_id+1

    solver_method: One of 'Exact', 'IntersectionBased', or 'Cgc'. 
    """
    gm = opengm.gm( np.ones(node_count)*node_count )
    pf = opengm.pottsFunctions( [node_count, node_count], np.array([0]), edge_weights )
    fids = gm.addFunctions( pf )
    gm.addFactors( fids, edge_ids )

    if solver_method == 'Exact':
        inf = opengm.inference.Multicut( gm )
    elif solver_method == 'IntersectionBased':
        inf = opengm.inference.IntersectionBased( gm )
    elif solver_method == 'Cgc':
        inf = opengm.inference.Cgc( gm, parameter=opengm.InfParam(planar=False) )
    else:
        assert False, "Unknown solver method: {}".format( solver_method )

    ret = inf.infer( inf.verboseVisitor() )
    if ret.name != "NORMAL":
        raise RuntimeError("OpenGM inference failed with status: {}".format( ret.name ))

    mapping_index_array = inf.arg().astype(np.uint32)
    return mapping_index_array
            

if __name__ == "__main__":
    import vigra

    from lazyflow.utility import blockwise_view

    # Superpixels are just (20,20,20) blocks, each with a unique value, 1-125
    superpixels = np.zeros( (100,100,100), dtype=np.uint32 )
    superpixel_block_view = blockwise_view( superpixels, (20,20,20) )
    assert superpixel_block_view.shape == (5,5,5,20,20,20)
    superpixel_block_view[:] = np.arange(1, 126).reshape( (5,5,5) )[..., None, None, None]

    superpixels = superpixels[...,None]
    assert superpixels.min() == 1
    assert superpixels.max() == 125

    # Make 3 random probability classes
    probabilities = np.random.random( superpixels.shape[:-1] + (3,) ).astype( np.float32 )
    probabilities = vigra.taggedView(probabilities, 'zyxc')

    superpixels = vigra.taggedView(superpixels, 'zyxc')

    from lazyflow.graph import Graph
    op = OpMulticut(graph=Graph())
    op.VoxelData.setValue( probabilities )
    op.InputSuperpixels.setValue( superpixels )
    assert op.Output.ready()
    seg = op.Output[:].wait()

    assert seg.min() == 0

    print "DONE."
