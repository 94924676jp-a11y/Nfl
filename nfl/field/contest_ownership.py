#!/usr/bin/env python3.12
"""Archived DraftKings contest ownership: the ingest, and the refusal while it is absent.

WHY THIS EXISTS AS CODE AND NOT AS A NOTE. The field model ships
`NOT_CALIBRATED_NO_ARCHIVED_CONTEST_OWNERSHIP`, and that state was being carried as prose. Prose
does not stop anyone approximating. This module makes the absence structural: there is exactly one
door into realised ownership, it validates its input against the real DraftKings export schema, and
it returns a named refusal rather than a number when the file is not there.

WHAT THE DATA IS. A DraftKings contest standings CSV, which the ENTERING ACCOUNT can download after
the contest finalises. `external-research/.../source_registry.csv` records its fields as
`Rank, EntryName, TimeRemaining, Points, Lineup` on the standings side and
`Player, Roster Position, %Drafted, FPTS` on the ownership side. `%Drafted` is the realised
ownership this project needs. The whole entry list is strictly better than the marginals, because
whole lineups carry duplication and pairwise correlation and `%Drafted` carries neither.

WHAT IT IS NOT, AND THIS IS THE TRAP WORTH NAMING. `nfl/dfs/vintage/*.slice.csv` carries
FantasyCruncher `Exp.`, `EXP+` and `Used` columns. Those are a PROJECTED exposure from another
model, not realised contest ownership. Calibrating our field model against them would be fitting
our forecast to somebody else's forecast, which is the same category error as tuning a projection
toward a sportsbook line, and it is separately forbidden: FantasyCruncher is context only and may
never become a feature input. This module will not read them.

WHICH CONTESTS. The entries the owner actually submitted are on disk, so the request is not "find
ownership somewhere" but a checkable list of contest ids. `wanted()` derives it from the
`DKEntries_*.csv` files rather than from a list someone typed, so it cannot go stale against them.
"""
from __future__ import annotations

import csv
import glob
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

#: Where a downloaded contest standings CSV is dropped. One directory, so there is one door.
DROP_DIR = _REPO / 'nfl/dfs/contest_results'
MANIFEST = _REPO / 'nfl/field/OWNERSHIP_ACQUISITION_MANIFEST.json'

#: The columns the ownership block of a DK contest standings export carries. A file missing any of
#: them is REFUSED, not partially read: a %Drafted column that turned out to be named something
#: else would otherwise be silently absent and every ownership would read as unknown-treated-as-zero.
REQUIRED_OWNERSHIP_COLUMNS = ('Player', 'Roster Position', '%Drafted', 'FPTS')

#: Entry files, which say which contests exist to be asked for. The wildcard LEADS as well as
#: trails: `DKEntries*.csv` silently missed `2026-09-25_ATL_GB_DKEntries_UPLOAD.csv`, dropping a
#: real entered contest out of the shopping list with no error. A search that can come back short
#: without saying so is the defect this project keeps paying for, so the glob is repo-wide and the
#: count is asserted against the entry files by nfl/tests/test_contest_ownership.py.
ENTRY_GLOBS = ('**/*DKEntries*.csv',)

#: Directories whose entry files are FIXTURES for tests rather than contests the owner entered.
#: Their contest ids are only requested if they also appear in a real entry file, which is checked
#: rather than assumed -- a fixture built by copying a real upload carries a real contest id.
FIXTURE_DIRS = ('nfl/research/showdown_fixture/',)

CALIBRATION_STATE_WITHOUT_IT = 'NOT_CALIBRATED_NO_ARCHIVED_CONTEST_OWNERSHIP'

_CLASSIC = re.compile(r'\(Early Only\)|\(Main\)|\(Afternoon Only\)', re.I)
_SHOWDOWN = re.compile(r'showdown', re.I)


def _game_type(contest_name: str) -> str:
    if _SHOWDOWN.search(contest_name):
        return 'SHOWDOWN'
    if _CLASSIC.search(contest_name):
        return 'CLASSIC'
    return 'UNKNOWN'


