#!/usr/bin/env python3.12
"""The one door into realised contest ownership, and every way it must refuse.

The field model is uncalibrated because no archived DraftKings ownership exists. That state was
prose, and prose does not stop anyone approximating. These checks hold the absence structural: the
shopping list is derived from the entry files rather than typed, a malformed export is refused whole
rather than read around, and the refusal is BLOCKED-on-DATA rather than a zero.

One check exists because the first version of the module had the bug it now guards: the entry glob
was `DKEntries*.csv`, which silently missed `2026-09-25_ATL_GB_DKEntries_UPLOAD.csv` and dropped a
real entered contest out of the list with no error at all.
"""
from __future__ import annotations

import csv
import glob
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.field import contest_ownership as CO  # noqa: E402

RESULTS = []


def check(name):
    def deco(fn):
        RESULTS.append((name, fn))
        return fn
    return deco


def _write(d: pathlib.Path, name: str, header, rows):
    p = d / name
    with p.open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return p


@check('the shopping list is every contest in the entry files, with none dropped')
def t_no_contest_dropped():
    o = CO.wanted()
    assert o.state.name == 'PASS', o.detail
    got = {c['contest_id'] for c in o.value}
    on_disk = set()
    for f in glob.glob(str(_REPO / '**/*DKEntries*.csv'), recursive=True):
        rel = str(pathlib.Path(f).relative_to(_REPO))
        if any(rel.startswith(x) for x in CO.FIXTURE_DIRS):
            continue
        with open(f, newline='', encoding='utf-8-sig') as fh:
            for r in csv.DictReader(fh):
                cid = (r.get('Contest ID') or '').strip()
                if cid:
                    on_disk.add(cid)
    assert got == on_disk, (
        f'the module lists {len(got)} contests and the entry files hold {len(on_disk)}. Dropped: '
        f'{sorted(on_disk - got)}. Invented: {sorted(got - on_disk)}. A shopping list that comes '
        f'back short without an error is the whole defect class.')
    dated = [f for f in glob.glob(str(_REPO / '**/*DKEntries*.csv'), recursive=True)
             if not pathlib.Path(f).name.startswith('DKEntries')]
    assert dated, 'no date-prefixed entry file exists any more; this check no longer guards anything'
    return (f'{len(got)} contests, matching the entry files exactly, including '
            f'{len(dated)} whose filename does not start with DKEntries')


@check('every wanted contest is classified CLASSIC or SHOWDOWN, never left UNKNOWN silently')
def t_game_type():
    o = CO.wanted()
    unknown = [c['contest_id'] for c in o.value if c['game_type'] == 'UNKNOWN']
    assert not unknown, (
        f'{len(unknown)} contests have no game type: {unknown}. A Classic field model calibrated '
        f'on Showdown ownership would be calibrated on the wrong game, so the split cannot be '
        f'left to chance.')
    classic = [c for c in o.value if c['game_type'] == 'CLASSIC']
    assert classic, 'no Classic contest at all would mean the Classic field can never be calibrated'
    return f'{len(classic)} CLASSIC and {len(o.value) - len(classic)} SHOWDOWN, none unknown'


@check('a well-formed export loads, and the sum is documented as slots not one hundred')
def t_positive_path():
    d = pathlib.Path(tempfile.mkdtemp())
    p = _write(d, 'c1.csv', list(CO.REQUIRED_OWNERSHIP_COLUMNS),
               [['Josh Allen', 'QB', '31.4%', '24.6'],
                ['Bijan Robinson', 'RB', '22.1%', '18.2'],
                ['Puka Nacua', 'WR', '18.9', '11.4']])
    o = CO.load_one(p)
    assert o.state.name == 'PASS', f'{o.code}: {o.detail}'
    assert o.value['n_players'] == 3
    assert abs(o.value['ownership']['Josh Allen']['pct_drafted'] - 31.4) < 1e-9
    assert abs(o.value['ownership']['Puka Nacua']['pct_drafted'] - 18.9) < 1e-9, \
        'a bare number and a percent-signed number must parse the same'
    assert '900' in o.value['SUM_MEANING'] and 'NOT expected to be 100' in o.value['SUM_MEANING']
    return f'3 players, sum {o.value["sum_pct_drafted"]}, with and without a percent sign'


@check('a missing %Drafted column is refused, not read around')
def t_schema_refusal():
    d = pathlib.Path(tempfile.mkdtemp())
    p = _write(d, 'c2.csv', ['Player', 'Roster Position', 'FPTS'],
               [['Josh Allen', 'QB', '24.6']])
    o = CO.load_one(p)
    assert o.state.name == 'FAIL' and o.code == 'CONTEST_CSV_SCHEMA_MISMATCH', o.code
    assert '%Drafted' in str(o.evidence.get('columns_required')), o.evidence
    return 'a file without %Drafted fails by name instead of returning every player at zero'


