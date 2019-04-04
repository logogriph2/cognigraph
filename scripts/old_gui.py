import sys

from pyqtgraph import QtCore, QtGui

from cognigraph.pipeline import Pipeline
from cognigraph.nodes import sources, processors, outputs
from cognigraph import TIME_AXIS
from cognigraph.gui.window import GUIWindow

app = QtGui.QApplication(sys.argv)

pipeline = Pipeline()

# file_path = r"/home/dmalt/Code/python/real_eyes/Koleno.eeg"
file_path = r"/home/dmalt/Data/cognigraph/data/Koleno.eeg"
# vhdr_file_path = r"/home/dmalt/Code/python/real_eyes/Koleno.vhdr"
# vhdr_file_path = r"/home/dmalt/Data/cognigraph/data/Koleno.vhdr"
# vhdr_file_path = r"/home/dmalt/Data/cognigraph/data/Koleno.fif"
fwd_path = r'/home/dmalt/mne_data/MNE-sample-data/MEG/sample/dmalt_custom-fwd.fif'
source = sources.FileSource(file_path=file_path)
pipeline.source = source
# pipeline.source = sources.LSLStreamSource(stream_name='cognigraph-mock-stream')

# Processors
preprocessing = processors.Preprocessing(collect_for_x_seconds=120)
pipeline.add_processor(preprocessing)

linear_filter = processors.LinearFilter(lower_cutoff=8.0, upper_cutoff=12.0)
pipeline.add_processor(linear_filter)

inverse_model = processors.InverseModel(method='MNE', forward_model_path=fwd_path, snr=1.0)
pipeline.add_processor(inverse_model)

# beamformer = processors.Beamformer(forward_model_path=fwd_path, output_type='activation')
# pipeline.add_processor(beamformer)

envelope_extractor = processors.EnvelopeExtractor()
pipeline.add_processor(envelope_extractor)

# Outputs
global_mode = outputs.BrainViewer.LIMITS_MODES.GLOBAL
three_dee_brain = outputs.BrainViewer(limits_mode=global_mode, buffer_length=6)
pipeline.add_output(three_dee_brain)
pipeline.add_output(outputs.LSLStreamOutput())
# pipeline.initialize_all_nodes()

signal_viewer = outputs.SignalViewer()
pipeline.add_output(signal_viewer, parent=linear_filter)

window = GUIWindow(pipeline=pipeline)
window.init_ui()
window.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
window.show()



base_controls = window._controls._base_controls
source_controls = base_controls.source_controls
processors_controls = base_controls.processors_controls
outputs_controls = base_controls.outputs_controls

source_controls.source_type_combo.setValue(source_controls.SOURCE_TYPE_PLACEHOLDER)


linear_filter_controls = processors_controls.children()[0]

envelope_controls = processors_controls.children()[2]
# envelope_controls.disabled.setValue(True)


three_dee_brain_controls = outputs_controls.children()[0]
three_dee_brain_controls.limits_mode_combo.setValue('Global')
three_dee_brain_controls.limits_mode_combo.setValue('Local')

window.initialize()


def run():
    pipeline.update_all_nodes()
    # print(pipeline.source._samples_already_read / 500)


timer = QtCore.QTimer()
timer.timeout.connect(run)
frequency = pipeline.frequency
timer.setInterval(1000. / frequency * 10)

source.loop_the_file = False
source.MAX_SAMPLES_IN_CHUNK = 5
# envelope.disabled = True


if __name__ == '__main__':
    import sys

    timer.start()
    timer.stop()

    # TODO: this runs when in iPython. It should not.
    # Start Qt event loop unless running in interactive mode or using pyside.
    # if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
    #     sys.exit(QtGui.QApplication.instance().exec_())
