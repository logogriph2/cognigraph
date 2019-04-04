import os.path as op
from PyQt5 import QtGui
from ...nodes.node import ProcessorNode
from ...nodes import processors
from ...helpers.pyqtgraph import MyGroupParameter, parameterTypes
from ...helpers.misc import class_name_of
from ..widgets import RoiSelectionDialog
import logging


class ProcessorNodeControls(MyGroupParameter):

    DISABLED_NAME = 'Disable: '

    @property
    def PROCESSOR_CLASS(self):
        raise NotImplementedError

    @property
    def CONTROLS_LABEL(self):
        raise NotImplementedError

    def __init__(self, processor_node: PROCESSOR_CLASS = None, **kwargs):
        super().__init__(name=self.CONTROLS_LABEL, **kwargs)

        if processor_node is None:
            raise ValueError("Right now we can create controls only"
                             " for an already existing node")

        self._processor_node = processor_node  # type: self.PROCESSOR_CLASS
        self._create_parameters()
        self._add_disable_parameter()

        self.logger = logging.getLogger(type(self).__name__)
        self.logger.debug('Constructor called')

    def _create_parameters(self):
        raise NotImplementedError

    def _add_disable_parameter(self):
        disabled_value = False  # TODO: change once disabling is implemented
        disabled = parameterTypes.SimpleParameter(
            type='bool', name=self.DISABLED_NAME,
            value=disabled_value, readonly=False)
        disabled.sigValueChanged.connect(self._on_disabled_changed)
        self.disabled = self.addChild(disabled)

    def _on_disabled_changed(self, param, value):
        self._processor_node.disabled = value


class PreprocessingControls(ProcessorNodeControls):
    PROCESSOR_CLASS = processors.Preprocessing
    CONTROLS_LABEL = 'Preprocessing'

    DURATION_NAME = 'Baseline duration: '

    def _create_parameters(self):

        duration_value = self._processor_node.collect_for_x_seconds
        duration = parameterTypes.SimpleParameter(
            type='int', name=self.DURATION_NAME, suffix='s',
            limits=(30, 180), value=duration_value)
        self.duration = self.addChild(duration)
        self.duration.sigValueChanged.connect(self._on_duration_changed)

    def _on_duration_changed(self, param, value):
        self._processor_node.collect_for_x_seconds = value


class LinearFilterControls(ProcessorNodeControls):
    PROCESSOR_CLASS = processors.LinearFilter
    CONTROLS_LABEL = 'Linear filter'

    LOWER_CUTOFF_NAME = 'Lower cutoff: '
    UPPER_CUTOFF_NAME = 'Upper cutoff: '

    def _create_parameters(self):

        lower_cutoff_value = self._processor_node.lower_cutoff
        upper_cutoff_value = self._processor_node.upper_cutoff

        lower_cutoff = parameterTypes.SimpleParameter(
            type='float', name=self.LOWER_CUTOFF_NAME,
            suffix='Hz', limits=(0, upper_cutoff_value - 0.01),
            value=lower_cutoff_value)
        upper_cutoff = parameterTypes.SimpleParameter(
            type='float', name=self.UPPER_CUTOFF_NAME, suffix='Hz',
            limits=(lower_cutoff_value, 100), value=upper_cutoff_value)

        self.lower_cutoff = self.addChild(lower_cutoff)
        self.upper_cutoff = self.addChild(upper_cutoff)

        lower_cutoff.sigValueChanged.connect(self._on_lower_cutoff_changed)
        upper_cutoff.sigValueChanged.connect(self._on_upper_cutoff_changed)

    def _on_lower_cutoff_changed(self, param, value):
        # Update the node
        if value == 0.0:
            self._processor_node.lower_cutoff = None
        else:
            self._processor_node.lower_cutoff = value  # TODO: implement on the filter side
        # Update the upper cutoff so that it is not lower that the lower one
        if self.upper_cutoff.value() != 0.0:
            self.upper_cutoff.setLimits((value, 100))

    def _on_upper_cutoff_changed(self, param, value):
        # Update the node
        if value == 0.0:
            self._processor_node.upper_cutoff = None
            value = 100
        else:
            self._processor_node.upper_cutoff = value  # TODO: implement on the filter side

        if self.lower_cutoff.value() != 0:
            # Update the lower cutoff so that it is not higher that the upper one
            self.lower_cutoff.setLimits((0, value))


