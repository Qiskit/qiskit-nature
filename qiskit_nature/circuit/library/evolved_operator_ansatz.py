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

"""The evolved operator ansatz."""

from typing import List, Union, Optional

from qiskit.circuit import Parameter, ParameterVector, QuantumRegister
from qiskit.circuit.library import BlueprintCircuit
from qiskit.opflow import OperatorBase, EvolutionBase, PauliTrotterEvolution


class EvolvedOperatorAnsatz(BlueprintCircuit):
    """The evolved operator ansatz."""

    def __init__(self,
                 operators: Union[OperatorBase, List[OperatorBase]],
                 reps: int = 1,
                 evolution: Optional[EvolutionBase] = None,
                 insert_barriers: bool = False,
                 name: str = 'EvolvedOps') -> None:
        """
        Args:
            operators: The operators to evolve.
            reps: The number of times to repeat the evolved operators.
            evolution: An opflow converter object to construct the evolution.
                Defaults to Trotterization.
            insert_barriers: Whether to insert barriers in between each evolution.
            name: The name of the circuit.
        """
        if evolution is None:
            evolution = PauliTrotterEvolution()

        super().__init__(name=name)
        self._operators = None
        self._evolution = evolution
        self._reps = reps
        self._insert_barriers = insert_barriers

        # use setter to set operators
        self.operators = operators

    def _check_configuration(self, raise_on_failure: bool = True) -> bool:
        if self.operators is None:
            if raise_on_failure:
                raise ValueError('The operators are not set.')
            return False

        if self.reps < 0:
            if raise_on_failure:
                raise ValueError('The reps cannot be smaller than 0.')
            return False

    @property
    def reps(self) -> int:
        """The number of times the evolved operators are repeated."""
        return self._reps

    @property
    def evolution(self) -> EvolutionBase:
        """The evolution converter used to compute the evolution."""
        return self._evolution

    @property
    def operators(self) -> List[OperatorBase]:
        """The operators that are evolved in this circuit."""
        return self._operators

    @operators.setter
    def operators(self, operators: Union[OperatorBase, List[OperatorBase]]) -> None:
        """Set the operators to be evolved."""
        if not isinstance(operators, list):
            operators = [operators]

        if len(operators) > 1:
            num_qubits = operators[0].num_qubits
            if any([operators[i].num_qubits != operators[0].num_qubits
                    for i in range(1, len(operators))]):
                raise ValueError('All operators must act on the same number of qubits (for now).')

        self._operators = operators

    @property
    def qregs(self):
        """A list of the quantum registers associated with the circuit."""
        if self._data is None:
            self._build()
        return self._qregs

    @qregs.setter
    def qregs(self, qregs):
        """Set the quantum registers associated with the circuit."""
        self._qregs = qregs
        self._qubits = [qbit for qreg in qregs for qbit in qreg]
        self._invalidate()

    def _build(self):
        if self._data is not None:
            return

        self._check_configuration()
        self._data = []

        # get the evolved operators as circuits
        coeff = Parameter('c')
        evolved_ops = [self.evolution.convert((coeff * op).exp_i()) for op in self.operators]
        circuits = [evolved_op.to_circuit() for evolved_op in evolved_ops]

        # set the registers
        num_qubits = circuits[0].num_qubits
        qr = QuantumRegister(num_qubits, 'q')
        self.add_register(qr)

        # build the circuit
        times = ParameterVector('t', self.reps * len(self.operators))
        times_it = iter(times)

        first = True
        for _ in range(self.reps):
            for circuit in circuits:
                if first:
                    first = False
                else:
                    if self._insert_barriers:
                        self.barrier()
                self.compose(circuit.assign_parameters({coeff: next(times_it)}), inplace=True)
