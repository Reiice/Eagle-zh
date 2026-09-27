"""Force the duplicate keys of one sentence to carry one Chinese string.

Eagle reaches the same sentence through several keys, and 14 translator runs cannot be trusted
to agree on all of them:

  * `%@` / `%d` variants -- one Swift literal, two candidate keys.
  * the English and the Spanish form of one `LaraL10n.text(en:, es:)` call -- two keys, and
    after the source patch the English one is looked up first while the Spanish one still has
    to answer for `Text("Spanish")` sites on a Chinese device.

Left alone the table ends up with two different Chinese sentences for one UI label, which is
exactly what the first build looked like. This pass picks a canonical member and rewrites the
rest, swapping only the placeholder tokens so the strings stay format-correct.

Canonical choice: prefer the `%@` variant (that is what L10nText produces at runtime) and,
within a pair, the English key (it is the one the patched lookup tries first).
"""

from __future__ import annotations

import argparse
import json
import os
import re

import sys

# A cp936 console cannot encode every character these tables contain.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

SPEC_SPLIT = re.compile(r"(%@|%d|%lld|%llu|%lu|%f|%\.\d+f|%)")


def skeleton(value: str) -> list[str]:
    return SPEC_SPLIT.split(value)


def respec(value: str, target_key: str) -> str | None:
    """Re-render `value`'s placeholders in the order/type `target_key` expects.

    Returns None when the counts disagree. That happens legitimately: Chinese drops the
    English plural marker, so a two-placeholder key can translate to a one-placeholder
    sentence. Copying such a value onto the sibling would invent a placeholder of the wrong
    type -- a runtime format-string bug -- so the sibling keeps its own translation instead.
    """
    from_spec = SPEC_SPLIT.findall(value)
    want = re.findall(r"%@|%d|%lld|%llu|%lu|%f|%\.\d+f", target_key)
    if len(from_spec) != len(want):
        return None
    parts = SPEC_SPLIT.split(value)
    out = []
    idx = 0
    for piece in parts:
        if SPEC_SPLIT.fullmatch(piece or ""):
            out.append(want[idx])
            idx += 1
        else:
            out.append(piece)
    return "".join(out)


def canonical_pick(keys: list[str], table: dict[str, str]) -> str:
    with_at = [k for k in keys if "%@" in k]
    pool = with_at or keys
    # Longest value wins ties: a fuller sentence is likelier to be the deliberate one.
    return max(pool, key=lambda k: (0 if "%@" in k else 1, -len(table.get(k, "")), k))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True, help="merged key->zh JSON")
    ap.add_argument("--master", required=True, help="work/master.pruned.json (carries `literal`)")
    ap.add_argument("--pairs", required=True, help="work/pairs.json")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    table = json.load(open(args.table, encoding="utf-8"))
    rows = json.load(open(args.master, encoding="utf-8"))["rows"]
    pairs = [tuple(p) for p in json.load(open(args.pairs, encoding="utf-8"))]

    # Group by the Swift literal a key was derived from.
    groups: dict[str, list[str]] = {}
    for row in rows:
        lit = row.get("literal")
        if lit:
            groups.setdefault(lit, []).append(row["key"])

    rewrites: list[dict] = []
    skipped: list[str] = []

    def unify(keys: list[str], why: str, prefer: str | None = None) -> None:
        present = [k for k in keys if k in table]
        if len(present) < 2:
            return
        # `prefer` matters for en/es pairs: the patched lookup tries the English key first, so
        # its wording is what users actually see and should win.
        canon_key = prefer if prefer in present else canonical_pick(present, table)
        canon = table[canon_key]
        for k in present:
            if k == canon_key:
                continue
            want = respec(canon, k)
            if want is None:
                skipped.append(k)
                continue
            if table[k] != want:
                rewrites.append({"key": k, "before": table[k], "after": want,
                                 "canonical_of": canon_key, "why": why})
                table[k] = want

    for lit, keys in sorted(groups.items()):
        if len(set(keys)) > 1:
            unify(sorted(set(keys)), "same swift literal")

    # English/Spanish pairs come from ONE `LaraL10n.text(en:, es:)` call, so by construction
    # they are the same sentence and should read the same in Chinese. The exception is where
    # the author deliberately wrote different things per language -- a brand name in English
    # and a translated word in Spanish (DarkBoardView pairs "Icon Studio" with "Iconos").
    # That case is detectable: the value is still identical to its own key, i.e. an
    # intentional Latin passthrough. Leave those alone; unify everything else.
    review: list[dict] = []
    for english, spanish in pairs:
        if english in table and spanish in table:
            a, b = table[english], table[spanish]
            if a == b:
                continue
            if a == english or b == spanish:
                review.append({"en": english, "es": spanish, "zh_en": a, "zh_es": b,
                               "why": "one side is a deliberate Latin passthrough"})
                continue
            unify([english, spanish], "en/es twin", prefer=english)

    json.dump(table, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # The review list must NOT land next to the table: compile_strings loads every *.json in
    # the directory it is given, and this file is a list, not a translation table.
    review_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(args.out))),
                               "pair-review.json")
    json.dump(review, open(review_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"table entries ....... {len(table)}")
    print(f"literal groups ..... {sum(1 for v in groups.values() if len(v) > 1)}")
    print(f"pairs .............. {len(pairs)}")
    print(f"rewrites ........... {len(rewrites)}")
    print(f"left alone (placeholder count differs) {len(set(skipped))}")
    print(f"pairs left for review {len(review)} -> {review_path}")
    for r in rewrites[:12]:
        print(f"   [{r['why']}] {r['key'][:40]!r}\n        {r['before']!r} -> {r['after']!r}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
