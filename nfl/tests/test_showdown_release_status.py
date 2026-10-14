#!/usr/bin/env python3.12
"""ENG-014 / ENG-017 (owner directive OD-001, 2026-10-14) on the direct Showdown path, nfl/tools/showdown_tonight.py.

  ENV      an NFL_SHOWDOWN_* value the code does not declare refuses the run, end to end, before any state is built
  CLOCK    a run after kickoff is refused; only an explicit diagnostic proceeds, and it is not releasable
  DIAG     a diagnostic run keeps no file under an upload name
  CONFIG   the effective configuration names each switch and whether the environment or the code default set it"""
from __future__ import annotations

import datetime as dt
import os
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import showdown_tonight as ST  # noqa: E402

PASSED = FAILED = 0
ATL_EXPORT = _REPO / 'nfl/dfs/salaries/raw/showdown_atl_no_2026W4/DKEntries_ATL_NO_SHOWDOWN_2026W4.fd0c1faa2271ca66.csv'


def check(ok, label=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}')
    return bool(ok)


def test_undeclared_env_refuses_end_to_end():
    check(ST.undeclared_env({'NFL_SHOWDOWN_SELECTOR': 'GREEDY', 'PATH': '/x'}) == [], 'negative control: declared switches pass')
    check(ST.undeclared_env({'NFL_SHOWDOWN_SELECTER': 'X'}) == ['NFL_SHOWDOWN_SELECTER'], 'a misspelt switch is named')
    os.environ['NFL_SHOWDOWN_SELECTER'] = 'FIXED_POLICY_V1'
    try:
        o = ST.run(ATL_EXPORT, 'ATL_NO_2026W4', 'TEST_ENV_REFUSAL')
    finally:
        os.environ.pop('NFL_SHOWDOWN_SELECTER', None)
    check(o.state.value == 'BLOCKED' and o.code == 'UNDECLARED_RUN_CONFIG',
          f'positive control: the direct run refuses an undeclared switch before any state ({o.state.value} {o.code})')


def test_kickoff_gate():
    k = '2026-10-19T13:00:00'
    before = dt.datetime(2026, 10, 19, 16, 59, tzinfo=dt.timezone.utc)
    after = dt.datetime(2026, 10, 19, 17, 0, tzinfo=dt.timezone.utc)
    check(ST.kickoff_gate(k, now=before) == 'OK', 'negative control: a minute before a 1pm ET kickoff (EDT) is OK')
    check(ST.kickoff_gate(k, now=after) == 'REFUSE', 'at kickoff the run refuses')
    check(ST.kickoff_gate(k, now=after, diagnostic=True) == 'DIAGNOSTIC', 'an explicit diagnostic proceeds, labelled')


def test_diagnostic_withholds_every_upload():
    d = pathlib.Path(tempfile.mkdtemp(prefix='st_diag_'))
    for n in ('SHOWDOWN_X_DK_UPLOAD.csv', 'SHOWDOWN_X_DK_UPLOAD_123.csv', 'SHOWDOWN_X_FINAL_LINEUPS.csv'):
        (d / n).write_text('x\n')
    got = ST.withhold_uploads(d, 'SHOWDOWN_X')
    check(sorted(got) == ['SHOWDOWN_X_DK_UPLOAD.DIAGNOSTIC_NOT_RELEASABLE.csv', 'SHOWDOWN_X_DK_UPLOAD_123.DIAGNOSTIC_NOT_RELEASABLE.csv'],
          f'both upload files renamed ({got})')
    left = [f.name for f in d.glob('SHOWDOWN_X_DK_UPLOAD*.csv') if not f.name.endswith('.DIAGNOSTIC_NOT_RELEASABLE.csv')]
    check(left == [], f'no file remains under an upload name ({left})')
    check((d / 'SHOWDOWN_X_FINAL_LINEUPS.csv').exists(), 'non-upload artifacts are left for analysis')
    import shutil
    shutil.rmtree(d, ignore_errors=True)


def test_effective_config_names_each_switch_and_its_source():
    c = ST.effective_config(ATL_EXPORT, None, ST.RELEASE_DIAGNOSTIC, ['NO_ROSTER_CAPTURE'], env={'NFL_SHOWDOWN_SELECTOR': 'FIXED_POLICY_V1'})
    check(c['selector'] == {'value': 'FIXED_POLICY_V1', 'source': 'ENV'}, f"selector from the environment ({c['selector']})")
    check(c['overlap_policy'] == {'value': 'EQUAL_SIZE', 'source': 'CODE_DEFAULT'}, f"overlap from the code default ({c['overlap_policy']})")
    check(c['forecast_arm']['source'] == 'CODE_DEFAULT', 'forecast arm recorded with its source')
    check(c['release_status'] == ST.RELEASE_DIAGNOSTIC and c['release_reasons'] == ['NO_ROSTER_CAPTURE'], 'release status and reason recorded')
    check(c['inputs']['export']['sha256'] and len(c['inputs']['export']['sha256']) == 64, 'the export is pinned by sha256')
    check(c['exposure_and_relaxation']['fixed_policy']['level'] == 2, 'the cap policy travels with the run')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
    check(PASSED > 0, 'the module counted at least one check')


if __name__ == '__main__':
    for n, f in sorted((k, v) for k, v in globals().items() if k.startswith('test_') and callable(v)):
        f()
    print(f'PASSED {PASSED}  FAILED {FAILED}')
