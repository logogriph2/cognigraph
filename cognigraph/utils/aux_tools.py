from contextlib import contextmanager
import sys


@contextmanager
def nostdout():
    """Kill standart output.

    Example
    -------
    >> with nostdout():
           raw = mne.io.Raw(fname)

    """
    # -- Works both in python2 and python3 -- #
    try:
        from io import StringIO
    except ImportError:
        from io import StringIO
    # --------------------------------------- #
    save_stdout = sys.stdout
    sys.stdout = StringIO()
    yield
    sys.stdout = save_stdout
