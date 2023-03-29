# Copyright 2023-2023 TeNPy Developers, GNU GPLv3
from __future__ import annotations
from numpy import prod
from typing import Any, TYPE_CHECKING

from .abelian import AbstractAbelianBackend
from .abstract_backend import AbstractBlockBackend, Block, Data, Dtype
from .no_symmetry import AbstractNoSymmetryBackend
from .nonabelian import AbstractNonabelianBackend
from ..misc import inverse_permutation
from ..symmetries import VectorSpace

__all__ = ['TorchBlockBackend', 'NoSymmetryTorchBackend', 'AbelianTorchBackend', 'NonabelianTorchBackend']


if TYPE_CHECKING:
    # can not import Tensor at runtime, since it would be a circular import
    # this clause allows mypy etc to evaluate the type-hints anyway
    from ..tensors import Tensor


class TorchBlockBackend(AbstractBlockBackend):

    svd_algorithms = ['gesvdj', 'gesvd']

    def __init__(self, device: str = 'cpu') -> None:
        global torch_module
        try:
            import torch
        except ImportError as e:
            raise ImportError('Could not import torch. Use a different backend or install torch.') from e
        self.device = device
        torch_module = torch
        super().__init__()
        self.tenpy_dtype_map = {
            torch.float32: Dtype.float32,
            torch.float64: Dtype.float64,
            torch.complex64: Dtype.complex64,
            torch.complex128: Dtype.complex128,
        }
        self.backend_dtype_map = {
            Dtype.float32: torch.float32,
            Dtype.float64: torch.float64,
            Dtype.complex64: torch.complex64,
            Dtype.complex128: torch.complex128,
        }

    def block_is_real(self, a: Block):
        return not torch_module.is_complex(a)

    def block_tdot(self, a: Block, b: Block, idcs_a: list[int], idcs_b: list[int]) -> Block:
        return torch_module.tensordot(a, b, (idcs_a, idcs_b))

    def block_shape(self, a: Block) -> tuple[int]:
        return tuple(a.shape)

    def block_item(self, a: Block) -> float | complex:
        return a.item()

    def block_dtype(self, a: Block) -> Dtype:
        return self.tenpy_dtype_map[a.dtype]

    def block_to_dtype(self, a: Block, dtype: Dtype) -> Block:
        return a.type(self.backend_dtype_map[dtype])

    def block_copy(self, a: Block) -> Block:
        return torch_module.tensor(a, device=self.device)

    def _block_repr_lines(self, a: Block, indent: str, max_width: int, max_lines: int) -> list[str]:
        torch_module.set_printoptions(linewidth=max_width - len(indent))
        lines = [f'{indent}{line}' for line in repr(a).split('\n')]
        torch_module.set_printoptions(profile='default')
        if len(lines) > max_lines:
            first = (max_lines - 1) // 2
            last = max_lines - 1 - first
            lines = lines[:first] + [f'{indent}...'] + lines[-last:]
        return lines

    def matrix_svd(self, a: Block, algorithm: str | None) -> tuple[Block, Block, Block]:
        if algorithm is None:
            algorithm = 'gesvd'
        assert algorithm in self.svd_algorithms
        U, S, V = torch_module.linalg.svd(a, full_matrices=False, driver=algorithm)
        return U, S, V

    def block_outer(self, a: Block, b: Block) -> Block:
        return torch_module.tensordot(a, b, ([], []))

    def block_inner(self, a: Block, b: Block, axs2: list[int] | None) -> complex:
        # TODO is this faster than torch.sum(a * b.transpose[axs2]) ?
        axs1 = list(range(len(a.shape)))
        if axs2 is None:
            axs2 = axs1
        return torch_module.tensordot(torch_module.conj(a), b, (axs1, axs2))

    def block_transpose(self, a: Block, permutation: list[int]) -> Block:
        return torch_module.permute(a, permutation)  # TODO: this is documented as a view. is that a problem?

    def block_trace(self, a: Block, idcs1: list[int], idcs2: list[int]) -> Block:
        other_idcs = [n for n in range(len(a.shape)) if n not in idcs1 and n not in idcs2]
        a = torch_module.permute(a, other_idcs + idcs1 + idcs2)
        num_other = len(other_idcs)
        num_trace = len(idcs1)
        trace_dim = prod(a.shape[num_other:num_other + num_trace])
        a = torch_module.reshape(a, [*a.shape[:num_other], trace_dim, trace_dim])
        return a.diagonal(offset=0, dim1=-1, dim2=-2).sum(-1)

    def block_conj(self, a: Block) -> Block:
        return torch_module.conj(a)

    def block_combine_legs(self, a: Block, legs: list[int]) -> Block:
        # TODO optimize this?
        legs_before_new_leg = [n for n in range(legs[0]) if n not in legs]
        legs_after_new_leg = [n for n in range(legs[0] + 1, len(a.shape)) if n not in legs]
        permutation = legs_before_new_leg + legs + legs_after_new_leg
        new_shape = [a.shape[n] for n in legs_before_new_leg] + [prod([a.shape[n] for n in legs])] \
            + [a.shape[n] for n in legs_after_new_leg]
        a = torch_module.permute(a, permutation)
        return torch_module.reshape(a, new_shape)

    def block_split_leg(self, a: Block, leg: int, dims: list[int]) -> Block:
        return torch_module.reshape(a, (*a.shape[:leg], *dims, *a.shape[leg + 1:]))

    def block_allclose(self, a: Block, b: Block, rtol: float, atol: float) -> bool:
        return torch_module.allclose(a, b, rtol=rtol, atol=atol)

    def block_squeeze_legs(self, a: Block, idcs: list[int]) -> Block:
        # TODO (JU) this is ugly... but torch.squeeze squeezes all axes of dim 1, cant control which
        idx = [0 if ax in idcs else slice(None, None, None) for ax in range(len(a.shape))]
        return a[idx]

    def block_norm(self, a: Block) -> float:
        return torch_module.norm(a)

    def block_matrixify(self, a: Block, idcs1: list[int], idcs2: list[int]) -> tuple[Block, Any]:
        permutation = idcs1 + idcs2
        a = torch_module.permute(a, permutation)
        a_shape = a.shape
        matrix_shape = prod(a_shape[:len(idcs1)]), prod(a_shape[len(idcs1):])
        matrix = torch_module.reshape(a, matrix_shape)
        aux = (permutation, a_shape)
        return matrix, aux

    def block_dematrixify(self, matrix: Block, aux: Any) -> Block:
        permutation, a_shape = aux
        res = torch_module.reshape(matrix, a_shape)
        return torch_module.permute(res, inverse_permutation(permutation))

    def matrix_exp(self, matrix: Block) -> Block:
        raise NotImplementedError  # TODO: could not find a torch implementation via their docs...?

    def matrix_log(self, matrix: Block) -> Block:
        raise NotImplementedError  # TODO: could not find a torch implementation via their docs...?

    def block_random_uniform(self, dims: list[int], dtype: Dtype) -> Block:
        return torch_module.rand(*dims, dtype=self.backend_dtype_map[dtype], device=self.device)

    def block_random_normal(self, dims: list[int], dtype: Dtype, sigma: float) -> Block:
        # Note that if device is CUDA, this function synchronizes the device with the CPU
        mean = torch_module.zeros(size=dims, dtype=self.backend_dtype_map[dtype], device=self.device)
        std = sigma * torch_module.ones_like(mean, device=self.device)
        return torch_module.normal(mean, std)

    def block_from_numpy(self, a) -> Block:
        return torch_module.tensor(a, device=self.device)

    def zero_block(self, shape: list[int], dtype: Dtype) -> Block:
        return torch_module.zeros(shape, dtype=self.backend_dtype_map[dtype], device=self.device)

    def eye_block(self, legs: list[int], dtype: Dtype) -> Data:
        matrix_dim = prod(legs)
        eye = torch_module.eye(matrix_dim, dtype=self.backend_dtype_map[dtype], device=self.device)
        eye = torch_module.reshape(eye, legs + legs)
        return eye


