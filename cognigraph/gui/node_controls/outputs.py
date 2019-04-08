from pyqtgraph.parametertree import parameterTypes

from ...nodes import outputs
from ...utils.pyqtgraph import MyGroupParameter, SliderParameter

import logging

from PyQt5 import QtWidgets


class OutputNodeControls(MyGroupParameter):

    @property
    def OUTPUT_CLASS(self):
        raise NotImplementedError

    @property
    def CONTROLS_LABEL(self):
        raise NotImplementedError

    def __init__(self, output_node: OUTPUT_CLASS = None, **kwargs):
        super().__init__(name=self.CONTROLS_LABEL, **kwargs)

        if output_node is None:
            raise ValueError("Right now we can create controls"
                             " only for an already existing node")

        self._output_node = output_node  # type: self.OUTPUT_CLASS
        self._create_parameters()

        self.logger = logging.getLogger(type(self).__name__)
        self.logger.debug('Constructor called')

    def _create_parameters(self):
        raise NotImplementedError


class BrainViewerControls(OutputNodeControls):
    OUTPUT_CLASS = outputs.BrainViewer
    CONTROLS_LABEL = '3D visualization settings'

    TAKE_ABS_BOOL_NAME = 'Show absolute values: '
    LIMITS_MODE_COMBO_NAME = 'Limits: '
    LOCK_LIMITS_BOOL_NAME = 'Lock current limits: '
    BUFFER_LENGTH_SLIDER_NAME = 'Buffer length: '
    LOWER_LIMIT_SPIN_BOX_NAME = 'Lower limit: '
    UPPER_LIMIT_SPIN_BOX_NAME = 'Upper limit: '
    THRESHOLD_SLIDER_NAME = 'Show activations exceeding '

    def _create_parameters(self):
        take_abs_bool = parameterTypes.SimpleParameter(
            type='bool', name=self.TAKE_ABS_BOOL_NAME,
            value=True, readonly=True)
        take_abs_bool.sigValueChanged.connect(self._on_take_abs_toggled)
        self.take_abs_bool = self.addChild(take_abs_bool)

        limits_modes = self.OUTPUT_CLASS.LIMITS_MODES
        limits_mode_values = [limits_modes.LOCAL,
                              limits_modes.GLOBAL, limits_modes.MANUAL]
        limits_mode_value = self._output_node.limits_mode
        limits_mode_combo = parameterTypes.ListParameter(
            name=self.LIMITS_MODE_COMBO_NAME, values=limits_mode_values,
            value=limits_mode_value)
        limits_mode_combo.sigValueChanged.connect(self._on_limits_mode_changed)
        self.limits_mode_combo = self.addChild(limits_mode_combo)

        lock_limits_bool = parameterTypes.SimpleParameter(
            type='bool', name=self.LOCK_LIMITS_BOOL_NAME, value=False)
        lock_limits_bool.sigValueChanged.connect(self._on_lock_limits_toggled)
        self.lock_limits_bool = self.addChild(lock_limits_bool)

        buffer_length_value = self._output_node.buffer_length
        buffer_length_slider = SliderParameter(
            name=self.BUFFER_LENGTH_SLIDER_NAME, limits=(0.1, 10),
            value=buffer_length_value, prec=3, suffix=' s')
        buffer_length_slider.sigValueChanged.connect(
            self._on_buffer_length_changed)
        self.buffer_length_slider = self.addChild(buffer_length_slider)

        lower_limit_value = self._output_node.colormap_limits.lower
        upper_limit_value = self._output_node.colormap_limits.upper
        lower_limit_spinbox = parameterTypes.SimpleParameter(
            type='float', name=self.LOWER_LIMIT_SPIN_BOX_NAME,
            decimals=3, limits=(None, upper_limit_value))
        upper_limit_spinbox = parameterTypes.SimpleParameter(
            type='float', name=self.UPPER_LIMIT_SPIN_BOX_NAME,
            decimals=3, limits=(lower_limit_value, None))
        lower_limit_spinbox.sigValueChanged.connect(
            self._on_lower_limit_changed)
        upper_limit_spinbox.sigValueChanged.connect(
            self._on_upper_limit_changed)
        self.lower_limit_spinbox = self.addChild(lower_limit_spinbox)
        self.upper_limit_spinbox = self.addChild(upper_limit_spinbox)

        threshold_value = self._output_node.threshold_pct
        threshold_slider = SliderParameter(
            name=self.THRESHOLD_SLIDER_NAME, limits=(0, 99),
            value=threshold_value, prec=0, suffix='%')
        threshold_slider.sigValueChanged.connect(self._on_threshold_changed)
        self.threshold_slider = self.addChild(threshold_slider)

        gif_button = parameterTypes.ActionParameter(
            type='action', name='Record gif')
        gif_button.sigActivated.connect(self._toggle_gif_button)
        self.gif_button = self.addChild(gif_button)

    def _toggle_gif_button(self):
        print('in _toggle_gif_button')
        if self.gif_button.name() == "Stop recording":
            self.gif_button.setName("Record gif")

            self._output_node._stop_gif()
            save_path = QtWidgets.QFileDialog.getSaveFileName(
                caption="Save the recording", filter="Gif image (*.gif)")[0]
            self._output_node._save_gif(save_path)
        else:
            self._reset_gif_sector()
            self.gif_button.setName("Stop recording")
            self._output_node._start_gif()

    def _reset_gif_sector(self):
        # Get to the main window widget
        widgetRect = (self.parent().parent().widget.parent().parent().parent()
                      .centralWidget().widget(0).geometry())
        widgetRect.moveTopLeft(
            self.parent().parent().widget.parent().parent().parent()
            .centralWidget().mapToGlobal(widgetRect.topLeft()))
        self._output_node.sector = (widgetRect.left(), widgetRect.top(),
                                    widgetRect.right(), widgetRect.bottom())

    def _on_take_abs_toggled(self, param, value):
        # Changes to these setting
        pass

        # Changes to the node
        self._output_node.take_abs = value

    def _on_limits_mode_changed(self, param, value):
        # Changes to these settings
        if value == self.OUTPUT_CLASS.LIMITS_MODES.GLOBAL:
            self.lock_limits_bool.show(True)
            self.buffer_length_slider.show(True)
            self.lower_limit_spinbox.show(False)
            self.upper_limit_spinbox.show(False)

        if value == self.OUTPUT_CLASS.LIMITS_MODES.LOCAL:
            self.lock_limits_bool.show(False)
            self.buffer_length_slider.show(False)
            self.lower_limit_spinbox.show(False)
            self.upper_limit_spinbox.show(False)

        if value == self.OUTPUT_CLASS.LIMITS_MODES.MANUAL:
            self.lock_limits_bool.show(False)
            self.buffer_length_slider.show(False)
            self.lower_limit_spinbox.show(True)
            self.upper_limit_spinbox.show(True)

        # Changes to the node
        self._output_node.limits_mode = value

    def _on_lock_limits_toggled(self, param, value):
        # Changes to these settings
        pass

        # Changes to the node
        self._output_node.lock_limits = value

    def _on_buffer_length_changed(self, param, value):
        # Changes to these setting
        pass

        # Changes to the node
        self._output_node.buffer_length = value

    def _on_lower_limit_changed(self, param, value):
        # Changes to these settings
        pass

        # Changes to the node
        self._output_node.colormap_limits.lower = value

    def _on_upper_limit_changed(self, param, value):
        # Changes to these settings
        pass

        # Changes to the node
        self._output_node.colormap_limits.upper = value

    def _on_threshold_changed(self, param, value):
        # Changes to these setting
        pass

        # Changes to the node
        self._output_node.threshold_pct = value


