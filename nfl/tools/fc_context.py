#!/usr/bin/env python3.12
"""FantasyCruncher as EXTERNAL_FC_CONTEXT. A reader that cannot become a feature.

WHY A SEPARATE MODULE AND NOT A FLAG ON `dk_universe.load()`. `dk_universe.load()`
strips every third-party projection column at parse time and names them as it drops
them. That is the quarantine working, and widening it to "return them when asked" would
put the firewall one keyword argument away from being open. So the values are read here
instead, in a module that no proprietary layer imports.

THE FIREWALL IS STRUCTURAL, NOT A COMMENT.

  1. Every value comes back inside a dict whose key is `EXTERNAL_FC_CONTEXT`, wrapped
     per field with its source and retrieval time. There is no bare float to
     accidentally assign to a feature.
  2. `assert_no_proprietary_importer()` inspects the live import graph and REFUSES if a
     proprietary module is on the stack. The refusal happens before any value is
     returned, so a proprietary caller gets an exception rather than a number.
  3. A test asserts that no module under the proprietary prefixes imports this file.

WHAT THIS FILE IS NOT. It is not a projection source, not a benchmark we tune toward,
and not a tie-breaker. Its only legitimate uses are owner-facing display and diagnosing
where an external opinion differs from our observed role evidence -- and the second one
is a question about FC, never a correction to us.

ONE FINDING ABOUT THE EXPORT ITSELF, AND IT MATTERS BEFORE ANYONE READS A NUMBER FROM
IT. The file carries both `FC`/`FC Proj` and `My`/`My Proj` columns plus a `Diff`. In
all 273 rows `My` is byte-identical to `FC` and `Diff` is zero. The `My Proj` column is
therefore FC echoed back, not a second opinion, and certainly not ours. Anybody reading
`My Proj` as a proprietary number would be reading FantasyCruncher.
"""
from __future__ import annotations

import csv
import hashlib
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'fc-context-2026w3-1'
CONTEXT_KEY = 'EXTERNAL_FC_CONTEXT'

SRC = (_REPO / 'nfl/dfs/salaries/raw'
       / 'THIRDPARTY_players_EARLY_ONLY_2026W3_POSTINACTIVES_CONTEXT_ONLY.csv')

RETRIEVED = '2026-09-27 post-inactives, relayed by the owner'
SOURCE_NAME = 'FantasyCruncher DraftKings NFL 2026 week 3 export'

#: Any module whose name starts with one of these may not read this file.
PROPRIETARY_PREFIXES = (
    'nfl.production', 'nfl.research.qb2', 'nfl.research.v4', 'nfl.research.shadow',
    'nfl.features', 'nfl.model', 'sportsplatform.engine',
)

FIELDS = ('FC Proj', 'Floor', 'Ceiling', 'Exp.', 'Used', 'Con.', 'Value',
          'VegasPts', 'STDV', '2025 Avg', '2026 Avg', 'Def v Pos', 'pDepth')

NOT_A_MODEL_INPUT = (
    'EXTERNAL COMPARISON ONLY. No value in this block may enter a proprietary feature, '
    'be averaged against our numbers, calibrate anything, or break a tie. It is here to '
    'be looked at and to be disagreed with.')

MY_PROJ_IS_FC = (
    'the export carries a `My`/`My Proj` column and a `Diff`. In all 273 rows `My` is '
    'byte-identical to `FC` and `Diff` is 0.0, so `My Proj` is FantasyCruncher echoed '
    'back rather than a second opinion. It is not ours and is deliberately not read.')


class ProprietaryImportRefused(RuntimeError):
    """Raised when a proprietary module tries to read external FC values."""


def assert_no_proprietary_importer():
    """Refuse if a proprietary module is on the import graph. Load-bearing.

    Checked before any value is returned, so a proprietary caller receives an exception
    instead of a projection.
    """
    offenders = sorted(m for m in list(sys.modules)
                       if any(m == p or m.startswith(p + '.')
                              for p in PROPRIETARY_PREFIXES))
    if offenders:
        return Outcome.fail(
            'FC_READ_FROM_PROPRIETARY_CONTEXT',
            f'{len(offenders)} proprietary module(s) are imported in this process, so '
            f'external FantasyCruncher values will not be returned: {offenders[:6]}. '
            f'Read them from a process that holds no proprietary layer.',
            offenders=offenders[:20], n_offenders=len(offenders))
    return Outcome.ok('FC_READ_CONTEXT_CLEAN', 0,
                      'no proprietary module on the import graph')


def _digest() -> str:
    return hashlib.sha256(SRC.read_bytes()).hexdigest()


def _num(v):
    v = (v or '').strip().replace('%', '')
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return v


