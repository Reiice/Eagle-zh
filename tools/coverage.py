"""Classify each key by whether Localizable.strings can actually reach it at runtime.

Eagle has three parallel text mechanisms and only one of them reads the device table:

  * SwiftUI `Text("literal")` / `.navigationTitle("literal")` / `.alert("literal")` -- the
    argument is a LocalizedStringKey, resolved by Bundle.main against the device's
    preferred localizations. A zh-Hans.lproj table DOES answer these.

  * `LaraL10n.text(en: "...", es: "...")` -- a plain Swift function that picks one of two
    hardcoded arguments based on UserDefaults["lara.interfaceLanguage"] (see
    lara/config/LaraLanguage.swift). It returns a String, so SwiftUI renders it verbatim.

  * `LaraL10n.localized("...")` -- reads a .strings table, but opens
    `Bundle(path: <in-app language>.lproj)` where the in-app language is only ever "en" or
    "es". A Chinese device therefore still gets English out of it.

Anything nested inside the latter two is unreachable by injection, so an occurrence counts
only when its innermost enclosing call is an API known to take a LocalizedStringKey.
"""

from __future__ import annotations

import argparse
import json
import os
import re

# Calls whose string argument becomes a plain String -- device localization never sees it.
OPAQUE_CALLS = ["LaraL10n.text(", "LaraL10n.localized("]

# APIs that accept LocalizedStringKey and therefore consult the device's .lproj table.
LOCALIZED_APIS = {
    "Text", "Label", "Button", "Toggle", "Picker", "Menu", "Section",
    "NavigationTitle", "NavigationLink", "TextField", "SecureField",
    "LabeledContent", "Help", "GroupBox", "Link", "PlainAlert", "Alert",
    "ConfirmationDialog", "ErrorText",
}
# Modifier forms, matched case-insensitively on the selector name.
LOCALIZED_MODIFIERS = {
    "navigationtitle", "alert", "confirmationdialog", "help", "accessibilitylabel",
    "accessibilityvalue", "accessibilityhint", "pickerstyle", "sheet", "popover",
}


def opaque_ranges(text: str) -> list[tuple[int, int]]:
    """Character spans covered by a LaraL10n.text/localized(...) call, paren-balanced."""
    spans = []
    for marker in OPAQUE_CALLS:
        i = 0
        while True:
            j = text.find(marker, i)
            if j < 0:
                break
            depth = 0
            k = j + len(marker) - 1
            while k < len(text):
                c = text[k]
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            spans.append((j, min(k, len(text) - 1)))
            i = j + len(marker)
    return spans


# walk back from the literal to the innermost `identifier(`
ENCLOSING_RE = re.compile(r"([A-Za-z_]\w*)\s*\([^()]*$")


def enclosing_call(text: str, off: int) -> str | None:
    m = ENCLOSING_RE.search(text, 0, off)
    return m.group(1) if m else None


def literal_spans(text: str, lit: str) -> list[int]:
    """Offsets where `lit` appears as a quoted Swift literal."""
    needle = '"' + lit.replace("\\", "\\\\").replace('"', '\\"') + '"'
    out, i = [], text.find(needle)
    while i >= 0:
        out.append(i)
        i = text.find(needle, i + 1)
    return out


def is_localized_api(name: str) -> bool:
    if name in LOCALIZED_APIS:
        return True
    return name.lower() in LOCALIZED_MODIFIERS


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--master", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = json.load(open(args.master, encoding="utf-8"))["rows"]
    files = []
    for root, _d, fs in os.walk(os.path.join(args.repo, "lara")):
        for f in fs:
            if f.endswith(".swift"):
                p = os.path.join(root, f)
                try:
                    files.append((p, open(p, encoding="utf-8").read()))
                except UnicodeDecodeError:
                    pass

    cache = {p: opaque_ranges(t) for p, t in files}

    reachable, opaque_only, no_site, unknown = [], [], [], []
    for row in rows:
        key = row["key"]
        if re.search(r"%\w", key):
            unknown.append(key)  # synthesized interpolation keys are not verbatim
            continue
        hits = 0
        good = 0
        for p, t in files:
            for off in literal_spans(t, key):
                hits += 1
                if any(a <= off <= b for a, b in cache[p]):
                    continue
                if is_localized_api(enclosing_call(t, off) or ""):
                    good += 1
        if hits == 0:
            no_site.append(key)
        elif good:
            reachable.append(key)
        else:
            opaque_only.append(key)

    json.dump(
        {
            "counts": {
                "reachable_via_strings": len(reachable),
                "opaque_only": len(opaque_only),
                "no_source_site": len(no_site),
                "interpolation_candidates": len(unknown),
            },
            "reachable_via_strings": reachable,
            "opaque_only": opaque_only,
            "no_source_site": no_site,
            "interpolation_candidates": unknown,
        },
        open(args.out, "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )
    print(f"reachable through the device table ..... {len(reachable)}")
    print(f"only inside LaraL10n.text/localized .. {len(opaque_only)}")
    print(f"no verbatim source occurrence ........ {len(no_site)}")
    print(f"interpolation candidates (unmatched) . {len(unknown)}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

