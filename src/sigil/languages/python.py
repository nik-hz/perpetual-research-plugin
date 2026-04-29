"""Python language adapter using libcst."""

from __future__ import annotations

import os
from pathlib import Path

import libcst as cst

from sigil.format import compute_hash, parse_sigil_line
from sigil.languages.base import FunctionRecord


class _Visitor(cst.CSTVisitor):
    METADATA_DEPENDENCIES = (cst.metadata.PositionProvider,)

    def __init__(self, rel_path: str):
        self.rel_path = rel_path
        self.scope: list[str] = []
        self.records: list[FunctionRecord] = []

    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        self.scope.append(node.name.value)

    def leave_ClassDef(self, original_node: cst.ClassDef) -> None:
        self.scope.pop()

    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        symbol = ".".join([*self.scope, node.name.value])
        symbol_id = f"{self.rel_path}::{symbol}"

        stripped = node.with_changes(decorators=(), leading_lines=())
        body_code = cst.Module(body=[]).code_for_node(stripped)
        h = compute_hash(body_code)

        existing = None
        for line in node.leading_lines:
            if line.comment:
                parsed = parse_sigil_line(line.comment.value)
                if parsed:
                    existing = parsed
                    break

        pos = self.get_metadata(cst.metadata.PositionProvider, node)
        line_range = (pos.start.line, pos.end.line)

        self.records.append(FunctionRecord(symbol_id, h, line_range, existing))
        self.scope.append(node.name.value)

    def leave_FunctionDef(self, original_node: cst.FunctionDef) -> None:
        self.scope.pop()


class _Updater(cst.CSTTransformer):
    def __init__(self, rel_path: str, targets: dict[str, str]):
        self.rel_path = rel_path
        self.targets = targets
        self.scope: list[str] = []

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:
        self.scope.append(node.name.value)
        return True

    def leave_ClassDef(self, original_node, updated_node):
        self.scope.pop()
        return updated_node

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:
        self.scope.append(node.name.value)
        return True

    def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef):
        symbol = ".".join(self.scope)
        self.scope.pop()
        symbol_id = f"{self.rel_path}::{symbol}"
        new_text = self.targets.get(symbol_id)
        if new_text is None:
            return updated_node

        new_leading = []
        replaced = False
        for ll in updated_node.leading_lines:
            if ll.comment and parse_sigil_line(ll.comment.value):
                new_leading.append(ll.with_changes(comment=cst.Comment(value=new_text)))
                replaced = True
            else:
                new_leading.append(ll)
        if not replaced:
            new_leading.append(cst.EmptyLine(comment=cst.Comment(value=new_text)))
        return updated_node.with_changes(leading_lines=tuple(new_leading))


class PythonAdapter:
    comment_prefix: str = "#"
    extensions: tuple[str, ...] = (".py",)

    def parse(self, path: Path, rel_path: str) -> list[FunctionRecord]:
        source = path.read_text(encoding="utf-8")
        module = cst.parse_module(source)
        wrapper = cst.metadata.MetadataWrapper(module)
        visitor = _Visitor(rel_path)
        wrapper.visit(visitor)
        return visitor.records

    def write_sigils(self, path: Path, rel_path: str, sigils: dict[str, str]) -> None:
        if not sigils:
            return
        source = path.read_text(encoding="utf-8")
        module = cst.parse_module(source)
        new_module = module.visit(_Updater(rel_path, sigils))
        tmp = path.with_suffix(path.suffix + ".sig.tmp")
        tmp.write_text(new_module.code, encoding="utf-8")
        os.replace(tmp, path)
