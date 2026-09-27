"""Build the set of keys that must NOT be sent for translation again.

Two kinds are excluded, for different reasons:
  * keys already translated (a previous run's merged table, plus the Lara seed)
  * keys the quality gate threw away -- they are not in the final master, so asking a
    translator for them would burn effort on strings that never ship.

Keeping this in one place is what lets `prepare` be re-run after widening the key universe
without re-translating the ~900 strings that were already done.
"""

from __future__ import annotations

import argparse
import glob
import json
import os


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", required=True, help="unpruned work/master.json")
    ap.add_argument("--pruned", required=True, help="work/master.pruned.json")
    ap.add_argument("--translated", action="append", default=[],
                    help="directories of key->zh JSON; may be repeated")
    ap.add_argument("--seeded", action="append", default=[])
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    full = {r["key"] for r in json.load(open(args.master, encoding="utf-8"))["rows"]}
    kept = {r["key"] for r in json.load(open(args.pruned, encoding="utf-8"))["rows"]}
    dropped = full - kept

    done: set[str] = set()
    for d in args.translated:
        for f in glob.glob(os.path.join(d, "*.json")):
            done |= set(json.load(open(f, encoding="utf-8")))
    for f in args.seeded:
        done |= set(json.load(open(f, encoding="utf-8")))

    excluded = done | dropped
    json.dump({k: "" for k in sorted(excluded)},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False)

    print(f"already translated .. {len(done)}")
    print(f"dropped by gate ..... {len(dropped)}")
    print(f"excluded from batch . {len(excluded)}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