def wanted() -> Outcome:
    """Every contest the owner entered, read from the entry files. This is the shopping list."""
    found = {}
    files_read, fixture_only = [], {}
    for g in ENTRY_GLOBS:
        for f in sorted(glob.glob(str(_REPO / g), recursive=True)):
            p = pathlib.Path(f)
            rel = str(p.relative_to(_REPO))
            is_fixture = any(rel.startswith(d) for d in FIXTURE_DIRS)
            try:
                with p.open(newline='', encoding='utf-8-sig') as fh:
                    rows = list(csv.DictReader(fh))
            except Exception as e:  # noqa: BLE001
                return Outcome.fail('ENTRY_FILE_UNREADABLE', f'{p.name}: {e}')
            files_read.append(rel)
            for r in rows:
                cid = (r.get('Contest ID') or '').strip()
                if not cid:
                    continue
                name = (r.get('Contest Name') or '').strip()
                if is_fixture:
                    fixture_only.setdefault(cid, rel)
                    continue
                d = found.setdefault(cid, {
                    'contest_id': cid, 'contest_name': name,
                    'entry_fee': (r.get('Entry Fee') or '').strip(),
                    'game_type': _game_type(name), 'our_entries': 0, 'from_files': set()})
                d['our_entries'] += 1
                d['from_files'].add(p.name)
    if not found:
        return Outcome.fail(
            'NO_ENTRY_FILES_FOUND',
            'no DKEntries CSV yielded a Contest ID, so the list of contests to ask for cannot be '
            'built. This is an empty result where a populated one was expected, which is an error '
            'and not a finding.',
            globs_searched=list(ENTRY_GLOBS), files_read=files_read)
    out = sorted(found.values(), key=lambda d: (d['game_type'], d['contest_id']))
    for d in out:
        d['from_files'] = sorted(d['from_files'])
    orphan_fixtures = {c: f for c, f in fixture_only.items() if c not in found}
    return Outcome.ok('CONTESTS_ENUMERATED', value=out,
                      detail=f'{len(out)} contests across {len(files_read)} entry files',
                      files_read=files_read,
                      fixture_contest_ids_not_in_any_real_entry_file=orphan_fixtures)


def _parse_pct(v):
    s = str(v or '').strip().rstrip('%').strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def load_one(path: pathlib.Path) -> Outcome:
    """One contest standings CSV -> realised ownership, or a NAMED refusal. Never a partial read."""
    if not path.exists():
        return Outcome.blocked('CONTEST_CSV_ABSENT', f'{path} does not exist', cause=Cause.DATA)
    try:
        text = path.read_text(encoding='utf-8-sig')
    except Exception as e:  # noqa: BLE001
        return Outcome.fail('CONTEST_CSV_UNREADABLE', f'{path.name}: {e}')
    rows = list(csv.DictReader(text.splitlines()))
    if not rows:
        return Outcome.fail('CONTEST_CSV_EMPTY',
                            f'{path.name} parsed to zero rows. An empty file is an error, not an '
                            f'ownership of zero for every player.')
    cols = set(rows[0].keys())
    missing = [c for c in REQUIRED_OWNERSHIP_COLUMNS if c not in cols]
    if missing:
        return Outcome.fail(
            'CONTEST_CSV_SCHEMA_MISMATCH',
            f'{path.name} is missing {missing}. Refused rather than read around: a missing '
            f'%Drafted column would make every ownership unknown, and unknown read as zero is the '
            f'defect this project keeps paying for.',
            columns_present=sorted(cols), columns_required=list(REQUIRED_OWNERSHIP_COLUMNS))
    own, bad = {}, []
    for r in rows:
        name = (r.get('Player') or '').strip()
        if not name:
            continue
        pct = _parse_pct(r.get('%Drafted'))
        if pct is None:
            bad.append(name)
            continue
        own[name] = {'pct_drafted': pct,
                     'roster_position': (r.get('Roster Position') or '').strip(),
                     'fpts': _parse_pct(r.get('FPTS'))}
    if not own:
        return Outcome.fail('CONTEST_CSV_NO_OWNERSHIP_ROWS',
                            f'{path.name} has the right columns and no parseable player rows',
                            unparseable_examples=bad[:5])
    if bad:
        return Outcome.fail(
            'CONTEST_CSV_UNPARSEABLE_OWNERSHIP',
            f'{len(bad)} of {len(bad) + len(own)} players in {path.name} have a %Drafted that does '
            f'not parse. Partially-read ownership is refused: the players that dropped out would '
            f'silently become zero-owned, which is exactly the leverage the field model looks for.',
            examples=bad[:5])
    total = sum(v['pct_drafted'] for v in own.values())
    return Outcome.ok('CONTEST_OWNERSHIP_LOADED', value={
        'file': path.name, 'n_players': len(own),
        'sum_pct_drafted': round(total, 2),
        'SUM_MEANING': ('the sum over players of %Drafted is roughly 100 times the number of '
                        'roster slots -- about 900 for a nine-slot Classic lineup -- because each '
                        'entry contributes to nine players. It is NOT expected to be 100.'),
        'ownership': own})