@check('a partially parseable file is refused whole')
def t_partial_refusal():
    d = pathlib.Path(tempfile.mkdtemp())
    p = _write(d, 'c3.csv', list(CO.REQUIRED_OWNERSHIP_COLUMNS),
               [['Josh Allen', 'QB', '31.4%', '24.6'],
                ['Bijan Robinson', 'RB', '', '18.2'],
                ['Puka Nacua', 'WR', 'n/a', '11.4']])
    o = CO.load_one(p)
    assert o.state.name == 'FAIL' and o.code == 'CONTEST_CSV_UNPARSEABLE_OWNERSHIP', o.code
    assert 'Bijan Robinson' in o.evidence['examples']
    return ('two unparseable rows refuse the whole file, because a dropped player becomes '
            'zero-owned and zero-owned is what the field model calls leverage')


@check('an empty file is an error and not an ownership of zero')
def t_empty_refusal():
    d = pathlib.Path(tempfile.mkdtemp())
    (d / 'c4.csv').write_text('')
    o = CO.load_one(d / 'c4.csv')
    assert o.state.name == 'FAIL' and o.code == 'CONTEST_CSV_EMPTY', o.code
    o2 = CO.load_one(d / 'does_not_exist.csv')
    assert o2.state.name == 'BLOCKED' and o2.code == 'CONTEST_CSV_ABSENT'
    return 'empty FAILs, absent BLOCKs, and neither returns a number'


@check('the absence is BLOCKED on DATA, names the contests, and does not fabricate a calibration')
def t_status_blocked():
    o = CO.status()
    if o.state.name == 'PASS':
        return f'archived ownership is now present ({o.value["n_loaded"]} files); this check retires'
    assert o.state.name == 'BLOCKED' and o.code == 'NO_ARCHIVED_CONTEST_OWNERSHIP', o.code
    assert o.evidence['cause'] == 'DATA', (
        'the bytes are outside the repository, so the cause is DATA. Calling it ENVIRONMENT or '
        'failing would say something is broken here, and nothing is.')
    assert o.evidence['classic_wanted'], 'the refusal must name what would resolve it'
    assert 'OUT-040' in o.evidence['outbox'], (
        'per the standing rule, nothing is marked blocked on something outside the repository '
        'without the request being written into the outbox')
    return f'BLOCKED on DATA, naming {len(o.evidence["classic_wanted"])} Classic contest ids'


@check('FantasyCruncher exposure is named as not a substitute, and is not read')
def t_fc_not_a_substitute():
    m = json.loads((_REPO / 'nfl/field/OWNERSHIP_ACQUISITION_MANIFEST.json').read_text())
    txt = m['NOT_A_SUBSTITUTE']
    assert 'FantasyCruncher' in txt and 'never become a feature input' in txt
    src = (_REPO / 'nfl/field/contest_ownership.py').read_text()
    assert 'vintage' not in src.split('"""')[2], (
        'the module body must not reach into nfl/dfs/vintage, which is where the FantasyCruncher '
        'Exp./EXP+/Used columns live. Naming the trap in a docstring is not the same as being '
        'unable to fall into it.')
    return 'the trap is named in the manifest and the module body has no path to the FC columns'


@check('the manifest says the data can expire, because this one actually can')
def t_time_sensitive():
    m = json.loads((_REPO / 'nfl/field/OWNERSHIP_ACQUISITION_MANIFEST.json').read_text())
    assert 'TIME_SENSITIVE' in m and 'cannot be reconstructed' in m['TIME_SENSITIVE']
    assert m['WHERE_TO_PUT_IT'] == str(CO.DROP_DIR.relative_to(_REPO))
    return 'expiry is stated, and the drop directory in the manifest is the one the loader reads'


def main() -> int:
    ok = fail = 0
    for name, fn in RESULTS:
        try:
            detail = fn()
        except AssertionError as e:
            print(f'FAIL  {name}\n        {e}')
            fail += 1
        except Exception as e:  # noqa: BLE001
            print(f'ERROR {name}\n        {type(e).__name__}: {e}')
            fail += 1
        else:
            print(f'pass  {name}\n        {detail}')
            ok += 1
    print(f'\n{ok} passed, {fail} failed, {len(RESULTS)} checks')
    return 1 if fail else 0


if __name__ == '__main__':
    raise SystemExit(main())
