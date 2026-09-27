"""Minimal Mach-O reader: enough to pull __TEXT.__cstring out of an arm64 binary,
plus Apple .strings (plist) helpers. No third-party dependencies.
"""

from __future__ import annotations

import plistlib
import struct

MH_MAGIC_64 = 0xFEEDFACF
FAT_MAGIC = 0xCAFEBABE
FAT_MAGIC_LE = 0xBEBAFECA
LC_SEGMENT_64 = 0x19


def _slices(data: bytes) -> list[tuple[int, int]]:
    magic = struct.unpack_from("<I", data, 0)[0]
    if magic in (FAT_MAGIC, FAT_MAGIC_LE):
        n = struct.unpack_from("!I", data, 4)[0]
        out = []
        for i in range(n):
            off, size = struct.unpack_from("!II", data, 8 + i * 20)[0:2]
            # fat_arch: cputype, cpusubtype, offset, size, align
            ct, _cst, off, size, _al = struct.unpack_from("!iiIII", data, 8 + i * 20)
            if ct == 0x0100000C:  # CPU_ARCH_ABI64 arm64
                out.append((off, size))
        if out:
            return out
        return [(struct.unpack_from("!II", data, 8)[0], struct.unpack_from("!II", data, 8)[1])]
    return [(0, len(data))]


def cstrings(path: str, sections: tuple[str, ...] = ("__cstring", "__objc_methname")) -> set[str]:
    with open(path, "rb") as fh:
        data = fh.read()
    out: set[str] = set()
    for base, _size in _slices(data):
        magic = struct.unpack_from("<I", data, base)[0]
        if magic != MH_MAGIC_64:
            continue
        ncmds = struct.unpack_from("<I", data, base + 16)[0]
        p = base + 32
        for _ in range(ncmds):
            cmd, cmdsize = struct.unpack_from("<II", data, p)
            if cmd == LC_SEGMENT_64:
                segname = data[p + 8 : p + 24].rstrip(b"\0").decode()
                nsect = struct.unpack_from("<I", data, p + 64)[0]
                sp = p + 72
                for _s in range(nsect):
                    sectname = data[sp : sp + 16].rstrip(b"\0").decode()
                    _sn2 = data[sp + 16 : sp + 32].rstrip(b"\0").decode()
                    addr, size = struct.unpack_from("<QQ", data, sp + 32)
                    offset = struct.unpack_from("<I", data, sp + 48)[0]
                    if sectname in sections and segname == "__TEXT":
                        raw = data[base + offset : base + offset + size]
                        for chunk in raw.split(b"\0"):
                            if len(chunk) < 3:
                                continue
                            try:
                                out.add(chunk.decode("utf-8"))
                            except UnicodeDecodeError:
                                pass
                    sp += 80
            p += cmdsize
    return out


def read_strings(path: str) -> dict[str, str]:
    """Read a .strings file in either binary-plist or UTF-8 text plist form."""
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith(b"bplist00"):
        return plistlib.loads(raw)
    text = raw.decode("utf-8-sig", errors="replace")
    entries: dict[str, str] = {}
    pair = re_compile_pair()
    for m in pair.finditer(text):
        entries[_unquote(m.group(1))] = _unquote(m.group(2))
    return entries


def re_compile_pair():
    import re

    return re.compile(r'"((?:[^"\\]|\\.)*)"\s*=\s*"((?:[^"\\]|\\.)*)"\s*;')


def _unquote(s: str) -> str:
    return (
        s.replace('\\"', '"')
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\\\", "\\")
        .replace("\\u{", "\\u")
    )


def write_strings(path: str, table: dict[str, str], binary: bool = True) -> None:
    data = plistlib.dumps(table, fmt=plistlib.FMT_BINARY if binary else plistlib.FMT_XML)
    with open(path, "wb") as fh:
        fh.write(data)
