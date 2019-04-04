import os
import time
from types import SimpleNamespace

import tables
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QSizePolicy

import mne
import nibabel as nib
import numpy as np
import pyqtgraph.opengl as gl
from matplotlib import cm
from matplotlib.colors import Colormap as matplotlib_Colormap
from mne.datasets import sample
from scipy import sparse

from ..helpers.pysurfer.smoothing_matrix import smoothing_matrix, mesh_edges
from .node import OutputNode
from .. import CHANNEL_AXIS, TIME_AXIS, PYNFB_TIME_AXIS
from ..helpers.lsl import (convert_numpy_format_to_lsl,
                           convert_numpy_array_to_lsl_chunk,
                           create_lsl_outlet)
from ..helpers.matrix_functions import last_sample, make_time_dimension_second
from ..helpers.ring_buffer import RingBuffer
from ..helpers.channels import read_channel_types, channel_labels_saver
from vendor.nfb.pynfb.widgets.signal_viewers import RawSignalViewer

# visbrain visualization imports
from ..gui.brain_visual import BrainMesh
from vispy import scene
# from vispy.app import Canvas

import torch


class WidgetOutput(OutputNode):
    def init_widget(self):
        if self.widget is not None:
            parent = self.widget.parent()
            ind = parent.indexOf(self.widget)
            cur_width = self.widget.size().width()
            cur_height = self.widget.size().height()
            self.widget.deleteLater()
            self.widget = self._create_widget()
            parent.insertWidget(ind, self.widget)
            self.widget.resize(cur_width, cur_height)
        else:
            self.widget = self._create_widget()
            self.widget.setMinimumWidth(50)

        def _create_widget(self):
            raise NotImplementedError


class LSLStreamOutput(OutputNode):

    def _on_input_history_invalidation(self):
        pass

    def _check_value(self, key, value):
        pass  # TODO: check that value as a string usable as a stream name

    CHANGES_IN_THESE_REQUIRE_RESET = ('stream_name', )

    UPSTREAM_CHANGES_IN_THESE_REQUIRE_REINITIALIZATION = (
        'source_name', 'mne_info', 'dtype')

    SAVERS_FOR_UPSTREAM_MUTABLE_OBJECTS = (
        {'mne_info': lambda info: (info['sfreq'], ) +
         channel_labels_saver(info)})

    def _reset(self):
        # It is impossible to change then name of an already
        # started stream so we have to initialize again
        self._should_reinitialize = True
        self.initialize()

    def __init__(self, stream_name=None):
        super().__init__()
        self._provided_stream_name = stream_name
        self.stream_name = None
        self._outlet = None

    def _initialize(self):
        # If no name was supplied we will use a modified
        # version of the source name (a file or a stream name)
        source_name = self.traverse_back_and_find('source_name')
        self.stream_name = (self._provided_stream_name or
                            (source_name + '_output'))

        # Get other info from somewhere down the predecessor chain
        dtype = self.traverse_back_and_find('dtype')
        channel_format = convert_numpy_format_to_lsl(dtype)
        mne_info = self.traverse_back_and_find('mne_info')
        frequency = mne_info['sfreq']
        channel_labels = mne_info['ch_names']
        channel_types = read_channel_types(mne_info)

        self._outlet = create_lsl_outlet(
            name=self.stream_name, frequency=frequency,
            channel_format=channel_format, channel_labels=channel_labels,
            channel_types=channel_types)

    def _update(self):
        chunk = self.parent.output
        lsl_chunk = convert_numpy_array_to_lsl_chunk(chunk)
        self._outlet.push_chunk(lsl_chunk)


