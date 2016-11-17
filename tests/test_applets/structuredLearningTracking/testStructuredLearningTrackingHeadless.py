###############################################################################
#   ilastik: interactive learning and segmentation toolkit
#
#       Copyright (C) 2011-2014, the ilastik developers
#                                <team@ilastik.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# In addition, as a special exception, the copyright holders of
# ilastik give you permission to combine ilastik with applets,
# workflows and plugins which are not covered under the GNU
# General Public License.
#
# See the LICENSE file for details. License information is also available
# on the ilastik web site at:
#           http://ilastik.org/license.html
###############################################################################
import os
import sys
import imp
import numpy as np
import h5py
import tempfile
import csv
import nose

from lazyflow.graph import Graph
from lazyflow.operators.ioOperators import OpStackLoader
from lazyflow.operators.opReorderAxes import OpReorderAxes

import ilastik
from lazyflow.utility.timer import timeLogged

import logging
logger = logging.getLogger(__name__)

class TestStructuredLearningTrackingHeadless(object):    
    PROJECT_FILE = 'data/inputdata/mitocheckTrackingWithLearningFromSegmentation.ilp'
    RAW_DATA_FILE = 'data/inputdata/mitocheck_2d+t/mitocheck_small_2D+t.h5'
    PREDICTION_FILE = 'data/inputdata/mitocheck_2d+t/mitocheck_small_2D+t_export.h5'
    BINARY_SEGMENTATION_FILE = 'data/inputdata/mitocheck_2d+t/mitocheck_small_2D+t_Simple-Segmentation.h5'

    @classmethod
    def setupClass(cls):
        logger.info('starting setup...')
        cls.original_cwd = os.getcwd()

        # Load the ilastik startup script as a module.
        # Do it here in setupClass to ensure that it isn't loaded more than once.
        logger.info('looking for ilastik.py...')
        ilastik_entry_file_path = os.path.join( os.path.split( os.path.realpath(ilastik.__file__) )[0], "../ilastik.py" )
        if not os.path.exists( ilastik_entry_file_path ):
            raise RuntimeError("Couldn't find ilastik.py startup script: {}".format( ilastik_entry_file_path ))
            
        cls.ilastik_startup = imp.load_source( 'ilastik_startup', ilastik_entry_file_path )


    @classmethod
    def teardownClass(cls):
        removeFiles = []#['data/inputdata/mitocheckStructuredLearningTracking_Tracking-Weights.h5','data/inputdata/mitocheckStructuredLearningTracking_Tracking-Result.h5']
        
        # Clean up: Delete any test files we generated
        for f in removeFiles:
            try:
                os.remove(f)
            except:
                pass
        pass


    @timeLogged(logger)
    def testStructuredLearningTrackingHeadless(self):
        # Skip test if structured learning tracking can't be imported. If it fails the problem is most likely that CPLEX is not installed.
        try:
            import ilastik.workflows.tracking.structured
        except ImportError as e:
            logger.warn( "Structured learning tracking could not be imported. CPLEX is most likely missing: " + str(e) )
            raise nose.SkipTest 
        
        # Skip test because there are missing files
        if not os.path.isfile(self.PROJECT_FILE) or not os.path.isfile(self.RAW_DATA_FILE) or not os.path.isfile(self.BINARY_SEGMENTATION_FILE):
            logger.info("Test files not found.")   
        
        args = ' --project='+self.PROJECT_FILE
        args += ' --headless'
        args += ' --export_source=Tracking-Result'
        #args += ' --export_weights=_Tracking-Weights'
        args += ' --raw_data '+self.RAW_DATA_FILE#+'/data'
        #args += ' --prediction_maps '+self.PREDICTION_FILE#+'/exported_data'
        args += ' --binary_image '+self.BINARY_SEGMENTATION_FILE#+'/exported_data'

        sys.argv = ['ilastik.py'] # Clear the existing commandline args so it looks like we're starting fresh.
        sys.argv += args.split()

        # Start up the ilastik.py entry script as if we had launched it from the command line
        self.ilastik_startup.main()


if __name__ == "__main__":
    # Make the program quit on Ctrl+C
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    import sys
    import nose
    sys.argv.append("--nocapture")    # Don't steal stdout.  Show it on the console as usual.
    sys.argv.append("--nologcapture") # Don't set the logging level to DEBUG.  Leave it alone.
    nose.run(defaultTest=__file__)
