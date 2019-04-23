import numpy as np

import pytest
from cognigraph.nodes.processors import MCE
from cognigraph.nodes.sources import FileSource
from cognigraph.nodes.tests.prepare_inv_tests_data import (info,  # noqa
                                                           fwd_model_path)


@pytest.fixture# noqa
def mce(info, fwd_model_path):  # noqa
    snr = 1
    n_comp = 10
    mce = MCE(snr, fwd_model_path, n_comp)
    mce.mne_info = info
    N_SEN = len(info['ch_names'])
    mce.input = np.random.rand(N_SEN)
    parent = FileSource()
    parent.output = np.random.rand(info['nchan'], 1)
    parent.mne_info = info
    mce.parent = parent
    return mce


@pytest.fixture# noqa
def mce_def(info):  # noqa
    mce_def = MCE()
    parent = FileSource()
    parent.mne_info = info
    parent.output = np.random.rand(info['nchan'], 1)
    mce_def.parent = parent
    return mce_def


def test_defaults(mce_def):
    assert(mce_def.mne_forward_model_file_path is None)
    assert(mce_def.mne_info is None)


def test_initialize(mce):
    mce.initialize()


def test_reset(mce):
    out_hist = mce._reset()
    assert(out_hist is True)


def test_update(mce):
    mce._initialize()
    mce._update()


def test_check_value(mce):
    with pytest.raises(ValueError):
        mce.snr = -1
