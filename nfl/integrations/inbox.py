#!/usr/bin/env python3.12
"""The drop folder: the owner's manual exports, recognised by their own headers and stored by content.

    python3.12 nfl/integrations/inbox.py                 # ingest every file in nfl/dfs/inbox/drop/
    python3.12 nfl/integrations/inbox.py --list          # what has been ingested, newest first

WHY. DraftKings and Fantasy Cruncher both prohibit automated access in their terms, so the only
route their data may take into this system is a file the owner downloaded by hand. That file should
need no renaming, no typing of hashes and no copy-and-paste: drop it here and it is classified by
the cells of its header (never by its file name), copied into a content-addressed store, and
recorded with provenance in an append-only ledger.

RECOGNISED KINDS (the signatures are the files' own columns):
  DK_SALARIES            a row starting `Position, Name + ID, Name, ID, Roster Position, Salary,
                         Game Info, TeamAbbrev` and no `Entry ID` column. Classic or Showdown is
                         read from the roster positions (`CPT` means Showdown).
  DK_ENTRIES             first row carries `Entry ID, Contest Name, Contest ID, Entry Fee`.
                         ACCOUNT_PRIVATE: the owner's entries and fees. Read only, never re-uploaded.
  DK_CONTEST_STANDINGS   first row carries `Rank, EntryId, EntryName, Points, Lineup` and the
                         ownership block `Player, Roster Position, %Drafted, FPTS`. POSTLOCK ONLY:
                         realised ownership is never available before lock and is labelled so.
  FC_PLAYERS_EXPORT      a row carrying `Player, Pos, Salary, Team, Opp` and an FC projection
                         column. BENCHMARK, NEVER A MODEL INPUT.

Anything else is refused with a named code and recorded, so an unrecognised file is visible on the
status board rather than silently ignored. Nothing is deleted: the original stays in the drop folder
and a second ingest of the same bytes is a no-op (INBOX_ALREADY_INGESTED).
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'inbox-1'
DROP = _REPO / 'nfl' / 'dfs' / 'inbox' / 'drop'
STORE = _REPO / 'nfl' / 'dfs' / 'inbox' / 'store'
LEDGER = _REPO / 'nfl' / 'dfs' / 'inbox' / 'INBOX_LEDGER.jsonl'

DK_POOL_COLS = ('Position', 'Name + ID', 'Name', 'ID', 'Roster Position', 'Salary', 'Game Info', 'TeamAbbrev')
DK_ENTRY_COLS = ('Entry ID', 'Contest Name', 'Contest ID', 'Entry Fee')
DK_STANDINGS_COLS = ('Rank', 'EntryId', 'EntryName', 'Points', 'Lineup')
DK_OWNERSHIP_COLS = ('Player', 'Roster Position', '%Drafted', 'FPTS')
FC_COLS = ('Player', 'Pos', 'Salary', 'Team', 'Opp')
FC_PROJ_COLS = ('FC Proj', 'FC')

KIND_POLICY = {
    'DK_SALARIES': {'role': 'CONTEST_PRICING_AND_DK_IDS_ONLY', 'privacy': 'NOT_PRIVATE',
                    'never_model_input': False, 'available_prelock': True,
                    'football_input': False,
                    'note': 'Prices and ids assign players to contests; they are never a football input.'},
    'DK_ENTRIES': {'role': 'OWNER_ENTRY_TEMPLATE', 'privacy': 'ACCOUNT_PRIVATE',
                   'never_model_input': True, 'available_prelock': True, 'football_input': False,
                   'note': 'The owner\'s own entries and fees. Read only; this system never uploads or edits them.'},
    'DK_CONTEST_STANDINGS': {'role': 'POSTGAME_GRADING_AND_REALISED_OWNERSHIP', 'privacy': 'THIRD_PARTY_USERNAMES',
                             'never_model_input': True, 'available_prelock': False, 'football_input': False,
                             'note': 'Realised ownership exists only after lock. Never a prelock input for the '
                                     'contest it describes; usable for later slates only as history.'},
    'FC_PLAYERS_EXPORT': {'role': 'BENCHMARK_CONTEXT_ONLY', 'privacy': 'LICENSED_PERSONAL_USE',
                          'never_model_input': True, 'available_prelock': True, 'football_input': False,
                          'note': 'Fantasy Cruncher projections are an independent comparison, never a model input. '
                                  'FC terms: personal, non-commercial use; not redistributed.'},
}


def _now():
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _cells(r):
    return [(c or '').strip() for c in r]


def _has_run(cells, cols):
    """Index where `cols` appear contiguously in `cells`, or None."""
    n = len(cols)
    for j in range(len(cells) - n + 1):
        if tuple(cells[j:j + n]) == cols:
            return j
    return None


def classify(rows):
    """(kind, detail) from the parsed CSV rows, or (None, reason)."""
    if not rows:
        return None, 'no rows'
    first = _cells(rows[0])
    if all(c in first for c in DK_STANDINGS_COLS):
        if not all(c in first for c in DK_OWNERSHIP_COLS):
            return None, 'standings header without the ownership block (Player, Roster Position, %Drafted, FPTS)'
        return 'DK_CONTEST_STANDINGS', 'standings header in row 1'
    if all(c in first for c in DK_ENTRY_COLS):
        return 'DK_ENTRIES', 'entries header in row 1'
    for i, r in enumerate(rows[:12]):
        cells = _cells(r)
        j = _has_run(cells, DK_POOL_COLS)
        if j is not None:
            return 'DK_SALARIES', f'pool header at row {i + 1}, column {j + 1}'
        if all(c in cells for c in FC_COLS) and any(c in cells for c in FC_PROJ_COLS):
            return 'FC_PLAYERS_EXPORT', f'FC header at row {i + 1}'
    return None, f'first row {first[:8]} matches no recognised export'


def _dk_salaries_summary(rows):
    hi = None
    for i, r in enumerate(rows):
        j = _has_run(_cells(r), DK_POOL_COLS)
        if j is not None:
            hi, off = i, j
            break
    hdr = _cells(rows[hi])[off:]
    recs = []
    for r in rows[hi + 1:]:
        if len(r) <= off or not (r[off] or '').strip():
            continue
        recs.append(dict(zip(hdr, _cells(r)[off:])))
    if not recs:
        return Outcome.blocked('INBOX_DK_POOL_EMPTY', 'the salary header parsed and no player rows follow it',
                               cause=Cause.DATA)
    ids = collections.Counter(d.get('ID') for d in recs)
    dup = sorted(k for k, v in ids.items() if v > 1)
    if dup:
        return Outcome.fail('INBOX_DUPLICATE_DK_ID', f'{len(dup)} DK id(s) appear more than once: {dup[:5]}')
    games, kicks, bad_sal = set(), set(), 0
    for d in recs:
        m = re.match(r'^([A-Z]{2,3})@([A-Z]{2,3})\s+(.*)$', d.get('Game Info', ''))
        if m:
            games.add(f'{m.group(1)}@{m.group(2)}')
            kicks.add(m.group(3).strip())
        try:
            int(d.get('Salary') or '')
        except ValueError:
            bad_sal += 1
    rp = {d.get('Roster Position', '') for d in recs}
    return Outcome.ok('INBOX_SUMMARY', value={
        'game_type': 'SHOWDOWN' if any('CPT' in x for x in rp) else 'CLASSIC',
        'n_players': len(recs), 'n_games': len(games), 'games': sorted(games), 'kickoffs': sorted(kicks),
        'by_position': dict(collections.Counter(d.get('Position') for d in recs)),
        'malformed_salaries': bad_sal, 'pool_header_row': hi + 1, 'pool_header_column': off + 1})


def _dk_entries_summary(rows):
    hdr = _cells(rows[0])
    ent = [dict(zip(hdr, _cells(r))) for r in rows[1:] if r and (r[0] or '').strip().isdigit()]
    if not ent:
        return Outcome.blocked('INBOX_DK_ENTRIES_EMPTY', 'the entries header parsed and no entry rows follow it',
                               cause=Cause.DATA)
    has_pool = any(_has_run(_cells(r), DK_POOL_COLS) is not None for r in rows[:12])
    return Outcome.ok('INBOX_SUMMARY', value={
        'n_entries': len(ent), 'n_contests': len({e.get('Contest ID') for e in ent}),
        'contest_ids': sorted({e.get('Contest ID') for e in ent}), 'carries_player_pool': has_pool})


def _standings_summary(rows, original_name):
    hdr = _cells(rows[0])
    ix = {c: hdr.index(c) for c in DK_OWNERSHIP_COLS}
    n_entries, own, bad = 0, 0, []
    for r in rows[1:]:
        c = _cells(r) + [''] * (len(hdr) - len(r))
        if c[hdr.index('EntryId')]:
            n_entries += 1
        if c[ix['Player']]:
            own += 1
            try:
                float(c[ix['%Drafted']].rstrip('%'))
            except ValueError:
                bad.append(c[ix['Player']])
    if bad:
        return Outcome.fail('INBOX_STANDINGS_OWNERSHIP_UNPARSEABLE',
                            f'{len(bad)} player(s) with unparseable %Drafted, e.g. {bad[:3]}; refused whole, '
                            f'because a dropped player would read as zero-owned')
    if not own or not n_entries:
        return Outcome.blocked('INBOX_STANDINGS_EMPTY', f'{n_entries} entries, {own} ownership rows',
                               cause=Cause.DATA)
    m = re.search(r'(\d{6,})', original_name)
    return Outcome.ok('INBOX_SUMMARY', value={'n_entries': n_entries, 'n_ownership_rows': own,
                                              'contest_id_from_filename': m.group(1) if m else None})


def _fc_summary(rows):
    for i, r in enumerate(rows[:12]):
        cells = _cells(r)
        if all(c in cells for c in FC_COLS):
            hdr = cells
            break
    recs = [dict(zip(hdr, _cells(r))) for r in rows[i + 1:] if r and (r[0] or '').strip()]
    if not recs:
        return Outcome.blocked('INBOX_FC_EMPTY', 'the FC header parsed and no player rows follow it',
                               cause=Cause.DATA)
    return Outcome.ok('INBOX_SUMMARY', value={
        'n_players': len(recs), 'teams': sorted({d.get('Team') for d in recs if d.get('Team')}),
        'carries_dk_ids': 'ID' in hdr, 'columns': hdr})


SUMMARISE = {'DK_SALARIES': lambda rows, name: _dk_salaries_summary(rows),
             'DK_ENTRIES': lambda rows, name: _dk_entries_summary(rows),
             'DK_CONTEST_STANDINGS': _standings_summary,
             'FC_PLAYERS_EXPORT': lambda rows, name: _fc_summary(rows)}


def ledger_rows(ledger=None):
    p = pathlib.Path(ledger or LEDGER)
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]


def ingest_file(path, *, store=None, ledger=None, now=None) -> Outcome:
    """Classify, store and record one dropped file. Never modifies or deletes `path`."""
    path = pathlib.Path(path)
    store = pathlib.Path(store or STORE)
    ledger = pathlib.Path(ledger or LEDGER)
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    seen = {r['sha256']: r for r in ledger_rows(ledger)}
    if sha in seen:
        return Outcome.ok('INBOX_ALREADY_INGESTED', value=seen[sha],
                          detail=f'{path.name}: same bytes as {seen[sha]["original_name"]} ({seen[sha]["code"]})')
    base = {'spec_version': SPEC_VERSION, 'ingested_at': now or _now(), 'original_name': path.name,
            'n_bytes': len(raw), 'sha256': sha, 'sha256_is_of': 'uncompressed_bytes',
            'mtime_utc': dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
            .strftime('%Y-%m-%dT%H:%M:%SZ'),
            'acquisition': 'OWNER_MANUAL_EXPORT', 'retrieved_at_basis':
                'the instant the file was ingested here; NOT when the platform published it'}

    def record(o, **extra):
        row = dict(base, state=o.state.value, code=o.code, detail=o.detail, **extra)
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with open(ledger, 'a') as fh:
            fh.write(json.dumps(row, sort_keys=True) + '\n')
        return o if o.state.value != 'PASS' else Outcome.ok(o.code, value=row, detail=o.detail)

    if not raw.strip():
        return record(Outcome.blocked('INBOX_EMPTY_FILE', f'{path.name}: zero bytes of content',
                                      cause=Cause.EMPTY_INPUT), kind=None)
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return record(Outcome.fail('INBOX_NOT_UTF8', f'{path.name}: not UTF-8 text; spreadsheets must be '
                                                     f'exported as CSV'), kind=None)
    rows = list(csv.reader(text.splitlines()))
    kind, why = classify(rows)
    if kind is None:
        return record(Outcome.fail('INBOX_UNRECOGNISED_HEADER', f'{path.name}: {why}'), kind=None)
    s = SUMMARISE[kind](rows, path.name)
    if s.state.value != 'PASS':
        return record(s, kind=kind)
    store.mkdir(parents=True, exist_ok=True)
    blob = store / f'{kind}.{sha[:16]}.csv.gz'
    if not blob.exists():
        blob.write_bytes(gzip.compress(raw, mtime=0))
    if hashlib.sha256(gzip.decompress(blob.read_bytes())).hexdigest() != sha:
        return record(Outcome.fail('INBOX_STORE_SHA_MISMATCH', f'{blob.name} does not round-trip'), kind=kind)
    try:
        rel = str(blob.resolve().relative_to(_REPO))
    except ValueError:
        rel = str(blob)
    return record(Outcome.ok('INBOX_INGESTED', value=True, detail=f'{path.name}: {kind} ({why})'),
                  kind=kind, blob=rel, summary=s.value, **KIND_POLICY[kind])


def ingest_all(drop=None, **kw):
    drop = pathlib.Path(drop or DROP)
    files = sorted(p for p in drop.glob('*') if p.is_file() and not p.name.startswith('.')
                   and p.name != 'README.md')
    return [(p, ingest_file(p, **kw)) for p in files]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--drop', default=str(DROP))
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args(argv)
    if a.list:
        for r in reversed(ledger_rows()):
            print(f"{r['ingested_at']} {r['state']}[{r['code']}] {r.get('kind')} {r['original_name']} "
                  f"{r['sha256'][:12]}")
        return 0
    res = ingest_all(a.drop)
    if not res:
        print(f'NOTHING_DROPPED: no files in {a.drop}')
        return 0
    worst = 0
    for p, o in res:
        print(f'{o.state.value}[{o.code}] {o.detail}')
        worst = max(worst, 0 if o.state.value == 'PASS' else 2)
    return worst


if __name__ == '__main__':
    raise SystemExit(main())