class InverseModelControls(ProcessorNodeControls):
    CONTROLS_LABEL = 'Inverse modelling'
    PROCESSOR_CLASS = processors.InverseModel
    METHODS_COMBO_NAME = 'Method: '
    FILE_PATH_STR_NAME = 'Path to forward solution: '

    def __init__(self, pipeline, **kwargs):
        kwargs['title'] = 'Forward solution file'
        super().__init__(pipeline, **kwargs)

        try:
            file_path = self._processor_node.mne_forward_model_file_path
        except Exception:
            file_path = ''

        # Add LineEdit for choosing file
        file_path_str = parameterTypes.SimpleParameter(
                type='str', name=self.FILE_PATH_STR_NAME, value=file_path)

        file_path_str.sigValueChanged.connect(self._on_file_path_changed)

        self.file_path_str = self.addChild(file_path_str)

        # Add PushButton for choosing file
        file_path_button = parameterTypes.ActionParameter(
                type='action', name="Select data...")

        file_path_button.sigActivated.connect(self._choose_file)

        self.file_path_button = self.addChild(file_path_button)

    def _create_parameters(self):

        method_values = self.PROCESSOR_CLASS.SUPPORTED_METHODS
        method_value = self._processor_node.method
        methods_combo = parameterTypes.ListParameter(
            name=self.METHODS_COMBO_NAME, values=method_values,
            value=method_value)
        methods_combo.sigValueChanged.connect(self._on_method_changed)
        self.methods_combo = self.addChild(methods_combo)

    def _on_method_changed(self, param, value):
        self._processor_node.method = value

    def _choose_file(self):
        file_path = QtGui.QFileDialog.getOpenFileName(
                caption="Select forward solution",
                filter="MNE-python forward (*-fwd.fif)")

        if file_path != "":
            self.file_path_str.setValue(file_path[0])

    def _on_file_path_changed(self, param, value):
        self._processor_node.mne_forward_model_file_path = value


class EnvelopeExtractorControls(ProcessorNodeControls):
    PROCESSOR_CLASS = processors.EnvelopeExtractor
    CONTROLS_LABEL = 'Extract envelope: '

    FACTOR_NAME = 'Factor: '
    METHODS_COMBO_NAME = 'Method: '

    def _create_parameters(self):

        method_values = ['Exponential smoothing']  # TODO: change once we support more methods
        method_value = self._processor_node.method
        methods_combo = parameterTypes.ListParameter(
            name=self.METHODS_COMBO_NAME, values=method_values,
            value=method_value)
        methods_combo.sigValueChanged.connect(self._on_method_changed)
        self.methods_combo = self.addChild(methods_combo)

        factor_value = self._processor_node.factor
        factor_spin_box = parameterTypes.SimpleParameter(
            type='float', name=self.FACTOR_NAME, decimals=2,
            limits=(0.5, 0.99), value=factor_value)
        factor_spin_box.sigValueChanged.connect(self._on_factor_changed)
        self.factor_spin_box = self.addChild(factor_spin_box)

    def _on_method_changed(self):
        pass  # TODO: implement

    def _on_factor_changed(self):
        pass  # TODO: implement


