"""The DraftKings salary/eligibility universe. NOT a football input, structurally.

WHERE THIS SITS, AND WHY THE ORDER IS NOT NEGOTIABLE

    football simulation -> player distributions -> DK scoring
      -> salary / eligible universe -> lineup construction

Everything in this module is the fourth arrow. It supplies WHO may be rostered
and WHAT THEY COST. It supplies no estimate of how anyone will play.

THE COLUMN SPLIT IS ENFORCED, NOT DOCUMENTED
--------------------------------------------
The delivered file carries fourteen columns of third-party projection, market
and optimizer output: Def v Pos, VegasPts, STDV, FC, My, Diff, Floor, Ceiling,
FC Proj, My Proj, Exp., Used, Con., Value. A comment saying "do not use these"
is worth nothing -- the next reader takes the whole row because the whole row
is there.

So `load()` never returns them. They are dropped at parse time, the dropped
set is reported by name, and `forbidden_columns()` exists so a test can assert
the list rather than trust it. A caller that wants them gets a named refusal,
because the honest failure is a refusal and the dishonest one is a value.

`2025 Avg` and `2026 Avg` are dropped with the same treatment. They are
descriptive rather than projected, but the directive authorises them only
"unless separately justified", and nobody has justified them, so the module
does not carry them and says why.

THE HEADER IS ON LINE 2, AND THAT IS A TRAP
-------------------------------------------
The file opens with a row of twenty-three commas. `csv.DictReader` over the
bytes as delivered takes that line as the header and returns 537 rows keyed by
the empty string -- every meaningful column blank, no error raised. That is the
shape of the 7,926-row export this project already had to diagnose once. So
the header is LOCATED by finding the row whose first cell is `Player`, and
`HeaderNotFound` is raised if there is none.

TEAM CODES DIFFER AND THE CROSSWALK IS DECLARED
-----------------------------------------------
DraftKings writes JAC and LAR where this repository writes JAX and LA. Two
codes, both unambiguous, both stated below. Nothing is guessed by string
distance: a DK code absent from `DK_TO_CANONICAL` and absent from our own set
is refused by name.

ELIGIBILITY IS NOT INFERRED FROM THE FILE
-----------------------------------------
The file holds all 32 clubs and all 16 Week-2 games. A DK Classic main slate is
a CONTEST, and which games a contest covers is a fact about that contest, not
about this file. So the raw universe and the main-slate universe are separate
objects, and the second one stays UNRESOLVED until the contest's game set is
supplied. One exclusion is made without the contest, because it needs no
knowledge of DraftKings at all: DET@BUF kicked off 2026-09-18T00:15Z and is
already played, so its rows cannot belong to a contest that has not locked.
That is a clock fact. Every other game is UNRESOLVED, not excluded.
"""
from __future__ import annotations

import csv
import collections
import gzip
import hashlib
import io
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'dk-salary-universe-1'

#: The delivered artifact, by content hash. Named rather than globbed: a glob
#: would silently pick up a second delivery and change what "the universe" is.
BLOB = _REPO / 'nfl' / 'vintage' / 'dk_salaries.c143c94f152a7d6b.csv.gz'
BLOB_SHA256 = ('c143c94f152a7d6bfb07ee84e5d88502'
               'c831fc672c0f7dc011984d85b28b2bec')

#: What a row may carry into anything downstream.
KEPT_COLUMNS = ('Player', 'Pos', 'Salary', 'Team', 'Opp')

#: Kept, and quarantined: read only against governed evidence, never alone.
RECONCILE_ONLY_COLUMNS = ('Inj', 'pDepth')

