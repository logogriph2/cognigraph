import pytest
import os.path as op
from mne.io import Raw

from cognigraph import COGNIGRAPH_ROOT
<<<<<<< HEAD
=======
from cognigraph.utils.io import DataDownloader
import logging
>>>>>>> 8282a5628ef42a24f61e0561d32de8c1ebc25c94

test_data_path = op.join(COGNIGRAPH_ROOT, 'tests/data')


@pytest.fixture
def info(scope='session'):
    """Get info with applied average projection"""
<<<<<<< HEAD
    info_src_path = op.join(test_data_path, 'Koleno_raw.fif')
    raw = Raw(info_src_path, preload=True)
    raw.set_eeg_reference('average', projection=True)
    return raw.info
=======
    logging.basicConfig(filename=None, level=logging.INFO)
    dloader = DataDownloader()
    info_src_path = dloader.get_file('Koleno_raw.fif')
    print('new')
    raw = Raw(info_src_path, preload=True)
    raw.set_eeg_reference('average', projection=True)
    return raw.info


@pytest.fixture(scope='session')
def fwd_model_path():
    dloader = DataDownloader()
    return dloader.get_file('dmalt_custom_lr.fif')
>>>>>>> 8282a5628ef42a24f61e0561d32de8c1ebc25c94