class BrainViewer(OutputNode):

    CHANGES_IN_THESE_REQUIRE_RESET = ('buffer_length', 'take_abs', )
    UPSTREAM_CHANGES_IN_THESE_REQUIRE_REINITIALIZATION = (
        'mne_forward_model_file_path', 'mne_info')

    SAVERS_FOR_UPSTREAM_MUTABLE_OBJECTS = {'mne_info': channel_labels_saver}

    LIMITS_MODES = SimpleNamespace(GLOBAL='Global', LOCAL='Local',
                                   MANUAL='Manual')

    def __init__(self, take_abs=True, limits_mode=LIMITS_MODES.LOCAL,
                 buffer_length=1, threshold_pct=50, **brain_painter_kwargs):
        super().__init__()

        self.limits_mode = limits_mode
        self.lock_limits = False
        self.buffer_length = buffer_length
        self.take_abs = take_abs
        self.colormap_limits = SimpleNamespace(lower=None, upper=None)
        self._threshold_pct = threshold_pct

        self._limits_buffer = None  # type: RingBuffer
        self._brain_painter = BrainPainter(threshold_pct=threshold_pct,
                                           **brain_painter_kwargs)

    def _initialize(self):
        mne_forward_model_file_path = self.traverse_back_and_find(
            'mne_forward_model_file_path')
        self._brain_painter.initialize(mne_forward_model_file_path)

        self.background_colors = self._calculate_background_colors(
            self.show_curvature)
        self.sender.reinit.emit()
        # if self.widget is None:
        #     self.mesh_data = self._get_mesh_data_from_surfaces_dir()
        #     self.widget = self._create_widget()
        self.smoothing_matrix = self._get_smoothing_matrix(
            mne_forward_model_file_path)
        # else:  # Do not recreate the widget, just clear it
        #     for item in self.widget.items:
        #         self.widget.removeItem(item)

        frequency = self.traverse_back_and_find('mne_info')['sfreq']
        buffer_sample_count = np.int(self.buffer_length * frequency)
        self._limits_buffer = RingBuffer(row_cnt=2, maxlen=buffer_sample_count)

    def _on_input_history_invalidation(self):
        self._should_reset = True
        self.reset()

    def _check_value(self, key, value):
        pass

    def _reset(self):
        self._limits_buffer.clear()

    @property
    def threshold_pct(self):
        return self._threshold_pct

    @threshold_pct.setter
    def threshold_pct(self, value):
        self._threshold_pct = value
        self._brain_painter.threshold_pct = value

    counter = 0
    def _update(self):
        self.counter += 1
        if self.counter == 50:
            self._should_reinitialize = True
        sources = self.parent.output
        if self.take_abs:
            sources = np.abs(sources)
        self._update_colormap_limits(sources)
        normalized_sources = self._normalize_sources(last_sample(sources))
        self._brain_painter.draw(normalized_sources)

    def _update_colormap_limits(self, sources):
        self._limits_buffer.extend(np.array([
            make_time_dimension_second(np.min(sources, axis=CHANNEL_AXIS)),
            make_time_dimension_second(np.max(sources, axis=CHANNEL_AXIS)),
        ]))

        if self.limits_mode == self.LIMITS_MODES.GLOBAL:
            mins, maxs = self._limits_buffer.data
            self.colormap_limits.lower = np.percentile(mins, q=5)
            self.colormap_limits.upper = np.percentile(maxs, q=95)
        elif self.limits_mode == self.LIMITS_MODES.LOCAL:
            sources = last_sample(sources)
            self.colormap_limits.lower = np.min(sources)
            self.colormap_limits.upper = np.max(sources)
        elif self.limits_mode == self.LIMITS_MODES.MANUAL:
            pass

    def _normalize_sources(self, last_sources):
        minimum = self.colormap_limits.lower
        maximum = self.colormap_limits.upper
        if minimum == maximum:
            return last_sources * 0
        else:
            return (last_sources - minimum) / (maximum - minimum)

    @property
    def widget(self):
        if self._brain_painter.widget is not None:
            return self._brain_painter.widget
        else:
            raise AttributeError('{} does not have widget yet.' +
                                 'Probably has not been initialized')


