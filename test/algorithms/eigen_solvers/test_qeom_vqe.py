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

""" Test of Eom VQE."""

import warnings
import unittest
from test import QiskitNatureTestCase

import numpy as np
from qiskit import BasicAer
from qiskit.circuit.library import RealAmplitudes

from qiskit.utils import QuantumInstance, algorithm_globals
from qiskit.algorithms.optimizers import COBYLA, SPSA
from qiskit.algorithms import NumPyEigensolver
from qiskit.opflow import Z2Symmetries
from qiskit_nature import QiskitNatureError
from qiskit_nature.algorithms import QEomVQE
from qiskit_nature.drivers import PySCFDriver, UnitsType
from qiskit_nature.core import Hamiltonian, TransformationType, QubitMappingType
from qiskit_nature.components.variational_forms import UCCSD
from qiskit_nature.circuit.library import HartreeFock


@unittest.skip("Skip test until refactored.")
class TestEomVQE(QiskitNatureTestCase):
    """Test Eom VQE."""

    def setUp(self):
        """Setup."""
        super().setUp()
        try:
            algorithm_globals.random_seed = 0
            atom = 'H .0 .0 .7414; H .0 .0 .0'
            pyscf_driver = PySCFDriver(atom=atom,
                                       unit=UnitsType.ANGSTROM, charge=0, spin=0, basis='sto3g')
            self.molecule = pyscf_driver.run()
            warnings.filterwarnings('ignore', category=DeprecationWarning)
            core = Hamiltonian(transformation=TransformationType.FULL,
                               qubit_mapping=QubitMappingType.PARITY,
                               two_qubit_reduction=True,
                               freeze_core=False,
                               orbital_reduction=[])
            warnings.filterwarnings('always', category=DeprecationWarning)
            qubit_op, _ = core.run(self.molecule)
            exact_eigensolver = NumPyEigensolver(k=2 ** qubit_op.num_qubits)
            result = exact_eigensolver.compute_eigenvalues(qubit_op)
            self.reference = result.eigenvalues.real
        except QiskitNatureError:
            self.skipTest('PYSCF driver does not appear to be installed')

    def test_h2_two_qubits_statevector(self):
        """Test H2 with parity mapping and statevector backend."""
        two_qubit_reduction = True
        qubit_mapping = 'parity'
        warnings.filterwarnings('ignore', category=DeprecationWarning)
        core = Hamiltonian(transformation=TransformationType.FULL,
                           qubit_mapping=QubitMappingType.PARITY,
                           two_qubit_reduction=two_qubit_reduction,
                           freeze_core=False,
                           orbital_reduction=[])
        warnings.filterwarnings('always', category=DeprecationWarning)
        qubit_op, _ = core.run(self.molecule)

        num_orbitals = core.molecule_info['num_orbitals']
        num_particles = core.molecule_info['num_particles']

        initial_state = HartreeFock(num_orbitals=num_orbitals,
                                    num_particles=num_particles, qubit_mapping=qubit_mapping,
                                    two_qubit_reduction=two_qubit_reduction)
        var_form = UCCSD(num_orbitals=num_orbitals,
                         num_particles=num_particles,
                         initial_state=initial_state,
                         qubit_mapping=qubit_mapping, two_qubit_reduction=two_qubit_reduction)
        optimizer = COBYLA(maxiter=1000, tol=1e-8)

        backend = BasicAer.get_backend('statevector_simulator')
        eom_vqe = QEomVQE(var_form, optimizer=optimizer, num_orbitals=num_orbitals,
                          num_particles=num_particles, qubit_mapping=qubit_mapping,
                          two_qubit_reduction=two_qubit_reduction,
                          quantum_instance=QuantumInstance(backend))

        result = eom_vqe.compute_minimum_eigenvalue(qubit_op)
        np.testing.assert_array_almost_equal(self.reference, result['energies'], decimal=4)

    def test_h2_one_qubit_statevector(self):
        """Test H2 with tapering and statevector backend."""
        two_qubit_reduction = True
        qubit_mapping = 'parity'
        warnings.filterwarnings('ignore', category=DeprecationWarning)
        core = Hamiltonian(transformation=TransformationType.FULL,
                           qubit_mapping=QubitMappingType.PARITY,
                           two_qubit_reduction=two_qubit_reduction,
                           freeze_core=False,
                           orbital_reduction=[])
        warnings.filterwarnings('always', category=DeprecationWarning)
        qubit_op, _ = core.run(self.molecule)

        num_orbitals = core.molecule_info['num_orbitals']
        num_particles = core.molecule_info['num_particles']

        # tapering
        z2_symmetries = Z2Symmetries.find_Z2_symmetries(qubit_op)
        # know the sector
        tapered_op = z2_symmetries.taper(qubit_op)[1]

        initial_state = HartreeFock(num_orbitals=num_orbitals,
                                    num_particles=num_particles, qubit_mapping=qubit_mapping,
                                    two_qubit_reduction=two_qubit_reduction,
                                    sq_list=tapered_op.z2_symmetries.sq_list)
        var_form = UCCSD(num_orbitals=num_orbitals,
                         num_particles=num_particles, initial_state=initial_state,
                         qubit_mapping=qubit_mapping, two_qubit_reduction=two_qubit_reduction,
                         z2_symmetries=tapered_op.z2_symmetries)
        optimizer = SPSA(maxiter=50)

        backend = BasicAer.get_backend('statevector_simulator')
        quantum_instance = QuantumInstance(backend)
        eom_vqe = QEomVQE(var_form, optimizer=optimizer, num_orbitals=num_orbitals,
                          num_particles=num_particles, qubit_mapping=qubit_mapping,
                          two_qubit_reduction=two_qubit_reduction,
                          z2_symmetries=tapered_op.z2_symmetries, untapered_op=qubit_op,
                          quantum_instance=quantum_instance)
        result = eom_vqe.compute_minimum_eigenvalue(tapered_op)
        np.testing.assert_array_almost_equal(self.reference, result['energies'], decimal=5)

    def test_h2_one_qubit_qasm(self):
        """Test H2 with tapering and qasm backend"""
        two_qubit_reduction = True
        qubit_mapping = 'parity'
        warnings.filterwarnings('ignore', category=DeprecationWarning)
        core = Hamiltonian(transformation=TransformationType.FULL,
                           qubit_mapping=QubitMappingType.PARITY,
                           two_qubit_reduction=two_qubit_reduction,
                           freeze_core=False,
                           orbital_reduction=[])
        warnings.filterwarnings('always', category=DeprecationWarning)
        qubit_op, _ = core.run(self.molecule)

        num_orbitals = core.molecule_info['num_orbitals']
        num_particles = core.molecule_info['num_particles']

        # tapering
        z2_symmetries = Z2Symmetries.find_Z2_symmetries(qubit_op)
        # know the sector
        tapered_op = z2_symmetries.taper(qubit_op)[1]

        var_form = RealAmplitudes(tapered_op.num_qubits, reps=1)
        optimizer = SPSA(maxiter=50)

        backend = BasicAer.get_backend('qasm_simulator')
        quantum_instance = QuantumInstance(backend, shots=65536)
        eom_vqe = QEomVQE(var_form, optimizer, num_orbitals=num_orbitals,
                          num_particles=num_particles, qubit_mapping=qubit_mapping,
                          two_qubit_reduction=two_qubit_reduction,
                          z2_symmetries=tapered_op.z2_symmetries, untapered_op=qubit_op,
                          quantum_instance=quantum_instance)

        result = eom_vqe.compute_minimum_eigenvalue(tapered_op)
        np.testing.assert_array_almost_equal(self.reference, result['energies'], decimal=2)


if __name__ == '__main__':
    unittest.main()
