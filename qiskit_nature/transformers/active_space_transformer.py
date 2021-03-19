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

"""The Active-Space Reduction interface."""

from typing import List, Optional, Tuple
import copy
import logging
import numpy as np

from .base_transformer import BaseTransformer
from .. import QiskitNatureError
from ..drivers import QMolecule

logger = logging.getLogger(__name__)


class ActiveSpaceTransformer(BaseTransformer):
    r"""The Active-Space reduction.

    The reduction is done by computing the inactive Fock operator which is defined as
    :math:`F^I_{pq} = h_{pq} + \sum_i 2 g_{iipq} - g_{iqpi}` and the inactive energy which is
    given by :math:`E^I = \sum_j h_{jj} + F ^I_{jj}`, where :math:`i` and :math:`j` iterate over
    the inactive orbitals.
    By using the inactive Fock operator in place of the one-electron integrals, `h1`, the
    description of the active space contains an effective potential generated by the inactive
    electrons. Therefore, this method permits the exclusion of non-core electrons while
    retaining a high-quality description of the system.

    For more details on the computation of the inactive Fock operator refer to
    https://arxiv.org/abs/2009.01872.

    The active space can be configured in one of the following ways through the initializer:
        - when only `num_electrons` and `num_molecular_orbitals` are specified, these integers
          indicate the number of active electrons and orbitals, respectively. The active space will
          then be chosen around the Fermi level resulting in a unique choice for any pair of
          numbers.  Nonetheless, the following criteria must be met:
              1. the remaining number of inactive electrons must be a positive, even number
              2. the number of active orbitals must not exceed the total number of orbitals minus
              the number of orbitals occupied by the inactive electrons
        - when, in addition to the above, `num_alpha` is specified, this can be used to disambiguate
          the active space in systems with non-zero spin. Thus, `num_alpha` determines the number of
          active alpha electrons. The number of active beta electrons can then be determined based
          via `num_beta = num_electrons - num_alpha`. The same requirements as listed in the
          previous case must be met.
        - finally, it is possible to select a custom set of active orbitals via their indices using
          `active_orbitals`. This allows selecting an active space which is not placed around the
          Fermi level as described in the first case, above. When using this keyword argument, the
          following criteria must be met *in addition* to the ones listed above:
              1. the length of `active_orbitals` must be equal to `num_molecular_orbitals`.
              2. the sum of electrons present in `active_orbitals` must be equal to `num_electrons`.

    References:
        - *M. Rossmannek, P. Barkoutsos, P. Ollitrault, and I. Tavernelli, arXiv:2009.01872
          (2020).*
    """

    def __init__(self,
                 num_electrons: Optional[int] = None,
                 num_molecular_orbitals: Optional[int] = None,
                 num_alpha: Optional[int] = None,
                 active_orbitals: Optional[List[int]] = None,
                 freeze_core: bool = False,
                 remove_orbitals: Optional[List[int]] = None,
                 ):
        """Initializes a transformer which can reduce a `QMolecule` to a configured active space.

        This transformer requires the AO-basis matrices `hcore` and `eri` to be available, as well
        as the basis-transformation matrix `mo_coeff`. A `QMolecule` produced by Qiskit's drivers in
        general satisfies these conditions unless it was read from an FCIDump file. However, those
        integrals are likely already reduced by the code which produced the file or can be
        transformed using this driver after copying the MO-basis integrals of the produced
        `QMolecule` into the AO-basis containers and initializing `mo_coeff` with an identity matrix
        of appropriate size.

        Args:
            num_electrons: The number of active electrons. This may only be omitted if `freeze_core`
                           is used.
            num_molecular_orbitals: The number of active orbitals. This may only be omitted if
                                    `freeze_core` is used.
            num_alpha: The optional number of active alpha-spin electrons.
            active_orbitals: A list of indices specifying the molecular orbitals of the active
                             space. This argument must match with the remaining arguments and should
                             only be used to enforce an active space that is not chosen purely
                             around the Fermi level.
            freeze_core: A convenience argument to quickly enable the inactivity of the
                         `QMolecule.core_orbitals`. This keyword overwrites the use of all other
                         keywords (except `remove_orbitals`) and, thus, cannot be used in
                         combination with them.
            remove_orbitals: A list of indices specifying molecular orbitals which are removed in
                             combination with the `freeze_core` option. No checks are performed on
                             the nature of these orbitals, so the user must make sure that these are
                             _unoccupied_ orbitals, which can be removed without taking any energy
                             shifts into account.
        """
        self.num_electrons = num_electrons
        self.num_molecular_orbitals = num_molecular_orbitals
        self.num_alpha = num_alpha
        self.active_orbitals = active_orbitals
        self.freeze_core = freeze_core
        self.remove_orbitals = remove_orbitals

        self._beta: bool = None
        self._mo_occ_total: np.ndarray = None
        self._mo_occ_inactive: Tuple[np.ndarray, np.ndarray] = None
        self._mo_coeff_active: Tuple[np.ndarray, np.ndarray] = None
        self._mo_coeff_inactive: Tuple[np.ndarray, np.ndarray] = None
        self._density_inactive: Tuple[np.ndarray, np.ndarray] = None
        self._num_particles: Tuple[int, int] = None

    def transform(self, q_molecule: QMolecule) -> QMolecule:
        """Reduces the given `QMolecule` to a given active space.

        Args:
            q_molecule: the `QMolecule` to be transformed.

        Returns:
            A new `QMolecule` instance.

        Raises:
            QiskitNatureError: If more electrons or orbitals are requested than are available, if an
                               uneven number of inactive electrons remains, or if the number of
                               selected active orbital indices does not match
                               `num_molecular_orbitals`.
        """
        valid = self._check_configuration()
        if not valid:
            raise QiskitNatureError("Insufficient Active-Space configuration. You must either use "
                                    "the `freeze_core` option or choose another active space.")

        # get molecular orbital coefficients
        mo_coeff_full = (q_molecule.mo_coeff, q_molecule.mo_coeff_b)
        self._beta = mo_coeff_full[1] is not None
        # get molecular orbital occupation numbers
        mo_occ_full = self._extract_mo_occupation_vector(q_molecule)
        self._mo_occ_total = mo_occ_full[0] + mo_occ_full[1] if self._beta else mo_occ_full[0]

        active_orbs_idxs, inactive_orbs_idxs = self._determine_active_space(q_molecule)

        # split molecular orbitals coefficients into active and inactive parts
        self._mo_coeff_inactive = (mo_coeff_full[0][:, inactive_orbs_idxs],
                                   mo_coeff_full[1][:, inactive_orbs_idxs] if self._beta else None)
        self._mo_coeff_active = (mo_coeff_full[0][:, active_orbs_idxs],
                                 mo_coeff_full[1][:, active_orbs_idxs] if self._beta else None)
        self._mo_occ_inactive = (mo_occ_full[0][inactive_orbs_idxs],
                                 mo_occ_full[1][inactive_orbs_idxs] if self._beta else None)

        self._compute_inactive_density_matrix()

        # construct new QMolecule
        q_molecule_reduced = copy.deepcopy(q_molecule)
        # Energies and orbitals
        q_molecule_reduced.num_orbitals = self.num_molecular_orbitals
        q_molecule_reduced.num_alpha = self._num_particles[0]
        q_molecule_reduced.num_beta = self._num_particles[1]
        q_molecule_reduced.mo_coeff = self._mo_coeff_active[0]
        q_molecule_reduced.mo_coeff_b = self._mo_coeff_active[1]
        q_molecule_reduced.orbital_energies = q_molecule.orbital_energies[active_orbs_idxs]
        if self._beta:
            q_molecule_reduced.orbital_energies_b = q_molecule.orbital_energies_b[active_orbs_idxs]
        q_molecule_reduced.kinetic = None
        q_molecule_reduced.overlap = None

        # reduce electronic energy integrals
        self._reduce_to_active_space(q_molecule, q_molecule_reduced,
                                     'energy_shift',
                                     ('hcore', 'hcore_b'),
                                     ('mo_onee_ints', 'mo_onee_ints_b'),
                                     'eri',
                                     ('mo_eri_ints', 'mo_eri_ints_ba', 'mo_eri_ints_bb')
                                     )

        # reduce dipole moment integrals
        self._reduce_to_active_space(q_molecule, q_molecule_reduced,
                                     'x_dip_energy_shift',
                                     ('x_dip_ints', None),
                                     ('x_dip_mo_ints', 'x_dip_mo_ints_b')
                                     )
        self._reduce_to_active_space(q_molecule, q_molecule_reduced,
                                     'y_dip_energy_shift',
                                     ('y_dip_ints', None),
                                     ('y_dip_mo_ints', 'y_dip_mo_ints_b')
                                     )
        self._reduce_to_active_space(q_molecule, q_molecule_reduced,
                                     'z_dip_energy_shift',
                                     ('z_dip_ints', None),
                                     ('z_dip_mo_ints', 'z_dip_mo_ints_b')
                                     )

        return q_molecule_reduced

    def _check_configuration(self):
        # either freeze_core is specified
        valid = self.freeze_core
        # or at least num_electrons and num_molecular_orbitals must be valid
        valid |= isinstance(self.num_electrons, int) and \
            isinstance(self.num_molecular_orbitals, int)

        return valid

    def _extract_mo_occupation_vector(self, q_molecule: QMolecule):
        mo_occ_full = (q_molecule.mo_occ, q_molecule.mo_occ_b)
        if mo_occ_full[0] is None:
            # QMolecule provided by driver without `mo_occ` information available. Constructing
            # occupation numbers based on ground state HF case.
            occ_alpha = [1.] * q_molecule.num_alpha + [0.] * (q_molecule.num_orbitals -
                                                              q_molecule.num_alpha)
            if self._beta:
                occ_beta = [1.] * q_molecule.num_beta + [0.] * (q_molecule.num_orbitals -
                                                                q_molecule.num_beta)
            else:
                occ_alpha[:q_molecule.num_beta] = [o + 1 for o in occ_alpha[:q_molecule.num_beta]]
                occ_beta = None
            mo_occ_full = (np.asarray(occ_alpha), np.asarray(occ_beta))
        return mo_occ_full

    def _determine_active_space(self, q_molecule: QMolecule):
        nelec_total = q_molecule.num_alpha + q_molecule.num_beta

        if self.freeze_core:
            inactive_orbs_idxs = q_molecule.core_orbitals
            if self.remove_orbitals is not None:
                inactive_orbs_idxs.extend(self.remove_orbitals)
            active_orbs_idxs = [o for o in range(q_molecule.num_orbitals)
                                if o not in inactive_orbs_idxs]

            # compute number of active electrons
            nelec_inactive = sum([self._mo_occ_total[o] for o in inactive_orbs_idxs])
            nelec_active = nelec_total - nelec_inactive

            num_alpha = (nelec_active - (q_molecule.multiplicity - 1)) // 2
            num_beta = nelec_active - num_alpha

            self._num_particles = (num_alpha, num_beta)

            return (active_orbs_idxs, inactive_orbs_idxs)

        # compute number of inactive electrons
        nelec_inactive = nelec_total - self.num_electrons
        if self.num_alpha is not None:
            if not self._beta:
                warning = 'The provided instance of QMolecule does not provide any beta ' \
                          + 'coefficients but you tried to specify a separate number of alpha' \
                          + ' electrons. Continuing as if it does not matter.'
                logger.warning(warning)
            num_alpha = self.num_alpha
            num_beta = self.num_electrons - self.num_alpha
        else:
            num_beta = (self.num_electrons - (q_molecule.multiplicity - 1)) // 2
            num_alpha = self.num_electrons - num_beta

        self._num_particles = (num_alpha, num_beta)

        self._validate_num_electrons(nelec_inactive)
        self._validate_num_orbitals(nelec_inactive, q_molecule)

        # determine active and inactive orbital indices
        if self.active_orbitals is None:
            norbs_inactive = nelec_inactive // 2
            inactive_orbs_idxs = list(range(norbs_inactive))
            active_orbs_idxs = list(range(norbs_inactive,
                                          norbs_inactive+self.num_molecular_orbitals))
        else:
            active_orbs_idxs = self.active_orbitals
            inactive_orbs_idxs = [o for o in range(nelec_total // 2) if o not in
                                  self.active_orbitals and self._mo_occ_total[o] > 0]

        return (active_orbs_idxs, inactive_orbs_idxs)

    def _validate_num_electrons(self, nelec_inactive: int):
        """Validates the number of electrons.

        Args:
            nelec_inactive: the computed number of inactive electrons.

        Raises:
            QiskitNatureError: if the number of inactive electrons is either negative or odd.
        """
        if nelec_inactive < 0:
            raise QiskitNatureError("More electrons requested than available.")
        if nelec_inactive % 2 != 0:
            raise QiskitNatureError("The number of inactive electrons must be even.")

    def _validate_num_orbitals(self,
                               nelec_inactive: int,
                               q_molecule: QMolecule):
        """Validates the number of orbitals.

        Args:
            nelec_inactive: the computed number of inactive electrons.
            q_molecule: the `QMolecule` to be transformed.

        Raises:
            QiskitNatureError: if more orbitals were requested than are available in total or if the
                               number of selected orbitals mismatches the specified number of active
                               orbitals.
        """
        if self.active_orbitals is None:
            norbs_inactive = nelec_inactive // 2
            if norbs_inactive + self.num_molecular_orbitals > q_molecule.num_orbitals:
                raise QiskitNatureError("More orbitals requested than available.")
        else:
            if self.num_molecular_orbitals != len(self.active_orbitals):
                raise QiskitNatureError("The number of selected active orbital indices does not "
                                        "match the specified number of active orbitals.")
            if max(self.active_orbitals) >= q_molecule.num_orbitals:
                raise QiskitNatureError("More orbitals requested than available.")
            if sum(self._mo_occ_total[self.active_orbitals]) != self.num_electrons:
                raise QiskitNatureError("The number of electrons in the selected active orbitals "
                                        "does not match the specified number of active electrons.")

    def _compute_inactive_density_matrix(self):
        """Computes the inactive density matrix."""
        density_inactive_a = np.dot(self._mo_coeff_inactive[0]*self._mo_occ_inactive[0],
                                    np.transpose(self._mo_coeff_inactive[0]))
        density_inactive_b = None
        if self._beta:
            density_inactive_b = np.dot(self._mo_coeff_inactive[1]*self._mo_occ_inactive[1],
                                        np.transpose(self._mo_coeff_inactive[1]))
        self._density_inactive = (density_inactive_a, density_inactive_b)

    def _reduce_to_active_space(self,
                                q_molecule: QMolecule,
                                q_molecule_reduced: QMolecule,
                                energy_shift_attribute: str,
                                ao_1e_attribute: Tuple[str, str],
                                mo_1e_attribute: Tuple[str, str],
                                ao_2e_attribute: Optional[str] = None,
                                mo_2e_attribute: Optional[Tuple[str, str, str]] = None,
                                ) -> None:
        """A utility method which performs the actual orbital reduction computation.

        Args:
            q_molecule: the original `QMolecule` object.
            q_molecule_reduced: the reduced `QMolecule` object.
            energy_shift_attribute: the name of the attribute which stores the energy shift.
            ao_1e_attribute: the names of the AO-basis 1-electron matrices.
            mo_1e_attribute: the names of the MO-basis 1-electron matrices.
            ao_2e_attribute: the name of the AO-basis 2-electron matrix.
            mo_2e_attribute: the names of the MO-basis 2-electron matrices.
        """
        ao_1e_matrix = (getattr(q_molecule, ao_1e_attribute[0]),
                        getattr(q_molecule, ao_1e_attribute[1]) if self._beta else None)
        if ao_2e_attribute:
            ao_2e_matrix = getattr(q_molecule, ao_2e_attribute)
        else:
            ao_2e_matrix = None

        if ao_2e_matrix is None:
            # no 2-electron AO matrix is given
            inactive_op = copy.deepcopy(ao_1e_matrix)
        else:
            inactive_op = self._compute_inactive_fock_op(ao_1e_matrix, ao_2e_matrix)

        energy_shift = self._compute_inactive_energy(ao_1e_matrix, inactive_op)

        mo_1e_matrix, mo_2e_matrix = self._compute_active_integrals(inactive_op, ao_2e_matrix)

        getattr(q_molecule_reduced, energy_shift_attribute)['ActiveSpaceTransformer'] = energy_shift
        setattr(q_molecule_reduced, ao_1e_attribute[0], inactive_op[0])
        setattr(q_molecule_reduced, mo_1e_attribute[0], mo_1e_matrix[0])
        if self._beta:
            setattr(q_molecule_reduced, ao_1e_attribute[1], inactive_op[1])
            setattr(q_molecule_reduced, mo_1e_attribute[1], mo_1e_matrix[1])
        if mo_2e_matrix is not None:
            setattr(q_molecule_reduced, mo_2e_attribute[0], mo_2e_matrix[0])
            if self._beta:
                setattr(q_molecule_reduced, mo_2e_attribute[1], mo_2e_matrix[1])
                setattr(q_molecule_reduced, mo_2e_attribute[2], mo_2e_matrix[2])

    def _compute_inactive_fock_op(self,
                                  hcore: Tuple[np.ndarray, Optional[np.ndarray]],
                                  eri: np.ndarray,
                                  ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """Computes the inactive Fock operator.

        Args:
            hcore: the alpha- and beta-spin core Hamiltonian pair.
            eri: the electron-repulsion-integrals in MO format.

        Returns:
            The pair of alpha- and beta-spin inactive Fock operators.
        """
        # compute inactive Fock matrix
        coulomb_inactive = np.einsum('ijkl,ji->kl', eri, self._density_inactive[0])
        exchange_inactive = np.einsum('ijkl,jk->il', eri, self._density_inactive[0])
        fock_inactive = hcore[0] + coulomb_inactive - 0.5 * exchange_inactive
        fock_inactive_b = coulomb_inactive_b = exchange_inactive_b = None

        if self._beta:
            # if hcore[1] is None we use the alpha-spin core Hamiltonian
            hcore_b = hcore[1] or hcore[0]
            coulomb_inactive_b = np.einsum('ijkl,ji->kl', eri, self._density_inactive[1])
            exchange_inactive_b = np.einsum('ijkl,jk->il', eri, self._density_inactive[1])
            fock_inactive = hcore[0] + coulomb_inactive + coulomb_inactive_b - exchange_inactive
            fock_inactive_b = hcore_b + coulomb_inactive + coulomb_inactive_b - exchange_inactive_b

        return (fock_inactive, fock_inactive_b)

    def _compute_inactive_energy(self,
                                 hcore: Tuple[np.ndarray, Optional[np.ndarray]],
                                 fock_inactive: Tuple[np.ndarray, Optional[np.ndarray]],
                                 ) -> float:
        """Computes the inactive energy.

        Args:
            hcore: the alpha- and beta-spin core Hamiltonian pair.
            fock_inactive: the alpha- and beta-spin inactive fock operator pair.

        Returns:
            The inactive energy.
        """
        # compute inactive energy
        e_inactive = 0.0
        if not self._beta and self._mo_coeff_inactive[0].size > 0:
            e_inactive += 0.5 * np.einsum('ij,ji', self._density_inactive[0],
                                          hcore[0]+fock_inactive[0])
        elif self._beta and self._mo_coeff_inactive[1].size > 0:
            e_inactive += 0.5 * np.einsum('ij,ji', self._density_inactive[0],
                                          hcore[0]+fock_inactive[0])
            e_inactive += 0.5 * np.einsum('ij,ji', self._density_inactive[1],
                                          hcore[1]+fock_inactive[1])

        return e_inactive

    def _compute_active_integrals(self,
                                  fock_inactive: Tuple[np.ndarray, Optional[np.ndarray]],
                                  eri: Optional[np.ndarray] = None,
                                  ) -> Tuple[
                                      Tuple[np.ndarray, Optional[np.ndarray]],
                                      Optional[Tuple[np.ndarray,
                                                     Optional[np.ndarray],
                                                     Optional[np.ndarray]]]
                                      ]:
        """Computes the h1 and h2 integrals for the active space.

        Args:
            fock_inactive: the alpha- and beta-spin inactive fock operator pair.
            eri: the electron-repulsion-integrals in MO format.

        Returns:
            The h1 and h2 integrals for the active space. The storage format is the following:
                ((alpha-spin h1, beta-spin h1),
                 (alpha-alpha-spin h2, beta-alpha-spin h2, beta-beta-spin h2))
        """
        # compute new 1- and 2-electron integrals
        hij = np.dot(np.dot(np.transpose(self._mo_coeff_active[0]), fock_inactive[0]),
                     self._mo_coeff_active[0])
        hij_b = None
        if self._beta:
            hij_b = np.dot(np.dot(np.transpose(self._mo_coeff_active[1]), fock_inactive[1]),
                           self._mo_coeff_active[1])

        if eri is None:
            return ((hij, hij_b), None)

        hijkl = np.einsum('pqrs,pi,qj,rk,sl->ijkl', eri,
                          self._mo_coeff_active[0], self._mo_coeff_active[0],
                          self._mo_coeff_active[0], self._mo_coeff_active[0],
                          optimize=True)

        hijkl_bb = hijkl_ba = None

        if self._beta:
            hijkl_bb = np.einsum('pqrs,pi,qj,rk,sl->ijkl', eri,
                                 self._mo_coeff_active[1], self._mo_coeff_active[1],
                                 self._mo_coeff_active[1], self._mo_coeff_active[1],
                                 optimize=True)
            hijkl_ba = np.einsum('pqrs,pi,qj,rk,sl->ijkl', eri,
                                 self._mo_coeff_active[1], self._mo_coeff_active[1],
                                 self._mo_coeff_active[0], self._mo_coeff_active[0],
                                 optimize=True)

        return ((hij, hij_b), (hijkl, hijkl_ba, hijkl_bb))
