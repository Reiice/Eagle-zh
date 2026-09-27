"""Prove the Chinese build differs from the upstream IPA only where it should.

Compares every entry against the source IPA: identical bytes, identical permissions,
identical layout -- plus exactly the injected zh-Hans.lproj files and the removed
_CodeSignature. Anything else moving is a packaging bug.
"""

from __future__ import annotations

import argparse
import hashlib
import plistlib
import zipfile

EXPECTED_ADDED = {
    "Payload/Eagle.app/zh-Hans.lproj/Localizable.strings",
    "Payload/Eagle.app/zh-Hans.lproj/InfoPlist.strings",
}


def crc(z: zipfile.ZipFile, name: str) -> tuple[str, int, int]:
    info = z.getinfo(name)
    return hashlib.sha256(z.read(name)).hexdigest()[:16], (info.external_attr >> 16) & 0o7777, info.compress_type


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="upstream Eagle IPA")
    ap.add_argument("--zh", required=True, help="produced Chinese IPA")
    args = ap.parse_args()

    with zipfile.ZipFile(args.base) as base, zipfile.ZipFile(args.zh) as zh:
        b, z = set(base.namelist()), set(zh.namelist())
        added = z - b
        removed = b - z
        shared = sorted(b & z)

        sig_left = [n for n in z if "_CodeSignature" in n]
        bad_bytes, bad_mode = [], []
        for n in shared:
            hb, mb, _cb = crc(base, n)
            hz, mz, _cz = crc(zh, n)
            if hb != hz:
                bad_bytes.append(n)
            if mb != mz:
                bad_mode.append((n, oct(mb), oct(mz)))

        exe = zh.getinfo("Payload/Eagle.app/Eagle")
        table = plistlib.loads(zh.read("Payload/Eagle.app/zh-Hans.lproj/Localizable.strings"))
        info = plistlib.loads(zh.read("Payload/Eagle.app/zh-Hans.lproj/InfoPlist.strings"))
        entries = len(z)
        total = sum(i.file_size for i in zh.infolist())

    problems = []
    if not added <= EXPECTED_ADDED:
        problems.append(f"unexpected additions: {sorted(added - EXPECTED_ADDED)}")
    if removed - {n for n in removed if "_CodeSignature" in n}:
        problems.append(f"unexpected removals: {sorted(removed - {n for n in removed if '_CodeSignature' in n})}")
    if sig_left:
        problems.append(f"signature survived: {sig_left}")
    if bad_bytes:
        problems.append(f"content changed: {bad_bytes}")
    if bad_mode:
        problems.append(f"permissions changed: {bad_mode}")
    if not any(n == "Payload/Eagle.app/" or n.startswith("Payload/Eagle.app/") for n in z):
        problems.append("Payload/Eagle.app layout lost")
    if (exe.external_attr >> 16) & 0o111 == 0:
        problems.append("main binary is not executable")

    print(f"entries ............. base {len(b)} -> zh {entries}")
    print(f"added ............... {sorted(added)}")
    print(f"removed ............. {sorted(removed)}")
    print(f"changed content ..... {len(bad_bytes)}")
    print(f"changed permissions.. {len(bad_mode)}")
    print(f"uncompressed ........ {total/1024/1024:.1f} MiB")
    print(f"zh strings .......... {len(table)} keys, {len(info)} InfoPlist keys")
    print(f"Eagle binary ........ 0o{(exe.external_attr >> 16) & 0o7777:o}")
    if problems:
        print("\nPROBLEMS:")
        for p in problems:
            print("  -", p)
        return 1
    print("\nVERDICT: PASS -- only zh-Hans.lproj added, only _CodeSignature removed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
