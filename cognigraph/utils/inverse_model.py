import os

import numpy as np
import mne
from mne.datasets import sample

from ..utils.misc import all_upper

data_path = sample.data_path(verbose='ERROR')
sample_dir = os.path.join(data_path, 'MEG', 'sample')
neuromag_forward_file_path = os.path.join(
    sample_dir, 'sample_audvis-meg-oct-6-fwd.fif')
standard_1005_forward_file_path = os.path.join(
    sample_dir, 'sample_1005-eeg-oct-6-fwd.fif')


def _pick_columns_from_matrix(matrix: np.ndarray,
                              output_column_labels: list,
                              input_column_labels: list) -> np.ndarray:
    """
    From matrix take only the columns that correspond to
    output_column_labels - in the order of the latter.
    :param matrix: each column in matrix has a label (eg. EEG channel name)
    :param output_column_labels: labels that we need
    :param input_column_labels: labels that we have
    :return: np.ndarray with len(output_column_labels) columns
    and the same number of rows as matrix has.

    """

    # Choose the right columns, put zeros where label is missing
    row_count = matrix.shape[0]
    output_matrix = np.zeros((row_count, len(output_column_labels)))

    # List of length-two arrays to two tuples
    indices_in_input, indices_in_output = zip(
        *[(input_column_labels.index(label), idx)
          for idx, label in enumerate(output_column_labels)
          if label in input_column_labels])

    output_matrix[:, indices_in_output] = matrix[:, indices_in_input]
    return output_matrix


def matrix_from_inverse_operator(
        inverse_operator, mne_info, snr, method) -> np.ndarray:
    # Create a dummy mne.Raw object
    picks = mne.pick_types(mne_info, eeg=True, meg=False, exclude='bads')
    info_goods = mne.pick_info(mne_info, sel=picks)
    channel_count = info_goods['nchan']
    dummy_eye = np.identity(channel_count)

    dummy_raw = mne.io.RawArray(
        data=dummy_eye, info=info_goods, verbose='ERROR')

    contains_eeg_channels = len(
        mne.pick_types(mne_info, meg=False, eeg=True)) > 0

    if contains_eeg_channels:
        dummy_raw.set_eeg_reference(ref_channels='average',
                                    verbose='ERROR', projection=True)

    # Applying inverse operator to identity matrix gives inverse model matrix
    lambda2 = 1.0 / snr ** 2
    stc = mne.minimum_norm.apply_inverse_raw(dummy_raw, inverse_operator,
                                             lambda2, method, verbose='ERROR')

    return stc.data


def get_mesh_data_from_forward_solution(forward_solution):
    """Get reduced source space for which the forward was computed"""

    left_hemi, right_hemi = forward_solution['src']

    vertices = np.r_[left_hemi['rr'], right_hemi['rr']]
    lh_vertex_cnt = left_hemi['rr'].shape[0]
    faces = np.r_[left_hemi['use_tris'],
                  lh_vertex_cnt + right_hemi['use_tris']]
    sources_idx = np.r_[left_hemi['vertno'],
                        lh_vertex_cnt + right_hemi['vertno']]

    return sources_idx, vertices, faces, lh_vertex_cnt


def get_default_forward_file(mne_info: mne.Info):
    """
    Based on the labels of channels in mne_info
    return either neuromag or standard 1005 forward model file
    :param mne_info - mne.Info instance
    :return: str: path to the forward-model file

    """

    channel_labels_upper = all_upper(mne_info['ch_names'])

    if max(label.startswith('MEG ') for label in channel_labels_upper) is True:
        return neuromag_forward_file_path

    else:
        montage_1005 = mne.channels.read_montage(kind='standard_1005')
        montage_labels_upper = all_upper(montage_1005.ch_names)
        if any([label_upper in montage_labels_upper
                for label_upper in channel_labels_upper]):
            return standard_1005_forward_file_path


def get_clean_forward(forward_model_path: str, mne_info: mne.Info):
    """
    Assemble the gain matrix from the forward model so that
    its rows correspond to channels in mne_info
    :param force_fixed: whether to return the gain matrix that uses
    fixed orientations of dipoles
    :param drop_missing: what to do with channels that are not
    in the forward solution? If False, zero vectors will be
    returned for them, if True, they will not be represented
    in the returned matrix.
    :param forward_model_path:
    :param mne_info:
    :return: np.ndarray with as many rows as there are dipoles
    in the forward model and as many rows as there are
    channels in mne_info (well, depending on drop_missing).
    It drop_missing is True, then also returns indices of
    channels that are both in the forward solution and mne_info

    """

    # Get the gain matrix from the forward solution
    forward = mne.read_forward_solution(forward_model_path, verbose='ERROR')

    # Take only the channels present in mne_info
    ch_names = mne_info['ch_names']
    goods = mne.pick_types(mne_info, eeg=True, stim=False, eog=False,
                           ecg=False, exclude='bads')
    ch_names_data = [ch_names[i] for i in goods]
    ch_names_fwd = forward['info']['ch_names']
    # Take only channels from both mne_info and the forward solution
    ch_names_intersect = [n for n in ch_names_fwd if
                          n.upper() in all_upper(ch_names_data)]
    missing_ch_names = [n for n in ch_names_data if
                        n.upper() not in all_upper(ch_names_fwd)]

    missing_fwd_ch_names = [n for n in ch_names_fwd if
                            n.upper() not in all_upper(ch_names_data)]

    if len(missing_fwd_ch_names) > 0:
        raise ValueError(mne_info['ch_names'], ch_names_fwd, mne_info['bads'])

    missing_fwd_ch_names = [n for n in ch_names_fwd if
                            n.upper() not in all_upper(ch_names_data)]

    if len(missing_fwd_ch_names) > 0:
        raise ValueError(mne_info['ch_names'], ch_names_fwd, mne_info['bads'])

    fwd = mne.pick_channels_forward(forward, include=ch_names_intersect)
    return fwd, missing_ch_names


def make_inverse_operator(fwd, mne_info, depth=None,
                          loose=1, fixed=False):
    """
    Make noise covariance matrix and create inverse operator using only
    good channels

    """
    # The inverse operator will use channels common to
    # forward_model_file_path and mne_info.

    picks = mne.pick_types(mne_info, eeg=True, meg=False, exclude='bads')
    info_goods = mne.pick_info(mne_info, sel=picks)

    N_SEN = fwd['nchan']
    ch_names = info_goods['ch_names']
    cov_data = np.identity(N_SEN)
    cov = mne.Covariance(cov_data, ch_names, mne_info['bads'],
                         mne_info['projs'], nfree=1)
    inv = mne.minimum_norm.make_inverse_operator(info_goods, fwd, cov,
                                                 depth=None, loose=0.8,
                                                 fixed=False, verbose='ERROR')
    return inv
