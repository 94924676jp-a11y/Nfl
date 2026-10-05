#!/usr/bin/env bash
# Post-portfolio finishing pipeline for a staged ATL@NO scenario: audit -> both SHADOW boards (BLEND, FC_ONLY)
# -> FC comparison -> video claims -> PRELOCK board. Reads artifacts only; recomputes no football.
# usage: finish.sh SCENARIO   (BASE | FANT_OUT | any staged scenario dir name)
s=$1; cd /home/user/nfl
E=nfl/dfs/salaries/raw/showdown_atl_no_2026W4/DKEntries_ATL_NO_SHOWDOWN_2026W4.fd0c1faa2271ca66.csv
FC=nfl/dfs/salaries/raw/showdown_atl_no_2026W4/THIRDPARTY_FC_showdown_ATL_NO_2026W4_CONTEXT_ONLY.330fdd518c66ea57.csv
D=nfl/dfs/salaries/showdown_atl_no
LOG=${LOG:-/tmp/showdown_finish_$s.log}
: > $LOG
step() { name=$1; shift; "$@" 2>&1 | grep -v "worlds solved" >> $LOG; echo "STEP $name EXIT ${PIPESTATUS[0]}" >> $LOG; }
step audit python3.12 nfl/tools/showdown_portfolio_audit.py $E $D/$s
step board_blend python3.12 nfl/field/showdown_shadow_board.py $E $D/$s $D/SHADOW_${s}_BLEND
step board_fc python3.12 nfl/field/showdown_shadow_board.py $E $D/$s $D/SHADOW_${s}
step arch_blend python3.12 nfl/field/showdown_archetype_field.py $E $D/$s $D/SHADOW_${s}_BLEND
step arch_fc python3.12 nfl/field/showdown_archetype_field.py $E $D/$s $D/SHADOW_${s}
step fc_compare python3.12 nfl/tools/showdown_fc_compare.py $D/$s $FC
step claims python3.12 nfl/tools/showdown_external_claims.py $D/$s
step prelock python3.12 nfl/tools/showdown_prelock_board.py $E $D/$s
echo FINISHED >> $LOG
