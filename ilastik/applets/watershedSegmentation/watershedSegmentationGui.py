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
##############################################################################
from functools import partial
from contextlib import contextmanager
import threading
import os

import numpy as np

import sip
from PyQt4.QtCore import Qt
from PyQt4.QtGui import QWidget, QLabel, QSpinBox, QDoubleSpinBox, QVBoxLayout, \
                        QHBoxLayout, QSpacerItem, QSizePolicy, QColor, QPen, QComboBox, QPushButton
from PyQt4.Qt import QCheckBox, QLineEdit, QButtonGroup, QRadioButton, pyqtSlot



from ilastik.utility.gui import threadRouted
from volumina.pixelpipeline.datasources import LazyflowSource, ArraySource
from volumina.layer import GrayscaleLayer, ColortableLayer, generateRandomColors
#from ilastik.applets.layerViewer.layerViewerGui import LayerViewerGui
from ilastik.applets.watershedLabeling.watershedLabelingGui import WatershedLabelingGui


from lazyflow.request import Request
from lazyflow.utility import TransposedView
#from lazyflow.operators import OpValueCache, OpTrainClassifierBlocked, OpClassifierPredict,\
                               #OpSlicedBlockedArrayCache, OpMultiArraySlicer2, \
                               #OpPixelOperator, OpMaxChannelIndicatorOperator, OpCompressedUserLabelArray, OpFeatureMatrixCache

#for the LabelPipeline
from lazyflow.operators import OpCompressedUserLabelArray
import logging
from PyQt4.Qt import QCheckBox
logger = logging.getLogger(__name__)