class BeamformerControls(ProcessorNodeControls):
    PROCESSOR_CLASS = processors.Beamformer
    CONTROLS_LABEL = 'Beamformer'

    ADAPTIVENESS_NAME = 'Use adaptive version: '
    SNR_NAME = 'SNR: '
    OUTPUT_TYPE_COMBO_NAME = 'Output type: '
    FORGETTING_FACTOR_NAME = 'Forgetting factor (per second): '
    FILE_PATH_STR_NAME = 'Path to forward solution: '

    def __init__(self, pipeline, **kwargs):
        kwargs['title'] = 'Forward solution file'
        super().__init__(pipeline, **kwargs)

        try:
            file_path = self._processor_node.mne_forward_model_file_path
        except:
            file_path = ''
        # Add LineEdit for choosing file
        file_path_str = parameterTypes.SimpleParameter(
                type='str', name=self.FILE_PATH_STR_NAME, value=file_path)

        file_path_str.sigValueChanged.connect(self._on_file_path_changed)
        self.file_path_str = self.addChild(file_path_str)
        # Add PushButton for choosing file
        file_path_button = parameterTypes.ActionParameter(
                type='action', name="Select data...")

        file_path_button.sigActivated.connect(self._choose_file)
        self.file_path_button = self.addChild(file_path_button)

    def _create_parameters(self):
        # snr: float = 3.0, output_type: str = 'power', is_adaptive: bool = False,
        # forgetting_factor_per_second = 0.99
        is_adaptive = self._processor_node.is_adaptive
        adaptiveness_check = parameterTypes.SimpleParameter(
            type='bool', name=self.ADAPTIVENESS_NAME,
            value=is_adaptive, readonly=False)
        adaptiveness_check.sigValueChanged.connect(self._on_adaptiveness_changed)
        self.adaptiveness_check = self.addChild(adaptiveness_check)

        reg_value = self._processor_node.reg
        snr_spin_box = parameterTypes.SimpleParameter(
            type='float', name=self.SNR_NAME, decimals=2,
            limits=(0, 100.0), value=reg_value)
        snr_spin_box.sigValueChanged.connect(self._on_snr_changed)
        self.snr_spin_box = self.addChild(snr_spin_box)

        output_type_value = self._processor_node.output_type
        output_type_values = self.PROCESSOR_CLASS.SUPPORTED_OUTPUT_TYPES
        output_type_combo = parameterTypes.ListParameter(
            name=self.OUTPUT_TYPE_COMBO_NAME, values=output_type_values,
            value=output_type_value)
        output_type_combo.sigValueChanged.connect(self._on_output_type_changed)
        self.output_type_combo = self.addChild(output_type_combo)

        forgetting_factor_value =\
            self._processor_node.forgetting_factor_per_second
        forgetting_factor_spin_box = parameterTypes.SimpleParameter(
            type='float', name=self.FORGETTING_FACTOR_NAME, decimals=2,
            limits=(0.90, 0.99), value=forgetting_factor_value)
        forgetting_factor_spin_box.sigValueChanged.connect(
            self._on_forgetting_factor_changed)
        self.forgetting_factor_spin_box = self.addChild(
            forgetting_factor_spin_box)

    def _on_adaptiveness_changed(self, param, value):
        self.forgetting_factor_spin_box.show(value)
        self._processor_node.is_adaptive = value

    def _on_snr_changed(self, param, value):
        self._processor_node.snr = value

    def _on_output_type_changed(self, param, value):
        self._processor_node.output_type = value

    def _on_forgetting_factor_changed(self, param, value):
        self._processor_node.forgetting_factor_per_second = value

    def _choose_file(self):
        file_path = QtGui.QFileDialog.getOpenFileName(
                caption="Select forward solution",
                filter="MNE-python forward (*-fwd.fif)")

        if file_path != "":
            self.file_path_str.setValue(file_path[0])

    def _on_file_path_changed(self, param, value):
        self._processor_node.mne_forward_model_file_path = value


