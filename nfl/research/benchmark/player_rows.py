"""Benchmark mandate (2026-10-14), player scorecard step 1: per player-week rows for the PRODUCTION arm of the forward
chain on held-out seasons, with transparent naive baselines computed from the same panel for the same rows.

    python3.12 nfl/research/benchmark/player_rows.py VINTAGE APPEARANCE OUT.json [SEASONS]
        VINTAGE = STRICT | LEGACY        APPEARANCE = ON (production, unconditional) | OFF (given that he plays)

Writes only OUT, with two row sets:
  conditional    players who PLAYED in week W, scored on their realised DK points (forward_chain limit 1)
  unconditional  every allocation-pool candidate; one who did not play scores exactly zero (what a DFS slot pays)

Baselines (no model, no fitted constant, nothing from week W or later):
  STD   mean DK points over his appearances in weeks before W of the same season (a per-APPEARANCE mean)
  L3    mean of his last three appearances before W, across seasons
  PRIOR_SEASON  his mean DK points per appearance in the previous season
  *_U   the unconditional form: the per-appearance mean x his appearance rate this season before W (appearances / the
        weeks his pool club played before W). Used only on the unconditional rows.
A baseline without history for a player-week is None; comparisons use rows where every predictor exists."""
import collections
import json
import pathlib
import sys

sys.path.insert(0, '.')
from nfl.tools import forward_chain as F, player_prior as P  # noqa: E402

vintage, appearance, out = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
seasons = [int(s) for s in (sys.argv[4].split(',') if len(sys.argv) > 4 else ['2024', '2025'])]
assert appearance in ('ON', 'OFF'), appearance
F.VINTAGE[0] = vintage
F.APPLY_APPEARANCE[0] = appearance == 'ON'
F.PER_PLAYER_SINK, F.PER_PLAYER_SINK_DFS = [], []
po = P.load_panel()
assert po.state.name == 'PASS', po
panel = po.value
res, per_week = F.evaluate(panel, P.position_index(), seasons, [('PROD', 1.0, None)])

hist = {}
club_weeks = collections.defaultdict(set)
for g, ss in panel['players'].items():
    seq = []
    for s, ws in ss.items():
        for w, row in ws.items():
            if row.get('team'):
                seq.append((int(s), int(w), F.actual_dk(row)))
                club_weeks[(row['team'], int(s))].add(int(w))
    hist[g] = sorted(seq)


def base(g, season, week):
    before = [x for x in hist.get(g, []) if (x[0], x[1]) < (season, week)]
    std = [p for s, w, p in before if s == season]
    prev = [p for s, w, p in before if s == season - 1]
    return before, std, {'STD': (sum(std) / len(std)) if std else None, 'n_std': len(std),
                         'L3': (sum(p for *_x, p in before[-3:]) / len(before[-3:])) if before else None,
                         'PRIOR_SEASON': (sum(prev) / len(prev)) if prev else None}


cond = []
for (season, week, label, g, pos, proj, actual) in F.PER_PLAYER_SINK:
    _b, _s, b = base(g, season, week)
    cond.append({'season': season, 'week': week, 'gsis': g, 'pos': pos, 'proj': proj, 'actual': actual, **b})
unc = []
for (season, week, label, g, pos, proj, actual, appeared, club) in F.PER_PLAYER_SINK_DFS:
    _b, std, b = base(g, season, week)
    played = len([w for w in club_weeks.get((club, season), ()) if w < week])
    rate = (len(std) / played) if played else None
    u = {k + '_U': (b[k] * rate if (b[k] is not None and rate is not None) else None) for k in ('STD', 'L3', 'PRIOR_SEASON')}
    unc.append({'season': season, 'week': week, 'gsis': g, 'pos': pos, 'club': club, 'proj': proj, 'actual': actual,
                'appeared': appeared, 'appearance_rate_before': rate, **u})
out.write_text(json.dumps({'vintage': vintage, 'appearance': appearance, 'seasons': seasons,
                           'arm': 'PROD blend 1.0, production prior cap', 'n_weeks': len(per_week),
                           'conditional': cond, 'unconditional': unc}))
print('conditional', len(cond), 'unconditional', len(unc), 'weeks', len(per_week), vintage, appearance)
