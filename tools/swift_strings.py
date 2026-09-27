"""A small Swift string-literal scanner.

The regex used before -- `"((?:[^"\\\\]|\\\\.)*)"` -- cannot represent Swift's
`\\(expression)` holes, because the expression may itself contain string literals:

    Text("Delete \\(count) item\\(count == 1 ? "" : "s")?")

The regex stops at the quote inside the interpolation, so the key came out truncated
("Delete %@ item\\(count == 1 ? ") and could never be looked up. That left 92 UI slots
untranslatable for a reason that had nothing to do with translation.

This module reads a literal the way the compiler does: escapes, nested quotes inside
interpolations, and balanced parentheses.
"""

from __future__ import annotations


def read_string(text: str, i: int) -> tuple[str, int] | None:
    """At text[i] == '"', return (inner_source, index_past_closing_quote).

    `inner_source` keeps `\\(...)` holes verbatim so callers can split them later.
    """
    if i >= len(text) or text[i] != '"':
        return None
    i += 1
    out: list[str] = []
    while i < len(text):
        c = text[i]
        if c == "\\":
            if i + 1 < len(text) and text[i + 1] == "(":
                hole, i = _read_interpolation(text, i + 1)
                out.append(hole)
                continue
            if i + 1 < len(text):
                out.append(text[i:i + 2])
                i += 2
                continue
        if c == '"':
            return "".join(out), i + 1
        out.append(c)
        i += 1
    return "".join(out), i


def _read_interpolation(text: str, i: int) -> tuple[str, int]:
    """At text[i] == '(', consume the balanced `\\(...)` and return it including the backslash."""
    depth = 0
    j = i
    out: list[str] = ["\\"]
    while j < len(text):
        c = text[j]
        if c == '"':
            inner, j2 = read_string(text, j)
            out.append('"' + (inner or "") + '"')
            j = j2
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            out.append(c)
            j += 1
            if depth == 0:
                return "".join(out), j
            continue
        out.append(c)
        j += 1
    return "".join(out), j


def call_arg_string(text: str, open_paren: int) -> tuple[str, int] | None:
    """Read the first string argument after `(`, skipping an optional `label:`."""
    i = open_paren + 1
    while i < len(text):
        c = text[i]
        if c.isspace():
            i += 1
            continue
        if c == '"':
            return read_string(text, i)
        m = _LABEL.match_from(text, i)
        if m:
            i = m
            continue
        return None
    return None


class _Label:
    @staticmethod
    def match_from(text: str, i: int) -> int | None:
        j = i
        while j < len(text) and (text[j].isalnum() or text[j] == "_"):
            j += 1
        if j == i:
            return None
        k = j
        while k < len(text) and text[k].isspace():
            k += 1
        if k < len(text) and text[k] == ":":
            k += 1
            while k < len(text) and text[k].isspace():
                k += 1
            return k
        return None
