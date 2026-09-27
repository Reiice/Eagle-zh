"""Generate the upstream source patch that turns Eagle into a trilingual app.

Two things had to change in Eagle's own code, and neither is reachable from resources:

1. There is no third language. `LaraLanguage` only knows english/spanish, so 简体中文 has to
   become a real menu option -- the pickers already iterate `LaraLanguage.allCases`, so adding
   a case is enough. The lookup must load zh-Hans.lproj BY PATH rather than trusting the
   device language, otherwise choosing Chinese on an English device does nothing and choosing
   English on a Chinese device leaks Chinese.

2. `LaraL10n.text(en: "Found \\(n) paths", ...)` interpolates before the call, so the function
   receives "Found 5 paths" and no static key can ever match it. `L10nText` captures the
   template and the values separately; every interpolation becomes `%@` holding a
   pre-rendered string, which keeps English and Spanish output identical to what Swift
   produced before this type existed, and lets a translation reorder placeholders.

   Call sites that pass String *variables* (not literals) do not convert implicitly, so they
   are wrapped explicitly; the generator asserts none were missed.

A third hunk restores behaviour rather than translating it: Eagle 1.0.5 kept its 3-app-limit
bypass page but deleted the only view that presented it, so Home grows the entry back.

The diff is generated against the checked-out source rather than hand-written, so a moved
anchor fails loudly instead of producing a silently mis-patched build.
"""

from __future__ import annotations

import argparse
import difflib
import os
import re

LARA_LANGUAGE = "lara/config/LaraLanguage.swift"
HOME_VIEW = "lara/views/new/LaraHomeView.swift"
PBXPROJ = "lara.xcodeproj/project.pbxproj"

# ---------------------------------------------------------------- LaraLanguage.swift

OLD_CASES = """    case english = "en"
    case spanish = "es"
"""
NEW_CASES = """    case english = "en"
    case spanish = "es"
    case simplifiedChinese = "zh-Hans"
"""

OLD_DISPLAY = """        case .english: return "English"
        case .spanish: return "Español"
"""
NEW_DISPLAY = """        case .english: return "English"
        case .spanish: return "Español"
        case .simplifiedChinese: return "简体中文"
"""

OLD_SHORT = """        case .english: return "EN"
        case .spanish: return "ES"
"""
NEW_SHORT = """        case .english: return "EN"
        case .spanish: return "ES"
        case .simplifiedChinese: return "中文"
"""

OLD_L10N = """nonisolated enum LaraL10n {
    static var language: LaraLanguage {
        guard
            let rawValue = UserDefaults.standard.string(forKey: LaraLanguage.storageKey),
            let language = LaraLanguage(rawValue: rawValue)
        else {
            return .english
        }
        return language
    }

    static func text(en: String, es: String) -> String {
        language == .spanish ? es : en
    }

    static func localized(_ key: String) -> String {
        if language == .spanish {
            return key
        }
        guard
            let path = Bundle.main.path(forResource: language.rawValue, ofType: "lproj"),
            let bundle = Bundle(path: path)
        else {
            return key
        }
        return bundle.localizedString(forKey: key, value: key, table: nil)
    }
}
"""