#LayerViewerGui->LabelingGui->WatershedSegmentationGui
class WatershedSegmentationGui(WatershedLabelingGui):

    ###########################################
    ### AppletGuiInterface Concrete Methods ###
    ###########################################
    def centralWidget( self ):
        return self
    
    '''
    def appletDrawer(self):
        return self._drawer
    '''

    def stopAndCleanUp(self):
        # Unsubscribe to all signals
        for fn in self.__cleanup_fns:
            fn()

        # Base class
        super( WatershedSegmentationGui, self ).stopAndCleanUp()
    
    ###########################################
    ###########################################
    
    def __init__(self, parentApplet, topLevelOperatorView, watershedLabelingDrawerUiPath=None ):

        #init the slots
        labelSlots                  = WatershedLabelingGui.LabelingSlots()
        labelSlots.labelInput       = topLevelOperatorView.CorrectedSeedsIn
        labelSlots.labelOutput      = topLevelOperatorView.CorrectedSeedsOut
        labelSlots.labelEraserValue = topLevelOperatorView.opLabelPipeline.opLabelArray.eraser
        labelSlots.labelDelete      = topLevelOperatorView.opLabelPipeline.DeleteLabel
        labelSlots.labelNames       = topLevelOperatorView.LabelNames

        self.RawDataName = "Seeds"
        self.__cleanup_fns = []

        self._currently_updating = False
        self.topLevelOperatorView = topLevelOperatorView

        '''
        # We provide our own UI file (which adds an extra control for interactive mode)
        if watershedLabelingDrawerUiPath is None:
            watershedLabelingDrawerUiPath = os.path.split(__file__)[0] + '/watershedLabelingDrawer.ui'
        '''

        super(WatershedSegmentationGui, self).__init__( parentApplet, \
                labelSlots, topLevelOperatorView, watershedLabelingDrawerUiPath )
        #use the default watershedLabelingDrawerUi of the super-class
        #super(WatershedSegmentationGui, self).__init__( parentApplet, labelSlots, topLevelOperatorView)

        '''
        self._sp_colortable = generateRandomColors(256, clamp={'v': 1.0, 's' : 0.5}, zeroIsTransparent=True)
        '''
        

        # Any time watershed is re-computed, re-update the layer set, 
        # in case the set of debug layers has changed.
        '''
        self.topLevelOperatorView.watershed_completed.subscribe( self.updateAllLayers )
        '''


        #pixel value functionality
        self._labelControlUi.pixelValueCheckBox.stateChanged.connect(self.toggleConnectionPixelValue)

        op = self.topLevelOperatorView 
        ############################################################
        # BEGIN TODO
        ############################################################



                

        # init the CorrectedSeedsIn with the ndarray of Seeds
        self.resetCorrectedSeedsInFromSeeds()

        # add Seeds for drawing and illustration
        self.addAsManyLabelsAsMaximumValueOfCorrectedSeedsIn()


        '''
        op = self.topLevelOperatorView 
        array = op.Seeds.value
        print array.shape
        #array = [1,2,3,4,5]
        #print array
        #TODO mache Inputslot darus???
        op.CorrectedSeedsIn.disconnect()
        op.CorrectedSeedsIn.setValue ( array )
        print op.CorrectedSeedsIn.value
        #op.CorrectedSeedsIn.value(op.Seeds.value)
        '''
        ############################################################
        # END TODO
        ############################################################

    '''

    def initAppletDrawerUi(self):
        """
        Overridden from base class (LayerViewerGui)
        """
        op = self.topLevelOperatorView
        
        #handler which takes the qt_signal and the slot that fits to this signal and connects them
        # clean-up and dirty-Notification will be done here too
        def configure_update_handlers( qt_signal, op_slot ):
            qt_signal.connect( self.configure_operator_from_gui )
            op_slot.notifyDirty( self.configure_gui_from_operator )
            self.__cleanup_fns.append( partial( op_slot.unregisterDirty, self.configure_gui_from_operator ) )

        def control_layout_wlw( widget1, label_text, widget2 ):
            """
            Define the way, how the labels for input widgets are shown in the gui
            They are added to a horizontal BoxLayout and afterwards 
            this layout is added to a vertivalLayoutBox
            """
            row_layout = QHBoxLayout()
            row_layout.addWidget(widget1)
            row_layout.addWidget( QLabel(label_text) )
            row_layout.addSpacerItem( QSpacerItem(10, 0, QSizePolicy.Expanding) )
            row_layout.addWidget(widget2)
            return row_layout

        def control_layout(*args):
            """
            Define the way, how the input widgets are shown in the gui
            They are added to a horizontal BoxLayout and afterwards 
            this layout is added to a vertivalLayoutBox
            """
            space=10
            row_layout = QHBoxLayout()
            begin = True
            # Add all arguments passed on
            for widget in args:
                #convert strings to QLabel
                #for python3.x add:
                #basestring = str
                if isinstance(widget, basestring):
                    widget = QLabel(widget)
                #only add space after first widget
                if not begin:
                    row_layout.addSpacerItem( QSpacerItem(space, 0, QSizePolicy.Expanding) )
                row_layout.addWidget(widget)
                begin = False
            return row_layout



        ############################################################
        #Configure the Gui
        ############################################################
        drawer_layout = QVBoxLayout()

            ############################################################
            # additional seeds
            ############################################################
        drawer_layout.addLayout( control_layout("Set additional seeds:") )
        drawer_layout.addLayout( control_layout("Caution: no effect in Batch Processing") )
        drawer_layout.addLayout( control_layout("") )

        """
        #channel Selection
        channel_box = QSpinBox()
        def set_channel_box_range(*args):
            if sip.isdeleted(channel_box):
                return
            channel_box.setMinimum(0)
            #throws an exception, if probabilities in input data aren't there, 
            #Fixed with op.Input.ready()
            if op.RawData.ready():
                channel_box.setMaximum( op.RawData.meta.getTaggedShape()['c']-1 )
            else:
                #only showed in debug mode
                #TODO not good, because emitted everytime when Input Data is changed
                logging.warning( "RawData not ready (maybe not existing)" )

        set_channel_box_range()
        op.RawData.notifyMetaChanged( set_channel_box_range )
        configure_update_handlers( channel_box.valueChanged, op.ChannelSelection )
        drawer_layout.addLayout( control_layout( self.RawDataName + " Channel", channel_box ) )
        self.channel_box = channel_box
        #connect the channel spinbox with the layer channel box
        self.channel_box.valueChanged.connect(self.on_RawData_channelChanged)
        """


        #show pixel value
        pixelValue = QLabel('unused')
        showPixelValue = QCheckBox()
        #configure_update_handlers not necessary here, 
        #because no information is passed on for calculations
        drawer_layout.addLayout( control_layout_wlw(showPixelValue, "Show Pixel-Value for Seeds:", pixelValue) )
        self.pixelValue = pixelValue
        self.showPixelValue = showPixelValue
        self.showPixelValue.stateChanged.connect(self.toggleConnectionPixelValue)
        
        

        #brush value dropdown or similar
        brush_value_box = QSpinBox()
        
        def set_brush_value_box_range(*args):
            if sip.isdeleted(brush_value_box):
                return
            brush_value_box.setMinimum(0)
            #throws an exception, if probabilities in input data aren't there, 
            #Fixed with op.Input.ready()
            if op.RawData.ready():
                if op.RawData.meta.drange:
                    #set min and max to the value range of the image
                    brush_value_box.setMinimum( op.RawData.meta.drange[0] )
                    brush_value_box.setMaximum( op.RawData.meta.drange[1] )
            else:
                #only showed in debug mode
                #TODO not good, because emitted everytime when Input Data is changed
                logging.warning( "RawData not ready (maybe not existing)" )
        set_brush_value_box_range()
        op.RawData.notifyMetaChanged( set_brush_value_box_range )
        configure_update_handlers( brush_value_box.valueChanged, op.BrushValue )
        drawer_layout.addLayout( control_layout("Brush value:", brush_value_box) )
        self.brush_value_box = brush_value_box
        #self.showPixelValue.stateChanged.connect(self.toggleConnectionPixelValue)

        ############################################################
        # BEGIN TODO
        ############################################################

        #pixel classification training applets
        # We provide our own UI file (which adds an extra control for interactive mode)
        #watershedLabelingDrawerUiPath = os.path.split(__file__)[0] + '/watershedLabelingDrawer.ui'

        #SIEHE TODO LISTE AUF BLOCK

        #toolBar = QToolBar()
        #first =  QToolButton()
        #arrowToolButton
        #paintToolButton
        #eraserToolButton
        #thresToolButton
        #brushSizeCaption
        #brushSizeComboBox
        
        #c++
        #button->setIcon(QIcon("<imagePath>"));
        #button->setIconSize(QSize(65,65));


        ############################################################
        # END TODO
        ############################################################

            ############################################################
            # seeded watershed
            ############################################################
        drawer_layout.addLayout( control_layout("") )
        drawer_layout.addLayout( control_layout("Seeded watershed:") )


        """
        seed_method_combo = QComboBox()
        seed_method_combo.addItem("Connected")
        seed_method_combo.addItem("Clustered")
        configure_update_handlers( seed_method_combo.currentIndexChanged, op.GroupSeeds )
        drawer_layout.addLayout( control_layout( "Seed WatershedLabeling", seed_method_combo ) )
        self.seed_method_combo = seed_method_combo
        
        enable_debug_box = QCheckBox()
        configure_update_handlers( enable_debug_box.toggled, op.EnableDebugOutputs )
        drawer_layout.addLayout( control_layout( "Show Debug Layers", enable_debug_box ) )
        self.enable_debug_box = enable_debug_box

        compute_button = QPushButton("Update Watershed", clicked=self.onUpdateWatershedsButton)
        drawer_layout.addWidget( compute_button )
        """

        
        ############################################################
        #Init the drawer for the Applet
        ############################################################
        # Finally, the whole drawer widget
        # which means all widgets created before are initilized to one widget, 
        # that is saved as a class member
        drawer = QWidget(parent=self)
        drawer.setLayout(drawer_layout)

        # Save these members for later use
        self._drawer = drawer

        # Initialize everything with the operator's initial values
        self.configure_gui_from_operator()

        # Delete space, so that the Layout lies on top of the page and not on bottom
        drawer_layout.setSpacing(0)
        drawer_layout.addSpacerItem( QSpacerItem(0, 10, QSizePolicy.Minimum, QSizePolicy.Expanding) )

    '''
    @contextmanager
    def set_updating(self):
        assert not self._currently_updating
        self._currently_updating = True
        yield
        self._currently_updating = False

    def configure_gui_from_operator(self, *args):
        """
        see configure_update_handlers
        """
        #TODO don't now, why to do this
        if self._currently_updating:
            return False
        with self.set_updating():
            op = self.topLevelOperatorView
            '''
            self.channel_box.setValue( op.ChannelSelection.value )
            rawData_layer = self.getLayerByName(self.RawDataName)
            if rawData_layer:
                rawData_layer.channel = op.ChannelSelection.value
            '''
            
            self.brush_value_box.setValue( op.BrushValue.value )
            #self.threshold_box.setValue( op.Pmin.value )
            #self.membrane_size_box.setValue( op.MinMembraneSize.value )
            #self.superpixel_size_box.setValue( op.MinSegmentSize.value )
            #self.seed_presmoothing_box.setValue( op.SigmaMinima.value )
            #self.watershed_presmoothing_box.setValue( op.SigmaWeights.value )
            #self.seed_method_combo.setCurrentIndex( int(op.GroupSeeds.value) )
            #self.enable_debug_box.setChecked( op.EnableDebugOutputs.value )

    def configure_operator_from_gui(self):
        """
        see configure_update_handlers
        """
        if self._currently_updating:
            return False
        with self.set_updating():
            op = self.topLevelOperatorView
            op.ChannelSelection.setValue( self.channel_box.value() )
            op.BrushValue.setValue( self.brush_value_box.value() )

            #op.Pmin.setValue( self.threshold_box.value() )
            #op.MinMembraneSize.setValue( self.membrane_size_box.value() )
            #op.MinSegmentSize.setValue( self.superpixel_size_box.value() )
            #op.SigmaMinima.setValue( self.seed_presmoothing_box.value() )
            #op.SigmaWeights.setValue( self.watershed_presmoothing_box.value() )
            #op.GroupSeeds.setValue( bool(self.seed_method_combo.currentIndex()) )
            #op.EnableDebugOutputs.setValue( self.enable_debug_box.isChecked() )

    '''
    def onUpdateWatershedsButton(self):
        def updateThread():
            """
            Temporarily unfreeze the cache and freeze it again after the views are finished rendering.
            """
            self.topLevelOperatorView.FreezeCache.setValue(False)
            
            # This is hacky, but for now it's the only way to do it.
            # We need to make sure the rendering thread has actually seen that the cache
            # has been updated before we ask it to wait for all views to be 100% rendered.
            # If we don't wait, it might complete too soon (with the old data).
            ndim = len(self.topLevelOperatorView.Superpixels.meta.shape)
            self.topLevelOperatorView.Superpixels((0,)*ndim, (1,)*ndim).wait()

            # Wait for the image to be rendered into all three image views
            for imgView in self.editor.imageViews:
                if imgView.isVisible():
                    imgView.scene().joinRenderingAllTiles()
            self.topLevelOperatorView.FreezeCache.setValue(True)

        self.getLayerByName("Superpixels").visible = True
        th = threading.Thread(target=updateThread)
        th.start()
    '''

    @pyqtSlot(int)
    def on_RawData_channelChanged(self, channel):
        """
        update the layer-channel after the channel_box has changed its value
        """
        rawData_layer = self.getLayerByName(self.RawDataName)
        if rawData_layer:
            rawData_layer.channel = self.channel_box.value()
        


    def setupLayers(self):
        """
        Responsable for the elements in the 'Viewer Controls'
        These are the views (e.g. opacitiy of Raw Data)
        that can be adjusted in the left corner of the program
        And for the Elements, that can be seen in the 'Central Widget', 
        these are excactly the one, that are shown in the Viewer Controls

        """

        layers = []
        op = self.topLevelOperatorView

        '''
        # Superpixels
        if op.Superpixels.ready():
            layer = ColortableLayer( LazyflowSource(op.Superpixels), self._sp_colortable )
            layer.name = "Superpixels"
            layer.visible = True
            layer.opacity = 0.5
            layers.append(layer)
            del layer

        # Debug layers
        if op.debug_results:
            for name, compressed_array in op.debug_results.items():
                axiskeys = op.Superpixels.meta.getAxisKeys()[:-1] # debug images don't have a channel axis
                permutation = map(lambda key: axiskeys.index(key) if key in axiskeys else None, 'txyzc')
                arraysource = ArraySource( TransposedView(compressed_array, permutation) )
                if compressed_array.dtype == np.uint32:
                    layer = ColortableLayer(arraysource, self._sp_colortable)
                else:
                    layer = GrayscaleLayer(arraysource)
                    # TODO: Normalize? Maybe the drange should be included with the debug image.
                layer.name = name
                layer.visible = False
                layer.opacity = 1.0
                layers.append(layer)
                del layer

        # Threshold
        if op.ThresholdedInput.ready():
            layer = ColortableLayer( LazyflowSource(op.ThresholdedInput), self._threshold_colortable )
            layer.name = "Thresholded Input"
            layer.visible = True
            layer.opacity = 1.0
            layers.append(layer)
            del layer
        '''

        #Boundaries
        if op.Boundaries.ready():
            layer = self._create_grayscale_layer_from_slot( op.Boundaries, op.Boundaries.meta.getTaggedShape()['c'] )
            layer.name = "Boundaries"
            layer.visible = False
            layer.opacity = 1.0
            layers.append(layer)
            del layer

        # Raw Data (color)
        if op.RawData.ready():
            layer = self.createStandardLayerFromSlot( op.RawData )
            layer.name = "Raw Data"
            layer.visible = False
            layer.opacity = 1.0
            layers.append(layer)
            del layer

        #TODO color?
        if op.Seeds.ready():
            layer = self._create_grayscale_layer_from_slot( op.Seeds, op.Seeds.meta.getTaggedShape()['c'] )
            #changing the Channel in the layer, 
            #changes the RawData Channel in the applet gui as well
            #layer.channelChanged.connect(self.channel_box.setValue)
            #setValue() will emit valueChanged() if the new value is different from the old one.
            #not necessary: self.channel_box.valueChanged.emit(i)

            layer.name = "Seeds"
            layer.visible = False
            layer.opacity = 1.0
            layers.append(layer)
            del layer


        #TODO color?
        if op.CorrectedSeedsIn.ready():
            layer = self.createStandardLayerFromSlot( op.CorrectedSeedsIn )
            #layer = self._create_grayscale_layer_from_slot( op.CorrectedSeedsIn, op.CorrectedSeedsIn.meta.getTaggedShape()['c'] )
            #changing the Channel in the layer, 
            #changes the RawData Channel in the applet gui as well
            #layer.channelChanged.connect(self.channel_box.setValue)
            #setValue() will emit valueChanged() if the new value is different from the old one.
            #not necessary: self.channel_box.valueChanged.emit(i)

            layer.name = "Corrected Seeds"
            layer.visible = True
            layer.opacity = 1.0
            layers.append(layer)
            del layer
        return layers

        '''
        #TODO color?
        if op.CorrectedSeedsOut.ready():
            layer = self.createStandardLayerFromSlot( op.CorrectedSeedsOut )
            #layer = self._create_grayscale_layer_from_slot( op.CorrectedSeedsIn, op.CorrectedSeedsIn.meta.getTaggedShape()['c'] )
            #changing the Channel in the layer, 
            #changes the RawData Channel in the applet gui as well
            #layer.channelChanged.connect(self.channel_box.setValue)
            #setValue() will emit valueChanged() if the new value is different from the old one.
            #not necessary: self.channel_box.valueChanged.emit(i)

            layer.name = "Corrected Seeds Out"
            layer.visible = True
            layer.opacity = 1.0
            layers.append(layer)
            del layer
        else:
            print op.CorrectedSeedsOut
            logging.warning("CorrectedSeedsOut not ready")
        '''


        return layers



    #slightly faster with pyqtSlot
    @pyqtSlot(int)
    def on_SpinBox_valueChanged_depricated(self, i):
        """
        executed when x,y,z,t or c is changed
        get the current values and change the view for the pixel-value
        The spinbox has updated its value, 
        so the new value i (of signal) == x.SpinBox.value() (for y,z as well)
        i remains unused

        """
        x = self.volumeEditorWidget.quadViewStatusBar.xSpinBox.value()
        y = self.volumeEditorWidget.quadViewStatusBar.ySpinBox.value()
        z = self.volumeEditorWidget.quadViewStatusBar.zSpinBox.value()
        t = self.volumeEditorWidget.quadViewStatusBar.timeSpinBox.value()
        c = self.channel_box.value()
        self.changeToNewPixelValue(x, y, z, t, c)

    def on_SpinBox_valueChanged(self, i):
        """
        executed when x,y,z or t is changed
        get the current values and change the view for the pixel-value
        The spinbox has updated its value, 
        so the new value i (of signal) == x.SpinBox.value() (for y,z as well)
        i remains unused

        """
        x = self.volumeEditorWidget.quadViewStatusBar.xSpinBox.value()
        y = self.volumeEditorWidget.quadViewStatusBar.ySpinBox.value()
        z = self.volumeEditorWidget.quadViewStatusBar.zSpinBox.value()
        t = self.volumeEditorWidget.quadViewStatusBar.timeSpinBox.value()
        #hard-coded that we only use the channel zero of the Seeds
        c = 0
        self.changeToNewPixelValue(x, y, z, t, c)



    def changeToNewPixelValue(self, x, y, z, t, c):
        """
        get the coord. information and get the value of the array-coord
        set the text of the gui to that value
        """
        op = self.topLevelOperatorView
        #TODO change Seeds to CorrectedSeedsIn
        data = op.CorrectedSeedsIn
        #data = op.Seeds
        tags = data.meta.axistags
        if data.ready():
            count = 0
            array = [0,0,0,0,0]
            # rearrangement of the indices of x,y,z,t,c to have the correct axis-order
            # indices always start with 0,1,...
            # if the dimensions are tagged, then they are ordered like: 0,1,2
            # and not like 1, 2, 3
            # so that the section with e.g. count == 3 makes sense
            
            tupl = (('x', x, tags.index('x')),
                    ('y', y, tags.index('y')),
                    ('z', z, tags.index('z')),
                    ('t', t, tags.index('t')),
                    ('c', c, tags.index('c')))

            #copy the axis-value into the array at the right index for all axes
            for (letter, value, index) in tupl:
                if (letter in tags):
                    count+=1
                    array[index] = value


            """ worse performance than if..elif..
            def f(count, data, array):
                for i in range(count):
                    data = data[array[i]]
                return data
            newValue = f(count, data.value, array)
            """
            if (count == 2):
                newValue = data.value[array[0],array[1]]
            elif (count == 3):
                newValue = data.value[array[0],array[1],array[2]]
            elif (count == 4):
                newValue = data.value[array[0],array[1],array[2],array[3]]
            elif (count == 5):
                newValue = data.value[array[0],array[1],array[2],array[3],array[4]]

            #show the value of the pixel under the curser on the gui
            self._labelControlUi.pixelValue.setText(str(newValue))

            """print infos
            print xIndex, ":", yIndex, ":", zIndex, ":", tIndex
            print tags
            print data
            print "array:", array
            print "pixelValue:", newValue
            """






    @pyqtSlot()
    def toggleConnectionPixelValue(self):
        """
        connect or disconnect the valueChanged signals from 
        coordinates x,y,z,t,c with the slot: on_SpinBox_valueChanged
        so that changes can be registered or not
        Additionally: change the label of the pixelValue

        Explanation for the x,y,z,timeSpinBox:
        # Connect the standard signal, that is emitted, when a QSpinBox changes its value, 
        # 'valueChanged' with the function that handles this change
        # to compute the changed value of the pixel with the new coordinates
        # Origin for better understanding:
        # volumina/volumina/sliceSelctorHud.py:
        # QuadStatusBar.xSpinBox (and y,z)
        # with standard signal: valueChanged
        # /volumina/volumina/volumeEditorWidget.py
        # self=VolumneEditorWidget
        # self.quadViewStatusBar = QuadStatusBar()
        # e.g. 
        #self.volumeEditorWidget.quadViewStatusBar.zSpinBox.valueChanged.connect( self.on_SpinBox_valueChanged )
        """

        #tuple with x,y,z,t,c and their spinBoxes
        sBar = self.volumeEditorWidget.quadViewStatusBar
        #tupl = (sBar.xSpinBox,  sBar.ySpinBox, sBar.zSpinBox, sBar.timeSpinBox, self.channel_box)
        tupl = (sBar.xSpinBox,  sBar.ySpinBox, sBar.zSpinBox, sBar.timeSpinBox)
        #if self.showPixelValue.isChecked():
        if self._labelControlUi.pixelValueCheckBox.isChecked():
            #connect x,y,z,t,c
            for box in tupl:
                box.valueChanged.connect(self.on_SpinBox_valueChanged)

            #emit signal (of local widget) to read in the pixel values immediately 
            #number is irrelevant, see on_SpinBox_valueChanged
            sBar.xSpinBox.valueChanged.emit(0)

        else:
            #disconnect x,y,z,t,c
            for box in tupl:
                box.valueChanged.disconnect(self.on_SpinBox_valueChanged)
            #reset pixelValue-Label
            self._labelControlUi.pixelValue.setText("unused")
            #self.pixelValue.setText("unused")






    def addAsManyLabelsAsMaximumValueOfCorrectedSeedsIn(self):
        """
        get the maximum value in CorrectedSeedsIn
        add as many Labels (Seeds for Labeling) as the Maximum value
        """
        op = self.topLevelOperatorView 
        #array = op.CorrectedSeedsIn
        array = op.CorrectedSeedsIn.value
        arrayMax = np.amax(array)

        for i in range(arrayMax):
            super( WatershedSegmentationGui, self )._addNewLabel()

    def resetCorrectedSeedsInFromSeeds(self):
        """
        reset the InputSlot CorrectedSeedsIn to the Seeds
        if Seeds is not ready, then initialize CorrectedSeedsIn with an array 
        of the right dimensions and values of zero (=background)
        CorrectedSeedsIn is connected to the OpLabelPipeline, so it is loaded into the cache
        """

        op = self.topLevelOperatorView 
        if op.Seeds.ready():
            # Read from file
            # copy the meta-data and the array from Seeds
            default_seeds_volume = op.Seeds[:].wait()
            op.CorrectedSeedsIn.meta = op.Seeds.meta
            op.CorrectedSeedsIn._value =  default_seeds_volume 


            
        else:
        #TODO if the Seeds is empty, then the CorrectedSeedsIn must have the right dimensions,
        #like the RawData (only one channel) and be a ndarray with values = 0
        #FIXME
            raise NotImplementedError