class BrainPainter():
    # draw_sig = pyqtSignal('PyQt_PyObject')
    time_since_draw = time.time()

    def __init__(self, threshold_pct=50,
                 brain_colormap: matplotlib_Colormap = cm.Greys,
                 data_colormap: matplotlib_Colormap = cm.Reds,
                 show_curvature=True, surfaces_dir=None):
        """
        This is the last step.
        Object of this class draws any data on the cortex mesh given to it.
        No changes, except for thresholding, are made.

        :param threshold_pct:
        Only values exceeding this percentage threshold will be shown
        :param show_curvature:
        If True, concave areas will be shown in darker grey,
        convex - in lighter
        :param surfaces_dir:
        Path to the Fressurfer surf directory.
        If None, mne's sample's surfaces will be used.
        """
        # super().__init__()

        self.threshold_pct = threshold_pct
        self.show_curvature = show_curvature

        self.brain_colormap = brain_colormap
        self.data_colormap = data_colormap

        self.surfaces_dir = surfaces_dir
        self.mesh_data = None
        self.smoothing_matrix = None
        self.widget = None

        self.background_colors = None
        self.mesh_item = None

        self.sender = Communicate()
        self.sender.draw_sig.connect(self.on_draw)
        self.sender.reinit.connect(self.init_widget)

    def initialize(self, mne_forward_model_file_path):

        self.background_colors = self._calculate_background_colors(
            self.show_curvature)
        self.sender.reinit.emit()
        # if self.widget is None:
        #     self.mesh_data = self._get_mesh_data_from_surfaces_dir()
        #     self.widget = self._create_widget()
        self.smoothing_matrix = self._get_smoothing_matrix(
            mne_forward_model_file_path)
        # else:  # Do not recreate the widget, just clear it
        #     for item in self.widget.items:
        #         self.widget.removeItem(item)

    def init_widget(self):
        if self.widget is not None:
            parent = self.widget.parent()
            ind = parent.children().index(self.widget)
            cur_width = self.widget.size().width()
            cur_height = self.widget.size().height()
            self.widget.deleteLater()
            self.widget = None
            self.mesh_data = self._get_mesh_data_from_surfaces_dir()
            self.widget = self._create_widget()
            self.widget.resize(cur_width, cur_height)
            parent.insertWidget(ind, self.widget)
            self.widget.resize(cur_width, cur_height)
        else:
            self.mesh_data = self._get_mesh_data_from_surfaces_dir()
            self.widget = self._create_widget()
            self.widget.setMinimumWidth(50)


    def on_draw(self, normalized_values):

        sources_smoothed = self.smoothing_matrix.dot(normalized_values)
        threshold = self.threshold_pct / 100
        mask = sources_smoothed <= threshold

        # reset colors to white
        self.mesh_data._alphas[:, :] = 0.
        self.mesh_data._alphas_buffer.set_data(self.mesh_data._alphas)

        if np.any(~mask):
            self.mesh_data.add_overlay(sources_smoothed[~mask],
                                       vertices=np.where(~mask)[0],
                                       to_overlay=1)
        self.mesh_data.update()

    def draw(self, normalized_values):
        self.sender.draw_sig.emit(normalized_values)

    def _get_mesh_data_from_surfaces_dir(self, cortex_type='inflated'):
        if self.surfaces_dir:
            surf_paths = [os.path.join(self.surfaces_dir,
                                       '{}.{}'.format(h, cortex_type))
                          for h in ('lh', 'rh')]
        else:
            raise NameError('surfaces_dir is not set')
        lh_mesh, rh_mesh = [nib.freesurfer.read_geometry(surf_path) for surf_path in surf_paths]
        lh_vertexes, lh_faces = lh_mesh
        rh_vertexes, rh_faces = rh_mesh

        # Move all the vertices so that the lh has x (L-R) <= 0 and rh - >= 0
        lh_vertexes[:, 0] -= np.max(lh_vertexes[:, 0])
        rh_vertexes[:, 0] -= np.min(rh_vertexes[:, 0])

        # Combine two meshes
        vertices = np.r_[lh_vertexes, rh_vertexes]
        lh_vertex_cnt = lh_vertexes.shape[0]
        faces = np.r_[lh_faces, lh_vertex_cnt + rh_faces]

        # Move the mesh so that the center of the brain is at (0, 0, 0) (kinda)
        vertices[:, 1:2] -= np.mean(vertices[:, 1:2])

        mesh_data = BrainMesh(vertices=vertices, faces=faces)

        return mesh_data

    def _get_mesh_data_from_forward_solution(self, forward_solution_file_path):
        forward_solution = mne.read_forward_solution(
            forward_solution_file_path, verbose='ERROR')

        left_hemi, right_hemi = forward_solution['src']

        vertexes = np.r_[left_hemi['rr'], right_hemi['rr']]
        lh_vertex_cnt = left_hemi['rr'].shape[0]
        faces = np.r_[left_hemi['use_tris'],
                      lh_vertex_cnt + right_hemi['use_tris']]
        sources_idx = np.r_[left_hemi['vertno'],
                            lh_vertex_cnt + right_hemi['vertno']]

        return sources_idx, vertexes, faces

    def _create_widget(self):
        canvas = scene.SceneCanvas(keys='interactive', show=True)

        # Add a ViewBox to let the user zoom/rotate
        view = canvas.central_widget.add_view()
        view.camera = 'turntable'
        view.camera.fov = 50
        view.camera.distance = 400
        # Make light follow the camera
        self.mesh_data.shared_program.frag['camtf'] = view.camera.transform
        view.add(self.mesh_data)
        return canvas.native


    def _calculate_background_colors(self, show_curvature):
        if show_curvature:
            curvature_file_paths = [os.path.join(self.surfaces_dir,
                                                 "{}.curv".format(h)) for h in ('lh', 'rh')]
            curvatures = [nib.freesurfer.read_morph_data(path) for path in curvature_file_paths]
            curvature = np.concatenate(curvatures)
            return self.brain_colormap((curvature > 0) / 3 + 1 / 3)  # 1/3 for concave, 2/3 for convex
        else:
            background_color = self.brain_colormap(0.5)
            total_vertex_cnt = self.mesh_data.vertexes().shape[0]
            return np.tile(background_color, total_vertex_cnt)

    @staticmethod
    def _guess_surfaces_dir_based_on(mne_forward_model_file_path):
        # If the forward model that was used is from the mne's sample dataset, then we can use curvatures from there
        path_to_sample = os.path.realpath(sample.data_path(verbose='ERROR'))
        if os.path.realpath(mne_forward_model_file_path).startswith(path_to_sample):
            return os.path.join(path_to_sample, "subjects", "sample", "surf")

    @staticmethod
    def read_smoothing_matrix():
        lh_npz = np.load('playground/vs_pysurfer/smooth_mat_lh.npz')
        rh_npz = np.load('playground/vs_pysurfer/smooth_mat_rh.npz')

        smooth_mat_lh = sparse.coo_matrix((
            lh_npz['data'], (lh_npz['row'], lh_npz['col'])),
            shape=lh_npz['shape'] + rh_npz['shape'])

        lh_row_cnt, lh_col_cnt = lh_npz['shape']
        smooth_mat_rh = sparse.coo_matrix((
            rh_npz['data'], (rh_npz['row'] + lh_row_cnt, rh_npz['col'] + lh_col_cnt)),
            shape=rh_npz['shape'] + lh_npz['shape'])

        return smooth_mat_lh.tocsc() + smooth_mat_rh.tocsc()

    def _get_smoothing_matrix(self, mne_forward_model_file_path):
        """
        Creates or loads a smoothing matrix that lets us
        interpolate source values onto all mesh vertices

        """
        # Not all the vertices in the forward solution mesh are sources.
        # sources_idx actually indexes into the union of
        # high-definition meshes for left and right hemispheres.
        # The smoothing matrix then lets us assign a color to each vertex.
        # If in future we decide to use low-definition mesh from
        # the forward model for drawing, we should index into that.
        # Shorter: the coordinates of the jth source are
        # in self.mesh_data.vertexes()[sources_idx[j], :]
        smoothing_matrix_file_path = (
            os.path.splitext(mne_forward_model_file_path)[0] +
            '-smoothing-matrix.npz')
        try:
            return sparse.load_npz(smoothing_matrix_file_path)
        except FileNotFoundError:
            self.logger.info('Calculating smoothing matrix.' +
                             ' This might take a while the first time.')
            sources_idx, vertexes, faces =\
                self._get_mesh_data_from_forward_solution(
                    mne_forward_model_file_path)
            adj_mat = mesh_edges(self.mesh_data._faces)
            smoothing_mat = smoothing_matrix(sources_idx, adj_mat)
            sparse.save_npz(smoothing_matrix_file_path, smoothing_mat)
            return smoothing_mat


