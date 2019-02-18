from collections import namedtuple, OrderedDict

from pyqtgraph.parametertree import parameterTypes, ParameterTree, Parameter

from ..pipeline import Pipeline
from ..nodes import (
    sources as source_nodes,
    processors as processor_nodes,
    outputs as output_nodes
)
from .node_controls import (
    sources as source_controls,
    processors as processors_controls,
    outputs as outputs_controls
)
from ..helpers.pyqtgraph import MyGroupParameter
from ..helpers.misc import class_name_of

from .montage_menu import MontageMenu

import logging

NodeControlClasses = namedtuple('NodeControlClasses',
                                ['node_class', 'controls_class'])


class MultipleNodeControls(MyGroupParameter):
    """
    Base class for grouping of node settings (processors or outputs).
    Source is supported by a separate class.

    """

    @property
    def SUPPORTED_NODES(self):
        raise NotImplementedError

    def __init__(self, nodes, **kwargs):
        self._nodes = nodes
        super().__init__(**kwargs)

        for node in nodes:
            controls_class = self._find_controls_class_for_a_node(node)
            self.addChild(controls_class(node), autoIncrementName=True)

    @classmethod
    def _find_controls_class_for_a_node(cls, processor_node):
        for node_control_classes in cls.SUPPORTED_NODES:
            if isinstance(processor_node, node_control_classes.node_class):
                return node_control_classes.controls_class

        # Raise an error if processor node is not supported
        msg = ("Node of class {0} is not supported by {1}.\n"
               "Add NodeControlClasses(node_class, controls_class) to"
               " {1}.SUPPORTED_NODES").format(
                class_name_of(processor_node), cls.__name__)
        raise ValueError(msg)


class ProcessorsControls(MultipleNodeControls):
    SUPPORTED_NODES = [
        NodeControlClasses(processor_nodes.LinearFilter,
                           processors_controls.LinearFilterControls),
        NodeControlClasses(processor_nodes.InverseModel,
                           processors_controls.InverseModelControls),
        NodeControlClasses(processor_nodes.EnvelopeExtractor,
                           processors_controls.EnvelopeExtractorControls),
        NodeControlClasses(processor_nodes.Preprocessing,
                           processors_controls.PreprocessingControls),
        NodeControlClasses(processor_nodes.Beamformer,
                           processors_controls.BeamformerControls),
        NodeControlClasses(processor_nodes.MCE,
                           processors_controls.MCEControls),
        NodeControlClasses(processor_nodes.ICARejection,
                           processors_controls.ICARejectionControls),
        NodeControlClasses(processor_nodes.AtlasViewer,
                           processors_controls.AtlasViewerControls),
        NodeControlClasses(processor_nodes.AmplitudeEnvelopeCorrelations,
                           processors_controls.AmplitudeEnvelopeCorrelationsControls),
        NodeControlClasses(processor_nodes.Coherence,
                           processors_controls.CoherenceControls)
    ]


class OutputsControls(MultipleNodeControls):
    SUPPORTED_NODES = [
        NodeControlClasses(output_nodes.LSLStreamOutput,
                           outputs_controls.LSLStreamOutputControls),
        NodeControlClasses(output_nodes.BrainViewer,
                           outputs_controls.BrainViewerControls),
        NodeControlClasses(output_nodes.SignalViewer,
                           outputs_controls.SignalViewerControls),
        NodeControlClasses(output_nodes.FileOutput,
                           outputs_controls.FileOutputControls),
        NodeControlClasses(output_nodes.TorchOutput,
                           outputs_controls.TorchOutputControls),
        NodeControlClasses(output_nodes.ConnectivityViewer,
                           outputs_controls.ConnectivityViewerControls)
    ]


class BaseControls(MyGroupParameter):
    def __init__(self, pipeline):
        super().__init__(name='Base controls', type='BaseControls')
        self._pipeline = pipeline

        # TODO: Change names to delineate source_controls as defined here and
        # source_controls - gui.node_controls.source
        source_controls = SourceControls(pipeline=pipeline, name='Source')
        processors_controls = ProcessorsControls(nodes=pipeline._processors,
                                                 name='Processors')
        outputs_controls = OutputsControls(nodes=pipeline._outputs,
                                           name='Outputs')

        self.source_controls = self.addChild(source_controls)
        self.processors_controls = self.addChild(processors_controls)
        self.outputs_controls = self.addChild(outputs_controls)


class SourceControls(MyGroupParameter):
    """
    Represents a drop-down list with the names of supported source types.
    Selecting a type creates controls for that type below the drop-down.

    """

    # Order is important.
    # Entries with node subclasses must precede entries with the parent class
    SOURCE_OPTIONS = OrderedDict((
        ('LSL stream',
         NodeControlClasses(source_nodes.LSLStreamSource,
                            source_controls.LSLStreamSourceControls)),
        ('File data',
         NodeControlClasses(source_nodes.FileSource,
                            source_controls.FileSourceControls)),
    ))

    SOURCE_TYPE_COMBO_NAME = 'Source type: '
    SOURCE_TYPE_PLACEHOLDER = ''
    SOURCE_CONTROLS_NAME = 'source controls'

    def __init__(self, pipeline: Pipeline, **kwargs):
        self._pipeline = pipeline
        super().__init__(**kwargs)

        labels = ([self.SOURCE_TYPE_PLACEHOLDER] +
                  [label for label in self.SOURCE_OPTIONS])

        source_type_combo = parameterTypes.ListParameter(
            name=self.SOURCE_TYPE_COMBO_NAME, values=labels, value=labels[0])

        source_type_combo.sigValueChanged.connect(self._on_source_type_changed)
        self.source_type_combo = self.addChild(source_type_combo)

        if pipeline.source is not None:
            for source_option, classes in self.SOURCE_OPTIONS.items():
                if isinstance(pipeline.source, classes.node_class):
                    self.source_type_combo.setValue(source_option)
        #self.check_channels()

    def _on_source_type_changed(self, param, value):
        try:
            source_controls = self.source_controls
            self.removeChild(source_controls)
        except AttributeError:  # No source type has been chosen
            pass
        if value != self.SOURCE_TYPE_PLACEHOLDER:
            # Update source controls
            source_classes = self.SOURCE_OPTIONS[value]
            controls = source_classes.controls_class(
                pipeline=self._pipeline, name=self.SOURCE_CONTROLS_NAME)
            self.source_controls = self.addChild(controls)

            # Update source
            if not isinstance(self._pipeline.source,
                              source_classes.node_class):
                self._pipeline.source = self.source_controls.create_node()
                #self.check_channels()

    """def check_channels(self):

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
                    ---------------read-forward-file------------------------
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

            if len(missing_ch_names)>0:
                self.montage_menu = MontageMenu(source_ch_names=self.source_ch_names,
                                                forward_ch_names=self.forward_ch_names, source_bads =self.source_bads, forward_bads =self.forward_bads, source_controls=self)
                self.montage_menu.exec()"""


class Controls(object):
    def __init__(self, pipeline: Pipeline):
        super().__init__()
        self._pipeline = pipeline  # type: Pipeline
        self._base_controls = BaseControls(pipeline=self._pipeline)
        self.widget = self._base_controls.create_widget()

    def initialize(self):
        pass


