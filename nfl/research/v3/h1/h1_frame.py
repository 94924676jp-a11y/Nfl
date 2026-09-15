"""H1 step 2: the QB frame, built the way the frozen layer's own loader would.

`qb2_lib.load()` cannot run in this checkout: it calls
`rc1_lib -> s2_lib -> p4c_build.load_panel()`, which reads
`nfl/research/p4b/panel_enriched.pkl`, and that file is absent. The frame is
therefore rebuilt HERE from `nfl/research/qb2/qb.pkl` -- the artifact
`nfl/production/qb_v1.FRAME_PATH` names and hashes -- into exactly the row
schema `qb2_lib.attach` and `qb2_lib.simulate` expect. The schema is
transcribed from `qb2_lib.load`, field for field, and the fields are asserted
present rather than assumed.

DIFFERENCE R3, DECLARED. `qb2_lib.load` filters `position == 'QB'` from the
RC1 panel. That panel is unavailable, so position is inferred as "recorded at
least one dropback". The two differ only for a non-quarterback who dropped
back; the count is measured and reported rather than waved at.

PRIMARY PASSER. `ord == 1` in the brief's language: the largest dropback
count among a team's passers in one game. Ties broken by attempts then
gsis_id, and the tie rate is reported.
"""
from __future__ import annotations

import collections
import csv
import gzip
import hashlib
import pathlib
import pickle
import sys

_REPO = pathlib.Path(__file__).resolve().parents[4]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'qb2'),
           str(_REPO / 'nfl' / 'research' / 'v3' / 'h1')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

import h1_context as CTX                                          # noqa: E402

FRAME_PATH = _REPO / 'nfl' / 'research' / 'qb2' / 'qb.pkl'
Q7 = _REPO / 'nfl' / 'research' / 'q7' / 'q7_qb_game.csv.gz'
DENOM = _REPO / 'nfl' / 'research' / 'inputs' / 'denom_panel.csv.gz'

# transcribed from qb2_lib.load, field for field
_PLAYER = {'db': 'dropbacks', 'att': 'attempts', 'sacks': 'sacks',
           'scr': 'scrambles', 'spikes': 'spikes', 'cmp': 'completions',
           'ptd': 'pass_td', 'int': 'interceptions', 'drush': 'designed_rushes',
           'rtd': 'rush_td'}
_FLOAT = {'pyds': 'pass_yards', 'ryds': 'rush_yards'}


def frame_hash():
    return hashlib.sha256(FRAME_PATH.read_bytes()).hexdigest()


def load_denom():
    with gzip.open(DENOM, 'rt', newline='') as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise SystemExit('H1_DENOM_EMPTY')
    out = {}
    for r in rows:
        out[(int(r['season']), int(r['week']), r['team'])] = {
            'team_off_snaps': int(r['team_off_snaps']),
            'team_dropbacks_part': int(r['team_dropbacks_part']),
            'team_carries': int(r['team_carries']),
            'coach': r['coach'], 'rest': r['rest'], 'div_game': r['div_game']}
    return out