def load():
    """FC rows keyed by (name, team), each value wrapped and labelled."""
    guard = assert_no_proprietary_importer()
    if guard.state.value != 'PASS':
        return guard
    if not SRC.exists():
        return Outcome.blocked('FC_EXPORT_ABSENT', f'{SRC.name} not in tree',
                               cause=Cause.DATA)
    rows = list(csv.reader(SRC.open(newline='', encoding='utf-8-sig')))
    hdr_i = next((i for i, r in enumerate(rows)
                  if 'Player' in [c.strip() for c in r]), None)
    if hdr_i is None:
        return Outcome.fail('FC_EXPORT_SCHEMA', 'no header row containing Player')
    hdr = [c.strip() for c in rows[hdr_i]]
    idx = {c: i for i, c in enumerate(hdr)}
    missing = [f for f in ('Player', 'Team', 'Pos', 'Salary', 'FC Proj') if f not in idx]
    if missing:
        return Outcome.fail('FC_EXPORT_SCHEMA', f'export lacks {missing}')
    out, digest = {}, _digest()
    for r in rows[hdr_i + 1:]:
        if len(r) <= idx['Player'] or not r[idx['Player']].strip():
            continue
        name = r[idx['Player']].strip()
        team = r[idx['Team']].strip()
        vals = {f: _num(r[idx[f]]) for f in FIELDS if f in idx and len(r) > idx[f]}
        out[(name, team)] = {
            CONTEXT_KEY: vals,
            'fc_pos': r[idx['Pos']].strip(),
            'fc_salary': _num(r[idx['Salary']]),
            'fc_opponent': r[idx['Opp']].strip() if 'Opp' in idx else None,
            'source': SOURCE_NAME,
            'source_sha256': digest,
            'retrieved': RETRIEVED,
            'NOT_A_MODEL_INPUT': NOT_A_MODEL_INPUT,
            'MY_PROJ_IS_FC': MY_PROJ_IS_FC,
        }
    if not out:
        return Outcome.fail('FC_EXPORT_EMPTY', 'export parsed to zero player rows')
    return Outcome.ok('FC_CONTEXT_LOADED', out, f'{len(out)} FC rows',
                      n_rows=len(out), sha256=digest)


#: Declared aliases from FC spelling to the authoritative DK 457 spelling.
FC_TO_DK = {
    ('JaMarr Chase', 'CIN'): "Ja'Marr Chase",
    ('James Cook', 'BUF'): 'James Cook III',
    ('Kenneth Walker III', 'KC'): 'Kenneth Walker III',
    ('Michael Pittman', 'PIT'): 'Michael Pittman Jr.',
    ('KC Concepcion', 'CLE'): 'KC Concepcion Jr.',
    ('Demario Douglas', 'NE'): 'DeMario Douglas',
    ('Erick All Jr', 'CIN'): 'Erick All Jr.',
    ('Nick Westbrook', 'IND'): 'Nick Westbrook-Ikhine',
    ('Josh Palmer', 'BUF'): 'Joshua Palmer',
    ('A.J. Dillon', 'CAR'): 'AJ Dillon',
    ('Velus Jones', 'SEA'): 'Velus Jones Jr.',
    ('Lew Nichols III', 'PIT'): 'Lew Nichols',
    ('Andrew Ogletree', 'IND'): 'Drew Ogletree',
}
FC_TEAM_TO_DK = {'JAC': 'JAX'}
DST_NAME = re.compile(r'^(Bengals|Texans|Seahawks|Panthers|Steelers|Giants|Titans|'
                      r'Bills|Browns|Patriots|Lions|Chiefs|Commanders|Jets|Dolphins|'
                      r'Chargers|Colts|Jaguars)$')


def join_to_dk(fc_rows, dk_players):
    """Map FC rows onto DK dk_ids. Returns (by_dk_id, fc_only, dk_only)."""
    by_name = {}
    for dk_id, v in dk_players.items():
        by_name[(v['name'], v['team'])] = dk_id
    joined, fc_only = {}, []
    for (name, team), row in fc_rows.items():
        t = FC_TEAM_TO_DK.get(team, team)
        n = FC_TO_DK.get((name, team), name)
        dk_id = by_name.get((n, t))
        if dk_id is None and DST_NAME.match(name):
            dk_id = next((k for k, v in dk_players.items()
                          if v['position'] == 'DST' and v['team'] == t), None)
        if dk_id is None:
            fc_only.append({'fc_name': name, 'fc_team': team,
                            'fc_pos': row['fc_pos'], 'fc_salary': row['fc_salary'],
                            'reason': 'no DK row under this name and club'})
            continue
        joined[dk_id] = row
    dk_only = sorted(set(dk_players) - set(joined))
    return joined, fc_only, dk_only


def main() -> int:
    import json
    r = load()
    print(r)
    if r.state.value != 'PASS':
        return 1
    post = json.loads(
        (_REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json').read_text())
    joined, fc_only, dk_only = join_to_dk(r.value, post['players'])
    print(f'joined {len(joined)} | fc_only {len(fc_only)} | dk_only {len(dk_only)}')
    for x in fc_only[:10]:
        print('  FC-only:', x['fc_name'], x['fc_team'], x['fc_pos'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
