# This code is part of Qiskit.
#
# (C) Copyright IBM 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""The Second-Quantized Operator."""

from typing import List, Dict
from numbers import Number

from qiskit_nature import QiskitNatureError

from .particle_op import ParticleOp
from .fermionic_op import FermionicOp
from .spin_op import SpinOp
from .star_algebra_mixin import StarAlgebraMixin


class SecondQuantizedOp(StarAlgebraMixin):
    """A general SecondQuantizedSumOp.

    This class represents sums of mixed operators, i.e. linear combinations of
    SecondQuantizedOperators with identical particle type registers.
    """
    def __init__(self, operator_list: List[ParticleOp]):
        """
        """
        # TOOD: validation of operator_list

        self._fermion = None
        self._boson = None
        self._spin: Dict[int, SpinOp] = {}

        for op in operator_list:
            if isinstance(op, FermionicOp) and self._fermion is None:
                self._fermion = op
            elif isinstance(op, FermionicOp) and self._fermion is not None:
                raise QiskitNatureError("Only one FermionicOp can be set in initializer.")
            # if isinstance(op, BosonicOp):
            # if isinstance(op, SpinOp):

    def __repr__(self):
        return f"SecondQuantizedOp([{repr(self._fermion)}])"

    def __mul__(self, other):
        if not isinstance(other, Number):
            raise TypeError("Unsupported operand type(s) for *: 'SecondQuantizedOperator' and "
                            "'{}'".format(type(other).__name__))

        operator_list = []
        if self._fermion is not None:
            operator_list.append(other * self._fermion)

        return SecondQuantizedOp(operator_list)

    def __matmul__(self, other):
        if not isinstance(other, SecondQuantizedOp):
            raise TypeError("Unsupported operand type(s) for @: 'SecondQuantizedSumOp' and "
                            "'{}'".format(type(other).__name__))

    def __add__(self, other):
        if not isinstance(other, SecondQuantizedOp):
            raise TypeError("Unsupported operand type(s) for +: 'SecondQuantizedSumOp' and "
                            "'{}'".format(type(other).__name__))
        # TODO: implement

    @property
    def dagger(self):
        daggered_operator_list = []
        if self._fermion is not None:
            daggered_operator_list.append(self._fermion.dagger)

        return SecondQuantizedOp(daggered_operator_list)

    def map(self):
        """
        Mapping from SecondQuantizedOp to PauliSumOp
        """
        raise NotImplementedError

    def transform(self):
        """
        Transformation from SecondQuantizedOp to SecondQuantizedOp
        """
        raise NotImplementedError
