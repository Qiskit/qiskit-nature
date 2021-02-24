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

"""Test for SpinOp"""

import unittest
from itertools import product
from test import QiskitNatureTestCase

import numpy as np
from ddt import data, ddt

from qiskit.quantum_info import Pauli
from qiskit_nature.operators import SpinOp


def spin_labels(length):
    """Generate list of fermion labels with given length."""
    return ["".join(label) for label in product(["I", "X", "Y", "Z"], repeat=length)]


@ddt
class TestSpinOp(QiskitNatureTestCase):
    """FermionicOp tests."""

    def setUp(self):
        super().setUp()
        heisenberg_spin_array = np.array(
            [
                [1, 1, 0, 0, 0, 0],
                [0, 0, 1, 1, 0, 0],
                [0, 0, 0, 0, 1, 1],
                [0, 0, 0, 0, 1, 0],
                [0, 0, 0, 0, 0, 1],
            ]
        )
        heisenberg_coeffs = np.array([-1, -1, -1, -0.3, -0.3])
        self.heisenberg = SpinOp(
            (heisenberg_spin_array, heisenberg_coeffs),
            spin=1,
        )
        self.heisenberg_mat = self.heisenberg.to_matrix()

    @data(*spin_labels(1))
    def test_init_label(self, label):
        """Test __init__"""
        spin = SpinOp(f"{label}_0")
        self.assertListEqual(spin.to_list(), [(f"{label}_0", 1)])

    @data(*spin_labels(2))
    def test_init_len2_label(self, label):
        """Test __init__"""
        spin = SpinOp(f"{label[1]}_1 {label[0]}_0")
        self.assertListEqual(spin.to_list(), [(f"{label[1]}_1 {label[0]}_0", 1)])

    def test_init_pm_label(self):
        """Test __init__ with plus and minus label"""
        with self.subTest("plus"):
            plus = SpinOp([("+_0", 2)])
            desired = SpinOp([("X_0", 2), ("Y_0", 2j)])
            self.assertListEqual(plus.to_list(), desired.to_list())

        with self.subTest("minus"):
            minus = SpinOp([("-_0", 2)])
            desired = SpinOp([("X_0", 2), ("Y_0", -2j)])
            self.assertListEqual(minus.to_list(), desired.to_list())

        with self.subTest("plus tensor minus"):
            actual = SpinOp([("+_1 -_0", 3)])
            desired = SpinOp([("X_1 X_0", 3), ("X_1 Y_0", -3j), ("Y_1 X_0", 3j), ("Y_1 Y_0", 3)])
            self.assertSetEqual(frozenset(actual.to_list()), frozenset(desired.to_list()))

    @data(*spin_labels(1), *spin_labels(2))
    def test_init_dense_label(self, label):
        """Test __init__ for label_mode=dense"""
        if len(label) == 1:
            actual = SpinOp([(f"{label}", 1 + 1j)], label_mode="dense")
            desired = SpinOp([(f"{label}_0", 1 + 1j)])
        elif len(label) == 2:
            actual = SpinOp([(f"{label}", 1)], label_mode="dense")
            desired = SpinOp([(f"{label[0]}_1 {label[1]}_0", 1)])
        self.assertListEqual(actual.to_list(), desired.to_list())

    def test_neg(self):
        """Test __neg__"""
        actual = -self.heisenberg
        desired = -self.heisenberg_mat
        np.testing.assert_array_almost_equal(actual.to_matrix(), desired)

    def test_mul(self):
        """Test __mul__, and __rmul__"""
        actual = self.heisenberg * 2
        np.testing.assert_array_almost_equal(actual.to_matrix(), self.heisenberg_mat * 2)

    def test_div(self):
        """Test __truediv__"""
        actual = self.heisenberg / 3
        np.testing.assert_array_almost_equal(actual.to_matrix(), self.heisenberg_mat / 3)

    def test_add(self):
        """Test __add__"""
        actual = self.heisenberg + self.heisenberg
        np.testing.assert_array_almost_equal(actual.to_matrix(), self.heisenberg_mat * 2)

    def test_sub(self):
        """Test __sub__"""
        actual = self.heisenberg - self.heisenberg
        np.testing.assert_array_almost_equal(actual.to_matrix(), np.zeros((9, 9)))

    def test_adjoint(self):
        """Test adjoint method and dagger property"""
        actual = ~self.heisenberg
        np.testing.assert_array_almost_equal(actual.to_matrix(), self.heisenberg_mat.conj().T)

    def test_reduce(self):
        """Test reduce"""
        actual = (self.heisenberg - self.heisenberg).reduce()
        self.assertListEqual(actual.to_list(), [("I_1 I_0", 0)])

    def test_to_matrix(self):
        """Test to_matrix()"""
        actual = SpinOp([("X_2 Y_1 Z_0", 1)]).to_matrix()
        desired = Pauli("XYZ").to_matrix() / 8
        np.testing.assert_array_almost_equal(actual, desired)


if __name__ == "__main__":
    unittest.main()
