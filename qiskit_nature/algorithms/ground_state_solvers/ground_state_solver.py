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

"""The ground state calculation interface."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Union

import numpy as np

from qiskit import QuantumCircuit
from qiskit.algorithms import MinimumEigensolver
from qiskit.circuit import Instruction
from qiskit.quantum_info import Statevector
from qiskit.result import Result
from qiskit.opflow import OperatorBase, PauliSumOp

from .. import MinimumEigensolverFactory
from ...fermionic_operator import FermionicOperator
from ...bosonic_operator import BosonicOperator
from ...drivers.base_driver import BaseDriver
from ...mappers.second_quantization import QubitMapper
from ...operators.second_quantization.qubit_converter import QubitConverter
from ...problems.second_quantization.base_problem import BaseProblem
from ...results.electronic_structure_result import ElectronicStructureResult
from ...results.vibronic_structure_result import VibronicStructureResult
from ...transformations.transformation import Transformation


class GroundStateSolver(ABC):
    """The ground state calculation interface"""

    def __init__(self, qubit_converter: QubitConverter) -> None:
        """
        Args:
            qubit_mappers: transformation from driver to qubit operator (and aux. operators)
        """
        self._qubit_converter=qubit_converter

    @abstractmethod
    def solve(self, problem: BaseProblem) \
            -> Union[ElectronicStructureResult, VibronicStructureResult]:
        """Compute the ground state energy of the molecule that was supplied via the driver.

        Args:
            driver: a chemistry driver object which defines the chemical problem that is to be
                    solved by this calculation.
            aux_operators: Additional auxiliary operators to evaluate. Must be of type
                ``FermionicOperator`` if the qubit transformation is fermionic and of type
                ``BosonicOperator`` it is bosonic.

        Returns:
            An eigenstate result.
        """
        raise NotImplementedError

    @abstractmethod
    def returns_groundstate(self) -> bool:
        """Whether this class returns only the ground state energy or also the ground state itself.

        Returns:
            True, if this class also returns the ground state in the results object.
            False otherwise.
        """
        raise NotImplementedError

    @abstractmethod
    def evaluate_operators(self,
                           state: Union[str, dict, Result,
                                        list, np.ndarray, Statevector,
                                        QuantumCircuit, Instruction,
                                        OperatorBase],
                           operators: Union[PauliSumOp, OperatorBase, list, dict]
                           ) -> Union[float, List[float], Dict[str, List[float]]]:
        """Evaluates additional operators at the given state.

        Args:
            state: any kind of input that can be used to specify a state. See also ``StateFn`` for
                   more details.
            operators: either a single, list or dictionary of ``PauliSumOp``s or any kind
                       of operator implementing the ``OperatorBase``.

        Returns:
            The expectation value of the given operator(s). The return type will be identical to the
            format of the provided operators.
        """
        raise NotImplementedError
