from typing import List
from PyQt5 import QtCore, QtWidgets
from ..pipeline import Pipeline
from .controls import Controls
from .screen_recorder import ScreenRecorder

import logging
logger = logging.getLogger(name=__name__)

from .montage_menu import MontageMenu


class GUIWindow(QtWidgets.QMainWindow):
    def __init__(self, pipeline=Pipeline()):
        super().__init__()
        self._pipeline = pipeline  # type: Pipeline
        self._controls = Controls(pipeline=self._pipeline)
        self._controls_widget = self._controls.widget

        # Start button
        self.run_button = QtWidgets.QPushButton("Start")
        self.run_button.clicked.connect(self._toggle_run_button)

        # Record gif button and recorder
        self._gif_recorder = ScreenRecorder()
        self.gif_button = QtWidgets.QPushButton("Record gif")
        self.gif_button.clicked.connect(self._toggle_gif_button)

        # Resize screen
        self.resize(QtCore.QSize(
            QtWidgets.QDesktopWidget().availableGeometry().width() * 0.9,
            QtWidgets.QDesktopWidget().availableGeometry().height() * 0.9))

    def init_ui(self):
        self._controls.initialize()

        central_widget = QtWidgets.QSplitter()
        self.setCentralWidget(central_widget)

        # Build the controls portion of the window
        controls_layout = QtWidgets.QVBoxLayout()
        controls_layout.addWidget(self._controls_widget)

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addWidget(self.run_button)
        buttons_layout.addWidget(self.gif_button)

        controls_layout.addLayout(buttons_layout)

        self._controls_widget.setMinimumWidth(400)

        # Add control portion to the main widget
        controls_layout_wrapper = QtWidgets.QWidget()
        controls_layout_wrapper.setLayout(controls_layout)
        self.centralWidget().addWidget(controls_layout_wrapper)

    def initialize(self):
        logger.debug('Initializing all nodes')
        """---------------check inverse model here----------------------"""
        #self.check_channels()
        """-------------------------------------------------------------"""
        self._pipeline.initialize_all_nodes()
        for node_widget in self._node_widgets:
            if node_widget:
                # node_widget.setMinimumWidth(600)

                # insert widget at before-the-end pos (just before controls widget)
                self.centralWidget().insertWidget(self.centralWidget().count() - 1,
                                                  node_widget)
                self.centralWidget().insertWidget(
                    self.centralWidget().count() - 1, node_widget)
            else:
                raise ValueError('Node widget is not defined')

    def moveEvent(self, event):
        self._reset_gif_sector()
        return super(GUIWindow, self).moveEvent(event)

    def _reset_gif_sector(self):
        widgetRect = self.centralWidget().widget(0).geometry()
        widgetRect.moveTopLeft(
            self.centralWidget().mapToGlobal(widgetRect.topLeft()))
        self._gif_recorder.sector = (widgetRect.left(), widgetRect.top(),
                                     widgetRect.right(), widgetRect.bottom())

    def _toggle_run_button(self):
        if self.run_button.text() == "Pause":
            self.run_button.setText("Start")
        else:
            self.check_channels()
            self.run_button.setText("Pause")

    def _toggle_gif_button(self):
        if self.gif_button.text() == "Stop recording":
            self.gif_button.setText("Record gif")

            self._gif_recorder.stop()
            save_path = QtWidgets.QFileDialog.getSaveFileName(
                caption="Save the recording", filter="Gif image (*.gif)")[0]
            self._gif_recorder.save(save_path)
        else:
            self._reset_gif_sector()
            self.gif_button.setText("Stop recording")
            self._gif_recorder.start()

    @property
    def _node_widgets(self) -> List[QtWidgets.QWidget]:
        node_widgets = list()
        for node in self._pipeline.all_nodes:
            try:
                node_widgets.append(node.widget)
            except AttributeError:
                pass
        return node_widgets


    def check_channels(self):

        print("CHECK CHENNELS")

        import mne
        import os.path
        from ..helpers.misc import all_upper
        SUPPORTED_EXTENSIONS = {'Brainvision': ('.vhdr', '.eeg', '.vmrk'),
                                'MNE-python': ('.fif',),
                                'European Data Format': ('.edf',)}

        #source_channels = []
        #inverse_model_channels = []

        source_mne_info = None


        if self._pipeline.source is not None:
            if hasattr(self._pipeline.source,'mne_info'):
                if self._pipeline.source.mne_info is not None:
                    print('SOURCE MNE INFO',self._pipeline.source.mne_info)
                    self.source_ch_names = self._pipeline.source.mne_info['ch_names']

            if hasattr(self._pipeline.source,'_file_path'):
                #print('SOURCE FILE PATH',self._pipeline.source._file_path)
                basename = os.path.basename(self._pipeline.source._file_path)
                _, ext = os.path.splitext(basename)

                if ext in SUPPORTED_EXTENSIONS['Brainvision']:
                    raw = mne.io.read_raw_brainvision(vhdr_fname=self._pipeline.source._file_path,
                                                      verbose='ERROR')
                elif ext in SUPPORTED_EXTENSIONS['MNE-python']:
                    raw = mne.io.Raw(fname=self._pipeline.source._file_path, verbose='ERROR')

                elif ext in SUPPORTED_EXTENSIONS['European Data Format']:
                    raw = mne.io.edf.read_raw_edf(input_fname=self._pipeline.source._file_path, preload=True,
                                                  verbose='ERROR', stim_channel=-1,misc=[128, 129, 130])
                else:
                    raise ValueError(
                        'Cannot read {}.'.format(basename) +
                        'Extension must be one of the following: {}'.format(
                            self.SUPPORTED_EXTENSIONS.values()))
                source_mne_info = raw.info
                self.source_ch_names = source_mne_info['ch_names']
                self.source_bads = source_mne_info['bads']

        for _processor in self._pipeline._processors:
            if hasattr(_processor, 'mne_forward_model_file_path'):
                if _processor.mne_forward_model_file_path is not None:
                    #print('PROCESSOR FORWARD MODEL FILE PATH', _processor.mne_forward_model_file_path)
                    """---------------read-forward-file------------------------"""
                    f, tree, _ = mne.io.fiff_open(_processor.mne_forward_model_file_path)
                    with f as fid:
                        forward_mne_info = mne.forward._read_forward_meas_info(tree, fid)
                    '''---------------------------------------------'''
                    self.forward_ch_names = forward_mne_info['ch_names']
                    self.forward_bads = forward_mne_info["bads"]

        #source_bad_channels = source_mne_info['bads']

        if source_mne_info is not None:
            source_goods = mne.pick_types(source_mne_info, eeg=True, stim=False, eog=False,
                                   ecg=False, exclude='bads')
            source_ch_names_data = [self.source_ch_names[i] for i in source_goods]
            # Take only channels from both mne_info and the forward solution
            ch_names_intersect = [n for n in self.forward_ch_names if
                                  n.upper() in all_upper(source_ch_names_data)]
            missing_ch_names = [n for n in source_ch_names_data if
                                n.upper() not in all_upper(self.forward_ch_names)]
            print('source_ch_names_data',len(source_ch_names_data),'self.forward_ch_names',len(self.forward_ch_names))

            if len(missing_ch_names)>0:
                self.montage_menu = MontageMenu(source_ch_names=self.source_ch_names,
                                                forward_ch_names=self.forward_ch_names, source_bads =self.source_bads, forward_bads =self.forward_bads, source_controls=self)
                self.montage_menu.exec()
        else:
            print('NOT MNE INFO')

