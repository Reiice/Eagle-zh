"""Merge batch translations and impose the cross-batch term decisions.

Nine translator runs cannot agree with each other by hope, so the disagreements they
reported are resolved here from one auditable table (l10n/terms.json) rather than by
hand-editing a generated file.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re

import sys

# A cp936 console cannot encode every character these tables contain.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--translated-dir", action="append", required=True,
                    help="may be repeated; the first directory that defines a key wins")
    ap.add_argument("--seeded", help="optional extra table used only to fill keys no translated dir defines")
    ap.add_argument("--terms", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    table: dict[str, str] = {}
    origin: dict[str, str] = {}
    conflicts = 0
    for directory in args.translated_dir:
        for f in sorted(glob.glob(os.path.join(directory, "*.json"))):
            data = json.load(open(f, encoding="utf-8"))
            if not isinstance(data, dict):
                raise SystemExit(f"{f}: expected a flat JSON object, got {type(data).__name__}")
            for k, v in data.items():
                if not isinstance(v, str):
                    raise SystemExit(f"{f}: value for {k[:40]!r} is not a string")
                if k in table and table[k] != v:
                    conflicts += 1
                    print(f"  conflict {k[:50]!r}: kept {table[k][:30]!r}, ignoring {v[:30]!r}")
                    continue
                table.setdefault(k, v)
                origin.setdefault(k, os.path.basename(f))

    seeded = json.load(open(args.seeded, encoding="utf-8")) if args.seeded else {}
    filled = 0
    for k, v in seeded.items():
        if k not in table:
            table[k] = v
            origin[k] = "lara-seed"
            filled += 1

    terms = json.load(open(args.terms, encoding="utf-8"))
    changes: list[dict] = []
    for k in list(table):
        v = table[k]
        if k in terms.get("exact", {}):
            new = terms["exact"][k]
            if new != v:
                changes.append({"key": k, "before": v, "after": new, "rule": "exact"})
                v = new
        for src, dst in terms.get("global", []):
            if src in v:
                nv = v.replace(src, dst)
                if nv != v:
                    changes.append({"key": k, "before": v, "after": nv, "rule": f"global {src!r}"})
                    v = nv
        for src, dst in terms.get("regex", []):
            nv = re.sub(src, dst, v)
            if nv != v:
                changes.append({"key": k, "before": v, "after": nv, "rule": f"regex {src!r}"})
                v = nv
        table[k] = v

    os.makedirs(args.out_dir, exist_ok=True)
    out = os.path.join(args.out_dir, "normalized.json")
    json.dump(table, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(
        {"changes": changes, "conflicts": conflicts, "seeded_filled": filled},
        open(os.path.join(args.out_dir, "normalize-report.json"), "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )

    print(f"merged entries ..... {len(table)}")
    print(f"from batches ....... {sum(1 for o in origin.values() if o != 'lara-seed')}")
    print(f"seeded from Lara ... {filled}")
    print(f"cross-file conflicts {conflicts}")
    print(f"term rewrites ...... {len(changes)}")
    for c in changes[:12]:
        print(f"   [{c['rule']}] {c['key'][:34]!r} {c['before'][:26]!r} -> {c['after'][:26]!r}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