class Communicate(QObject):
    reinit = pyqtSignal()
    draw_sig = pyqtSignal('PyQt_PyObject')


class SignalViewer(WidgetOutput):
    CHANGES_IN_THESE_REQUIRE_RESET = ()

    UPSTREAM_CHANGES_IN_THESE_REQUIRE_REINITIALIZATION = ('mne_info', )
    SAVERS_FOR_UPSTREAM_MUTABLE_OBJECTS = {'mne_info': channel_labels_saver}

    def __init__(self):
        super().__init__()
        self.widget = None  # type: RawSignalViewer
        self.signal_sender = Communicate()
        self.signal_sender.reinit.connect(self.init_widget)

    def _initialize(self):
        mne_info = self.traverse_back_and_find('mne_info')
        # if self.widget is None:
        self.signal_sender.reinit.emit()
        # else:
        #     self.widget = RawSignalViewer(fs=mne_info['sfreq'],
        #                                   names=mne_info['ch_names'],
        #                                   seconds_to_plot=10)

    def _create_widget(self):
        mne_info = self.traverse_back_and_find('mne_info')
        return RawSignalViewer(fs=mne_info['sfreq'],
                               names=mne_info['ch_names'], seconds_to_plot=10)

    counter = 0
    def _update(self):
        self.counter += 1
        if not self.counter % 121:
            self._should_reinitialize = True
        chunk = self.parent.output
        if TIME_AXIS == PYNFB_TIME_AXIS:
            self.widget.update(chunk)
        else:
            self.widget.update(chunk.T)

    def _reset(self) -> bool:
        # Nothing to reset, really
        pass

    def _on_input_history_invalidation(self):
        # Don't really care, will draw whatever
        pass

    def _check_value(self, key, value):
        # Nothing to be set
        pass

