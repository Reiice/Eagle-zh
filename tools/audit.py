"""Validate the Chinese string table against the extracted key universe.

Every check here is mechanical on purpose: translation quality needs a human, but
placeholder corruption, dropped keys and leftover source text do not.
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

SPEC_RE = re.compile(r"%(?:\d+\$)?(?:ll|l|z|q)?(?:\.\d+)?[@difuoxXeEgGsc]")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
LATIN_RUN = re.compile(r"[A-Za-z\u00c0-\u024f]{2,}(?:[\s,]+[A-Za-z\u00c0-\u024f]{2,}){2,}")
# Never flag copy that legitimately stays in Latin script: URLs, paths, `code`, filenames.
SPAN_RE = re.compile(
    r"https?://\S+|[\w.\-]+\.(?:com|net|org|gg|io|dev)\b|[A-Za-z0-9_./-]+\.(?:png|jpg|jpeg|"
    r"json|plist|dylib|ipa|strings|car|md|txt|zip|ipsw|framework)|`[^`]*`|/[\w./-]+|\bcom\.\w+(\.\w+)+\b"
)
BRAND_WORDS = {
    "eagle", "aura", "wallet", "ios", "macos", "iphone", "ipad", "springboard",
    "remotecall", "kernelcache", "krw", "vfs", "pac", "dylib", "sha", "bundle",
    "id", "url", "api", "json", "ipa", "safari", "github", "discord", "trollstore",
    "sidestore", "livecontainer", "composer", "moment", "resonance", "styles",
    "studio", "guardian", "poster", "pocket", "match", "scene", "scenes", "dock",
    "leonardo", "ota", "uttype", "http", "https", "com", "app", "apps", "debug",
    "file", "files", "the", "and", "or", "of", "to", "in", "is", "it", "for",
    "mobilegestalt", "aslr", "intelligence", "metal", "glyph", "hud",
    "not", "on", "no", "yes", "a", "an", "b", "c", "x", "v", "ii", "iii",
    "capsule", "capsules", "smart", "focus", "voiceprint", "tapprint", "depth",
    "nugget", "wallpapers", "rainbow", "xcode", "uikit", "launchd", "cowabunga",
    # Device model strings and third-party credit handles: legitimately Latin, and listing
    # them keeps `no_cjk` down to real holes instead of a wall of expected noise.
    "pro", "max", "plus", "air", "mini", "gen", "inch", "cellular", "wifi",
    "yupa", "dirtyzerottcf", "ttc", "psd", "rgb", "hud", "metal",
    "pid", "uid", "gid", "edr", "jit", "gestalt", "db", "state", "application",
    "familycircled", "scream", "repo", "repos", "ros",
}


# Halfwidth punctuation sitting directly against Chinese text should be fullwidth.
HALF_PUNCT = re.compile(r"[\u4e00-\u9fff][,;?!:]|[,;?!:（] |[\u4e00-\u9fff][()]|(?<![A-Za-z0-9])[()](?=[\u4e00-\u9fff])")

# Mandated renderings from l10n/GLOSSARY.md. A key that mentions the source term must
# carry one of the accepted Chinese forms -- this is what catches a batch that went
# off on its own (terminación -> 末位数字 vs 尾号) instead of trusting a self-report.
TERM_RULES = [
    (re.compile(r"[Kk]ernelcache"), ["内核缓存"], "Kernelcache"),
    # 注销设备 is the project term; plain 注销 is accepted too because Lara's published build
    # writes 「注销后不锁屏」 and forcing the long form made translators deviate from the
    # reference wording for no reader benefit.
    (re.compile(r"\bRespring\b"), ["注销设备", "注销"], "Respring"),
    (re.compile(r"reiniciar la interfaz|restart the interface", re.I), ["重启界面", "注销设备"], "restart UI"),
    (re.compile(r"[Dd]ynamic [Ii]sland|\bIsland\b|isla "), ["灵动岛"], "Dynamic Island"),
    (re.compile(r"\bDock\b|dock"), ["Dock"], "Dock stays Latin"),
    (re.compile(r"[Oo]ffsets"), ["偏移"], "Offsets"),
    (re.compile(r"\bExploit\b|exploit"), ["漏洞利用"], "Exploit"),
    (re.compile(r"[Ss]andbox|caja de arena"), ["沙盒"], "Sandbox"),
    (re.compile(r"File Manager|gestor de archivos", re.I), ["文件管理器"], "File Manager"),
    (re.compile(r"[Hh]ome Screen|pantalla de inicio"), ["主屏幕"], "Home Screen"),
    (re.compile(r"[Ll]ock Screen|pantalla de bloqueo"), ["锁屏"], "Lock Screen"),
    (re.compile(r"[Pp]asscode|código de desbloqueo"), ["密码"], "Passcode"),
    (re.compile(r"[Ww]allpaper|fondo de pantalla"), ["壁纸"], "Wallpaper"),
    (re.compile(r"\bMix\b"), ["混搭"], "Mix"),
    (re.compile(r"composici[oó]n", re.I), ["混搭", "构图"], "Composición (功能名或摄影构图)"),
    (re.compile(r"[Cc]ollection|colección"), ["合集", "收藏"], "Collection"),
    (re.compile(r"[Ss]cene\b|escena\b"), ["场景"], "Scene"),
    (re.compile(r"terminación|\bending\b|last digits|dígitos finales", re.I), ["尾号", "末位数字"], "Card ending"),
    (re.compile(r"\bgallery\b|galería", re.I), ["图库", "主题库"], "Gallery"),
    (re.compile(r"superficie", re.I), ["区域"], "Aura surface"),
    (re.compile(r"recovery point|punto de recuperación"), ["恢复点"], "Recovery point"),
    (re.compile(r"\bsnapshot\b|instantánea"), ["快照"], "Snapshot"),
    # No "profile" rule: the word means a GitHub profile, a configuration profile, and an
    # icon label in different screens. Any single required translation produced only noise.
]


def specs(s: str) -> list[str]:
    return sorted(SPEC_RE.findall(s))


def counter_diff(a: list[str], b: list[str]) -> dict[str, int]:
    """Multiset a minus multiset b -- what appears in a more often than in b."""
    left = collections.Counter(a)
    for k, n in collections.Counter(b).items():
        left[k] -= n
    return {k: n for k, n in left.items() if n > 0}


def is_identity(value: str) -> bool:
    """A value that is intentionally untranslated (brand / technical token)."""
    words = re.findall(r"[A-Za-z\u00c0-\u024f]+", value)
    if not words:
        return True  # digits / punctuation / symbols only
    return all(w.lower() in BRAND_WORDS for w in words)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", required=True, help="work/master.json")
    ap.add_argument("--table", required=True, help="compiled zh-Hans Localizable.strings")
    ap.add_argument("--report", default=None, help="optional json dump of findings")
    ap.add_argument("--pairs", default=None, help="work/pairs.json, to cross-check en/es twins")
    args = ap.parse_args()

    master = json.load(open(args.master, encoding="utf-8"))["rows"]
    table = macho.read_strings(args.table)

    want = [r["key"] for r in master]
    have = set(table)
    want_set = set(want)

    findings: dict[str, list] = {
        "missing": [], "placeholder_mismatch": [], "placeholder_dropped": [],
        "newline_mismatch": [], "identical_to_key": [], "no_cjk": [],
        "leftover_latin": [], "extra_keys": [], "empty": [],
        "leading_space_lost": [],
        "halfwidth_punct": [], "term_violation": [], "pair_divergence": [],
    }

    for k in want:
        v = table.get(k)
        if v is None:
            findings["missing"].append(k)
            continue
        if not v.strip():
            findings["empty"].append(k)
            continue
        extra_specs = counter_diff(specs(v), specs(k))
        if extra_specs:
            findings["placeholder_mismatch"].append({"key": k, "zh": v,
                                                     "key_specs": specs(k), "zh_specs": specs(v),
                                                     "invented": extra_specs})
        dropped_specs = counter_diff(specs(k), specs(v))
        if dropped_specs:
            findings["placeholder_dropped"].append({"key": k, "zh": v, "missing": dropped_specs})
        if v.count("\n") != k.count("\n"):
            findings["newline_mismatch"].append({"key": k, "zh": v})
        if k != k.strip() and v.strip() == v:
            findings["leading_space_lost"].append({"key": k, "zh": v})
        if v == k:
            if not is_identity(v):
                findings["identical_to_key"].append(k)
            continue
        if not CJK_RE.search(v) and not is_identity(v):
            findings["no_cjk"].append({"key": k, "zh": v})
        scrubbed = SPAN_RE.sub(" ", v)
        for run in LATIN_RUN.finditer(scrubbed):
            words = re.findall(r"[A-Za-z\u00c0-\u024f]+", run.group(0))
            if any(w.lower() not in BRAND_WORDS for w in words):
                findings["leftover_latin"].append({"key": k, "zh": v, "run": run.group(0)})
                break
        if CJK_RE.search(v) and HALF_PUNCT.search(v):
            findings["halfwidth_punct"].append({"key": k, "zh": v})
        for rx, required, label in TERM_RULES:
            if rx.search(k) and not any(r in v for r in required):
                findings["term_violation"].append({"key": k, "zh": v, "term": label})

    for k in sorted(have - want_set):
        findings["extra_keys"].append(k)

    # Eagle's developers write both an English and a Spanish form of the same sentence, and
    # after the source patch either can become the lookup key. If both are in the table they
    # must read the same in Chinese -- unless the source pair itself differs, which happens,
    # so this is a review list rather than a hard failure.
    if args.pairs and os.path.exists(args.pairs):
        for english, spanish in json.load(open(args.pairs, encoding="utf-8")):
            ve, vs = table.get(english), table.get(spanish)
            if ve and vs and ve.strip() != vs.strip():
                findings["pair_divergence"].append({"en": english, "es": spanish, "zh_en": ve, "zh_es": vs})

    total = len(want)
    present = total - len(findings["missing"])
    print(f"keys expected .......... {total}")
    print(f"keys present ......... {present}")
    print(f"empty ................ {len(findings['empty'])}")
    print(f"placeholder invented . {len(findings['placeholder_mismatch'])}")
    print(f"placeholder dropped .. {len(findings['placeholder_dropped'])}  (legal for plural-only %@)")
    print(f"newline mismatch ..... {len(findings['newline_mismatch'])}")
    print(f"leading space lost ... {len(findings['leading_space_lost'])}")
    print(f"identical to key ..... {len(findings['identical_to_key'])}")
    print(f"no CJK at all ........ {len(findings['no_cjk'])}")
    print(f"leftover latin ....... {len(findings['leftover_latin'])}")
    print(f"halfwidth punct ...... {len(findings['halfwidth_punct'])}")
    print(f"term violations ...... {len(findings['term_violation'])}")
    print(f"en/es twin divergence  {len(findings['pair_divergence'])}")
    print(f"unexpected extra keys  {len(findings['extra_keys'])}")

    if args.report:
        os.makedirs(os.path.dirname(os.path.abspath(args.report)) or ".", exist_ok=True)
        json.dump(findings, open(args.report, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"-> {args.report}")

    hard = (findings["missing"] or findings["placeholder_mismatch"]
            or findings["empty"] or findings["newline_mismatch"])
    print("VERDICT:", "FAIL (blocking defects)" if hard else "PASS (no blocking defects)")
    return 1 if hard else 0


if __name__ == "__main__":
    raise SystemExit(main())