class LSLStreamOutputControls(OutputNodeControls):
    OUTPUT_CLASS = outputs.LSLStreamOutput
    CONTROLS_LABEL = 'LSL stream'

    STREAM_NAME_STR_NAME = 'Output stream name: '

    def _create_parameters(self):
        stream_name = self._output_node.stream_name
        stream_name_str = parameterTypes.SimpleParameter(
            type='str', name=self.STREAM_NAME_STR_NAME,
            value=stream_name, editable=False)
        stream_name_str.sigValueChanged.connect(self._on_stream_name_changed)
        self.stream_name_str = self.addChild(stream_name_str)

    def _on_stream_name_changed(self, param, value):
        # Changes to these setting
        pass

        # Changes to the node
        self._output_node.stream_name = value


class SignalViewerControls(OutputNodeControls):
    OUTPUT_CLASS = outputs.SignalViewer
    CONTROLS_LABEL = 'Signal Viewer'

    def _create_parameters(self):
        pass


class FileOutputControls(OutputNodeControls):
    OUTPUT_CLASS = outputs.FileOutput
    CONTROLS_LABEL = 'File Output'

    def _create_parameters(self):
        pass


class TorchOutputControls(OutputNodeControls):
    OUTPUT_CLASS = outputs.TorchOutput
    CONTROLS_LABEL = 'Torch Tensor Output'

    def _create_parameters(self):
        pass


class ConnectivityViewerControls(OutputNodeControls):
    """Connectvity viewer controls"""
    CONTROLS_LABEL = 'ConnectivityViewer controls'
    PROCESSOR_CLASS = outputs.ConnectivityViewer

    def _create_parameters(self):
        ...
