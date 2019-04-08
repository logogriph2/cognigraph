<<<<<<< HEAD:cognigraph/nodes/tests/test_InverseModel.py
import os.path as op
=======
>>>>>>> 8282a5628ef42a24f61e0561d32de8c1ebc25c94:cognigraph/nodes/tests/test_InverseModel.py
import numpy as np

import pytest
from cognigraph.nodes.processors import InverseModel
from cognigraph.nodes.sources import FileSource
<<<<<<< HEAD:cognigraph/nodes/tests/test_InverseModel.py
from cognigraph import COGNIGRAPH_ROOT
from cognigraph.nodes.tests.prepare_inv_tests_data import info  # noqa

test_data_path = op.join(COGNIGRAPH_ROOT, 'tests/data')


@pytest.fixture  # noqa
def inv_model(info):
    snr = 1
    fwd_model_path = op.join(test_data_path, 'dmalt_custom_lr-fwd.fif')
=======
from cognigraph.nodes.tests.prepare_inv_tests_data import (info,  # noqa
                                                           fwd_model_path)


@pytest.fixture
def inv_model(info, fwd_model_path):  # noqa
    snr = 1
>>>>>>> 8282a5628ef42a24f61e0561d32de8c1ebc25c94:cognigraph/nodes/tests/test_InverseModel.py
    method = 'MNE'
    inv_model = InverseModel(
        snr=snr, forward_model_path=fwd_model_path, method=method)
    inv_model.mne_info = info
    N_SEN = len(info['ch_names'])
    inv_model.input = np.random.rand(N_SEN)
    parent = FileSource()
    parent.output = np.random.rand(info['nchan'], 1)
    parent.mne_info = info
    inv_model.parent = parent
    return inv_model


<<<<<<< HEAD:cognigraph/nodes/tests/test_InverseModel.py
@pytest.fixture  # noqa
def inv_model_def(info):
=======
@pytest.fixture
def inv_model_def(info):  # noqa
>>>>>>> 8282a5628ef42a24f61e0561d32de8c1ebc25c94:cognigraph/nodes/tests/test_InverseModel.py
    inv_model_def = InverseModel()
    parent = FileSource()
    parent.mne_info = info
    parent.output = np.random.rand(info['nchan'], 1)
    inv_model_def.parent = parent
    return inv_model_def


def test_defaults(inv_model_def):
    assert(inv_model_def.mne_forward_model_file_path is None)
    assert(inv_model_def.mne_info is None)


def test_initialize(inv_model):
    inv_model.initialize()


def test_reset(inv_model):
    out_hist = inv_model._reset()
    assert(out_hist is True)


def test_update(inv_model):
    inv_model._initialize()
    inv_model._update()


def test_check_value(inv_model):
    with pytest.raises(ValueError):
        inv_model.snr = -1
