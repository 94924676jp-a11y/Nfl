#!/usr/bin/env python3.12
"""A refusal is a result. A crash is a defect. They may not share an exit code.

These tests exist because nfl-product-board.yml computed three different
outcomes and exited 1 for all three, for 1,116 scheduled runs. The three states
are behaviourally distinguished here, against the real log text from the
2026-09-26T16:54:38Z run, not against a paraphrase of it.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from nfl.tools import judge_board_pass as J

ok = fail = 0


def check(label, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
    else:
        fail += 1
        print(f'  FAIL {label} {detail}')


# The refusal block exactly as GitHub Actions recorded it, plus the summary line
# refresh_boards.py prints unconditionally at nfl/tools/refresh_boards.py:131.
GAMES = ('ARI_SF BAL_DAL CAR_CLE CIN_PIT HOU_IND KC_MIA LAC_BUF LA_DEN LV_NO '
         'MIN_TB NE_JAX NYJ_DET PHI_CHI SEA_WAS TEN_NYG').split()
LIVE = '\n'.join(
    f'2026_03_{g:<10s} REFUSED  feature_build: STAGE_DECLARED_UNIMPLEMENTED'
    for g in GAMES) + '\n-- 0 board(s) written, 15 game(s) checked\n'


def test_the_live_log_is_a_declared_refusal_not_a_failure():
    out = J.classify(LIVE)
    check('live state', out['state'] == J.REFUSED_DECLARED_DEBT, out['state'])
    check('live neutral', out['exit_code'] == J.NEUTRAL, out['exit_code'])
    check('live counted all 15', out['n_refused'] == 15, out['n_refused'])
    check('live code', out['codes'] == ['STAGE_DECLARED_UNIMPLEMENTED'])


def test_the_three_states_do_not_share_an_exit_code():
    codes = {J.classify(LIVE)['exit_code'],
             J.classify(LIVE + '\nTraceback (most recent call last)\n')['exit_code'],
             J.classify('')['exit_code']}
    check('refusal differs from crash',
          J.classify(LIVE)['exit_code']
          != J.classify(LIVE + '\nTraceback (most recent call last)\n')['exit_code'])
    check('two distinct codes across the three states', len(codes) == 2, codes)


def test_a_crash_outranks_declared_debt():
    # A traceback alongside declared debt is still a defect. If debt won here,
    # a real exception would be laundered into a neutral pass by any refusal.
    out = J.classify(LIVE + '\nTraceback (most recent call last)\n')
    check('crash wins', out['state'] == J.RAISED, out['state'])
    check('crash red', out['exit_code'] == J.FAILURE)


def test_an_undeclared_refusal_code_stays_red():
    out = J.classify('2026_03_ARI_SF  REFUSED  feature_build: NEW_THING\n'
                     '-- 0 board(s) written, 1 game(s) checked\n')
    check('undeclared red', out['exit_code'] == J.FAILURE, out)
    check('names the code', out['undeclared_codes'] == ['NEW_THING'], out)


def test_one_undeclared_code_among_declared_ones_stays_red():
    out = J.classify(LIVE.replace(
        '2026_03_TEN_NYG    REFUSED  feature_build: '
        'STAGE_DECLARED_UNIMPLEMENTED',
        '2026_03_TEN_NYG    REFUSED  feature_build: SOMETHING_ELSE'))
    check('mixed red', out['exit_code'] == J.FAILURE, out['state'])
    check('mixed names it', out['undeclared_codes'] == ['SOMETHING_ELSE'], out)


def test_an_unparseable_refusal_line_is_not_granted_neutral():
    out = J.classify('2026_03_ARI_SF  REFUSED  no code at all here\n'
                     '-- 0 board(s) written, 1 game(s) checked\n')
    check('unparseable red', out['exit_code'] == J.FAILURE, out['state'])


def test_an_empty_or_missing_log_is_not_a_clean_pass():
    for log in ('', '\n', 'some chatter and nothing else\n'):
        out = J.classify(log)
        check(f'empty not clean {log!r}', out['state'] == J.NO_SUMMARY,
              out['state'])
        check('empty red', out['exit_code'] == J.FAILURE)


def test_a_clean_pass_is_zero():
    out = J.classify('-- 15 board(s) written, 15 game(s) checked\n')
    check('clean', out['state'] == J.CLEAN, out['state'])
    check('clean zero', out['exit_code'] == J.OK)


def test_neutral_is_withdrawn_when_the_declaration_disappears():
    # The allowlist is not self-certifying. If SYSTEM_STATE.json stops declaring
    # the code, it stops qualifying, and the pass goes back to red. This is the
    # fail-closed direction and is the whole reason the allowlist is checked
    # against the repository rather than trusted from the module.
    empty = pathlib.Path('/tmp/_no_declaration.json')
    empty.write_text('{}')
    out = J.classify(LIVE, state_path=str(empty))
    check('withdrawn -> red', out['exit_code'] == J.FAILURE, out['state'])
    check('withdrawn names it',
          out['undeclared_codes'] == ['STAGE_DECLARED_UNIMPLEMENTED'], out)
    check('and is declared today',
          'STAGE_DECLARED_UNIMPLEMENTED' in J.declared())


def test_the_workflow_calls_the_module_and_keeps_its_other_steps():
    y = (pathlib.Path(__file__).resolve().parents[2]
         / '.github/workflows/nfl-product-board.yml').read_text()
    check('workflow calls the judge', 'judge_board_pass.py' in y)
    check('no untestable grep judging left',
          "grep -q 'Traceback" not in y, 'shell judging still present')
    for step in ('Refresh boards', 'Commit any board written',
                 'actions/checkout@v4'):
        check(f'kept {step}', step in y)


def test_the_cli_exit_code_matches_the_classification():
    root = pathlib.Path(__file__).resolve().parents[2]
    for log, want in ((LIVE, J.NEUTRAL), ('', J.FAILURE),
                      ('-- 1 board(s) written, 1 game(s) checked\n', J.OK)):
        f = pathlib.Path('/tmp/_judge_cli.log')
        f.write_text(log)
        r = subprocess.run([sys.executable,
                            str(root / 'nfl/tools/judge_board_pass.py'),
                            str(f)], capture_output=True, text=True)
        check(f'cli exit {want}', r.returncode == want,
              f'got {r.returncode}: {r.stdout.strip()[:80]}')


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith('test_') and callable(fn):
            fn()
    print(f'test_board_pass_judgement: {ok} ok, {fail} failed')
    return 1 if fail else 0


if __name__ == '__main__':
    raise SystemExit(main())