def build():
    if not FRAME_PATH.exists():
        raise SystemExit(f'H1_QB_FRAME_MISSING: {FRAME_PATH}')
    d = pickle.load(open(FRAME_PATH, 'rb'))
    P, T = d['player'], d['team']
    if not P or not T:
        raise SystemExit('H1_QB_FRAME_EMPTY: qb.pkl carries no rows')
    ctx = {(r['season'], r['week'], r['team']): r for r in CTX.load()}
    den = load_denom()

    rows = []
    for (season, week, team, pid), m in P.items():
        db = int(m.get('dropbacks', 0))
        if db <= 0:
            continue
        tk = (season, week, team)
        t = T.get(tk)
        if t is None:
            raise SystemExit(f'H1_TEAM_ROW_MISSING: {tk}')
        c = ctx.get(tk)
        if c is None:
            raise SystemExit(f'H1_CONTEXT_ROW_MISSING: {tk}')
        dn = den.get(tk)
        if dn is None:
            raise SystemExit(f'H1_DENOM_ROW_MISSING: {tk}')
        r = {'season': season, 'week': week, 'team': team, 'gsis_id': pid,
             'position': 'QB', 'ord': season * 100 + week,
             'game_id': c['game_id'], 'opponent': c['opponent'],
             'home': c['home'], 'points_for': c['points_for'],
             'points_against': c['points_against'],
             'team_rush_plays': c['rush_plays'],
             'team_rush_yards': c['rush_yards'],
             'team_designed_rush_plays': c['designed_rush_plays'],
             'team_db': int(t.get('dropbacks', 0)),
             'team_plays': int(t.get('plays', 0)),
             'team_rushes': int(t.get('team_rushes', 0)),
             'team_sacks_allowed': int(t.get('sacks', 0)),
             'team_off_snaps': dn['team_off_snaps'],
             'team_dropbacks_part': dn['team_dropbacks_part'],
             'team_carries': dn['team_carries'], 'coach': dn['coach']}
        for k, src in _PLAYER.items():
            r[k] = int(m.get(src, 0))
        for k, src in _FLOAT.items():
            r[k] = float(m.get(src, 0.0))
        r['rush_opp'] = r['drush'] + r['scr']
        rows.append(r)

    if not rows:
        raise SystemExit('H1_FRAME_EMPTY: no QB-game rows. Empty is an error.')

    # THE BINDING IDENTITY, checked rather than assumed.
    bad = [r for r in rows if r['att'] + r['sacks'] + r['scr'] != r['db']]
    if bad:
        raise SystemExit(
            f'H1_DROPBACK_IDENTITY_VIOLATED: {len(bad)} of {len(rows)} rows, '
            f'e.g. {bad[0]}')

    # primary passer per team-game
    by = collections.defaultdict(list)
    for r in rows:
        by[(r['game_id'], r['team'])].append(r)
    ties = 0
    for k, v in by.items():
        v.sort(key=lambda r: (-r['db'], -r['att'], r['gsis_id']))
        if len(v) > 1 and v[0]['db'] == v[1]['db']:
            ties += 1
        for i, r in enumerate(v):
            r['qb_ord'] = i + 1
            r['n_qb_in_team_game'] = len(v)

    rows.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
    return rows, {'n_rows': len(rows),
                  'n_team_games': len(by),
                  'n_primary_ties': ties,
                  'qb_frame_sha256': frame_hash(),
                  'per_season': dict(
                      collections.Counter(r['season'] for r in rows))}


def q7_crosscheck(rows):
    """Reconcile against the panel the brief pointed at. Reported, not trusted."""
    with gzip.open(Q7, 'rt', newline='') as fh:
        q7 = list(csv.DictReader(fh))
    idx = {(int(r['season']), int(r['week']), r['team'], r['gsis_id']): r
           for r in q7}
    mine = {(r['season'], r['week'], r['team'], r['gsis_id']): r for r in rows}
    inter = set(idx) & set(mine)
    agree = collections.Counter()
    for k in inter:
        a, b = idx[k], mine[k]
        for f, g in (('att', 'att'), ('sacks', 'sacks'), ('scr', 'scr'),
                     ('cmp', 'cmp'), ('db', 'db'), ('ptd', 'ptd'),
                     ('int', 'int')):
            agree[f] += int(int(a[f]) == b[g])
        agree['pyds'] += int(int(a['pyds']) == int(b['pyds']))
    return {'n_q7_rows': len(q7), 'n_h1_rows': len(rows),
            'n_matched_keys': len(inter),
            'n_q7_only': len(set(idx) - set(mine)),
            'n_h1_only': len(set(mine) - set(idx)),
            'field_agreement_on_matched': {k: int(v) for k, v in agree.items()},
            'q7_total_scrambles': sum(int(r['scr']) for r in q7),
            'h1_total_scrambles': sum(r['scr'] for r in rows)}


if __name__ == '__main__':
    import json
    rs, meta = build()
    print(json.dumps(meta, indent=1))
    print(json.dumps(q7_crosscheck(rs), indent=1))
