"""Compile the Chinese table into .strings files.

The repository keeps a reviewable UTF-8 text .strings; the IPA gets the binary-plist form
that Xcode itself emits, so the injected file is byte-compatible with its en/es siblings.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import plistlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import macho

INFOPLIST_ZH = {
    "CFBundleDisplayName": "Eagle中文",
    "NSMicrophoneUsageDescription": "Eagle 会采集一段四秒的音频样本，在本地生成视觉作品，随后删除该录音。",
}


def esc(s: str) -> str:
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
        .replace("\r", "\\r")
    )


def write_text_strings(path: str, table: dict[str, str], header: str) -> None:
    lines = [f"/* {header} */", f"/* {len(table)} strings */", ""]
    for k in sorted(table, key=lambda s: s.casefold()):
        lines.append(f'"{esc(k)}" = "{esc(table[k])}";')
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", required=True)
    ap.add_argument("--seeded", help="optional extra table used only to fill keys no translated dir defines")
    ap.add_argument("--translated-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--staging-dir", required=True, help="where to write the binary-plist copy the packager injects")
    args = ap.parse_args()

    master = json.load(open(args.master, encoding="utf-8"))["rows"]
    order = [r["key"] for r in master]
    seeded = json.load(open(args.seeded, encoding="utf-8")) if args.seeded else {}

    table: dict[str, str] = {}
    for f in sorted(glob.glob(os.path.join(args.translated_dir, "*.json"))):
        data = json.load(open(f, encoding="utf-8"))
        if not isinstance(data, dict):
            raise SystemExit(f"{f}: expected a flat JSON object")
        for k, v in data.items():
            if k in table and table[k] != v:
                print(f"  conflict resolved by later file: {k[:50]!r}")
            table[k] = v

    # Seeded Lara wording only fills gaps the translators left; a fresh translation wins,
    # because it was produced with this batch's context in hand.
    filled = 0
    for k in order:
        if k not in table and k in seeded:
            table[k] = seeded[k]
            filled += 1

    zh_dir = os.path.join(args.out_dir, "zh-Hans.lproj")
    os.makedirs(zh_dir, exist_ok=True)

    keep = {k: v for k, v in table.items() if k in set(order)}
    write_text_strings(os.path.join(zh_dir, "Localizable.strings"), keep, "Eagle — 简体中文")
    write_text_strings(os.path.join(zh_dir, "InfoPlist.strings"), INFOPLIST_ZH, "Eagle — 简体中文")

    # binary-plist staging copy used by the packager
    bin_dir = os.path.join(args.staging_dir, "zh-Hans.lproj")
    os.makedirs(bin_dir, exist_ok=True)
    macho.write_strings(os.path.join(bin_dir, "Localizable.strings"), keep, binary=True)
    macho.write_strings(os.path.join(bin_dir, "InfoPlist.strings"), INFOPLIST_ZH, binary=True)

    missing = [k for k in order if k not in keep]
    print(f"translated rows ... {len(keep)}")
    print(f"seeded fillings ... {filled}")
    print(f"missing after merge {len(missing)}")
    for k in missing[:10]:
        print("   -", k[:80])
    print(f"-> {zh_dir}")
    print(f"-> {bin_dir}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