class MCEControls(ProcessorNodeControls):
    CONTROLS_LABEL = 'MCE Inverse modelling'
    PROCESSOR_CLASS = processors.MCE

    FILE_PATH_STR_NAME = 'Path to forward solution: '
    def _create_parameters(self):
        # method_values = self.PROCESSOR_CLASS.SUPPORTED_METHODS
        # method_value = self._processor_node.method
        # methods_combo = parameterTypes.ListParameter(
        # name=self.METHODS_COMBO_NAME, values=method_values,
        # value=method_value)
        # methods_combo.sigValueChanged.connect(self._on_method_changed)
        # self.methods_combo = self.addChild(methods_combo)
        pass

    def __init__(self, pipeline, **kwargs):
        kwargs['title'] = 'Forward solution file'
        super().__init__(pipeline, **kwargs)

        try:
            file_path = self._processor_node.mne_forward_model_file_path
        except:
            file_path = ''
        # Add LineEdit for choosing file
        file_path_str = parameterTypes.SimpleParameter(
                type='str', name=self.FILE_PATH_STR_NAME, value=file_path)

        file_path_str.sigValueChanged.connect(self._on_file_path_changed)
        self.file_path_str = self.addChild(file_path_str)
        # Add PushButton for choosing file
        file_path_button = parameterTypes.ActionParameter(
                type='action', name="Select data...")

        file_path_button.sigActivated.connect(self._choose_file)
        self.file_path_button = self.addChild(file_path_button)

    def _on_method_changed(self, param, value):
        # self._processor_node.method = value
        pass

    def _choose_file(self):
        file_path = QtGui.QFileDialog.getOpenFileName(
                caption="Select forward solution",
                filter="MNE-python forward (*-fwd.fif)")

        if file_path != "":
            self.file_path_str.setValue(file_path[0])

    def _on_file_path_changed(self, param, value):
        self._processor_node.mne_forward_model_file_path = value


class ICARejectionControls(ProcessorNodeControls):
    CONTROLS_LABEL = 'ICA rejection'
    PROCESSOR_CLASS = processors.MCE

    METHODS_COMBO_NAME = 'Method: '

    def _create_parameters(self):

        # method_values = self.PROCESSOR_CLASS.SUPPORTED_METHODS
        # method_value = self._processor_node.method
        # methods_combo = parameterTypes.ListParameter(name=self.METHODS_COMBO_NAME,
        #                                              values=method_values, value=method_value)
        # methods_combo.sigValueChanged.connect(self._on_method_changed)
        # self.methods_combo = self.addChild(methods_combo)
        pass

    def _on_method_changed(self, param, value):
        # self._processor_node.method = value
        pass


class AtlasViewerControls(ProcessorNodeControls):
    OUTPUT_CLASS = processors.AtlasViewer
    CONTROLS_LABEL = 'Atlas Viewer'

    def _create_parameters(self):
        # for i, label in enumerate(self._processor_node.labels_info):
        #     val = parameterTypes.SimpleParameter(
        #         type='bool',
        #         name=label['name'] + ' --> ' + str(label['label_id']),
        #         value=label['state'])
        #     val.sigValueChanged.connect(
        #         lambda s, ss, ii=i, v=val: self._on_label_state_changed(ii, v))
        #     self.addChild(val)
        roi_selection_button = parameterTypes.ActionParameter(
            type='action', name='Select ROI')
        roi_selection_button.sigActivated.connect(self._choose_roi)
        self.roi_selection_button = self.addChild(roi_selection_button)

    def _choose_roi(self):
        # print(self._nodes)
        dialog = RoiSelectionDialog(self._processor_node.labels_info,
                                    self._processor_node.labels,
                                    op.join(self._processor_node.subjects_dir,
                                            self._processor_node.subject))
        if dialog.exec_():
            self._processor_node.labels_info = dialog.table.labels_info
            print('Ok')
        self.logger.debug('ROI selection button was clicked')

    def _on_label_state_changed(self, i, val):
        self._processor_node.labels_info[i]['state'] = val.value()
        self._processor_node.labels_info = self._processor_node.labels_info


class AmplitudeEnvelopeCorrelationsControls(ProcessorNodeControls):
    """Controls class for AEC node"""
    CONTROLS_LABEL = 'AmplitudeEnvelopeCorrelations controls'
    PROCESSOR_CLASS = processors.AmplitudeEnvelopeCorrelations

    def _create_parameters(self):
        ...


class CoherenceControls(ProcessorNodeControls):
    """Coherence node controls"""
    CONTROLS_LABEL = 'Coherence controls'
    PROCESSOR_CLASS = processors.Coherence

    def _create_parameters(self):
        ...
