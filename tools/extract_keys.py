"""Extract the authoritative set of localization keys for Eagle 1.0.5 (build 92).

Repo HEAD is the exact commit that produced the published IPA ("release: Eagle 1.0.5 build 92"),
so Swift source is the primary universe of keys. Every candidate is additionally confirmed to
exist inside the shipped Mach-O -- as a *substring*, because LLVM shares suffixes between
string literals, so a section-membership test gives false negatives ("Run Exploit" lives only
inside a longer alert message).

Membership is decided by provenance, not by directory. A literal qualifies when it sits at a
call site that resolves through a .strings table at runtime:

  Text("...") / .navigationTitle("...") / .alert("...")   LocalizedStringKey
  LaraL10n.text(en: "...", es: "...")                     after the source patch
  LaraL10n.localized("...")                               after the source patch

That keeps the exploit/kernel console chatter out of the table without hiding real UI copy that
happens to live in lara/classes or lara/config -- the earlier views/-only allow-list did hide
some, which is why the first build looked barely localized.

Interpolated copy is keyed differently per route, matching what each one actually looks up:
  * LocalizedStringKey keeps the compiler's specifier (%d for Int, %@ for String), so several
    spellings are emitted; unused ones are inert.
  * LaraL10n.text goes through L10nText, which records every hole as `%@`, so only the %@
    spelling can ever match.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import macho
import swift_strings

LOCALIZED_CALLS = [
    "Text", "Label", "Button", "Toggle", "Picker", "Menu", "Section",
    "NavigationTitle", "NavigationLink", "TextField", "SecureField",
    "LabeledContent", "Help", "GroupBox", "Link", "PlainAlert", "Alert",
    "ConfirmationDialog",
]
CALL_RE = re.compile(
    r'\b(?:' + "|".join(LOCALIZED_CALLS) + r')\s*\(\s*(?:[a-zA-Z_]\w*\s*:\s*)?"((?:[^"\\]|\\.)*)"'
)
NAMED_ARG_RE = re.compile(
    r'\b(?:title|text|message|subtitle|summary|caption|placeholder|prompt|label|valueLabel|footer)\s*:\s*"((?:[^"\\]|\\.)*)"'
)
LARAL10N_ARGS_RE = re.compile(r'\b(?:en|es)\s*:\s*"((?:[^"\\]|\\.)*)"')
# The english/spanish pair written at one call site. Eagle's developers author both forms, so
# the same sentence usually reaches the table twice under two different keys; without the link
# a translator turns them into two different Chinese sentences.
PAIR_RE = re.compile(
    r'LaraL10n\.text\s*\(\s*en:\s*"((?:[^"\\]|\\.)*)"\s*,\s*es:\s*"((?:[^"\\]|\\.)*)"\s*\)',
    re.S,
)
INTERP_RE = re.compile(r"\\\((.*?)\)")

ES_TOKENS = re.compile(
    r"\b(el|la|los|las|un|una|de|del|y|o|a|en|con|para|por|no|sí|es|su|sus|se|"
    r"como|también|aquí|este|esta|estos|muy|más|puede|tiene|está|son|ser|hacer|"
    r"color|fondo|pantalla|ajuste|cambiar|aplicar|mostrar|ocultar|elegir|guardar|"
    r"nombre|estilo|vista|efecto|valor|forma|área|texto|imagen|icono)\b",
    re.I,
)
ES_ACCENT = re.compile(r"[áéíóúñ¿¡ü]|\b[A-Z][a-z]+[áéíóúñ]")

REJECT_RES = [
    re.compile(r"^[a-z][\w.-]*\.[a-z]{2,}$"),          # sf symbols, prefs keys
    re.compile(r"^[/~.\\]"),
    re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=[^ ]"),
    re.compile(r"^(?:NS|UI|CG|CA|MK|WK|PK|SF|CF|CX|LA|AV|MTK|SK|CN|IN|OSS)[A-Z]"),
    re.compile(r"\.(?:png|jpe?g|car|json|plist|dylib|framework|md|ya?ml|svg|webp|ttf|otf|swift|strings|zip|txt|db|dmp|ipsw|heic|mov|theme)$"),
    re.compile(r"^#[0-9a-fA-F]{3,8}$"),
    re.compile(r"^\d"),
    re.compile(r"^[a-z][a-z0-9]*[A-Z]"),               # camelCase identifier
    re.compile(r"^https?://"),
    re.compile(r"^[A-Za-z0-9+/]{24,}={0,2}$"),         # base64 blob
    re.compile(r"^[a-z0-9_\-]+\.[a-z0-9_\-]+$"),
    re.compile(r"^[\w.\-]+(?:/[\w.\-]+)+$"),
]

# Still rejected even in source mode: these are never human-facing copy under any provenance.
SOFT_REJECT_RES = [
    re.compile(r"^https?://"),
    re.compile(r"^[A-Za-z0-9+/]{24,}={0,2}$"),
    re.compile(r"^[a-z][\w.-]*\.[a-z]{2,}$"),
    re.compile(r"^\."),                                   # ".EAGLE" -- a file-extension label
    re.compile(r"\.(?:png|jpe?g|car|json|plist|dylib|framework|md|ya?ml|svg|webp|ttf|otf|swift|strings|zip|db|dmp|ipsw|heic|mov)$"),
    re.compile(r"^#[0-9a-fA-F]{3,8}$"),
]

# Copy that is really a printf/log template rather than UI text.
# (`x\b` used to live here and matched any word ending in x, e.g. "icons".)
LOGGY = re.compile(r"0x[0-9a-f]|%ll|\berrno\b|\bpanic\b|\bassert\b|->|::")


def is_prose(s: str, strict: bool = True) -> bool:
    if not (3 <= len(s) <= 420) or s.count("\n") > 8 or "\t" in s:
        return False
    # The aggressive rejections exist to keep console/log strings out when a literal is
    # harvested from anywhere. Once membership requires a localized call site, provenance has
    # already done that job, and these patterns were measured to destroy real UI copy
    # ('3 smart crops' -> ^\d, 'UIKit repainted the battery...' -> the framework prefix,
    # 'Complete Eagle setup before applying icons.' -> LOGGY).
    if strict and (any(rx.search(s) for rx in REJECT_RES) or LOGGY.search(s)):
        return False
    if not strict and any(rx.search(s) for rx in SOFT_REJECT_RES):
        return False
    if not re.search(r"[A-Za-z\u00c0-\u024f]", s):
        return False
    words = [w for w in re.split(r"[\s,;:.!?()\[\]]+", s) if re.search(r"[A-Za-z\u00c0-\u024f]{2,}", w)]
    if len(words) >= 2:
        return True
    if len(words) == 1:
        w = words[0]
        if "_" in w or len(w) > 26:
            return False
        if w[0].isupper():
            return True
        # In source mode membership already requires a localized call site, so a lowercase
        # single word there is real copy -- the color swatch labels (blue, rosa, silver) and
        # the A-Z sort option were being dropped by the capitalisation test alone.
        return not strict
    return False


def has_spanish(s: str) -> bool:
    return bool(ES_ACCENT.search(s) or len(ES_TOKENS.findall(s)) >= 2)


def strip_escapes(s: str) -> str:
    return (
        s.replace('\\"', '"')
        .replace("\\\\", "\\")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
    )


def split_interps(literal: str) -> list[str]:
    """The literal segments of a Swift string, with `\\(...)` holes removed.

    Returns [seg0, seg1, ... segN] for N interpolations. A paren-balanced scan is required:
    a non-greedy regex stops at the first `)` and so mangles nested expressions such as
    `\\(min(a, b))` or `\\(value.formatted())` into segments with a stray trailing `)`, which
    then become keys nothing can ever look up.
    """
    segments: list[str] = []
    cur = ""
    i = 0
    while i < len(literal):
        if literal[i] == "\\" and i + 1 < len(literal) and literal[i + 1] == "(":
            depth = 1
            j = i + 2
            while j < len(literal) and depth:
                if literal[j] == "(":
                    depth += 1
                elif literal[j] == ")":
                    depth -= 1
                elif literal[j] == '"':
                    j += 1
                    while j < len(literal) and literal[j] != '"':
                        j += 2 if literal[j] == "\\" else 1
                j += 1
            if depth:                       # unbalanced: treat the rest as literal text
                cur += literal[i:]
                i = len(literal)
                break
            segments.append(cur)
            cur = ""
            i = j
            continue
        cur += literal[i]
        i += 1
    segments.append(cur)
    return segments


def interp_variants(literal: str) -> list[str]:
    """Runtime key spellings a LocalizedStringKey literal resolves to.

    The compiler substitutes a conversion specifier per interpolated type, so %@ (objects and
    strings) and %d (ints) are the realistic pair; %f/%lld/%lu cover the rarer ones and are
    inert when wrong.
    """
    kept = split_interps(literal)
    n = len(kept) - 1
    if n <= 0:
        return []
    out: list[str] = []
    # %@ covers String/objects and %d covers Int, which is every interpolated type Eagle uses in
    # user-facing text; the rarer float/long-long spellings only add inert near-duplicates.
    for specs in (["@"] * n, ["d"] * n):
        key = ""
        for i in range(n + 1):
            key += kept[i]
            if i < n:
                key += "%" + specs[i]
        key = strip_escapes(key)
        if key not in out:
            out.append(key)
    return out


def laral10n_template(literal: str) -> str | None:
    """The key L10nText builds for an interpolated `en:`/`es:` literal: every hole is `%@`."""
    kept = split_interps(literal)
    n = len(kept) - 1
    if n <= 0:
        return None
    out = ""
    for i in range(n + 1):
        out += kept[i]
        if i < n:
            out += "%@"
    return strip_escapes(out)


CALL_NAMES = set(LOCALIZED_CALLS)
LABEL_NAMES = {"title", "text", "message", "subtitle", "summary", "caption",
               "placeholder", "prompt", "label", "valueLabel", "footer"}
MODIFIER_NAMES = {"navigationTitle", "alert", "confirmationDialog", "help",
                  "accessibilityLabel", "accessibilityValue", "accessibilityHint"}
LARA_LABELS = {"en", "es"}


def classify_before(text: str, q: int) -> str | None:
    """Which localization route a literal at quote index `q` belongs to.

    'lara' -- an `en:`/`es:` argument, or `LaraL10n.localized(...)`; the key is the source
    string itself and L10nText renders every hole as `%@`.
    'key'  -- a LocalizedStringKey argument; the compiler picks the specifier per type.
    """
    i = q - 1
    while i >= 0 and text[i].isspace():
        i -= 1
    if i < 0:
        return None
    if text[i] == "(":
        j = i
        while j > 0 and (text[j - 1].isalnum() or text[j - 1] == "_"):
            j -= 1
        name = text[j:i]
        if name in CALL_NAMES or name in MODIFIER_NAMES:
            return "key"
        if name == "localized" and text[max(0, j - 9):j].endswith("LaraL10n."):
            return "lara"
        return None
    if text[i] == ":":
        j = i
        while j > 0 and (text[j - 1].isalnum() or text[j - 1] == "_"):
            j -= 1
        name = text[j:i]
        if name in LARA_LABELS:
            return "lara"
        if name in LABEL_NAMES:
            return "key"
    return None


def all_literals(text: str):
    """Yield (inner_source, quote_index) for every top-level Swift string literal."""
    i = 0
    n = len(text)
    while i < n:
        if text[i] == "#":                       # raw strings: skip the whole line for safety
            i += 1
            continue
        if text[i] != '"':
            i += 1
            continue
        got = swift_strings.read_string(text, i)
        if got is None:
            break
        inner, nxt = got
        yield inner, i
        i = max(nxt, i + 1)


def scan(repo_dir: str):
    """Collect literals by provenance across the whole target, plus exact en/es pairs."""
    callsite: dict[str, str] = {}
    larasite: dict[str, str] = {}
    interp_key: dict[str, str] = {}
    interp_lara: dict[str, str] = {}
    pairs: list[tuple[str, str]] = []

    for root, _d, files in os.walk(os.path.join(repo_dir, "lara")):
        for name in sorted(files):
            if not name.endswith(".swift"):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, repo_dir).replace("\\", "/")
            try:
                text = open(path, encoding="utf-8").read()
            except UnicodeDecodeError:
                continue
            pending_en: str | None = None
            for inner, q in all_literals(text):
                route = classify_before(text, q)
                if route is None:
                    continue
                label = _label_of(text, q)
                if label == "en" and "\\(" not in inner:
                    pending_en = inner
                elif label == "es" and pending_en is not None and "\\(" not in inner:
                    pairs.append((strip_escapes(pending_en), strip_escapes(inner)))
                    pending_en = None
                if "\\(" in inner:
                    (interp_lara if route == "lara" else interp_key).setdefault(inner, rel)
                else:
                    (larasite if route == "lara" else callsite).setdefault(strip_escapes(inner), rel)
    return callsite, larasite, interp_key, interp_lara, pairs


def _label_of(text: str, q: int) -> str | None:
    i = q - 1
    while i >= 0 and text[i].isspace():
        i -= 1
    if i < 0 or text[i] != ":":
        return None
    j = i
    while j > 0 and (text[j - 1].isalnum() or text[j - 1] == "_"):
        j -= 1
    return text[j:i]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--binary", required=True)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument(
        "--from-source",
        action="store_true",
        help="build for the CI source route: do not require the literal to appear in the "
             "shipped IPA. The published build 92 binary PREDATES the release commit, so "
             "~20%% of HEAD's UI strings are legitimately absent from it -- keeping the gate "
             "on would drop copy the freshly compiled app does show.",
    )
    args = ap.parse_args()

    catalog = macho.read_strings(args.catalog)
    blob = open(args.binary, "rb").read()
    strict = not args.from_source

    def in_binary(s: str) -> bool:
        return strict is False or s.encode("utf-8") in blob

    callsite, larasite, interp_key, interp_lara, pairs = scan(args.repo)

    tiers: dict[str, dict[str, str]] = {"A": {}, "B": {}, "C": {}, "I": {}}
    tiers["A"] = {k: "en.lproj catalog" for k in catalog}

    for lit, rel in callsite.items():
        if lit not in catalog and is_prose(lit, strict) and in_binary(lit):
            tiers["B"][lit] = rel

    covered = set(catalog) | set(tiers["B"])
    for lit, rel in larasite.items():
        if lit in covered or not is_prose(lit, strict) or not in_binary(lit):
            continue
        tiers["C"][lit] = rel

    for lit, rel in interp_lara.items():
        # L10nText records every hole as %@, so a %d spelling of these could never be looked up.
        skeleton = re.sub(r"\\\([^)]*\)", "aa", lit)
        if not is_prose(skeleton, strict):
            continue
        tmpl = laral10n_template(lit)
        if not tmpl or tmpl in catalog:
            continue
        head = tmpl.split("%", 1)[0].strip()[:20]
        if head and not in_binary(head):
            continue
        tiers["I"][tmpl] = lit

    for lit, rel in interp_key.items():
        # A LocalizedStringKey keeps the compiler's own specifier, so %@ and %d are both live.
        skeleton = re.sub(r"\\\([^)]*\)", "aa", lit)
        if not is_prose(skeleton, strict):
            continue
        for cand in interp_variants(lit):
            if cand in catalog:
                continue
            head = cand.split("%", 1)[0].strip()[:20]
            if head and not in_binary(head):
                continue
            tiers["I"][cand] = lit

    unique_pairs = sorted(set(pairs))
    report = {
        "counts": {t: len(v) for t, v in tiers.items()},
        "catalog": catalog,
        "pairs": [[e, s] for e, s in unique_pairs],
        "keys": {t: dict(sorted(v.items())) for t, v in tiers.items()},
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)

    allkeys = set().union(*[set(v) for v in tiers.values()])
    for t in ("A", "B", "C", "I"):
        print(f"tier {t}: {len(tiers[t])}")
    print(f"unique keys: {len(allkeys)}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
