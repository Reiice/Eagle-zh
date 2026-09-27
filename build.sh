#!/bin/sh
# Rebuild the Simplified Chinese Eagle localization end to end.
#
#   sh build.sh prepare   [eagle.ipa] [source-checkout]   # extract keys -> batches
#   sh build.sh pack      [eagle.ipa]                     # merge -> audit -> ipa
#   sh build.sh all       ...                             # both
#
# Omit the ipa and the script downloads the latest Eagle release asset itself.
#
# Needs only Python 3.12 (stdlib), unzip and curl. No macOS and no Xcode: the table is a
# resource, and the code that reads it lives in patch/ and is compiled by
# .github/workflows/build-zh.yml.
#
# Between prepare and pack, translate work/batches3/*.json into work/translated3/*.json (see
# l10n/TRANSLATOR.md). prepare never re-asks for a key that is already translated, so adding
# strings later only sends the difference.
set -eu

MODE="${1:-all}"
IPA="${2:-}"
SRC="${3:-}"
PY="${PYTHON:-python}"
UPSTREAM_API="https://api.github.com/repos/leonardob8777-bit/Eagle/releases/latest"

usage() {
  echo "usage: sh build.sh [all|prepare|pack] [eagle.ipa] [eagle-source-checkout]" >&2
}

need() {
  [ -n "$1" ] || { echo "missing required argument: $2" >&2; usage; exit 2; }
  [ -f "$1" ] || { echo "not a readable file: $1 ($2)" >&2; exit 2; }
}

# A fresh clone can reproduce the table without anyone handing it a file: no ipa argument
# resolves the upstream "Latest" release and pulls its .ipa asset. Some networks get a bare 403
# from the unauthenticated API; export GITHUB_TOKEN (any scope-less fine-grained token works)
# and the request is authenticated instead.
resolve_ipa() {
  if [ -z "$IPA" ]; then
    echo "no ipa given: fetching the latest Eagle release" >&2
    mkdir -p work
    AUTH=""
    [ -n "${GITHUB_TOKEN:-}" ] && AUTH="Authorization: bearer $GITHUB_TOKEN"
    curl -fsSL --retry 3 --retry-all-errors ${AUTH:+-H} ${AUTH:+"$AUTH"} \
      "$UPSTREAM_API" -o work/latest-release.json
    URL=$($PY -c 'import json,sys;d=json.load(open(sys.argv[1],encoding="utf-8"));a=[x for x in d.get("assets",[]) if x["name"].endswith(".ipa")];print(a[0]["browser_download_url"] if a else "")' work/latest-release.json)
    [ -n "$URL" ] || { echo "the latest Eagle release has no .ipa asset" >&2; exit 2; }
    IPA=work/upstream-eagle.ipa
    curl -fsSL --retry 3 --retry-all-errors -o "$IPA" "$URL"
    echo "fetched $URL" >&2
  fi
  need "$IPA" "eagle.ipa (arg 2)"
  VERBLD=$($PY -c 'import plistlib,sys,zipfile;d=plistlib.loads(zipfile.ZipFile(sys.argv[1]).read("Payload/Eagle.app/Info.plist"));print(d["CFBundleShortVersionString"],d["CFBundleVersion"])' "$IPA")
  OUT="dist/Eagle-${VERBLD% *}-${VERBLD#* }-zh-Hans.ipa"
}

APP=work/unpacked/Payload/Eagle.app
# Every directory holding key->zh JSON, newest first. normalize.py takes the first definition
# of a key it finds, so the order is the precedence order.
# Translator output directories plus the tracked hand-recovered entries in l10n/overrides.
# work/normalized and work/reconciled are *products* of this script and must never appear
# here, or normalize.py would feed its own report back in as a translation table.
TRANS="work/translated4 work/translated3 work/translated2 work/translated l10n/overrides"

prepare() {
  resolve_ipa
  mkdir -p work dist work/batches3
  rm -rf work/unpacked
  unzip -q -o "$IPA" -d work/unpacked

  if [ -n "$SRC" ]; then
    rm -rf work/upstream-src && cp -r "$SRC" work/upstream-src
  elif [ ! -d work/upstream-src ]; then
    echo "no Eagle source checkout: pass it as argument 3" >&2
    exit 1
  fi

  # --from-source: the published build 92 binary predates the release commit that produced it,
  # so roughly a fifth of HEAD's UI strings are absent from it. Requiring presence in that
  # binary would drop copy the freshly compiled app really does show. Drop the flag only when
  # regenerating the resource-injection table, where an inert key is worse than no key.
  $PY tools/extract_keys.py \
    --repo work/upstream-src \
    --binary "$APP/Eagle" \
    --catalog "$APP/en.lproj/Localizable.strings" \
    --from-source \
    --out work/keys.json

  $PY tools/build_master.py --keys work/keys.json --out work \
    --batch-dir work/batches --batch-size 95
  $PY tools/prune_master.py --master work/master.json --extra l10n/overrides/manual.json

  KNOWN=""; for d in $TRANS; do KNOWN="$KNOWN --translated $d"; done
  $PY tools/make_known.py --master work/master.json --pruned work/master.pruned.json \
    $KNOWN --out work/known.json
  # Re-batch from the pruned master, skipping everything already translated or gated out.
  $PY tools/build_master.py --keys work/keys.json --out work \
    --batch-dir work/batches3 --batch-size 95 --known work/known.json

  $PY tools/survey_scope.py --repo work/upstream-src --binary "$APP/Eagle" \
    --table l10n/zh-Hans.lproj/Localizable.strings --out work/scope.json
}

pack() {
  resolve_ipa
  $PY tools/prune_master.py --master work/master.json --extra l10n/overrides/manual.json

  TD=""; for d in $TRANS; do TD="$TD --translated-dir $d"; done
  $PY tools/normalize.py $TD \
    --terms l10n/terms.json --out-dir work/normalized

  # Force the duplicate keys of one sentence (%@/%d variants, en/es twins) to carry one string.
  # It must land in its own directory: compile_strings reads every *.json in the folder it is
  # given, so leaving this next to normalized.json would let the unreconciled copy win.
  mkdir -p work/reconciled
  $PY tools/reconcile.py --table work/normalized/normalized.json \
    --master work/master.pruned.json --pairs work/pairs.json \
    --out work/reconciled/reconciled.json

  $PY tools/compile_strings.py --master work/master.pruned.json \
    --translated-dir work/reconciled --out-dir l10n --staging-dir work/staging

  $PY tools/audit.py --master work/master.pruned.json \
    --table l10n/zh-Hans.lproj/Localizable.strings \
    --pairs work/pairs.json --report work/audit.json
  $PY tools/latin_report.py --table l10n/zh-Hans.lproj/Localizable.strings --out work/latin.json
  # Slot-level coverage is the honest number; a raw key count hides how much UI is still foreign.
  $PY tools/diagnose_gaps.py --pairs work/pairs.json \
    --table l10n/zh-Hans.lproj/Localizable.strings --binary "$APP/Eagle" \
    --catalog "$APP/en.lproj/Localizable.strings" --out work/gaps.json

  $PY tools/build_zh_ipa.py --ipa "$IPA" --staging-lproj work/staging/zh-Hans.lproj --out "$OUT"
  $PY tools/verify_ipa.py --base "$IPA" --zh "$OUT"
  # The cloud build is part of the deliverable; a bad key aborts it before any step runs.
  $PY tools/check_workflow.py .github/workflows/build-zh.yml
}

case "$MODE" in
  prepare) prepare ;;
  pack)    pack ;;
  all)     prepare; pack ;;
  *) usage; exit 2 ;;
esac