def status() -> Outcome:
    """Is realised ownership available? BLOCKED with the exact missing list while it is not."""
    w = wanted()
    if w.state.name != 'PASS':
        return w
    contests = w.value
    present, loaded, failures = [], {}, []
    DROP_DIR.mkdir(parents=True, exist_ok=True)
    for f in sorted(DROP_DIR.glob('*.csv')):
        o = load_one(f)
        if o.state.name == 'PASS':
            present.append(f.name)
            loaded[f.name] = {k: v for k, v in o.value.items() if k != 'ownership'}
        else:
            failures.append({'file': f.name, 'code': o.code, 'detail': o.detail})
    manifest = {
        'ARTIFACT': 'OWNERSHIP_ACQUISITION_MANIFEST',
        'WHAT_IS_NEEDED': ('a DraftKings contest standings CSV per contest below, downloaded by '
                           'the entering account after the contest finalised. The ownership block '
                           f'must carry {list(REQUIRED_OWNERSHIP_COLUMNS)}.'),
        'WHERE_TO_PUT_IT': str(DROP_DIR.relative_to(_REPO)),
        'TIME_SENSITIVE': ('the source registry records historical vintage support as "final only '
                           'unless downloaded during contest" and access as "contests the account '
                           'entered or can view". If DraftKings stops serving a finished contest '
                           'page, that week of ownership is gone and cannot be reconstructed. This '
                           'is the one item on the list that can expire.'),
        'NOT_A_SUBSTITUTE': ('FantasyCruncher Exp./EXP+/Used are a PROJECTED exposure from another '
                             'model, not realised ownership. They are context only, they may never '
                             'become a feature input, and calibrating against them would be '
                             'fitting our forecast to another forecast.'),
        'contests_entered': contests,
        'classic_contests_wanted': [c['contest_id'] for c in contests
                                    if c['game_type'] == 'CLASSIC'],
        'showdown_contests_wanted': [c['contest_id'] for c in contests
                                     if c['game_type'] == 'SHOWDOWN'],
        'files_present': present,
        'files_loaded': loaded,
        'files_refused': failures,
        'field_model_calibration_state': (CALIBRATION_STATE_WITHOUT_IT if not loaded
                                          else 'ARCHIVED_OWNERSHIP_PRESENT_NOT_YET_CONSUMED'),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2))
    if failures and not loaded:
        return Outcome.fail('CONTEST_OWNERSHIP_ALL_REFUSED',
                            f'{len(failures)} file(s) in the drop directory and none passed schema '
                            f'validation', failures=failures)
    if not loaded:
        return Outcome.blocked(
            'NO_ARCHIVED_CONTEST_OWNERSHIP',
            f'0 of {len(contests)} entered contests have an archived standings CSV. The field '
            f'model stays {CALIBRATION_STATE_WITHOUT_IT}.',
            cause=Cause.DATA,
            n_contests_wanted=len(contests),
            classic_wanted=[c['contest_id'] for c in contests if c['game_type'] == 'CLASSIC'],
            drop_dir=str(DROP_DIR.relative_to(_REPO)),
            outbox='docs/AGENT_OUTBOX.md OUT-040',
            note=('this is BLOCKED and not FAILED: nothing in the repository is broken, the bytes '
                  'are outside it. It is assigned, not stuck -- the contest ids are known and the '
                  'download is authenticated to the entering account.'))
    return Outcome.ok('ARCHIVED_CONTEST_OWNERSHIP_PRESENT', value={
        'n_loaded': len(loaded), 'n_wanted': len(contests), 'loaded': loaded,
        'refused': failures})


def main() -> int:
    o = status()
    print(o.state, o.code)
    print(o.detail)
    if o.state.name != 'PASS':
        print(json.dumps(o.evidence, indent=2, default=str))
    print(f'-> {MANIFEST.relative_to(_REPO)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
