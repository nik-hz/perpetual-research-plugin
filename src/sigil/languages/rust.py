"""Rust language adapter using tree-sitter."""

from __future__ import annotations

from pathlib import Path

from sigil.format import compute_hash, parse_sigil_line
from sigil.languages.base import FunctionRecord, treesitter_write_sigils

_parser = None


def _get_parser():
    global _parser
    if _parser is None:
        import tree_sitter_rust as tsrs
        from tree_sitter import Language, Parser
        _parser = Parser(Language(tsrs.language()))
    return _parser


def _walk_functions(node, rel_path: str, source_lines: list[str],
                    scope: list[str], records: list[FunctionRecord]) -> None:
    """Walk the Rust AST for function items, including inside impl blocks."""
    for child in node.children:
        if child.type == "impl_item":
            # Extract the type being implemented.
            type_node = child.child_by_field_name("type")
            impl_name = type_node.text.decode() if type_node else "<anon>"
            scope.append(impl_name)
            _walk_functions(child, rel_path, source_lines, scope, records)
            scope.pop()
            continue

        if child.type == "function_item":
            name_node = child.child_by_field_name("name")
            if not name_node:
                continue
            func_name = name_node.text.decode()
            symbol = ".".join([*scope, func_name])
            symbol_id = f"{rel_path}::{symbol}"

            body_text = child.text.decode()
            h = compute_hash(body_text)

            start_line = child.start_point[0]  # 0-based
            existing = None
            if start_line > 0:
                existing = parse_sigil_line(source_lines[start_line - 1])

            line_range = (start_line + 1, child.end_point[0] + 1)
            records.append(FunctionRecord(symbol_id, h, line_range, existing))
            continue

        # Recurse into declaration_list (impl body), mod_item, etc.
        if child.type in ("declaration_list", "mod_item"):
            _walk_functions(child, rel_path, source_lines, scope, records)


class RustAdapter:
    comment_prefix: str = "//"
    extensions: tuple[str, ...] = (".rs",)

    def parse(self, path: Path, rel_path: str) -> list[FunctionRecord]:
        source = path.read_text(encoding="utf-8")
        source_lines = source.split("\n")
        source_bytes = source.encode("utf-8")
        parser = _get_parser()
        tree = parser.parse(source_bytes)
        records: list[FunctionRecord] = []
        _walk_functions(tree.root_node, rel_path, source_lines, [], records)
        return records

    def write_sigils(self, path: Path, rel_path: str, sigils: dict[str, str]) -> None:
        treesitter_write_sigils(path, sigils, self.comment_prefix, self.parse, rel_path)
