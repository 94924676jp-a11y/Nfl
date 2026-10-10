#!/usr/bin/env python3.12
"""Validate an ingested DKSalaries file against the slate before any lineup is built. Read-only.

    python3.12 nfl/integrations/dk_pool_check.py 2026W5 --raw-dir RAW --state STATE.json [--roster-audit JSON]

Runs as soon as the owner's DKSalaries.csv is in the inbox, and needs no DKEntries file: research portfolios are
built on the pool; entries are only needed to assign lineups to contests, which is a separate, later step.

Checks, each a named result:
  POOL_IS_CLASSIC          no CPT roster positions
  GAMES_MATCH_SLATE        the file's games equal the slate's games, exactly
  KICKOFF_IN_SLATE         every row's kickoff is the slate kickoff
  POSITIONS_LEGAL          positions in {QB, RB, WR, TE, DST} and roster positions consistent with them
  SALARIES_PARSE           every salary is a positive integer
  IDS_UNIQUE               no DK id twice (the inbox already refuses a duplicate; repeated here as a guard)
  IDENTITY_MAPPED          every non-DST DK player maps to exactly one research-universe player by
                           normalised name + club; the unmatched are listed, never guessed
  UPLOAD_ELIGIBILITY       per player: BLOCKED when the state says he is not playing (Out), when the roster audit
                           marks his history unresolved, or when his identity is unmapped. Everyone else is
                           ELIGIBLE_PENDING_INACTIVES, never simply eligible, until the official inactives arrive.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

LEGAL = {'QB': {'QB'}, 'RB': {'RB/FLEX'}, 'WR': {'WR/FLEX'}, 'TE': {'TE/FLEX'}, 'DST': {'DST'}}


def check(slate_id, *, raw_dir, state, inbox_rows=None, roster_audit=None) -> Outcome:
    from nfl.dfs.salaries import early_only as EO
    from nfl.integrations import inbox as IB, rebuild as RB
    from nfl.tools import research_universe as RU
    from nfl.tools.sim_query import norm_name
    inbox_rows = inbox_rows if inbox_rows is not None else IB.ledger_rows()
    pool_ref = RB.dk_pool_for_slate(slate_id, inbox_rows)
    if not pool_ref:
        return Outcome.blocked('DK_POOL_NOT_DELIVERED', 'no CLASSIC DKSalaries file for this slate is in the inbox; '
                               'drop it in nfl/dfs/inbox/drop/ and run nfl/integrations/inbox.py',
                               cause=Cause.EMPTY_INPUT)
    p = EO.pool(blob=_REPO / pool_ref['blob'], sha_declared=pool_ref['sha256'])
    if p.state.value != 'PASS':
        return p
    rows = p.value
    kick = EO.SLATES[slate_id]['kickoff']
    games = {f"{g['away']}@{g['home']}" for g in state['games'].values()}
    res = {}
    rp = {r['roster_position'] for r in rows}
    res['POOL_IS_CLASSIC'] = not any('CPT' in x for x in rp)
    fg = {f"{r['away']}@{r['home']}" for r in rows if r['away']}
    res['GAMES_MATCH_SLATE'] = {'pass': fg == games, 'missing': sorted(games - fg), 'extra': sorted(fg - games)}
    bad_k = [r['dk_name'] for r in rows if r['kickoff'] != kick]
    res['KICKOFF_IN_SLATE'] = {'pass': not bad_k, 'rows_off_slate': bad_k[:20], 'n': len(bad_k)}
    bad_pos = [(r['dk_name'], r['dk_pos'], r['roster_position']) for r in rows
               if r['dk_pos'] not in LEGAL or r['roster_position'] not in LEGAL[r['dk_pos']]]
    res['POSITIONS_LEGAL'] = {'pass': not bad_pos, 'bad': bad_pos[:20]}
    bad_sal = [r['dk_name'] for r in rows if not isinstance(r['salary'], int) or r['salary'] <= 0]
    res['SALARIES_PARSE'] = {'pass': not bad_sal, 'bad': bad_sal[:20]}
    ids = collections.Counter(r['dk_id'] for r in rows)
    res['IDS_UNIQUE'] = {'pass': all(v == 1 for v in ids.values()), 'dup': [k for k, v in ids.items() if v > 1]}
    u = RU.build(slate_id, raw_dir)
    if u.state.value != 'PASS':
        return u
    uk = collections.defaultdict(list)
    for r in u.value:
        if r['dk_pos'] != 'DST':
            uk[(norm_name(r['dk_name']), r['team'])].append(r)
    by_state = {(norm_name(p['name']), p['team']): p for p in state['players'].values()}
    unresolved = {(norm_name(x['name']), x['team']) for x in ((roster_audit or {}).get('unresolved') or [])}
    players, unmatched = [], []
    for r in rows:
        key = (norm_name(r['dk_name']), r['team'])
        reasons = []
        if r['dk_pos'] != 'DST':
            m = uk.get(key, [])
            if len(m) != 1:
                reasons.append('IDENTITY_UNMAPPED' if not m else 'IDENTITY_AMBIGUOUS')
                unmatched.append({'dk_name': r['dk_name'], 'team': r['team'], 'pos': r['dk_pos'], 'n_matches': len(m)})
            st = (by_state.get(key) or {}).get('current_availability') or {}
            if st.get('designation') == 'OUT' or 'INACTIVE' in str(st.get('status')):
                reasons.append('NOT_PLAYING_OUT')
            if key in unresolved:
                reasons.append('ROSTER_HISTORY_UNRESOLVED')
        players.append({'dk_id': r['dk_id'], 'dk_name': r['dk_name'], 'team': r['team'], 'pos': r['dk_pos'],
                        'salary': r['salary'],
                        'upload': 'BLOCKED' if reasons else 'ELIGIBLE_PENDING_INACTIVES', 'reasons': reasons})
    res['IDENTITY_MAPPED'] = {'pass': not unmatched, 'unmatched': unmatched}
    counts = collections.Counter(x['upload'] for x in players)
    passed = all(v if isinstance(v, bool) else v['pass'] for v in res.values())
    ev = dict(checks=res, dk_file=pool_ref, n_rows=len(rows), upload_counts=dict(counts), players=players,
              NOTE='ELIGIBLE_PENDING_INACTIVES is not eligible: the official inactives decide it about 90 minutes '
                   'before kickoff. DKEntries is not required for this check.')
    if not passed:
        return Outcome.fail('DK_POOL_CHECK_FAILED', f"failed: {[k for k, v in res.items() if not (v if isinstance(v, bool) else v['pass'])]}",
                            **ev)
    return Outcome.ok('DK_POOL_CHECK_PASSED', value=players, detail=f'{len(rows)} rows; {dict(counts)}', **ev)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--raw-dir', required=True)
    ap.add_argument('--state', required=True)
    ap.add_argument('--roster-audit')
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    st = json.loads(pathlib.Path(a.state).read_text())
    ra = json.loads(pathlib.Path(a.roster_audit).read_text()) if a.roster_audit else None
    o = check(a.slate_id, raw_dir=a.raw_dir, state=st, roster_audit=ra)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps({'code': o.code, 'detail': o.detail, 'evidence': o.evidence},
                                                  indent=1, default=str) + '\n')
    return 0 if o.state.value == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
