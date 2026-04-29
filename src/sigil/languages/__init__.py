"""Language adapter registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sigil.languages.base import LanguageAdapter

_REGISTRY: dict[str, LanguageAdapter] | None = None


def _build_registry() -> dict[str, LanguageAdapter]:
    from sigil.languages.python import PythonAdapter
    from sigil.languages.typescript import TypeScriptAdapter
    from sigil.languages.go import GoAdapter
    from sigil.languages.rust import RustAdapter

    reg: dict[str, LanguageAdapter] = {}
    for adapter_cls in (PythonAdapter, TypeScriptAdapter, GoAdapter, RustAdapter):
        adapter = adapter_cls()
        for ext in adapter.extensions:
            reg[ext] = adapter
    return reg


def get_adapter(suffix: str) -> LanguageAdapter | None:
    """Return the adapter for a file extension, or None if unsupported."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return _REGISTRY.get(suffix)


def supported_extensions() -> tuple[str, ...]:
    """Return all supported file extensions."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build_registry()
    return tuple(_REGISTRY.keys())
