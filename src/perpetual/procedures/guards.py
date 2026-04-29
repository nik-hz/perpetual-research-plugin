from __future__ import annotations
from lark import Lark, Transformer, v_args

GUARD_GRAMMAR = r"""
    ?start: expr

    ?expr: or_expr
    ?or_expr: and_expr ("or" and_expr)*
    ?and_expr: not_expr ("and" not_expr)*
    ?not_expr: "not" not_expr -> not_op
             | atom

    ?atom: comparison
         | "always"  -> always
         | "never"   -> never
         | "(" expr ")"

    comparison: ref CMP_OP value

    ref: NAME ("." NAME)*
    value: NUMBER | ESCAPED_STRING

    CMP_OP: "<=" | ">=" | "!=" | "==" | "<" | ">"

    %import common.NUMBER
    %import common.ESCAPED_STRING
    %import common.CNAME -> NAME
    %import common.WS
    %ignore WS
"""

_parser = Lark(GUARD_GRAMMAR, parser="lalr")

def parse_guard(text: str):
    """Parse a guard expression into a tree. Returns the Lark tree."""
    return _parser.parse(text)

@v_args(inline=True)
class GuardEvaluator(Transformer):
    """Evaluate a guard expression against a context dict."""

    def __init__(self, context: dict):
        super().__init__()
        self.context = context

    def always(self):
        return True

    def never(self):
        return False

    def not_op(self, val):
        return not val

    def or_expr(self, *args):
        return any(args)

    def and_expr(self, *args):
        return all(args)

    def ref(self, *parts):
        obj = self.context
        for p in parts:
            if isinstance(obj, dict):
                obj = obj.get(str(p))
            else:
                return None
        return obj

    def value(self, v):
        s = str(v)
        if s.startswith('"') and s.endswith('"'):
            return s[1:-1]
        try:
            return float(s)
        except ValueError:
            return s

    # @sig a6a31bad | role: comparison | by: claude-code-b7232740 | at: 2026-04-29T22:57:37Z
    def comparison(self, left, op, right):
        op = str(op).strip()
        if left is None or right is None:
            return False
        try:
            if op == "<": return left < right
            if op == ">": return left > right
            if op == "<=": return left <= right
            if op == ">=": return left >= right
            if op == "==": return left == right
            if op == "!=": return left != right
        except TypeError:
            return False
        return False

    def NUMBER(self, tok):
        return float(tok)

    def ESCAPED_STRING(self, tok):
        return str(tok)[1:-1]

    def NAME(self, tok):
        return str(tok)

def evaluate_guard(text: str, context: dict) -> bool:
    """Parse and evaluate a guard expression against context. Returns bool."""
    if text.strip() == "always":
        return True
    if text.strip() == "never":
        return False
    tree = parse_guard(text)
    return GuardEvaluator(context).transform(tree)
