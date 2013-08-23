from PyQt4.QtCore import Qt
from PyQt4.QtGui import QColor

from volumina.api import LazyflowSource, ColortableLayer
from ilastik.applets.dataExport.dataExportGui import DataExportGui, DataExportLayerViewerGui

class ObjectClassificationDataExportGui( DataExportGui ):
    """
    A subclass of the generic data export gui that creates custom layer viewers.
    """
    def createLayerViewer(self, opLane):
        return ObjectClassificationResultsViewer(opLane)
        

def _createDefault16ColorColorTable():
    colors = []

    # Transparent for the zero label
    colors.append(QColor(0,0,0,0))

    # ilastik v0.5 colors
    colors.append( QColor( Qt.red ) )
    colors.append( QColor( Qt.green ) )
    colors.append( QColor( Qt.yellow ) )
    colors.append( QColor( Qt.blue ) )
    colors.append( QColor( Qt.magenta ) )
    colors.append( QColor( Qt.darkYellow ) )
    colors.append( QColor( Qt.lightGray ) )

    # Additional colors
    colors.append( QColor(255, 105, 180) ) #hot pink
    colors.append( QColor(102, 205, 170) ) #dark aquamarine
    colors.append( QColor(165,  42,  42) ) #brown
    colors.append( QColor(0, 0, 128) )     #navy
    colors.append( QColor(255, 165, 0) )   #orange
    colors.append( QColor(173, 255,  47) ) #green-yellow
    colors.append( QColor(128,0, 128) )    #purple
    colors.append( QColor(240, 230, 140) ) #khaki

#    colors.append( QColor(192, 192, 192) ) #silver
#    colors.append( QColor(69, 69, 69) )    # dark grey
#    colors.append( QColor( Qt.cyan ) )

    assert len(colors) == 16

    return [c.rgba() for c in colors]

class ObjectClassificationResultsViewer(DataExportLayerViewerGui):

    _colorTable16 = _createDefault16ColorColorTable()
    
    def setupLayers(self):
        layers = []

        fromDiskSlot = self.topLevelOperatorView.ImageOnDisk
        if fromDiskSlot.ready():
            exportLayer = ColortableLayer( LazyflowSource(fromDiskSlot), colorTable=self._colorTable16 )
            exportLayer.name = "Prediction - Exported"
            exportLayer.visible = True
            layers.append(exportLayer)

        previewSlot = self.topLevelOperatorView.ImageToExport
        if previewSlot.ready():
            previewLayer = ColortableLayer( LazyflowSource(previewSlot), colorTable=self._colorTable16 )
            previewLayer.name = "Prediction - Preview"
            previewLayer.visible = False
            layers.append(previewLayer)

        rawSlot = self.topLevelOperatorView.RawData
        if rawSlot.ready():
            rawLayer = self.createStandardLayerFromSlot(rawSlot)
            rawLayer.name = "Raw Data"
            rawLayer.opacity = 1.0
            layers.append(rawLayer)

        return layers 

