"""AST validation for Arena mission runs."""

from __future__ import annotations

from typing import Any


class AstValidationError(Exception):
    def __init__(self, message: str, code: str = "invalid_ast") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def _count_nodes(node: Any) -> int:
    if not isinstance(node, dict):
        return 0
    count = 1 if "op" in node else 0
    for key in ("body", "then", "else"):
        children = node.get(key)
        if isinstance(children, list):
            for child in children:
                count += _count_nodes(child)
    cond = node.get("cond")
    if isinstance(cond, dict):
        count += _count_nodes(cond)
    args = node.get("args")
    if isinstance(args, dict):
        for value in args.values():
            if isinstance(value, dict) and ("op" in value or "type" in value):
                count += _count_nodes(value)
    return count


def _max_depth(node: Any, depth: int = 0) -> int:
    if not isinstance(node, dict):
        return depth
    deepest = depth
    for key in ("body", "then", "else"):
        children = node.get(key)
        if isinstance(children, list):
            for child in children:
                deepest = max(deepest, _max_depth(child, depth + 1))
    cond = node.get("cond")
    if isinstance(cond, dict):
        deepest = max(deepest, _max_depth(cond, depth + 1))
    args = node.get("args")
    if isinstance(args, dict):
        for value in args.values():
            if isinstance(value, dict) and "op" in value:
                deepest = max(deepest, _max_depth(value, depth + 1))
    return deepest


def _collect_ops(node: Any, ops: set[str]) -> None:
    if not isinstance(node, dict):
        return
    op = node.get("op")
    if isinstance(op, str):
        ops.add(op)
    for key in ("body", "then", "else"):
        children = node.get(key)
        if isinstance(children, list):
            for child in children:
                _collect_ops(child, ops)
    cond = node.get("cond")
    if isinstance(cond, dict):
        _collect_ops(cond, ops)
    args = node.get("args")
    if isinstance(args, dict):
        for value in args.values():
            if isinstance(value, dict):
                _collect_ops(value, ops)


def _assert_program_shape(ast: Any) -> dict[str, Any]:
    if not isinstance(ast, dict):
        raise AstValidationError("AST ต้องเป็น object", "invalid_shape")
    if ast.get("type") != "program":
        raise AstValidationError('AST ต้องมี type เป็น "program"', "invalid_shape")
    body = ast.get("body")
    if not isinstance(body, list):
        raise AstValidationError("program.body ต้องเป็น array", "invalid_shape")
    return ast


def validate_ast(ast: Any, *, allowed_ops: list[str], limits: dict[str, Any]) -> None:
    """Raise AstValidationError if AST is invalid for the mission pack."""
    program = _assert_program_shape(ast)

    max_blocks = int(limits.get("maxBlocks", 40))
    max_depth = int(limits.get("maxDepth", 12))
    allowed = set(allowed_ops)

    block_count = sum(_count_nodes(node) for node in program["body"])
    if block_count > max_blocks:
        raise AstValidationError(
            f"จำนวนบล็อกเกินกำหนด ({block_count}/{max_blocks})",
            "too_many_blocks",
        )

    depth = max((_max_depth(node) for node in program["body"]), default=0)
    if depth > max_depth:
        raise AstValidationError(
            f"ความลึกของบล็อกเกินกำหนด ({depth}/{max_depth})",
            "too_deep",
        )

    found: set[str] = set()
    for node in program["body"]:
        _collect_ops(node, found)
    unknown = sorted(found - allowed)
    if unknown:
        raise AstValidationError(
            f"พบคำสั่งที่ไม่ได้รับอนุญาต: {', '.join(unknown)}",
            "unknown_op",
        )