NEW_L10N = """/// A text template plus the values interpolated into it.
///
/// Capturing the template is what makes `LaraL10n.text(en: "Found \\\\(n) paths", ...)`
/// localizable: as a plain String the number is already baked in, so no static table key could
/// ever match. Each interpolation becomes `%@` carrying a pre-rendered string, which keeps the
/// English and Spanish result identical to Swift's own interpolation.
nonisolated struct L10nText: ExpressibleByStringLiteral, ExpressibleByStringInterpolation {
    typealias StringInterpolation = Interpolation

    let template: String
    let values: [String]

    init(stringLiteral value: String) {
        template = value
        values = []
    }

    init(_ value: String) {
        template = value
        values = []
    }

    init(stringInterpolation: Interpolation) {
        template = stringInterpolation.template
        values = stringInterpolation.values
    }

    var string: String { render(template) }

    /// Substitutes the captured values positionally, so a translation may reorder `%@`.
    func render(_ template: String) -> String {
        guard !values.isEmpty else { return template }
        var out = ""
        var rest = template
        var index = 0
        while let range = rest.range(of: "%@") {
            out += rest[..<range.lowerBound]
            out += index < values.count ? values[index] : ""
            index += 1
            rest = String(rest[range.upperBound...])
        }
        return out + rest
    }

    struct Interpolation: StringInterpolationProtocol {
        var template = ""
        var values: [String] = []

        init(literalCapacity: Int, interpolationCount: Int) {
            template.reserveCapacity(literalCapacity)
            values.reserveCapacity(interpolationCount)
        }

        mutating func appendLiteral(_ literal: String) {
            template += literal
        }

        mutating func appendInterpolation(_ value: Any?) {
            template += "%@"
            values.append((value as? String) ?? String(describing: value))
        }
    }
}

nonisolated enum LaraL10n {
    static var language: LaraLanguage {
        guard
            let rawValue = UserDefaults.standard.string(forKey: LaraLanguage.storageKey),
            let language = LaraLanguage(rawValue: rawValue)
        else {
            return .english
        }
        return language
    }

    /// Resolved by path, not by device language: choosing 简体中文 has to work on an English
    /// device, and choosing English must not pick up Chinese from a Chinese device.
    private static let chineseBundle: Bundle? = {
        guard let path = Bundle.main.path(forResource: "zh-Hans", ofType: "lproj") else {
            return nil
        }
        return Bundle(path: path)
    }()

    private static let missingMarker = "\\u{0}\\u{0}missing"

    static func text(en: L10nText, es: L10nText) -> String {
        switch language {
        case .english:
            return en.string
        case .spanish:
            return es.string
        case .simplifiedChinese:
            // The table is keyed by whichever source form the developer wrote, so try the
            // English template first and fall back to the Spanish one.
            if let hit = chinese(en.template) { return en.render(hit) }
            if let hit = chinese(es.template) { return es.render(hit) }
            return en.string
        }
    }

    static func localized(_ key: String) -> String {
        switch language {
        case .spanish:
            return key
        case .simplifiedChinese:
            return chinese(key) ?? key
        case .english:
            guard
                let path = Bundle.main.path(forResource: language.rawValue, ofType: "lproj"),
                let bundle = Bundle(path: path)
            else {
                return key
            }
            return bundle.localizedString(forKey: key, value: key, table: nil)
        }
    }

    /// nil when nothing is translated, so callers fall back to the source text instead of
    /// rendering an empty label.
    private static func chinese(_ key: String) -> String? {
        guard let bundle = chineseBundle else { return nil }
        let value = bundle.localizedString(forKey: key, value: missingMarker, table: nil)
        guard value != missingMarker, !value.isEmpty, value != key else { return nil }
        return value
    }
}
"""

# ---------------------------------------------------------------- LaraHomeView.swift

# Eagle 1.0.5 kept `AppsView` (the 3-app-limit bypass: it clears the
# `com.apple.installd.validatedByFreeProfile` xattr off every installed bundle) but deleted the
# only view that ever presented it -- `TweaksView` has no instantiation point left in the tree,
# so the feature has no UI. Re-exposed on Home, next to the other system-level entry.
#
# Both labels are keys the shipped table already translates, so no new strings are needed.
# `localized(_:)` mirrors what upstream rendered before: en.lproj has 194 entries and neither of
# these is one of them, and es.lproj has a single entry, so English and Spanish show the raw key.
OLD_HOME_ENTRY = """                    if EagleFeaturePolicy.allows(.advancedSystemTools, channel: currentChannel) {
                        laboratoryTools
                    }
"""
NEW_HOME_ENTRY = """                    if EagleFeaturePolicy.allows(.advancedSystemTools, channel: currentChannel) {
                        laboratoryTools
                    }
                    threeAppBypassTool
"""

OLD_HOME_ROW = """    private var laboratoryTools: some View {"""
NEW_HOME_ROW = """    private var threeAppBypassTool: some View {
        NavigationLink(destination: AppsView().environmentObject(mgr)) {
            LaraToolRow(
                title: LaraL10n.localized("3 App Bypass"),
                subtitle: LaraL10n.localized(
                    "Needs to be reapplied everytime you sideload a new app."
                ),
                systemImage: "app.badge",
                accent: .orange
            )
        }
        .disabled(!mgr.sbxready)
        .buttonStyle(.plain)
        .background(Color(uiColor: .secondarySystemGroupedBackground),
                    in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .accessibilityIdentifier("three-app-bypass")
    }

    private var laboratoryTools: some View {"""

OLD_REGIONS = """			knownRegions = (
				en,
				es,
				Base,
			);"""
NEW_REGIONS = """			knownRegions = (
				en,
				es,
				zh-Hans,
				Base,
			);"""

CHUNKS = {
    LARA_LANGUAGE: [(OLD_CASES, NEW_CASES), (OLD_DISPLAY, NEW_DISPLAY),
                    (OLD_SHORT, NEW_SHORT), (OLD_L10N, NEW_L10N)],
    HOME_VIEW: [(OLD_HOME_ENTRY, NEW_HOME_ENTRY), (OLD_HOME_ROW, NEW_HOME_ROW)],
    PBXPROJ: [(OLD_REGIONS, NEW_REGIONS)],
}

