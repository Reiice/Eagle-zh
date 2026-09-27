"""Measure how much of Eagle's real text surface the current Chinese table covers.

The first pass harvested literals only from lara/views and lara/PartyUI and only at
LocalizedStringKey-looking call sites. Eagle also renders copy passed as the `en:` / `es:`
arguments of `LaraL10n.text(...)`, which lives across views, classes and config -- and after
the source patch those routes DO look up the table, so every key we never collected shows up
as untranslated English in the app.

Provenance is used as the noise filter instead of a directory allow-list: a literal counts
only when it sits at a call site that resolves through .strings at runtime, which keeps the
kernel/exploit log chatter out without hiding real UI copy that happens to live outside views/.

Interpolated copy is split in two, because they are not the same problem:

  format_key   Text("Found \\(n) paths")  -- LocalizedStringKey keeps the compiler's format
             string ("Found %d paths"), so a static table entry CAN match it.
  dynamic    LaraL10n.text(en: "Found \\(n) paths") -- the interpolation is evaluated before
             the call, so deviceLocalized() receives the finished "Found 5 paths". No static
             key can ever match; localizing these needs a source change to a format-aware API.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_keys as ek
import macho

LARA_TEXT_ARG = re.compile(r'\b(?:en|es)\s*:\s*"((?:[^"\\]|\\.)*)"')
LARA_TEXT_CALL = re.compile(r"LaraL10n\.text\s*\(")


def swift_files(repo_dir: str):
    for root, _d, files in os.walk(os.path.join(repo_dir, "lara")):
        for name in sorted(files):
            if not name.endswith(".swift"):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, repo_dir).replace("\\", "/")
            try:
                yield rel, open(path, encoding="utf-8").read()
            except UnicodeDecodeError:
                continue


def laratext_ranges(text: str) -> list[tuple[int, int]]:
    """Spans of each LaraL10n.text( ... ) call, paren-balanced."""
    spans = []
    for m in LARA_TEXT_CALL.finditer(text):
        depth, k = 0, m.end() - 1
        while k < len(text):
            if text[k] == "(":
                depth += 1
            elif text[k] == ")":
                depth -= 1
                if depth == 0:
                    break
            k += 1
        spans.append((m.start(), k))
    return spans


def inside(spans: list[tuple[int, int]], off: int) -> bool:
    return any(a <= off <= b for a, b in spans)


def scan(repo_dir: str):
    plain: dict[str, str] = {}
    format_interp: dict[str, str] = {}
    dynamic_interp: dict[str, str] = {}
    for rel, text in swift_files(repo_dir):
        spans = laratext_ranges(text)
        for rx in (ek.CALL_RE, ek.NAMED_ARG_RE, LARA_TEXT_ARG):
            for m in rx.finditer(text):
                lit = ek.strip_escapes(m.group(1))
                if "\\(" in m.group(1):
                    # `en:`/`es:` arguments are evaluated before text() sees them.
                    bucket = dynamic_interp if inside(spans, m.start()) else format_interp
                    bucket.setdefault(lit, rel)
                else:
                    plain.setdefault(lit, rel)
    return plain, format_interp, dynamic_interp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--binary", required=True)
    ap.add_argument("--table", required=True, help="current zh-Hans Localizable.strings")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    blob = open(args.binary, "rb").read()
    have = set(macho.read_strings(args.table))

    plain, format_interp, dynamic_interp = scan(args.repo)

    covered, missing = 0, {}
    for lit, rel in plain.items():
        if not ek.is_prose(lit) or lit.encode() not in blob:
            continue
        if lit in have:
            covered += 1
        else:
            missing[lit] = rel

    fmt_missing: dict[str, str] = {}
    for lit, rel in format_interp.items():
        for cand in ek.interp_variants(lit):
            if cand in have:
                continue
            head = cand.split("%", 1)[0].strip()[:20]
            if head and head.encode() not in blob:
                continue
            fmt_missing[cand] = lit

    dyn_missing = {lit: rel for lit, rel in dynamic_interp.items() if ek.is_prose(re.sub(r"\\\([^)]*\)", "aa", lit))}

    by_area: dict[str, int] = {}
    for rel in missing.values():
        a = "/".join(rel.split("/")[1:3])
        by_area[a] = by_area.get(a, 0) + 1

    report = {
        "counts": {
            "table_entries_today": len(have),
            "plain_literals_already_covered": covered,
            "plain_literals_missing": len(missing),
            "interpolated_format_keys_missing": len(fmt_missing),
            "interpolated_dynamic_needs_source_change": len(dyn_missing),
        },
        "missing_by_source_area": dict(sorted(by_area.items(), key=lambda kv: -kv[1])),
        "missing_plain": dict(sorted(missing.items())),
        "missing_format_keys": dict(sorted(fmt_missing.items())),
        "dynamic_needs_source_change": dict(sorted(dyn_missing.items())),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    json.dump(report, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    c = report["counts"]
    print(f"table entries today .................. {c['table_entries_today']}")
    print(f"plain literals already covered ....... {c['plain_literals_already_covered']}")
    print(f"plain literals MISSING ............... {c['plain_literals_missing']}")
    print(f"interpolated, fixable by table ....... {c['interpolated_format_keys_missing']}")
    print(f"interpolated, needs source change .... {c['interpolated_dynamic_needs_source_change']}")
    print("\nmissing plain literals by source area:")
    for a, n in list(report["missing_by_source_area"].items())[:14]:
        print(f"   {n:5d}  {a}")
    print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
