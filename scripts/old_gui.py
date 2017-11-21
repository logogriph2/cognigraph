from pyqtgraph import QtCore, QtGui

from cognigraph.pipeline import Pipeline
from cognigraph.nodes import sources, processors, outputs
from cognigraph import TIME_AXIS
from cognigraph.gui.window import GUIWindow

pipeline = Pipeline()
pipeline.source = sources.LSLStreamSource(stream_name='cognigraph-mock-stream')
linear_filter = processors.LinearFilter(lower_cutoff=0.1, upper_cutoff=40)
pipeline.add_processor(linear_filter)
pipeline.add_processor(processors.InverseModel(method='MNE'))
pipeline.add_output(outputs.ThreeDeeBrain())
pipeline.initialize_all_nodes()

window = GUIWindow(pipeline=pipeline)
window.init_ui()
window.show()


def run():
    pipeline.update_all_nodes()
    print(pipeline.source.output.shape[TIME_AXIS])


timer = QtCore.QTimer()
timer.timeout.connect(run)
frequency = pipeline.frequency

if __name__ == '__main__':
    import sys

    timer.start(1000. / frequency / 4)

    # TODO: this runs when in iPython. It should not.
    # Start Qt event loop unless running in interactive mode or using pyside.
    # if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
    #     sys.exit(QtGui.QApplication.instance().exec_())