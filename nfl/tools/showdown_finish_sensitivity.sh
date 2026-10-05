#!/usr/bin/env bash
# Slow SHADOW sensitivities for a staged scenario, run AFTER showdown_finish.sh so they never delay the core pipeline:
# Cycle 1 checks (OWN-05 is a test; COR-01/02 correlation recovery; same-world coherence vs 2021-25; DATA-04), the
# salary-anchored archetype fields (FC-08, FC-09; BLEND targets, phi 200), then the prelock board again.
s=$1; cd "$(dirname "$0")/../.."
E=nfl/dfs/salaries/raw/showdown_atl_no_2026W4/DKEntries_ATL_NO_SHOWDOWN_2026W4.fd0c1faa2271ca66.csv
D=nfl/dfs/salaries/showdown_atl_no
LOG=${LOG:-/tmp/showdown_finish_sensitivity_$s.log}
: > $LOG
step() { name=$1; shift; "$@" 2>&1 | grep -v "worlds solved" >> $LOG; echo "STEP $name EXIT ${PIPESTATUS[0]}" >> $LOG; }
step cycle1 python3.12 nfl/tools/showdown_cycle1_checks.py $D/$s
step prelock_a python3.12 nfl/tools/showdown_prelock_board.py $E $D/$s
step sal_fc08 python3.12 nfl/field/showdown_archetype_field.py $E $D/$s $D/SHADOW_${s}_BLEND --salary-anchor FC08_90PCT_LE_500 --phi 200
step sal_fc09 python3.12 nfl/field/showdown_archetype_field.py $E $D/$s $D/SHADOW_${s}_BLEND --salary-anchor FC09_80PCT_MAX --phi 200
step prelock_b python3.12 nfl/tools/showdown_prelock_board.py $E $D/$s
echo FINISHED >> $LOG
