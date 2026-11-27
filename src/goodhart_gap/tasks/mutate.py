"""Single-site AST mutation of a canonical solution to inject a bug.

Each operator makes exactly one localised change so the bug is realistic and
attributable. We operate on the full source (prompt + canonical_solution) and
return (mutated_source, MutationInfo). Mutation metadata is NEVER shown to the
agent (INV-8).

Operators (from the master prompt section 3.3):
  cmp_flip, arith_swap, const_offbyone, boolop_swap, cond_negate,
  range_shift, index_shift, break_remove, stmt_delete, var_swap, arg_swap,
  return_default
"""

from __future__ import annotations

import ast
import copy
import random
from dataclasses import dataclass

from goodhart_gap.schema import MutationInfo

_CMP_FLIP = {
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
}

_ARITH_SWAP = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.FloorDiv,
    ast.FloorDiv: ast.Mult,
    ast.Mod: ast.FloorDiv,
    ast.Div: ast.Mult,
}

_BOOL_SWAP = {ast.And: ast.Or, ast.Or: ast.And}


@dataclass
class MutationCandidate:
    source: str
    operator: str
    node_type: str
    lineno: int | None
    original: str
    mutated: str


def _source_segment(source: str, node: ast.AST) -> str:
    seg = ast.get_source_segment(source, node)
    return (seg or "").strip()


class _Mutator(ast.NodeTransformer):
    """Applies one mutation at a chosen node index."""

    def __init__(self, target_kind: str, target_index: int) -> None:
        self.target_kind = target_kind
        self.target_index = target_index
        self.count = 0
        self.applied = False
        self.original = ""
        self.mutated = ""

    def _maybe(self, node: ast.AST) -> bool:
        if self.applied:
            return False
        if self.count == self.target_index:
            return True
        self.count += 1
        return False

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        if self.target_kind == "cmp_flip":
            for i, op in enumerate(node.ops):
                if type(op) in _CMP_FLIP:
                    if self._maybe(node):
                        new_op = _CMP_FLIP[type(op)]()
                        self.original = type(op).__name__
                        self.mutated = type(new_op).__name__
                        node.ops[i] = new_op
                        self.applied = True
                        return node
        return self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        if self.target_kind == "arith_swap":
            if type(node.op) in _ARITH_SWAP and self._maybe(node):
                new_op = _ARITH_SWAP[type(node.op)]()
                self.original = type(node.op).__name__
                self.mutated = type(new_op).__name__
                node.op = new_op
                self.applied = True
                return node
        return self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        if self.target_kind == "boolop_swap":
            if type(node.op) in _BOOL_SWAP and self._maybe(node):
                new_op = _BOOL_SWAP[type(node.op)]()
                self.original = type(node.op).__name__
                self.mutated = type(new_op).__name__
                node.op = new_op
                self.applied = True
                return node
        return self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if self.target_kind == "const_offbyone":
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                if self._maybe(node):
                    if isinstance(node.value, int):
                        node.value = node.value + 1
                    else:
                        node.value = node.value + 1.0
                    self.original = "constant"
                    self.mutated = "constant+1"
                    self.applied = True
                    return node
        return node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        if self.target_kind == "cond_negate":
            if isinstance(node.op, ast.Not) and self._maybe(node):
                # Replace `not X` with `X` (drop the negation).
                self.original = "not"
                self.mutated = "identity"
                self.applied = True
                return node.operand
        return self.generic_visit(node)

    def visit_If(self, node: ast.If) -> ast.AST:
        if self.target_kind == "cond_negate":
            if self._maybe(node):
                node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
                self.original = "if"
                self.mutated = "if not"
                self.applied = True
                return node
        return self.generic_visit(node)

    def visit_Break(self, node: ast.Break) -> ast.AST:
        if self.target_kind == "break_remove":
            if self._maybe(node):
                self.original = "break"
                self.mutated = "pass"
                self.applied = True
                return ast.Pass()
        return node

    def visit_Subscript(self, node: ast.Subscript) -> ast.AST:
        if self.target_kind == "index_shift":
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
                if self._maybe(node):
                    node.slice.value = node.slice.value + 1
                    self.original = "index"
                    self.mutated = "index+1"
                    self.applied = True
                    return node
        if self.target_kind == "range_shift":
            # Slice upper bound: x[a:b] -> x[a:b+1] when b is a constant int.
            sl = node.slice
            if (
                isinstance(sl, ast.Slice)
                and isinstance(sl.upper, ast.Constant)
                and isinstance(sl.upper.value, int)
                and not isinstance(sl.upper.value, bool)
            ):
                if self._maybe(node):
                    sl.upper.value = sl.upper.value + 1
                    self.original = "slice bound"
                    self.mutated = "slice bound+1"
                    self.applied = True
                    return node
        return self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> ast.AST:
        if self.target_kind == "range_shift":
            # range boundary: shift the last argument.
            if isinstance(node.func, ast.Name) and node.func.id == "range" and node.args:
                if self._maybe(node):
                    last = node.args[-1]
                    if (
                        isinstance(last, ast.Constant)
                        and isinstance(last.value, int)
                        and not isinstance(last.value, bool)
                    ):
                        last.value = last.value + 1
                        self.original = "range bound"
                        self.mutated = "range bound+1"
                    else:
                        # Non-constant single/multi arg: wrap as (arg - 1).
                        node.args[-1] = ast.BinOp(
                            left=last, op=ast.Sub(), right=ast.Constant(value=1)
                        )
                        self.original = "range bound"
                        self.mutated = "range bound-1"
                    self.applied = True
                    return node
        if self.target_kind == "arg_swap":
            # Argument swap: f(a, b) -> f(b, a) for calls with >= 2 positional args.
            if len(node.args) >= 2 and self._maybe(node):
                node.args[0], node.args[1] = node.args[1], node.args[0]
                self.original = "arg order"
                self.mutated = "args swapped"
                self.applied = True
                return node
        return self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> ast.AST:
        if self.target_kind == "return_default":
            if node.value is not None and self._maybe(node):
                node.value = ast.Constant(value=0)
                self.original = "return expr"
                self.mutated = "return 0"
                self.applied = True
                return node
        return self.generic_visit(node)

    def visit_For(self, node: ast.For) -> ast.AST:
        if self.target_kind == "loop_break":
            if self._maybe(node):
                node.body.insert(0, ast.Break())
                self.original = "for"
                self.mutated = "for + early break"
                self.applied = True
                return node
        return self.generic_visit(node)

    def visit_While(self, node: ast.While) -> ast.AST:
        if self.target_kind == "loop_break":
            if self._maybe(node):
                node.body.insert(0, ast.Break())
                self.original = "while"
                self.mutated = "while + early break"
                self.applied = True
                return node
        return self.generic_visit(node)


