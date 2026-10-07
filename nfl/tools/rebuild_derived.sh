#!/usr/bin/env bash
# Rebuild the gitignored nfl/derived/ cache after a container reset, in dependency order, and verify it.
#
#   bash nfl/tools/rebuild_derived.sh            # rebuild, then compare with nfl/production/DERIVED_REBUILD_MANIFEST.json
#   bash nfl/tools/rebuild_derived.sh --record   # rebuild and (re)write the manifest -- only after a verified repro
#
# WHY. nfl/derived/ is never committed (it is regenerable from committed leaves), so a fresh container cannot run the
# live Showdown pipeline: proj_v1 refuses with BLOCKED[V1_INPUT_ABSENT] (first seen 2026-10-07, TD_RATES.json).
# numpy/pandas are not on the system interpreter either; they are installed with pip --target into PYLIB.
#
# FAIL-CLOSED. Every builder must exit 0 AND leave a non-empty artifact; a missing or empty artifact is an error,
# never a skipped step. A hash that differs from the manifest is reported by name and exits 4: the cache rebuilt,
# but not into the bytes the last verified reproduction used, so a live run on it is not the same engine.
set -u
cd "$(dirname "$0")/../.."
PYLIB=${PYLIB:-${SCRATCH_PYLIB:-/tmp/nfl_pylib}}
MANIFEST=nfl/production/DERIVED_REBUILD_MANIFEST.json
RECORD=0; [ "${1:-}" = "--record" ] && RECORD=1

if ! python3.12 -c "import numpy, pandas" 2>/dev/null; then
  if ! PYTHONPATH=$PYLIB python3.12 -c "import numpy, pandas" 2>/dev/null; then
    echo "deps: installing numpy pandas into $PYLIB"
    python3.12 -m pip install --quiet --target "$PYLIB" numpy pandas || { echo "FAIL DEPS_INSTALL"; exit 2; }
  fi
  export PYTHONPATH=$PYLIB${PYTHONPATH:+:$PYTHONPATH}
fi
echo "PYTHONPATH=${PYTHONPATH:-}"
# A fresh container's clone can be SHALLOW, and the frozen-candidate tests read pinned blobs from history
# (test_appearance_candidate_b: FROZEN_BLOB_NOT_RETRIEVABLE on 2026-10-07). Fetch the history; if that fails, say so.
if [ "$(git rev-parse --is-shallow-repository 2>/dev/null)" = "true" ]; then
  git fetch --quiet --unshallow origin "$(git rev-parse --abbrev-ref HEAD)" && echo "history: unshallowed" \
    || echo "WARN SHALLOW_CLONE: pinned-blob tests will fail until history is fetched"
fi

build() {  # name artifact command...
  name=$1; art=$2; shift 2
  "$@" > /tmp/rebuild_derived_$name.log 2>&1; rc=$?
  if [ $rc -ne 0 ]; then echo "FAIL $name EXIT $rc (log /tmp/rebuild_derived_$name.log)"; exit 3; fi
  if [ ! -s "$art" ]; then echo "FAIL $name ARTIFACT_MISSING_OR_EMPTY $art"; exit 3; fi
  echo "ok   $name -> $art"
}
# order matters: every later builder reads the panel. ROLE_STATE.json is NOT here: it is slate-specific and
# showdown_slate_run rebuilds it from the slate's own state on every run, so it has no fixed bytes to verify.
build usage_history nfl/derived/USAGE_HISTORY_2021_2026.json python3.12 nfl/tools/usage_history.py
build td_rates      nfl/derived/TD_RATES.json                python3.12 nfl/tools/td_rates.py
build kicker_model  nfl/derived/KICKER_RATES.json            python3.12 nfl/tools/kicker_model.py
build kicker_world  nfl/derived/KICKER_WORLD.json            python3.12 nfl/tools/kicker_world.py
build dst_model     nfl/derived/DST_RATES.json               python3.12 -c "import sys; sys.path.insert(0, '.'); from nfl.tools import dst_model as M; r = M.build(); sys.exit(0 if isinstance(r, tuple) else 1)"
build forward_chain nfl/derived/FORWARD_CHAIN.json           python3.12 nfl/tools/forward_chain.py
# The P4B research binaries (gitignored, read in place by research and several tests). regenerate.py verifies every
# leaf and both output hashes against ABC_MPR_IDENTITY and refuses on any mismatch; only verified bytes are copied.
RG=$(mktemp -d)
build p4b_regen "$RG/panel_enriched.pkl" python3.12 nfl/research/repro/regenerate.py --emit "$RG"
git checkout -q -- nfl/research/repro/regeneration_report.json 2>/dev/null || true   # its run report is not a rebuild output
cp "$RG/panel_enriched.pkl" "$RG/volume_store.npy" nfl/research/p4b/ && rm -rf "$RG" && echo "ok   p4b research binaries placed"

python3.12 - "$MANIFEST" "$RECORD" <<'PY'
import hashlib, json, pathlib, sys
man, record = pathlib.Path(sys.argv[1]), sys.argv[2] == '1'
names = ['USAGE_HISTORY_2021_2026.json', 'TD_RATES.json', 'KICKER_RATES.json',
         'KICKER_WORLD.json', 'DST_RATES.json', 'FORWARD_CHAIN.json']
now = {n: hashlib.sha256((pathlib.Path('nfl/derived') / n).read_bytes()).hexdigest() for n in names}
if record:
    man.write_text(json.dumps({'ARTIFACT': 'DERIVED_REBUILD_MANIFEST',
                               'MEANING': 'sha256 of each nfl/derived artifact as rebuilt by nfl/tools/rebuild_derived.sh '
                                          'in the container whose ATL@NO reproduction matched the frozen upload bytes',
                               'sha256': now}, indent=1, sort_keys=True) + '\n')
    print('RECORDED', man); sys.exit(0)
if not man.exists():
    print('FAIL MANIFEST_ABSENT', man); sys.exit(4)
want = json.loads(man.read_text())['sha256']
bad = {n: (want.get(n), now[n]) for n in names if want.get(n) != now[n]}
for n in names:
    print(('MATCH ' if n not in bad else 'DIFFERS ') + n)
sys.exit(4 if bad else 0)
PY
rc=$?; [ $rc -eq 0 ] && echo DERIVED_READY || echo "DERIVED_NOT_VERIFIED rc=$rc"; exit $rc