# Call sites that hand LaraL10n.text String expressions rather than literals: no implicit
# conversion exists, so they are wrapped explicitly. Multi-line forms are matched too.
# `$0.title` and `profile.green` must be covered -- a first version that only accepted a bare
# identifier missed exactly those and the build failed on them.
_ARG = r"(?!L10nText)(\$?\w+(?:\.\w+)*(?:\([^()]*\))?)"
WRAP_RE = re.compile(r"LaraL10n\.text\(\s*en:\s*" + _ARG + r"\s*,\s*es:\s*" + _ARG + r"\s*\)", re.S)
CALL_RE = re.compile(r"LaraL10n\.text\s*\(")


def argument_at(text: str, start: int) -> str:
    """The expression following `label:` up to the next comma or closing paren at depth 0."""
    depth = 0
    i = start
    while i < len(text):
        c = text[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif c == "," and depth == 0:
            break
        elif c == '"' and (i == 0 or text[i - 1] != "\\"):
            j = i + 1
            while j < len(text):
                if text[j] == '"':
                    break
                j += 2 if text[j] == "\\" else 1
            i = j
        i += 1
    return text[start:i].strip()


def unwrapped_variables(text: str) -> list[str]:
    """`en:` arguments that are not literals and not already wrapped.

    Deliberately an allow-list rather than a deny-list: anything that is not a string literal,
    not a ternary of literals, and not already `L10nText(...)` must be wrapped. The previous
    version recognised only bare identifiers, so `$0.title` slipped through and cost a CI run.
    """
    bad = []
    for m in CALL_RE.finditer(text):
        label = re.compile(r"\ben\s*:\s*").search(text, m.end(), m.end() + 60)
        if not label:
            continue
        arg = argument_at(text, label.end())
        if not arg or arg.startswith("L10nText"):
            continue
        if '"' in arg:
            continue                      # literal, or a ternary whose branches are literals
        bad.append(arg.splitlines()[0][:60])
    return bad


def apply_chunks(name: str, text: str) -> str:
    eol = "\r\n" if "\r\n" in text else "\n"
    for old, new in CHUNKS.get(name, []):
        old = old.replace("\n", eol)
        new = new.replace("\n", eol)
        if old not in text:
            raise SystemExit(f"{name}: anchor not found -- upstream changed, regenerate this patch")
        text = text.replace(old, new, 1)
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    originals: dict[str, str] = {}
    patched: dict[str, str] = {}
    wrapped: list[tuple[str, str]] = []

    # The project file lives beside lara/, not inside it, so os.walk(lara) alone silently
    # dropped the knownRegions hunk and the build then failed the "is zh-Hans declared" check.
    targets = [(os.path.join(args.repo, PBXPROJ), PBXPROJ)]
    for root, _dirs, files in os.walk(os.path.join(args.repo, "lara")):
        for fname in sorted(files):
            if not fname.endswith(".swift"):
                continue
            path = os.path.join(root, fname)
            targets.append((path, os.path.relpath(path, args.repo).replace("\\", "/")))

    for path, rel in targets:
        try:
            text = open(path, encoding="utf-8", newline="").read()
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        before = text
        text = apply_chunks(rel, text)
        if rel.endswith(".swift"):
            def sub(m: re.Match) -> str:
                wrapped.append((rel, f"{m.group(1)}/{m.group(2)}"))
                return f"LaraL10n.text(en: L10nText({m.group(1)}), es: L10nText({m.group(2)}))"
            text = WRAP_RE.sub(sub, text)
        if text != before:
            originals[rel], patched[rel] = before, text

    if PBXPROJ not in patched:
        raise SystemExit(f"{PBXPROJ} was not modified -- the knownRegions hunk would be missing")
    if HOME_VIEW not in patched:
        raise SystemExit(f"{HOME_VIEW} was not modified -- the 3 App Bypass entry would be missing")

    for rel, text in patched.items():
        if not rel.endswith(".swift"):
            continue
        leftovers = unwrapped_variables(text)
        if leftovers:
            raise SystemExit(
                f"{rel}: LaraL10n.text still receives String expressions that will not convert "
                f"to L10nText: {leftovers}; extend WRAP_RE so they are wrapped"
            )

    chunks = []
    for rel in sorted(originals):
        diff = "".join(difflib.unified_diff(
            originals[rel].splitlines(keepends=True),
            patched[rel].splitlines(keepends=True),
            fromfile=f"a/{rel}", tofile=f"b/{rel}",
        ))
        if diff.strip():
            chunks.append(diff)

    body = "\n".join(chunks)
    if not body.strip():
        raise SystemExit("no changes produced")
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(body if body.endswith("\n") else body + "\n")

    print(f"files changed ......... {len(chunks)}")
    print(f"variable call sites wrapped: {len(wrapped)}")
    for f, pair in wrapped:
        print(f"   {f}  ({pair})")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