class FileOutput(OutputNode):

    def _on_input_history_invalidation(self):
        pass

    def _check_value(self, key, value):
        pass  # TODO: check that value as a string usable as a stream name

    CHANGES_IN_THESE_REQUIRE_RESET = ('stream_name', )

    UPSTREAM_CHANGES_IN_THESE_REQUIRE_REINITIALIZATION = ('mne_info', )
    SAVERS_FOR_UPSTREAM_MUTABLE_OBJECTS = {'mne_info':
                                           lambda info: (info['sfreq'], ) +
                                           channel_labels_saver(info)}

    def _reset(self):
        self._should_reinitialize = True
        self.initialize()

    def __init__(self, output_fname='output.h5'):
        super().__init__()
        self.output_fname = output_fname
        self.out_file = None

    def _initialize(self):
        if self.out_file:  # for resets
            self.out_file.close()

        info = self.traverse_back_and_find('mne_info')
        col_size = info['nchan']
        self.out_file = tables.open_file(self.output_fname, mode='w')
        atom = tables.Float64Atom()

        self.output_array = self.out_file.create_earray(
            self.out_file.root, 'data', atom, (col_size, 0))

    def _update(self):
        chunk = self.parent.output
        self.output_array.append(chunk)


class TorchOutput(OutputNode):

    CHANGES_IN_THESE_REQUIRE_RESET = ()
    UPSTREAM_CHANGES_IN_THESE_REQUIRE_REINITIALIZATION = ()

    def _on_input_history_invalidation(self):
        pass

    def _check_value(self, key, value):
        pass  # TODO: check that value as a string usable as a stream name

    def _reset(self):
        pass

    def _initialize(self):
        pass

    def _update(self):
        self.output = torch.from_numpy(self.parent.output)
