"""Merge extracted keys into one translation master, then split into batches.

Each row carries whatever context a translator needs: the shipped English rendering when
the key already exists in Eagle's en.lproj catalog, the source file it came from, and the
Swift literal an interpolated key was synthesized from.
"""

from __future__ import annotations

import argparse
import json
import os
import re

SPEC_RE = re.compile(r"%(?:\d+\$)?(?:ll|l|z|q)?[@difuoxXeEgGsc%\n]")
CH_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff]")


def specs(s: str) -> list[str]:
    return sorted(SPEC_RE.findall(s))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--batch-dir", required=True)
    ap.add_argument("--batch-size", type=int, default=120)
    ap.add_argument(
        "--known",
        default=None,
        help="JSON object of already-translated key -> zh. Those keys stay in the master but are "
             "left out of the batches, so a re-run only asks for what is actually new.",
    )
    args = ap.parse_args()

    report = json.load(open(args.keys, encoding="utf-8"))
    catalog = report["catalog"]
    known: set[str] = set()
    if args.known:
        known = set(json.load(open(args.known, encoding="utf-8")))
    tier_of = {"A": "catalog", "B": "callsite", "C": "spanish", "I": "interpolated"}

    rows: dict[str, dict] = {}
    for tier, table in report["keys"].items():
        for key, src in table.items():
            row = rows.setdefault(key, {"key": key, "tiers": [], "src": src})
            row["tiers"].append(tier_of[tier])
            if tier == "I":
                row["literal"] = src

    master: list[dict] = []
    skipped: list[dict] = []

    # Link the two source forms of the same sentence so a translator sees them together and an
    # audit can demand they agree.
    pairs = [tuple(p) for p in report.get("pairs", [])]
    linked = 0
    for english, spanish in pairs:
        if english in rows and spanish in rows:
            rows[english].setdefault("sibling", spanish)
            rows[spanish].setdefault("sibling", english)
            linked += 1
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "pairs.json"), "w", encoding="utf-8") as fh:
        json.dump([[e, s] for e, s in pairs], fh, ensure_ascii=False, indent=1)
    print(f"en/es pairs ......... {len(pairs)} ({linked} both present as keys)")
    for key, row in sorted(rows.items()):
        en = catalog.get(key)
        rec = {
            "key": key,
            "en": en,
            "tiers": row["tiers"],
            "src": row["src"],
        }
        if "literal" in row:
            rec["literal"] = row["literal"]
        if "sibling" in row:
            # Without this the pairing is computed and printed but never reaches the batch,
            # and translators have no way to keep the two source forms of one sentence equal.
            rec["sibling"] = row["sibling"]
        # A key that is nothing but format specifiers carries no copy to translate.
        if not re.sub(r"%\w|[\s.,:!?()\-–—/]", "", key):
            rec["reason"] = "specifier-only"
            skipped.append(rec)
            continue
        master.append(rec)

    # Group identical English strings so a term is translated once, consistently.
    by_en: dict[str, list[str]] = {}
    for rec in master:
        if rec["en"]:
            by_en.setdefault(rec["en"], []).append(rec["key"])
    dup_groups = {e: ks for e, ks in by_en.items() if len(ks) > 1}

    os.makedirs(args.out, exist_ok=True)
    os.makedirs(args.batch_dir, exist_ok=True)
    with open(os.path.join(args.out, "master.json"), "w", encoding="utf-8") as fh:
        json.dump({"rows": master, "skipped": skipped}, fh, ensure_ascii=False, indent=1)

    for f in os.listdir(args.batch_dir):
        os.remove(os.path.join(args.batch_dir, f))
    todo = [r for r in master if r["key"] not in known]
    batches = [todo[i : i + args.batch_size] for i in range(0, len(todo), args.batch_size)]
    for i, b in enumerate(batches, 1):
        with open(os.path.join(args.batch_dir, f"batch-{i:02d}.json"), "w", encoding="utf-8") as fh:
            json.dump(b, fh, ensure_ascii=False, indent=1)

    print(f"master rows ......... {len(master)}")
    print(f"already translated .. {len(master) - len(todo)}")
    print(f"to translate ........ {len(todo)}")
    print(f"skipped ............. {len(skipped)}")
    print(f"batches ............. {len(batches)} x ~{args.batch_size}")
    print(f"already zh .......... {sum(1 for r in master if CH_RE.search(r['key']))}")
    print(f"shared-en groups .... {len(dup_groups)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
