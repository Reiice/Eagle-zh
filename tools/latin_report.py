"""List every Latin token that will still appear when the app is in Chinese.

"选择中文后尽量不再有其他语言" needs an auditable answer, not an impression. Two passes:

  untranslated  values with no Chinese characters at all -- each one is a deliberate
            passthrough (brand, command, filename) or a hole in the table.
  embedded    values that ARE Chinese but still contain Latin runs, e.g. "在 Dock 上应用".
            Anything not on the approved keep-list is a term to reconsider.

Format specifiers, URLs and file names are excluded from the "term" judgement because
they are not language.
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
import macho

CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9][A-Za-z0-9._+\-/]*")
SPEC = re.compile(r"%(?:\d+\$)?(?:ll|l|z|q)?(?:\.\d+)?[@difuoxXeEgGsc]")
URLISH = re.compile(r"^(?:https?|file|ssh|git|mailto|tel):|^/|^~|^[A-Za-z0-9_.\-]+\.[A-Za-z]{2,5}$")

# Approved to stay in Latin script: product names, protocol/API identifiers, file formats.
KEEP = {
    "Eagle", "EagleMatch", "EagleComposer", "EagleMoment", "EagleResonance", "EagleStyles",
    "EagleDepth", "EagleCapsule", "EagleScene", "Aura", "AuraStudio", "Guardian",
    "PocketPoster", "Nugget", "NuggetWallpapers", "SmartFocus", "Voiceprint", "Tapprint",
    "Rainbow", "Cowabunga", "DarkBoard", "LiquidGlass", "Wallet", "Apple", "iPhone", "iPad",
    "iOS", "macOS", "SwiftUI", "Xcode", "GitHub", "Discord", "Telegram",
    "SpringBoard", "Backboard", "launchd", "RemoteCall", "KRW", "VFS", "PAC", "ASLR",
    "Kernel", "Kernelcache", "dylib", "MachO", "IPA", "IPSW", "ipsw", "JSON", "Plist",
    "URL", "API", "Bundle", "BundleID", "UTType", "SF", "PNG", "JPG", "JPEG", "HEIC",
    "GIF", "MP4", "MOV", "Markdown", "HTML", "CSS", "SHA", "SHA256", "UTF8", "ASCII",
    "Dock", "Home", "TrollStore", "SideStore", "Sideloadly", "LiveContainer", "Filza",
    "OTA", "Beta", "Alpha", "Pro", "Max", "Plus", "Mini", "USB", "Wi-Fi", "WiFi",
    "OK", "ID", "TV", "PC", "MR", "CD", "DNA", "A18", "A17", "A16", "M1", "M2", "M3",
    "M4", "M5", "EN", "ES", "v2", "v3", "GPT",
}


def norm(t: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", t).title()


def classify(tok: str) -> str:
    if tok.upper() in {k.upper() for k in KEEP}:
        return "approved"
    if URLISH.search(tok):
        return "path-or-filename"
    if "." in tok and re.match(r"^[a-z]", tok):
        return "identifier"          # sf symbols, preference keys, reverse-DNS
    if re.search(r"[_\-]", tok):
        return "identifier"
    if tok.isupper() and len(tok) <= 5:
        return "acronym"
    return "review"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    table = macho.read_strings(args.table)

    untranslated = {k: v for k, v in table.items() if not CJK.search(v)}
    counts: collections.Counter = collections.Counter()
    where: dict[str, str] = {}
    classes: dict[str, str] = {}
    for k, v in table.items():
        if not CJK.search(v):
            continue
        for tok in TOKEN.findall(SPEC.sub(" ", v)):
            counts[tok] += 1
            where.setdefault(tok, k)
            classes.setdefault(tok, classify(tok))

    buckets: dict[str, list] = {}
    for tok, n in counts.most_common():
        buckets.setdefault(classes[tok], []).append({"token": tok, "count": n, "example_key": where[tok]})

    report = {
        "table_entries": len(table),
        "untranslated_entries": {"count": len(untranslated), "items": untranslated},
        "latin_tokens_by_class": {k: v for k, v in buckets.items()},
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    json.dump(report, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"table entries .......................... {len(table)}")
    print(f"entries with NO Chinese at all ......... {len(untranslated)}")
    for k, v in sorted(untranslated.items(), key=lambda kv: kv[1])[:40]:
        print(f"      {k[:58]!r:62s} -> {v!r}")
    print()
    for cls in ("review", "acronym", "identifier", "path-or-filename", "approved"):
        items = buckets.get(cls, [])
        print(f"{cls:20s} {len(items):4d} distinct tokens")
    print(f"\n-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
