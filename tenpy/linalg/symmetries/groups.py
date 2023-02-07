from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from itertools import product
from math import prod
from typing import TypeVar, Final


Sector = TypeVar('Sector')  # place-holder for the type of a sector. must support comparison (for sorting) and hashing


class FusionStyle(Enum):
    single = 0  # only one resulting sector, a ⊗ b = c, eg abelian symmetry groups
    multiple_unique = 10  # every sector appears at most once in pairwise fusion, N^{ab}_c \in {0,1}
    general = 20  # no assumptions N^{ab}_c = 0, 1, 2, ...


class BraidingStyle(Enum):
    bosonic = 0  # symmetric braiding with trivial twist; v ⊗ w ↦ w ⊗ v
    fermionic = 10  # symmetric braiding with non-trivial twist; v ⊗ w ↦ (-1)^p(v,w) w ⊗ v
    anyonic = 20  # non-symmetric braiding
    no_braiding = 30  # braiding is not defined


class Symmetry(ABC):
    """Base class for symmetries that impose a block-structure on tensors"""
    def __init__(self, fusion_style: FusionStyle, braiding_style: BraidingStyle, trivial_sector: Sector, 
                 group_name: str, descriptive_name: str | None = None):
        self.fusion_style = fusion_style
        self.braiding_style = braiding_style
        self.trivial_sector = trivial_sector
        self.group_name = group_name
        self.descriptive_name = descriptive_name

    @abstractmethod
    def is_valid_sector(self, a: Sector) -> bool:
        """Whether `a` is a valid sector of this symmetry"""
        ...

    @abstractmethod
    def fusion_outcomes(self, a: Sector, b: Sector) -> list[Sector]:
        """Returns all outcomes for the fusion of sectors.
        Each sector appears only once, regardless of its multiplicity (given by n_symbol) in the fusion"""
        ...

    @abstractmethod
    def sector_dim(self, a: Sector) -> int:
        """The dimension of a sector as a subspace of the hilbert space"""
        ...

    def sector_str(self, a: Sector) -> str:
        """Short and readable string for the sector. Is used in __str__ of symmetry-related objects."""
        return str(a)

    @abstractmethod
    def __repr__(self):
        # Convention: valid syntax for the constructor, i.e. "ClassName(..., name='...')"
        ...

    def __str__(self):
        res = self.group_name
        if self.descriptive_name is not None:
            res = res + f'("{self.descriptive_name}")'
        return res

    def __mul__(self, other):
        if isinstance(self, ProductSymmetry):
            factors = self.factors
        elif isinstance(self, Symmetry):
            factors = [self]
        else:
            return NotImplemented
        
        if isinstance(other, ProductSymmetry):
            factors = factors + other.factors
        elif isinstance(other, Symmetry):
            factors = factors + [other]
        else:
            return NotImplemented
        
        return ProductSymmetry(factors=factors)

    @abstractmethod
    def dual_sector(self, a: Sector) -> Sector:
        """
        The sector dual to a, such that N^{a,dual(a)}_u = 1.
        TODO: define precisely what the dual sector is.
        we want the canonical representative of its equivalence class
        """
        ...

    # TODO a bunch of methods, such as n-symbol etc which (i think) only matter for the non-abelian implementation


class NoSymmetry(Symmetry):
    """Trivial symmetry group that doesn't do anything. the only allowed sector is `None`"""

    def __init__(self):
        Symmetry.__init__(self, fusion_style=FusionStyle.single, braiding_style=BraidingStyle.bosonic, 
                          trivial_sector=None, group_name='NoSymmetry', descriptive_name=None)
    
    def is_valid_sector(self, a: Sector) -> bool:
        return a is None
    
    def fusion_outcomes(self, a: Sector, b: Sector) -> list[Sector]:
        return [None]
    
    def sector_dim(self, a: Sector) -> int:
        return 1
    
    def sector_str(self, a: Sector) -> int:
        return '.'
    
    def __repr__(self):
        return 'NoSymmetry()'
    
    def dual_sector(self, a: Sector) -> Sector:
        return None