class NoSymmetryTorchBackend(TorchBlockBackend, AbstractNoSymmetryBackend):
    def __init__(self, device: str = 'cpu'):
        TorchBlockBackend.__init__(self, device=device)
        AbstractNoSymmetryBackend.__init__(self)

    def svd(self, a: Tensor, axs1: list[int], axs2: list[int], new_leg: VectorSpace | None
            ) -> tuple[Data, Data, Data, VectorSpace]:
        a = torch_module.permute(a.data, axs1 + axs2)
        a_shape1 = a.shape[:len(axs1)]
        a_shape2 = a.shape[len(axs1):]
        a = torch_module.reshape(a, (prod(a_shape1), prod(a_shape2)))
        u, s, vh = self.matrix_svd(a)
        u = torch_module.reshape(u, (*a_shape1, len(s)))
        vh = torch_module.reshape(vh, (len(s), *a_shape2))
        if new_leg is None:
            new_leg = VectorSpace.non_symmetric(len(s), is_dual=False, is_real=False)
        return u, s, vh, new_leg


class AbelianTorchBackend(TorchBlockBackend, AbstractAbelianBackend):
    def __init__(self, device: str = 'cpu'):
        TorchBlockBackend.__init__(self, device=device)
        AbstractAbelianBackend.__init__(self)


class NonabelianTorchBackend(TorchBlockBackend, AbstractNonabelianBackend):
    def __init__(self, device: str = 'cpu'):
        TorchBlockBackend.__init__(self, device=device)
        AbstractNonabelianBackend.__init__(self)
