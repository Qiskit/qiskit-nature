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

from qiskit_nature import QiskitNatureError
from qiskit_nature.drivers import PySCFDriver, UnitsType
from qiskit_nature.operators.second_quantization import SecondQuantizedOp
from qiskit_nature.transformations.second_quantization.molecular.molecular_problem import MolecularProblem
from test import QiskitNatureTestCase


class TestMolecularProblem(QiskitNatureTestCase):
    """Molecular Problem tests."""

    def setUp(self):
        super().setUp()
        try:
            self.driver = PySCFDriver(atom='Li .0 .0 .0; H .0 .0 1.595',
                                 unit=UnitsType.ANGSTROM,
                                 charge=0,
                                 spin=0,
                                 basis='sto3g')
            transformation = []
            self.molecular_problem = MolecularProblem(self.driver, transformation)

        except QiskitNatureError:
            self.skipTest('PYSCF driver does not appear to be installed')

    def test_second_q_ops(self):
        second_quantized_ops = self.molecular_problem.second_q_ops()
        assert isinstance(second_quantized_ops[0], SecondQuantizedOp)