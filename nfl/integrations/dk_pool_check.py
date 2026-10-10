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
                           normalised name + club, then by a declared alias, then by stripping a declared
                           generational suffix (the production resolver's own rule, proj_v1.py
                           resolve_slate_identities: 'Aaron Jones Sr.' is the roster's 'Aaron Jones'). The
                           unmatched are listed, never guessed. A DK row whose name exists only on ANOTHER
                           club (a transfer DK has not caught up with, or the reverse) is
                           IDENTITY_TEAM_CONFLICT and fails the pool: SUN_INVALID_DK_POOL. A name the
                           week's roster capture does not hold at all is IDENTITY_UNMAPPED and fails it.
                           EXPLAINED BY THE ROSTER, NOT IDENTITY FAILURES: DK prices players our universe
                           rightly leaves out. Each is blocked from upload with the roster's own reason and
                           does not fail the pool:
                             NOT_ON_ACTIVE_ROSTER     the week's row is RES/DEV/EXE/CUT/... (status kept)
                             NON_SKILL_POSITION       active, but a long snapper or other non-skill role
                             ABSENT_FROM_WEEK_ROSTER  on this club in an earlier week, no row this week:
                                                      status UNKNOWN, never read as inactive
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
#: Declared, copied from proj_v1.resolve_slate_identities (that module is hash-pinned and is not edited):
#: stripping a known generational suffix is the same name, not a similarity search.
SUFFIXES = (' jr', ' sr', ' ii', ' iii', ' iv', ' v')
SKILL = {'QB', 'RB', 'FB', 'WR', 'TE'}
FAILS_POOL = {'IDENTITY_TEAM_CONFLICT', 'IDENTITY_AMBIGUOUS', 'IDENTITY_UNMAPPED'}


def _strip_suffix(n):
    for suf in SUFFIXES:
        if n.endswith(suf):
            return n[: -len(suf)].strip()
    return n


def _week_roster(universe_evidence, week):
    """{(stripped normalised name, club): [rows]} from the roster capture the universe itself read."""
    import csv
    import gzip
    from nfl.tools.sim_query import norm_name
    f = ((universe_evidence.get('sources') or {}).get('roster') or {}).get('file')
    out = collections.defaultdict(list)
    if not f:
        return out
    for r in csv.DictReader(gzip.open(_REPO / f, 'rt')):
        out[(_strip_suffix(norm_name(r['full_name'])), r['team'])].append(r)
    return out


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
    try:
        from nfl.tools.availability import NAME_ALIASES
    except Exception:
        NAME_ALIASES = {}
    uk = collections.defaultdict(list)
    uk_stripped = collections.defaultdict(list)
    by_name = collections.defaultdict(set)
    for r in u.value:
        if r['dk_pos'] != 'DST':
            uk[(norm_name(r['dk_name']), r['team'])].append(r)
            uk_stripped[(_strip_suffix(norm_name(r['dk_name'])), r['team'])].append(r)
            by_name[_strip_suffix(norm_name(r['dk_name']))].add(r['team'])
    week = u.evidence.get('week')
    roster = _week_roster(u.evidence, week)
    by_state = {(norm_name(p['name']), p['team']): p for p in state['players'].values()}
    unresolved = {(norm_name(x['name']), x['team']) for x in ((roster_audit or {}).get('unresolved') or [])}
    players, unmatched = [], []
    explained, how_matched = [], collections.Counter()
    for r in rows:
        key = (norm_name(r['dk_name']), r['team'])
        reasons = []
        if r['dk_pos'] != 'DST':
            m, how = uk.get(key, []), 'EXACT_NAME'
            alias = NAME_ALIASES.get((r['dk_name'], r['team']))
            if not m and alias:
                m, how = uk.get((norm_name(alias), r['team']), []), 'DECLARED_ALIAS'
            if not m:
                m, how = uk_stripped.get((_strip_suffix(key[0]), r['team']), []), 'SUFFIX_NORMALISED'
            if len(m) == 1:
                how_matched[how] += 1
                key = (norm_name(m[0]['dk_name']), m[0]['team'])
            else:
                sk = (_strip_suffix(key[0]), r['team'])
                wk = [x for x in roster.get(sk, []) if str(x.get('week')) == str(week)]
                earlier = [x for x in roster.get(sk, []) if str(x.get('week')) != str(week)]
                other = sorted(by_name.get(sk[0], set()) - {r['team']})
                if m:
                    code = 'IDENTITY_AMBIGUOUS'
                elif other:
                    code = 'IDENTITY_TEAM_CONFLICT'
                elif wk and wk[-1].get('status') != 'ACT':
                    code = 'NOT_ON_ACTIVE_ROSTER'
                elif wk and wk[-1].get('position') not in SKILL:
                    code = 'NON_SKILL_POSITION'
                elif not wk and earlier:
                    code = 'ABSENT_FROM_WEEK_ROSTER'
                else:
                    code = 'IDENTITY_UNMAPPED'
                reasons.append(code)
                rec = {'dk_name': r['dk_name'], 'team': r['team'], 'pos': r['dk_pos'], 'salary': r['salary'],
                       'n_matches': len(m), 'code': code, 'roster_club': other or None,
                       'week_roster_status': wk[-1].get('status') if wk else None,
                       'week_roster_position': wk[-1].get('position') if wk else None,
                       'last_seen': (max(earlier, key=lambda x: int(x['week'])).get('status') + ' week '
                                     + max(earlier, key=lambda x: int(x['week']))['week']) if earlier and not wk
                                    else None}
                (unmatched if code in FAILS_POOL else explained).append(rec)
            st = (by_state.get(key) or {}).get('current_availability') or {}
            if st.get('designation') == 'OUT' or 'INACTIVE' in str(st.get('status')):
                reasons.append('NOT_PLAYING_OUT')
            if key in unresolved:
                reasons.append('ROSTER_HISTORY_UNRESOLVED')
        players.append({'dk_id': r['dk_id'], 'dk_name': r['dk_name'], 'team': r['team'], 'pos': r['dk_pos'],
                        'salary': r['salary'],
                        'upload': 'BLOCKED' if reasons else 'ELIGIBLE_PENDING_INACTIVES', 'reasons': reasons})
    res['IDENTITY_MAPPED'] = {'pass': not unmatched, 'unmatched': unmatched, 'matched_by': dict(how_matched),
                              'explained_by_roster': explained,
                              'explained_counts': dict(collections.Counter(x['code'] for x in explained))}
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