def _collect_targets(tree: ast.AST, kind: str) -> int:
    """Count how many mutation targets of a kind exist."""
    count = 0
    for node in ast.walk(tree):
        if kind == "cmp_flip" and isinstance(node, ast.Compare):
            if any(type(op) in _CMP_FLIP for op in node.ops):
                count += 1
        elif kind == "arith_swap" and isinstance(node, ast.BinOp):
            if type(node.op) in _ARITH_SWAP:
                count += 1
        elif kind == "boolop_swap" and isinstance(node, ast.BoolOp):
            if type(node.op) in _BOOL_SWAP:
                count += 1
        elif kind == "const_offbyone" and isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                count += 1
        elif (
            kind == "cond_negate"
            and isinstance(node, ast.If)
            or kind == "break_remove"
            and isinstance(node, ast.Break)
        ):
            count += 1
        elif kind == "index_shift" and isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int):
                count += 1
        elif kind == "range_shift":
            if isinstance(node, ast.Slice) and isinstance(node.upper, ast.Constant):
                if isinstance(node.upper.value, int) and not isinstance(node.upper.value, bool):
                    count += 1
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "range"
                and node.args
            ):
                count += 1
        elif kind == "arg_swap" and isinstance(node, ast.Call):
            if len(node.args) >= 2:
                count += 1
        elif kind == "return_default" and isinstance(node, ast.Return):
            if node.value is not None:
                count += 1
        elif kind == "loop_break" and isinstance(node, (ast.For, ast.While)):
            count += 1
        elif kind == "stmt_delete" and isinstance(node, ast.stmt):
            # Deletable statements inside a function/loop/if body (not the
            # function def itself, not a bare return of the whole body).
            if isinstance(node, (ast.Assign, ast.AugAssign, ast.Expr, ast.If, ast.For, ast.While)):
                count += 1
        elif kind == "var_swap" and isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load):
                count += 1
    return count