class ProductSymmetry(Symmetry):
    """Multiple symmetry groups. The allowed sectors are lists of sectors of the factor symmetries."""

    def __init__(self, factors: list[Symmetry]):
        self.factors = factors
        if all(f.descriptive_name is not None for f in factors):
            descriptive_name = f'[{", ".join(f.descriptive_name for f in factors)}]'
        else:
            descriptive_name = None
        Symmetry.__init__(
            self, 
            fusion_style=max((f.fusion_style for f in factors), key=lambda style: style.value), 
            braiding_style=max((f.braiding_style for f in factors), key=lambda style: style.value),
            trivial_sector=[f.trivial_sector for f in factors],
            group_name=' ⨉ '.join(f.group_name for f in factors),
            descriptive_name=descriptive_name
        )

    def is_valid_sector(self, a: Sector) -> bool:
        if len(a) != len(self.factors):
            return False
        try:
            return all(f.is_valid_sector(b) for f, b in zip(self.factors, a))
        except TypeError:  
            # if a is not iterable
            return False

    def fusion_outcomes(self, a: Sector, b: Sector) -> list[Sector]:
        # this can probably be optimized. could also special-case FusionStyle.single
        all_outcomes = (f.fusion_outcomes(a_f, b_f) for f, a_f, b_f in zip(self.factors, a, b))
        return [list(combination) for combination in product(*all_outcomes)]

    def sector_dim(self, a: Sector) -> int:
        return prod(f.sector_dim(a_f) for f, a_f in zip(self.factors, a))

    def sector_str(self, a: Sector) -> str:
        return f'[{", ".join(f.sector_str(a_f) for f, a_f in zip(self.factors, a))}]'

    def __repr__(self):
        return ' * '.join(repr(f) for f in self.factors)

    def __str__(self):
        return ' ⨉ '.join(str(f) for f in self.factors)

    def dual_sector(self, a: Sector) -> Sector:
        return [f.dual_sector(a_f) for f, a_f in zip(self.factors, a)]


# TODO: call it GroupSymmetry instead?
class Group(Symmetry, ABC):
    """
    Base-class for symmetries that are described by a group via a faithful representation on the Hilbert space.
    Noteable counter-examples are fermionic parity or anyonic grading.
    """
    def __init__(self, fusion_style: FusionStyle, trivial_sector: Sector, group_name: str, descriptive_name: str | None = None):
        Symmetry.__init__(self, fusion_style=fusion_style, braiding_style=BraidingStyle.bosonic, 
                          trivial_sector=trivial_sector, group_name=group_name, 
                          descriptive_name=descriptive_name)


class AbelianGroup(Group, ABC):
    """
    Base-class for abelian symmetry groups
    """
    def __init__(self, trivial_sector: Sector, group_name: str, descriptive_name: str | None = None):
        Group.__init__(self, fusion_style=FusionStyle.single, trivial_sector=trivial_sector, 
                       group_name=group_name, descriptive_name=descriptive_name)

    def sector_dim(self, a: Sector) -> int:
        return 1


class QmodGroup(AbelianGroup, ABC):
    """
    Common code for Z_N and U(1) groups.
    The sectors are labelled by modular integers Z_N or all integers Z, respectively.
    Qmod, i.e. the divisor for modular addition is N or "no modulo"/1, respectively.
    Allowed sectors are integers, either 0, 1, ..., N or any (including negative) integer.
    Fusion is addition module Qmod 
    """
    def __init__(self, qmod: int, group_name: str, descriptive_name: str | None = None):
        self.qmod = qmod
        AbelianGroup.__init__(self, trivial_sector=0, group_name=group_name, 
                              descriptive_name=descriptive_name)

    def is_valid_sector(self, a: Sector) -> bool:
        return isinstance(a, int) and (self.qmod == 1 or 0 <= a < self.qmod)

    def fusion_outcomes(self, a: Sector, b: Sector) -> list[Sector]:
        return [(a + b) % self.qmod]

    def dual_sector(self, a: Sector) -> Sector:
        return (-a) % self.qmod