#: Dropped at parse time. Each one says which family it belongs to, because
#: "third-party projection" and "ownership estimate" are different objections
#: and a single label would hide that.
FORBIDDEN_COLUMNS = {
    'Def v Pos': 'third-party opponent-strength rating',
    'VegasPts': 'sportsbook-derived team total',
    'STDV': 'third-party dispersion estimate',
    '2025 Avg': 'prior-season scoring average -- descriptive, but not '
                'separately justified, so not carried',
    '2026 Avg': 'current-season scoring average -- same',
    'FC': 'third-party projection',
    'My': 'third-party projection',
    'Diff': 'difference of two third-party projections',
    'Floor': 'third-party quantile',
    'Ceiling': 'third-party quantile',
    'FC Proj': 'third-party projection',
    'My Proj': 'third-party projection',
    'Exp.': 'ownership expectation',
    'Used': 'ownership/exposure metric',
    'Con.': 'optimizer confidence metric',
    'Value': 'points-per-dollar, a function of a third-party projection',
    'Likes': 'third-party sentiment metric',
}

#: DraftKings club codes that differ from this repository's. Declared, not
#: matched by similarity.
DK_TO_CANONICAL = {'JAC': 'JAX', 'LAR': 'LA'}

#: Names DraftKings writes differently from the roster, with the evidence that
#: makes each one a FACT rather than a similarity. An alias is honoured only
#: when it resolves to exactly one canonical player ON THE SAME CLUB; if it
#: resolves to none or to several the row stays unmatched, so a stale alias
#: degrades to a refusal rather than to a wrong join.
#:
#: This table is the only place a name may be rewritten. There is no edit
#: distance anywhere in this package, because a matcher that scores names will
#: eventually join two different people and will never say so.
NAME_ALIASES = {
    ('Hollywood Brown', 'PHI'): {
        'canonical': 'Marquise Brown',
        'evidence': '"Hollywood" is the nickname DraftKings prints for '
                    'Marquise Brown. The 2026 week-2 roster capture holds '
                    'exactly one Marquise Brown -- 00-0035662, PHI, WR, '
                    'status ACT -- and no player named Hollywood in any club. '
                    'Same club, same position, unique. Recorded as an alias '
                    'rather than matched by similarity.',
    },
}

#: Already played at 2026-09-18T00:15Z. Excluded on the clock, not on any
#: assumption about how DraftKings builds a slate.
PLAYED_BEFORE_NOW = {('BUF', 'DET')}

MATCH_EXACT = 'EXACT_NAME_TEAM'
MATCH_NORMALIZED = 'NORMALIZED_NAME_TEAM'
MATCH_NAME_ONLY = 'NORMALIZED_NAME_ONLY_TEAM_DISAGREES'
MATCH_ALIAS = 'DECLARED_ALIAS'
STATUS_MATCHED = 'MATCHED_CANONICAL'
STATUS_AMBIGUOUS = 'AMBIGUOUS'
STATUS_UNMATCHED = 'UNMATCHED'
STATUS_DST = 'DST'


class HeaderNotFound(RuntimeError):
    """The file has no row beginning `Player`. Refuse rather than guess."""


class ForbiddenColumn(RuntimeError):
    """Someone asked this module for a projection column."""


def forbidden_columns() -> tuple:
    return tuple(sorted(FORBIDDEN_COLUMNS))


def column_disposition(name: str) -> str:
    if name in KEPT_COLUMNS:
        return 'KEPT_SALARY_AND_UNIVERSE'
    if name in RECONCILE_ONLY_COLUMNS:
        return 'KEPT_FOR_RECONCILIATION_ONLY'
    if name in FORBIDDEN_COLUMNS:
        raise ForbiddenColumn(
            f'{name!r} is {FORBIDDEN_COLUMNS[name]} and is dropped at parse '
            f'time. It may not enter a football layer, and there is no flag '
            f'that turns it on.')
    return 'UNKNOWN_COLUMN'


