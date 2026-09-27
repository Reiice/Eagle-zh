"""Why did a source string that Eagle displays never reach the table?

For every `LaraL10n.text(en:, es:)` slot that has no Chinese on either side, report the exact
gate that rejected it. Without this the answer is guesswork, and the last audit said 71% of
slots were covered while the goal is "no foreign language left".
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re

import sys

# A cp936 console cannot encode every character these tables contain.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_keys as ek
import macho


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--table", required=True)
    ap.add_argument("--binary", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    pairs = [tuple(p) for p in json.load(open(args.pairs, encoding="utf-8"))]
    table = macho.read_strings(args.table)
    catalog = macho.read_strings(args.catalog)
    blob = open(args.binary, "rb").read()

    reasons: collections.Counter = collections.Counter()
    examples: dict[str, list[str]] = {}
    missing = []

    for english, spanish in pairs:
        if english in table or spanish in table:
            continue
        missing.append((english, spanish))
        # Attribute the loss to the first gate that rejected either side.
        why = "kept-but-lost-downstream"
        for side in (english, spanish):
            if "\\(" in side:
                why = "interpolated: template not generated"
                break
            if not ek.is_prose(side):
                hits = [rx.pattern for rx in ek.REJECT_RES if rx.search(side)]
                if ek.LOGGY.search(side):
                    why = "rejected: LOGGY filter"
                elif hits:
                    why = f"rejected: REJECT_RES {hits[0]!r}"
                else:
                    why = "rejected: is_prose (too short / not sentence-like)"
                break
            if side.encode() not in blob:
                why = "not found in the shipped binary"
                break
        reasons[why] += 1
        examples.setdefault(why, []).append(english[:88])

    out = {
        "slots_total": len(pairs),
        "slots_covered": len(pairs) - len(missing),
        "slots_missing": len(missing),
        "reasons": dict(reasons.most_common()),
        "examples": {k: v[:12] for k, v in examples.items()},
    }
    json.dump({"summary": out, "missing": [list(p) for p in missing]},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"text() slots ...... {out['slots_total']}")
    print(f"covered ........... {out['slots_covered']} ({out['slots_covered']/len(pairs)*100:.1f}%)")
    print(f"MISSING ........... {out['slots_missing']}")
    print("\nwhy they are missing:")
    for reason, n in reasons.most_common():
        print(f"  {n:4d}  {reason}")
        print(f"          e.g. {examples[reason][0]!r}")
    print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
