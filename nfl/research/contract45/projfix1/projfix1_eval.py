"""PROJ-FIX-1 backtest (PREREG_PROJFIX1_ZERO_CLAIM.md @44f1b54e): forward_chain.evaluate with production settings on
held-out 2024-2025, flag per the environment. Writes only the given output file. Run from an isolated overlay root."""
import json, os, sys
sys.path.insert(0, '.')
from nfl.tools import forward_chain as F, player_prior as P
po = P.load_panel(); assert po.state.name == 'PASS', po
res, per_week = F.evaluate(po.value, P.position_index(), [2024, 2025], [('PROD', 1.0, None)])
flag = os.environ.get('NFL_PROJ_ZERO_CLAIM_IS_EVIDENCE') == '1'
out = [{'season': w['season'], 'week': w['week'], 'arm': w['arms'].get('PROD')} for w in per_week]
json.dump({'flag_zero_claim_is_evidence': flag, 'rows': out}, open(sys.argv[1], 'w'))
print('weeks', len(out), 'flag', flag)