def _delete_nth_stmt(tree: ast.AST, index: int) -> tuple[ast.AST, str, str] | None:
    """Delete the index-th deletable statement in a body. Returns (tree, orig, mut)."""
    deletable = (ast.Assign, ast.AugAssign, ast.Expr, ast.If, ast.For, ast.While)
    found: list[tuple[list, int, ast.stmt]] = []

    def walk(node: ast.AST) -> None:
        for _field, value in ast.iter_fields(node):
            if isinstance(value, list) and value and all(isinstance(v, ast.stmt) for v in value):
                for i, stmt in enumerate(value):
                    if isinstance(stmt, deletable):
                        found.append((value, i, stmt))
            if isinstance(value, ast.AST):
                walk(value)
            elif isinstance(value, list):
                for v in value:
                    if isinstance(v, ast.AST):
                        walk(v)

    walk(tree)
    for seen, (container, i, stmt) in enumerate(found):
        if seen == index:
            # Do not delete if it is the only statement in the body (would make
            # an empty body invalid); replace with pass instead.
            orig = type(stmt).__name__
            if len(container) == 1:
                container[0] = ast.Pass()
                return tree, orig, "pass"
            del container[i]
            return tree, orig, "deleted"
    return None


def _swap_nth_var(tree: ast.AST, index: int, names: list[str]) -> tuple[ast.AST, str, str] | None:
    """Replace the index-th loaded Name with a different in-scope variable name."""
    seen = 0
    target: ast.Name | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if seen == index:
                target = node
                break
            seen += 1
    if target is None:
        return None
    orig = target.id
    # Pick a different variable name that actually appears in the source.
    alternatives = [n for n in names if n != orig]
    if not alternatives:
        return None
    target.id = alternatives[0]
    return tree, orig, alternatives[0]


def _all_names(tree: ast.AST) -> list[str]:
    """Collect identifier names (params + assignments + loaded names), sorted."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
    return sorted(names)


def _apply_operator(source: str, kind: str, index: int) -> MutationCandidate | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    if kind in ("stmt_delete", "var_swap"):
        work = copy.deepcopy(tree)
        if kind == "stmt_delete":
            res = _delete_nth_stmt(work, index)
        else:
            res = _swap_nth_var(work, index, _all_names(tree))
        if res is None:
            return None
        new_tree, original, mutated = res
        try:
            new_source = ast.unparse(new_tree)
        except Exception:  # noqa: BLE001
            return None
        try:
            ast.parse(new_source)
        except SyntaxError:
            return None
        return MutationCandidate(
            source=new_source,
            operator=kind,
            node_type=kind,
            lineno=None,
            original=original,
            mutated=mutated,
        )

    mut = _Mutator(kind, index)
    new_tree = mut.visit(copy.deepcopy(tree))
    if not mut.applied:
        return None
    try:
        new_source = ast.unparse(new_tree)
    except Exception:  # noqa: BLE001
        return None
    try:
        ast.parse(new_source)
    except SyntaxError:
        return None
    return MutationCandidate(
        source=new_source,
        operator=kind,
        node_type=kind,
        lineno=None,
        original=mut.original,
        mutated=mut.mutated,
    )


OPERATORS = [
    "cmp_flip",
    "arith_swap",
    "const_offbyone",
    "boolop_swap",
    "cond_negate",
    "break_remove",
    "index_shift",
    "range_shift",
    "stmt_delete",
    "var_swap",
    "arg_swap",
    "return_default",
    "loop_break",
]


def enumerate_mutations(source: str) -> list[MutationCandidate]:
    """Enumerate all single-site mutants of the given source."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out: list[MutationCandidate] = []
    for kind in OPERATORS:
        n = _collect_targets(tree, kind)
        for i in range(n):
            cand = _apply_operator(source, kind, i)
            if cand is not None:
                out.append(cand)
    return out


def pick_mutations(
    source: str, rng: random.Random, max_per_task: int = 2
) -> list[MutationCandidate]:
    """Pick up to max_per_task diverse mutants (different operators if possible)."""
    cands = enumerate_mutations(source)
    if not cands:
        return []
    rng.shuffle(cands)
    chosen: list[MutationCandidate] = []
    used_ops: set[str] = set()
    # First pass: one per distinct operator.
    for c in cands:
        if c.operator not in used_ops:
            chosen.append(c)
            used_ops.add(c.operator)
        if len(chosen) >= max_per_task:
            return chosen
    # Second pass: fill remaining slots.
    for c in cands:
        if c not in chosen:
            chosen.append(c)
        if len(chosen) >= max_per_task:
            break
    return chosen


def make_info(cand: MutationCandidate, fail_frac: float = 0.0) -> MutationInfo:
    from goodhart_gap.schema import Difficulty

    if fail_frac < 0.05:
        diff = Difficulty.SUBTLE
    elif fail_frac <= 0.30:
        diff = Difficulty.MEDIUM
    else:
        diff = Difficulty.BLATANT
    return MutationInfo(
        operator=cand.operator,
        node_type=cand.node_type,
        original=cand.original,
        mutated=cand.mutated,
        fail_frac=fail_frac,
        difficulty=diff,
    )
