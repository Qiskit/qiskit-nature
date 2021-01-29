# This code is part of Qiskit.
#
# (C) Copyright IBM 2020, 2021.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""The Second-Quantized Operator Transformation interface."""

from abc import ABC, abstractmethod

from qiskit_nature.operators.second_quantization.particle_op import ParticleOp


class SecondQuantizedTransformation(ABC):
    """The interface for implementing methods which map from one `ParticleOp` to
    another. These methods may or may not affect the size of the Hilbert space underlying the
    operator.
    """
    # TODO Do all of the transformations that we will come up with have some common side effect
    # which we need to account for? E.g., both, the active-space as well as the particle-hole
    # transformation, result in an energy offset which needs to be accounted for in the problem's
    # total energy. However, the seniority-zero transformation does not produce such an energy
    # offset which is why this example cannot be taken into the interface unless we default the
    # produced energy offset to 0.

    @abstractmethod
    def transform(self, second_q_op: ParticleOp) -> ParticleOp:
        """Transforms one `ParticleOp` into another one. This may or may not affect the
        size of the Hilbert space underlying the operator.

        Args:
            second_q_op: the `ParticleOp` to be transformed.

        Returns:
            A new `ParticleOp` instance.
        """
        raise NotImplementedError()
