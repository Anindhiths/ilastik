###############################################################################
#   ilastik: interactive learning and segmentation toolkit
#
#       Copyright (C) 2011-2019, the ilastik developers
#                                <team@ilastik.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# In addition, as a special exception, the copyright holders of
# ilastik give you permission to combine ilastik with applets,
# workflows and plugins which are not covered under the GNU
# General Public License.
#
# See the LICENSE file for details. License information is also available
# on the ilastik web site at:
#        http://ilastik.org/license.html
###############################################################################
import numpy
import typing


class DtypeConvertFunction:
    """Data-type conversion and rescaling function class

    Simple callable class that converts between dtypes.

    Assumption for floats (as inputs): range [0.0 .. 1.0]

    This class was needed in order to be able to check functions for equality.
    When using this function as an input for OpPixelOperator.Function, changing
    the input value to the same conversion function will not result in
    dirtyness.
    """

    def __init__(self, dtype: numpy.typing.DTypeLike):
        """
        Args:
            dtype (numpy.dtype): dtype to which this functions __call__ will
              convert.
        """
        self._dtype = numpy.dtype(dtype)

        if self._dtype.char in numpy.typecodes["AllInteger"]:
            # For integer dtype scale according to dtype min and max to maximize precision
            dtype_info = numpy.iinfo(dtype)
            min_val = dtype_info.min
            max_val = dtype_info.max
            self._fun = lambda x: ((max_val - min_val) * x - min_val).astype(dtype)
        else:
            # For floating points, just coerce it to the new floating point dtype.
            self._fun = lambda x: x.astype(dtype)

    def __eq__(self, other: typing.Any) -> bool:
        if other is None:
            return False
        if not isinstance(other, DtypeConvertFunction):
            return False
        if self._dtype == other._dtype:
            return True
        return False

    def __call__(self, val: numpy.ndarray) -> numpy.ndarray:
        return self._fun(val)
