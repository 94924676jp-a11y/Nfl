"""The owner's DraftKings Early Only contest universe, from DraftKings' own export.

WHY THE ENTRIES FILE IS THE AUTHORITY AND THE SALARY FILE IS NOT

Two files arrived for this slate. `DKEntries (50).csv` is DraftKings' own
export: it carries the owner's 73 entries AND, in a second block, the contest
player pool with official DK player IDs, `Roster Position` (which states FLEX
eligibility outright) and `Game Info` (which carries each game's kickoff).
`draftkings_NFL_2026-week-2_players (2).csv` is a FantasyCruncher-style view
of the same slate -- useful, third-party, and 153 players smaller.

So the CONTEST UNIVERSE is read from the entries export and the other file is
treated as a secondary salary source to cross-check against it. An export from
the site is primary evidence about the site's own contest; a third-party
rendering of it is not.

THIS RESOLVES THE SLATE WITH EVIDENCE RATHER THAN WITH PERMISSION

`dk_universe.main_slate()` still DEFERS on the full-week file, and correctly:
it holds all 32 clubs and nothing in it says which games a contest covers. It
is not resolved here because the owner said so. It is resolved because every
one of the 409 pool rows carries `Game Info` reading `09/20/2026 01:00PM ET`
and naming one of eight matchups -- DraftKings stating its own contest's game
set in its own file. The check below reads those instants rather than trusting
the count, and refuses if any row disagrees.

WHAT THIS MODULE STILL WILL NOT DO

Produce a projection. The salary universe being resolved changes nothing
upstream: `artifact_sealing` blocks every game of the slate on
`current_season_input_freshness`, so there is no sealed forecast to attach to
a salary. Coverage is reported per player with a precise reason; a number is
not invented for anybody.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import glob
import gzip
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.dfs.salaries import dk_universe as DK                       # noqa: E402

SPEC_VERSION = 'dk-early-only-1'

ENTRIES_BLOB = (_REPO / 'nfl' / 'vintage'
                / 'dk_entries.d89da3219126d6b5.csv.gz')
ENTRIES_SHA = ('d89da3219126d6b54fa3b16bb3b50b98'
               'ca67d667fcdaef5bbec3744350be4d05')
SALARY_BLOB = (_REPO / 'nfl' / 'vintage'
               / 'dk_salaries_early.b34b389ebe3efc16.csv.gz')
SALARY_SHA = ('b34b389ebe3efc16df57f9245bf66aba'
              'c8d06ad1d32bd683d941ee817498fbc3')

#: The kickoff every Early Only row must carry. Read from the file and
#: CHECKED, not assumed: a row naming any other instant means the export is
#: not a single-window slate and the universe is refused rather than filtered.
EARLY_KICKOFF = '09/20/2026 01:00PM ET'

#: DK writes the pool's roster slot outright, so FLEX eligibility is evidence
#: rather than a rule we reconstruct.
FLEX_SLOTS = ('RB/FLEX', 'WR/FLEX', 'TE/FLEX')

_GAME = re.compile(r'^([A-Z]{2,3})@([A-Z]{2,3})\s+(.*)$')


class PoolNotFound(RuntimeError):
    """The entries export has no player-pool block."""


def _read(blob, sha_declared):
    raw = gzip.decompress(pathlib.Path(blob).read_bytes())
    import hashlib
    sha = hashlib.sha256(raw).hexdigest()
    return raw, sha, sha == sha_declared


def entries(blob=None) -> Outcome:
    """The owner's contest entries: one row per entry, with its lineup."""
    raw, sha, ok = _read(blob or ENTRIES_BLOB, ENTRIES_SHA)
    rows = list(csv.reader(raw.decode('utf-8-sig').splitlines()))
    hdr = rows[0]
    out = []
    for r in rows[1:]:
        if not r or not (r[0] or '').strip().isdigit():
            continue
        d = dict(zip(hdr, r))
        out.append({
            'entry_id': d.get('Entry ID', '').strip(),
            'contest_name': d.get('Contest Name', '').strip(),
            'contest_id': d.get('Contest ID', '').strip(),
            'entry_fee': d.get('Entry Fee', '').strip(),
            'lineup': {k: (d.get(k) or '').strip()
                       for k in ('QB', 'TE', 'FLEX', 'DST')},
            'rb': [c for c, k in zip(r, hdr) if k == 'RB'],
            'wr': [c for c, k in zip(r, hdr) if k == 'WR'],
        })
    if not out:
        return Outcome.blocked(
            'DK_ENTRIES_EMPTY',
            'the entries export parsed and produced no entry rows. Zero is an '
            'error, not an empty contest list.', cause=Cause.DATA)
    fees = collections.Counter(e['entry_fee'] for e in out)
    total = sum(float(f.lstrip('$')) for f in
                (e['entry_fee'] for e in out) if f)
    return Outcome.ok(
        'DK_ENTRIES_LOADED', value=out,
        detail=f'{len(out)} entries across '
               f'{len({e["contest_id"] for e in out})} contest(s)',
        spec_version=SPEC_VERSION, sha256=sha, sha256_matches_declared=ok,
        n_entries=len(out),
        by_contest=dict(collections.Counter(e['contest_name'] for e in out)),
        by_fee=dict(fees), total_entered=round(total, 2))


