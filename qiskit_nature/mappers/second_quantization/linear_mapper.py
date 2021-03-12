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

"""The Linear Mapper."""

from qiskit.opflow import PauliSumOp

from qiskit_nature.operators.second_quantization.spin_op import SpinOp

from .spin_mapper import SpinMapper


class LinearMapper(SpinMapper):
    """The Linear spin-to-qubit mapping. """

    def map(self, second_q_op: SpinOp) -> PauliSumOp:
        # TODO
        raise NotImplementedError()
