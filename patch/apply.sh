#!/bin/sh
# Prepare an Eagle source checkout for a full Simplified Chinese build.
#
#   sh patch/apply.sh <Eagle-source-checkout>
#
# After this, build on macOS:  sh ipabuild.sh   (needs Xcode; Eagle ad-hoc signs the result,
# and sideloading tools re-sign it anyway).
set -eu
SRC="${1:?usage: sh patch/apply.sh <path-to-Eagle-checkout>}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"

[ -d "$SRC/lara" ] || { echo "$SRC is not an Eagle checkout (no lara/ directory)" >&2; exit 1; }

git -C "$SRC" apply --check -p1 "$HERE/patch/eagle-zh-source.patch"

cp -r "$HERE/l10n/zh-Hans.lproj" "$SRC/lara/zh-Hans.lproj"
git -C "$SRC" apply -p1 "$HERE/patch/eagle-zh-source.patch"

echo "patched $SRC"
echo "  lara/zh-Hans.lproj/Localizable.strings  ($(grep -c ';$' "$SRC/lara/zh-Hans.lproj/Localizable.strings") entries)"
echo "  lara/config/LaraLanguage.swift          (text()/localized() now read the device table)"
echo "  lara/views/new/LaraHomeView.swift       (Home gains the 3 App Bypass entry Eagle dropped)"
echo "  lara.xcodeproj/project.pbxproj          (knownRegions += zh-Hans)"
echo
echo "The xcodeproj uses a PBXFileSystemSynchronizedRootGroup, so the new .lproj folder is"
echo "picked up by the build without any further project edits."