def _norm_name(s: str) -> str:
    """Casefold, strip punctuation and generational suffixes.

    Deliberately crude and deliberately NOT fuzzy. It collapses `A.J. Brown`
    and `AJ Brown`, `Marvin Harrison Jr.` and `Marvin Harrison`. It will not
    collapse two different people, because it never measures distance -- two
    names either normalise to the same string or they do not.
    """
    s = s.strip().lower()
    s = re.sub(r"[.'`’-]", '', s)
    s = re.sub(r'\s+(jr|sr|ii|iii|iv|v)$', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def _opponent(cell: str):
    """('SEA', is_home). The file writes both `@ SEA` and `vs SEA`."""
    s = cell.strip()
    home = not s.startswith('@')
    return re.sub(r'^(@|vs)\s*', '', s).strip(), home


def load(path=None) -> Outcome:
    """Parse the delivered file into salary/universe rows. Nothing else."""
    p = pathlib.Path(path) if path else BLOB
    if not p.exists():
        return Outcome.blocked(
            'DK_SALARY_BLOB_ABSENT',
            f'{p} is not in the vintage store. The universe is not '
            f'reconstructed from memory.', cause=Cause.DATA, path=str(p))
    raw = (gzip.decompress(p.read_bytes()) if str(p).endswith('.gz')
           else p.read_bytes())
    sha = hashlib.sha256(raw).hexdigest()
    lines = raw.decode('utf-8-sig').splitlines()
    table = list(csv.reader(lines))
    hdr_i = next((i for i, r in enumerate(table)
                  if r and r[0].strip() == 'Player'), None)
    if hdr_i is None:
        raise HeaderNotFound(
            f'{p}: no row begins with `Player`. The delivered file opens with '
            f'a row of commas, so a reader that takes line 1 as the header '
            f'produces rows keyed by the empty string and raises nothing.')
    header = [c.strip() for c in table[hdr_i]]
    dropped = [c for c in header if c in FORBIDDEN_COLUMNS]
    rows, bad = [], []
    for r in table[hdr_i + 1:]:
        if not any(c.strip() for c in r):
            continue
        d = dict(zip(header, r))
        opp, is_home = _opponent(d.get('Opp', ''))
        dk_team = (d.get('Team') or '').strip()
        sal_raw = (d.get('Salary') or '').strip()
        try:
            salary = int(sal_raw)
        except ValueError:
            salary = None
            bad.append({'player': d.get('Player'), 'salary_raw': sal_raw})
        rows.append({
            'dk_name': (d.get('Player') or '').strip(),
            'dk_pos': (d.get('Pos') or '').strip(),
            'dk_team': dk_team,
            'team': DK_TO_CANONICAL.get(dk_team, dk_team),
            'dk_opp': opp,
            'opponent': DK_TO_CANONICAL.get(opp, opp),
            'is_home': is_home,
            'salary': salary,
            'inj_flag': (d.get('Inj') or '').strip() or None,
            'dk_depth': (d.get('pDepth') or '').strip() or None,
        })
    ev = {
        'spec_version': SPEC_VERSION, 'blob': str(p), 'sha256': sha,
        'sha256_matches_declared': sha == BLOB_SHA256,
        'header_row_index': hdr_i, 'n_columns': len(header),
        'n_rows': len(rows),
        'columns_kept': list(KEPT_COLUMNS),
        'columns_reconcile_only': list(RECONCILE_ONLY_COLUMNS),
        'columns_dropped': sorted(dropped),
        'n_columns_dropped': len(dropped),
        'malformed_salaries': bad,
        'team_code_crosswalk': dict(DK_TO_CANONICAL),
    }
    if not rows:
        return Outcome.blocked(
            'DK_SALARY_FILE_EMPTY',
            'the file parsed and produced zero rows. Zero is an error, not a '
            'universe.', cause=Cause.DATA, **ev)
    return Outcome.ok('DK_SALARY_UNIVERSE_LOADED', value=rows,
                      detail=f'{len(rows)} row(s), {len(dropped)} projection '
                             f'column(s) dropped at parse time', **ev)


def matchups(rows) -> dict:
    """Canonical (away, home) pairs present in the file."""
    out = {}
    for r in rows:
        a, b = ((r['opponent'], r['team']) if r['is_home']
                else (r['team'], r['opponent']))
        out.setdefault((a, b), 0)
        out[(a, b)] += 1
    return out


def raw_universe(rows) -> dict:
    """RAW_DK_WEEK2_UNIVERSE. Everything in the file, nothing judged eligible."""
    mu = matchups(rows)
    sal = [r['salary'] for r in rows if r['salary'] is not None]
    return {
        'name': 'RAW_DK_WEEK2_UNIVERSE', 'spec_version': SPEC_VERSION,
        'n_rows': len(rows),
        'n_teams': len({r['team'] for r in rows}),
        'teams': sorted({r['team'] for r in rows}),
        'n_matchups': len(mu),
        'matchups': [{'away': a, 'home': h, 'rows': n}
                     for (a, h), n in sorted(mu.items())],
        'position_counts': dict(
            collections.Counter(r['dk_pos'] for r in rows)),
        'salary_min': min(sal) if sal else None,
        'salary_max': max(sal) if sal else None,
        'n_salary_missing': sum(1 for r in rows if r['salary'] is None),
        'duplicate_names': [n for n, c in collections.Counter(
            r['dk_name'] for r in rows).items() if c > 1],
        'eligibility': 'NOT_ASSESSED_HERE -- a contest decides it',
    }


def main_slate(rows, contest_games=None) -> Outcome:
    """DK_WEEK2_MAIN_SLATE_ELIGIBLE_UNIVERSE, or a refusal.

    `contest_games` is the DK Classic contest's own (away, home) set. Without
    it this DEFERS. It does not fall back on "the Sunday afternoon games",
    which is a convention about how slates are usually built and not a fact
    about this contest.
    """
    mu = matchups(rows)
    played = sorted({tuple(sorted(g)) for g in mu} & PLAYED_BEFORE_NOW)
    ev = {'spec_version': SPEC_VERSION,
          'games_in_file': [{'away': a, 'home': h} for a, h in sorted(mu)],
          'n_games_in_file': len(mu),
          'excluded_already_played': [list(g) for g in played],
          'excluded_already_played_rows': sum(
              n for (a, h), n in mu.items()
              if tuple(sorted((a, h))) in PLAYED_BEFORE_NOW)}
    if not contest_games:
        return Outcome.deferred(
            'DK_MAIN_SLATE_GAME_SET_NOT_SUPPLIED',
            'the contest\'s game set has not been supplied, so which of the '
            f'{len(mu)} games in this file are on the Classic main slate is '
            'unresolved. It is NOT inferred from the file, which carries all '
            '32 clubs, nor from the usual shape of a main slate. One game is '
            'excluded on the clock rather than on a contest rule: '
            f'{[list(g) for g in played]} already kicked off.',
            owed='the DK Classic contest game list', **ev)
    want = {tuple(x) for x in contest_games}
    unknown = sorted(want - set(mu))
    if unknown:
        return Outcome.fail(
            'DK_CONTEST_GAME_NOT_IN_FILE',
            f'the supplied contest names {len(unknown)} game(s) absent from '
            f'the salary file: {unknown}. A contest wider than the file is a '
            f'coverage defect, not a smaller universe.', **ev)
    keep = [r for r in rows
            if ((r['opponent'], r['team']) if r['is_home']
                else (r['team'], r['opponent'])) in want]
    return Outcome.ok(
        'DK_MAIN_SLATE_RESOLVED', value=keep,
        detail=f'{len(keep)} of {len(rows)} row(s) on {len(want)} contest '
               f'game(s)', n_eligible_rows=len(keep), **ev)


if __name__ == '__main__':
    o = load()
    print(o.state.value, o.code, '--', o.detail)
    if o.state is State.PASS:
        print(json.dumps(raw_universe(o.value), indent=1)[:2000])
        m = main_slate(o.value)
        print('\nmain slate:', m.state.value, m.code)
        print(' ', m.detail)
