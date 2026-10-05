#!/usr/bin/env bash
# OFFICIAL scenario for ATL@NO, run from the official inactive list alone (no blending of BASE / FANT_OUT).
#   nfl/tools/showdown_run_official.sh   (expects OFFICIAL_INACTIVES_ATL_NO_2026W4.json in the raw capture dir)
set -u
cd "$(dirname "$0")/../.."
R=nfl/dfs/salaries/raw/showdown_atl_no_2026W4
D=nfl/dfs/salaries/showdown_atl_no
E=$R/DKEntries_ATL_NO_SHOWDOWN_2026W4.fd0c1faa2271ca66.csv
FC=$R/THIRDPARTY_FC_showdown_ATL_NO_2026W4_CONTEXT_ONLY.330fdd518c66ea57.csv
OI=$R/OFFICIAL_INACTIVES_ATL_NO_2026W4.json
LOG=${LOG:-/tmp/showdown_official.log}
SCEN=${SCEN:-OFFICIAL}
OI=${OI_OVERRIDE:-$OI}
step() { name=$1; shift; "$@" 2>&1 | grep -v "worlds solved" >> $LOG; rc=${PIPESTATUS[0]}; echo "STEP $name EXIT $rc $(date -u +%H:%MZ)" >> $LOG; return $rc; }
: > $LOG
[ -s "$OI" ] || { echo "STEP preflight EXIT 2 NO_OFFICIAL_INACTIVES_FILE" >> $LOG; exit 2; }
# V4 designations: V3, with every Questionable / Doubtful resolved by the official list (named -> out via the list;
# not named -> NO_DESIGNATION). OUT and NO_OFFENSIVE_ROLE entries are kept.
step designations python3.12 - <<PY
import json, pathlib
v3 = json.loads(pathlib.Path('$D/DESIGNATIONS_ATL_NO_2026W4_V3.json').read_text())
oi = {n.strip() for n in json.loads(pathlib.Path('$OI').read_text())}
if not oi: raise SystemExit('OFFICIAL_INACTIVES_EMPTY')
v4 = {}
for n, s in v3.items():
    v4[n] = s if s in ('OUT', 'NO_OFFENSIVE_ROLE') or n in oi else 'NO_DESIGNATION'
pathlib.Path('$D/DESIGNATIONS_ATL_NO_2026W4_V4_$SCEN.json').write_text(json.dumps(v4, indent=1))
print('resolved', {n: (v3[n], v4[n]) for n in v3 if v3[n] != v4[n]}, 'official n', len(oi))
PY
step tonight flock /tmp/showdown_tonight.lock python3.12 nfl/tools/showdown_tonight.py $E --scenario $SCEN --tag ATL_NO_2026W4 \
  --designations $D/DESIGNATIONS_ATL_NO_2026W4_V4_$SCEN.json --official-inactives $OI \
  --confirmed-starters $D/STARTERS_ATL_NO_2026W4.json --starter-tier PUBLIC_DEPTH_CHART_AND_SNAPS_CITED \
  --depth-chart $R/depth_charts_2026_ATL_NO.1e6aa6437a6ae01b.csv || exit 3
step absent python3.12 -c "import json;s=json.load(open('$D/$SCEN/SCENARIO.json'));json.dump(s['absent_in_state'],open('$D/SHADOW_ABSENT_$SCEN.json','w'),indent=1);print(len(s['absent_in_state']))"
step shadow_fc python3.12 nfl/field/showdown_shadow_field.py $E $FC $D/SHADOW_$SCEN --absent $D/SHADOW_ABSENT_$SCEN.json
step shadow_blend python3.12 nfl/field/showdown_shadow_field.py $E $FC $D/SHADOW_${SCEN}_BLEND --absent $D/SHADOW_ABSENT_$SCEN.json --blend-draws $D/$SCEN/SHOWDOWN_ATL_NO_2026W4_DRAWS.json
step finish env LOG=${LOG%.log}_finish.log bash nfl/tools/showdown_finish.sh $SCEN
step cycle1 python3.12 nfl/tools/showdown_cycle1_checks.py $D/$SCEN
step prelock python3.12 nfl/tools/showdown_prelock_board.py $E $D/$SCEN
echo OFFICIAL_CORE_DONE >> $LOG
step sal_fc08 python3.12 nfl/field/showdown_archetype_field.py $E $D/$SCEN $D/SHADOW_${SCEN}_BLEND --salary-anchor FC08_90PCT_LE_500 --phi 200
step prelock_b python3.12 nfl/tools/showdown_prelock_board.py $E $D/$SCEN
echo OFFICIAL_ALL_DONE >> $LOG