class ZNSymmetry(QmodGroup):
    """Z_N symmetry. Sectors are integers `0`, `1`, ..., `N-1`"""
    def __init__(self, N: int, descriptive_name: str | None = None):
        self.N = N
        subscript_map = {'0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '⨉⨉⨉⨉', '6': '₆',
                         '7': '₇', '8': '₈', '9': '₉'}
        subscript_N = ''.join(subscript_map[char] for char in str(N))
        QmodGroup.__init__(self, qmod=N, group_name=f'ℤ{subscript_N}', descriptive_name=descriptive_name)
    
    def __repr__(self):
        return f'ZNSymmetry(N={self.N})'  # TODO include descriptive_name?


# TODO group_names U(1) and SU(2) or U₁ and SU₂ ?


class U1Symmetry(QmodGroup):
    """U(1) symmetry. Sectors are integers ..., `-2`, `-1`, `0`, `1`, `2`, ..."""
    def __init__(self, descriptive_name: str | None = None):
        QmodGroup.__init__(self, qmod=1, group_name='U(1)', descriptive_name=descriptive_name)

    def __repr__(self):
        return 'U1Symmetry()'

    
class SU2Symmetry(Group):
    """SU(2) symmetry. Sectors are positive integers `jj` = `0`, `1`, `2`, ...
    which label the spin `jj/2` irrep of SU(2).
    This is for convenience so that we can work with `int` objects.
    E.g. a spin-1/2 degree of freedom is represented by the sector `1`.
    """
    def __init__(self, descriptive_name: str | None = None):
        Group.__init__(self, fusion_style=FusionStyle.multiple_unique, trivial_sector=0, 
                       group_name='SU(2)', descriptive_name=descriptive_name)

    def is_valid_sector(self, a: Sector) -> bool:
        return isinstance(a, int) and a >= 0

    def fusion_outcomes(self, a: Sector, b: Sector) -> list[Sector]:
        # J_tot = |J1 - J2|, ..., J1 + J2
        return list(range(abs(a - b), a + b + 2, 2))

    def sector_dim(self, a: Sector) -> int:
        # dim = 2 * J + 1 = jj + 1
        return a + 1

    def sector_str(self, a: Sector) -> str:
        j_str = str(a // 2) if a % 2 == 0 else f'{a}/2'
        return f'J={j_str}'

    def __repr__(self):
        return 'SU2Symmetry()'

    def dual_sector(self, a: Sector) -> Sector:
        return a


class FermionParity(Symmetry):
    """Fermionic Parity. Sectors are `0` (even parity) and `1` (odd parity)"""

    def __init__(self):
        Symmetry.__init__(self, fusion_style=FusionStyle.single, braiding_style=BraidingStyle.fermionic, 
                          trivial_sector=0, group_name='FermionParity', descriptive_name=None)

    def is_valid_sector(self, a: Sector) -> bool:
        return a in [0, 1]

    def fusion_outcomes(self, a: Sector, b: Sector) -> list[Sector]:
        # equal sectors fuse to even parity, i.e. to `0 == int(False)`
        # unequal sectors fuse to odd parity i.e. to `1 == int(True)`
        return int(a != b)

    def sector_dim(self, a: Sector) -> int:
        return 1

    def sector_str(self, a: Sector) -> str:
        return 'even' if a == 0 else 'odd'

    def __repr__(self):
        return 'FermionParity()'

    def dual_sector(self, a: Sector) -> Sector:
        return a


no_symmetry: Final = NoSymmetry()
z2_symmetry: Final = ZNSymmetry(N=2)
z3_symmetry: Final = ZNSymmetry(N=3)
z4_symmetry: Final = ZNSymmetry(N=4)
z5_symmetry: Final = ZNSymmetry(N=5)
z6_symmetry: Final = ZNSymmetry(N=6)
z7_symmetry: Final = ZNSymmetry(N=7)
z8_symmetry: Final = ZNSymmetry(N=8)
z9_symmetry: Final = ZNSymmetry(N=9)
u1_symmetry: Final = U1Symmetry()
su2_symmetry: Final = SU2Symmetry()
fermion_parity: Final = FermionParity()
