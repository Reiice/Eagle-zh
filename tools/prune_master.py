"""Quality gate over the extracted key universe.

Tier A/B/C keys are proven user-facing copy (they sit at a localized call site or already
ship in Eagle's own catalog), so only outright parse artifacts and command/path strings are
dropped from them.

Tier I keys are *synthesized* candidates: each Swift literal containing interpolation was
fanned out across several specifier spellings because the runtime key depends on the
argument's type. Most of those candidates carry no translatable words at all ("%@ ms",
"%@ · %@") and several are regex artifacts from multi-line interpolation ("...countStyle:
.file))"). A candidate survives only if it still reads like copy after neutral tokens are
removed.

Dropping keys is safe against an in-flight translation run: the merge filters translator
output down to whatever the master asks for.
"""

from __future__ import annotations

import argparse
import json
import os
import re

SPEC_RE = re.compile(r"%(?:\d+\$)?(?:ll|l|z|q)?(?:\.\d+)?[@difuoxXeEgGsc]")

# Leftovers from regex over-running a Swift interpolation or trailing expression.
# Deliberately narrow: keys legitimately start with a space (LLVM suffix sharing), with
# "¿" (Spanish questions) or with "•" (bullet copy).
ARTIFACT_RE = re.compile(r"\\\(|\?\?|\.formatted\(|\.rounded|countStyle|\bself\b|=>|\bText\(")
COMMAND_RE = re.compile(r"^(?:\./|/|\w+://)|\s--|\.(?:sh|py|js|ts|c|h|hpp|m|d\.ts)\b")
TEMPLATE_RE = re.compile(r"\{[a-z_]+\}")

# Words that carry no translation work: brands, technical names, bare units, letters.
# Ordinary verbs and nouns (Failed, Version, Error, Delete) are deliberately NOT here --
# they are exactly the words a candidate key still needs translated.
NEUTRAL = {
    "eagle", "aura", "ios", "iphone", "ipad", "apple", "wallet", "dock",
    "composer", "moment", "resonance", "styles", "studio", "guardian", "match", "poster",
    "pocket", "springboard", "remotecall", "kernelcache", "krw", "vfs", "pac", "dylib",
    "sha", "bundle", "url", "api", "json", "ipa", "ota", "uttype", "github", "discord",
    "trollstore", "sidestore", "livecontainer", "leonardo", "safari", "scene", "scenes",
    "ms", "mb", "gb", "kb", "px", "dpi", "fps", "hz", "nm", "rgb", "hsl", "hex",
    "x", "y", "z", "v", "a", "b", "c", "d", "n", "i", "ii", "iii", "iv", "id", "vs",
}


def content_words(s: str) -> list[str]:
    s = SPEC_RE.sub(" ", s)
    words = re.findall(r"[A-Za-z\u00c0-\u024f]{2,}", s)
    return [w for w in words if w.lower() not in NEUTRAL]


def keep(row: dict) -> tuple[bool, str]:
    key = row["key"]
    tiers = row.get("tiers", [])

    if ARTIFACT_RE.search(key):
        return False, "parse artifact"
    if COMMAND_RE.search(key):
        return False, "command or path"
    if TEMPLATE_RE.search(key):
        return False, "template placeholder"
    if not key.strip():
        return False, "blank"

    if "interpolated" in tiers and set(tiers) == {"interpolated"}:
        if not content_words(key):
            return False, "no translatable words"
    return True, ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", required=True)
    ap.add_argument("--in-place", action="store_true")
    ap.add_argument(
        "--extra",
        action="append",
        default=[],
        help="JSON object of hand-recovered key -> translation; keys join the master as tier 'manual'",
    )
    args = ap.parse_args()

    doc = json.load(open(args.master, encoding="utf-8"))
    rows = list(doc["rows"])
    present = {r["key"] for r in rows}
    for path in args.extra:
        if not os.path.isfile(path):
            # A clone that never wrote hand-recovered entries must still be able to run the
            # pipeline; the keys simply stay out of the master until someone adds them.
            print(f"warning: --extra {path} does not exist, skipping")
            continue
        for k in json.load(open(path, encoding="utf-8")):
            if k not in present:
                rows.append({"key": k, "en": None, "tiers": ["manual"], "src": "recovered by hand"})
                present.add(k)

    kept: list[dict] = []
    dropped: list[dict] = []
    reasons: dict[str, int] = {}
    for row in rows:
        ok, why = keep(row)
        if ok:
            kept.append(row)
        else:
            row = dict(row)
            row["dropped_reason"] = why
            dropped.append(row)
            reasons[why] = reasons.get(why, 0) + 1

    out_rows = {"rows": kept, "skipped": doc.get("skipped", []) + dropped}
    target = args.master if args.in_place else args.master.replace(".json", ".pruned.json")
    json.dump(out_rows, open(target, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    by_tier: dict[str, int] = {}
    for r in kept:
        for t in r["tiers"]:
            by_tier[t] = by_tier.get(t, 0) + 1
    print(f"master rows ... {len(rows)}")
    print(f"kept .......... {len(kept)}")
    print(f"dropped ....... {len(dropped)}  {reasons}")
    print("kept by tier ..", dict(sorted(by_tier.items())))
    print(f"-> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
