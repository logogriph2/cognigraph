import numpy as np

from .. import TIME_AXIS, CHANNEL_AXIS


def make_time_dimension_second(ndarray: np.ndarray):
    """ To different people chunks of data are either TIME x CHANNEL or CHANNEL x TIME. We don't want to impose our
    preference on users so this can be set with TIME_AXIS constant. But at times we do need to have it in a
    particular way. Hence, this function. """
    if TIME_AXIS == 1:
        return ndarray
    elif TIME_AXIS == 0:
        return ndarray.T


def put_time_dimension_back_from_second(ndarray: np.ndarray):
    if TIME_AXIS == 1:
        return ndarray
    elif TIME_AXIS == 0:
        return ndarray.T


put_time_dimension_back_from_second.__doc__ = make_time_dimension_second.__doc__


def last_sample(ndarray: np.ndarray):
    if TIME_AXIS == 1:
        return ndarray[:, -1]
    elif TIME_AXIS == 0:
        return ndarray[-1, :]
    else:
        raise ValueError


def apply_quad_form_to_columns(A: np.ndarray, X: np.ndarray):
    # Returns [x.T.dot(A).dot(x) for x in X.T] - quadratic form A applied to each column of X.
    # Works about 20% faster if X is Fortran array (column-major).
    # Use numpy.asfortranarray(X) to convert, X.flags.f_continuous to check.
    return np.einsum('...i,...i->...', X.T.dot(A), X.T)