def pool(blob=None) -> Outcome:
    """The contest player pool, with DraftKings' own IDs and roster slots."""
    raw, sha, ok = _read(blob or ENTRIES_BLOB, ENTRIES_SHA)
    rows = list(csv.reader(raw.decode('utf-8-sig').splitlines()))
    hi = next((i for i, r in enumerate(rows)
               if len(r) > 14 and (r[14] or '').strip() == 'Position'), None)
    if hi is None:
        raise PoolNotFound(
            'the entries export has no row whose 15th cell is `Position`, so '
            'it carries no player-pool block. The pool is not reconstructed '
            'from the entry lineups, which name only nine players.')
    hdr = [c.strip() for c in rows[hi][14:]]
    out, bad_game, bad_salary = [], [], []
    for r in rows[hi + 1:]:
        if len(r) <= 14 or not (r[14] or '').strip():
            continue
        d = dict(zip(hdr, [c.strip() for c in r[14:]]))
        gi = d.get('Game Info', '')
        m = _GAME.match(gi)
        if not m:
            bad_game.append({'name': d.get('Name'), 'game_info': gi})
            away = home = kick = None
        else:
            away, home, kick = m.group(1), m.group(2), m.group(3).strip()
        try:
            sal = int(d.get('Salary') or '')
        except ValueError:
            sal = None
            bad_salary.append({'name': d.get('Name'),
                               'salary_raw': d.get('Salary')})
        dk_team = (d.get('TeamAbbrev') or '').strip()
        out.append({
            'dk_id': (d.get('ID') or '').strip(),
            'dk_name': (d.get('Name') or '').strip(),
            'name_and_id': (d.get('Name + ID') or '').strip(),
            'dk_pos': (d.get('Position') or '').strip(),
            'roster_position': (d.get('Roster Position') or '').strip(),
            'flex_eligible': (d.get('Roster Position') or '').strip()
                             in FLEX_SLOTS,
            'salary': sal,
            'dk_team': dk_team,
            'team': DK.DK_TO_CANONICAL.get(dk_team, dk_team),
            'game_info': gi, 'kickoff': kick,
            'away': DK.DK_TO_CANONICAL.get(away, away) if away else None,
            'home': DK.DK_TO_CANONICAL.get(home, home) if home else None,
        })
    ev = {'spec_version': SPEC_VERSION, 'sha256': sha,
          'sha256_matches_declared': ok, 'n_rows': len(out),
          'pool_header_line': hi + 1,
          'malformed_game_info': bad_game, 'malformed_salaries': bad_salary}
    if not out:
        return Outcome.blocked('DK_POOL_EMPTY', 'zero pool rows.',
                               cause=Cause.DATA, **ev)
    return Outcome.ok('DK_POOL_LOADED', value=out,
                      detail=f'{len(out)} pool row(s)', **ev)


def slate(pool_rows) -> Outcome:
    """The contest's game set, READ from the export rather than supplied.

    Every row must name the same kickoff. A row that does not is reported and
    the universe is refused: a pool spanning two windows is not an Early Only
    slate, and filtering it down to the ones that agree would be choosing the
    answer.
    """
    kicks = collections.Counter(r['kickoff'] for r in pool_rows)
    games = collections.Counter((r['away'], r['home']) for r in pool_rows)
    ev = {'spec_version': SPEC_VERSION,
          'kickoffs_present': dict(kicks),
          'games': [{'away': a, 'home': h, 'pool_rows': n}
                    for (a, h), n in sorted(games.items())],
          'n_games': len(games),
          'teams': sorted({r['team'] for r in pool_rows}),
          'n_teams': len({r['team'] for r in pool_rows}),
          'declared_kickoff': EARLY_KICKOFF}
    odd = sorted(k for k in kicks if k != EARLY_KICKOFF)
    if odd:
        return Outcome.fail(
            'DK_POOL_SPANS_MORE_THAN_ONE_WINDOW',
            f'the pool names {len(kicks)} distinct kickoff(s): {odd}. An '
            f'Early Only universe is one window; filtering the disagreeing '
            f'rows away would be choosing the answer rather than reading it.',
            **ev)
    return Outcome.ok(
        'DK_EARLY_SLATE_RESOLVED_FROM_EXPORT',
        value=sorted(games),
        detail=f'{len(games)} game(s), {ev["n_teams"]} club(s), every pool '
               f'row at {EARLY_KICKOFF}', **ev)


def secondary_salaries(blob=None) -> Outcome:
    """The FantasyCruncher-style file, for cross-checking salary only.

    Its projection columns go through the same wall as the full-week file --
    `dk_universe.load()` drops them at parse time -- so nothing here can carry
    a third-party number into anything.
    """
    o = DK.load(blob or SALARY_BLOB)
    if o.state is not State.PASS:
        return o
    return o


if __name__ == '__main__':
    e, p = entries(), pool()
    print(f'{e.state.value}[{e.code}] {e.detail}')
    print('  by contest:', json.dumps(e.evidence['by_contest'], indent=None))
    print('  total entered: $%.2f' % e.evidence['total_entered'])
    print(f'{p.state.value}[{p.code}] {p.detail}')
    s = slate(p.value)
    print(f'{s.state.value}[{s.code}] {s.detail}')
    for g in s.evidence['games']:
        print(f"    {g['away']:4s} @ {g['home']:4s}  {g['pool_rows']} players")
