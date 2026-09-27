"""Inject the Chinese .strings into Eagle's IPA and repackage it, unsigned.

Adding files to a signed bundle invalidates _CodeSignature/CodeResources, so the bundle is
emitted without a signature -- the same shape the published Lara中文 build ships in, and
what sideloading tools (TrollStore, Sideloadly, ESign, AltStore) expect to re-sign anyway.
Eagle's own build script ends in an ad-hoc signature for exactly this reason.

Everything else is copied through verbatim, including each entry's external attributes:
dropping the executable bit on the main binary or a dylib makes the app unlaunchable.
"""

from __future__ import annotations

import argparse
import os
import zipfile

EXECUTABLE_NAME_DEFAULT = "Eagle"


def mode_of(info: zipfile.ZipInfo) -> int:
    return (info.external_attr >> 16) & 0o7777


def needs_exec_bit(name: str, app_dir: str, exe_name: str) -> bool:
    """Only the entry points we can identify with certainty; every other mode is copied
    through from the source IPA, which already carries the correct permissions."""
    return name == app_dir + exe_name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ipa", required=True)
    ap.add_argument("--staging-lproj", required=True, help="dir containing zh-Hans.lproj/*.strings")
    ap.add_argument("--out", required=True)
    ap.add_argument("--exe", default=EXECUTABLE_NAME_DEFAULT)
    args = ap.parse_args()

    lproj_files = sorted(os.listdir(args.staging_lproj))
    if not lproj_files:
        raise SystemExit(f"nothing staged in {args.staging_lproj}")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    tmp = args.out + ".part"

    with zipfile.ZipFile(args.ipa) as src:
        names = src.namelist()
        apps = {n.split("/")[1] for n in names if n.startswith("Payload/") and len(n.split("/")) > 2}
        if apps != {"Eagle.app"}:
            raise SystemExit(f"unexpected Payload layout: {sorted(apps)}")
        app_dir = "Payload/Eagle.app/"

        injected = [f"zh-Hans.lproj/{f}" for f in lproj_files]
        inject_set = {app_dir + p for p in injected}
        clash = inject_set & set(names)
        if clash:
            raise SystemExit(f"refusing to overwrite existing entries: {sorted(clash)}")

        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as dst:
            stripped = 0
            for info in src.infolist():
                if info.filename.startswith(app_dir + "_CodeSignature/"):
                    stripped += 1
                    continue
                if info.is_dir():
                    out = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                    out.external_attr = (0o40755 << 16) | 0x10
                    out.create_system = 3
                    dst.writestr(out, b"")
                    continue
                data = src.read(info.filename)
                out = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                out.compress_type = zipfile.ZIP_DEFLATED
                out.create_system = 3
                mode = mode_of(info) or 0o644
                if needs_exec_bit(info.filename, app_dir, args.exe):
                    mode |= 0o755
                out.external_attr = (mode & 0o7777) << 16
                dst.writestr(out, data)

            for rel, fname in zip(injected, lproj_files):
                path = app_dir + rel
                data = open(os.path.join(args.staging_lproj, fname), "rb").read()
                out = zipfile.ZipInfo(path, date_time=(2026, 9, 27, 12, 0, 0))
                out.compress_type = zipfile.ZIP_DEFLATED
                out.create_system = 3
                out.external_attr = (0o644 & 0o7777) << 16
                dst.writestr(out, data)

    os.replace(tmp, args.out)

    with zipfile.ZipFile(args.out) as chk:
        bad = chk.testzip()
        got = set(chk.namelist())
        assert bad is None, f"corrupt entry: {bad}"
        assert "Payload/" in got or any(n.startswith("Payload/Eagle.app/") for n in got)
        assert not [n for n in got if "_CodeSignature" in n], "signature not stripped"
        for p in injected:
            assert app_dir + p in got, f"missing {p}"
        exe_mode = mode_of(chk.getinfo(app_dir + args.exe))

    size = os.path.getsize(args.out)
    print(f"entries ......... {len(got)}")
    print(f"stripped ....... {stripped} signature entries")
    print(f"injected ....... {', '.join(injected)}")
    print(f"{args.exe} mode ... 0o{exe_mode:o}")
    print(f"size ........... {size/1024/1024:.1f} MiB")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
