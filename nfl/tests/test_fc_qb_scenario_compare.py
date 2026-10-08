"""fc_qb_scenario_compare: FC version controls and refusal rules (synthetic FC exports in the real column layout)."""
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
from nfl.tools import fc_qb_scenario_compare as C  # noqa: E402

PASSED = FAILED = 0
H = ('Player,Inj,Likes,Pos,pDepth,Salary,Team,Opp,Def v Pos,VegasPts,STDV,2025 Avg,2026 Avg,FC,My,Diff,Floor,Ceiling,'
     'FC Proj,My Proj,Exp.,EXP+,Used,Con.,Value')


def check(ok, msg):
    global PASSED, FAILED
    PASSED, FAILED = (PASSED + 1, FAILED) if ok else (PASSED, FAILED + 1)
    print('  ok  ' if ok else '  FAIL', msg)


def fc(rows, d):
    p = pathlib.Path(d) / f'fc_{abs(hash(tuple(rows)))}.csv'
    body = [',' * 24, H] + [f'{n},{inj},0,{pos},{dep},{sal},{t},x,1,{veg},1,0,0,{pr},{pr},0,0,0,{pr},{pr},100,100,,0,1'
                            for n, inj, pos, dep, sal, t, veg, pr in rows]
    p.write_text('\n'.join(body) + '\n')
    return p


def test_controls():
    d = tempfile.mkdtemp()
    base = [('QA', '', 'QB', 'QB1', 9000, 'TB', 20.5, 18.0), ('QB2', '', 'QB', '', 6000, 'TB', 20.5, 0.0),
            ('W1', '', 'WR', 'WR1', 8000, 'TB', 20.5, 12.0), ('D1', '', 'WR', 'WR1', 9000, 'DAL', 28, 15.0)]
    swap = [('QA', '!', 'QB', '', 9000, 'TB', 20.5, 0.0), ('QB2', '', 'QB', 'QB1', 6000, 'TB', 20.5, 12.0),
            ('W1', '', 'WR', 'WR1', 8000, 'TB', 20.5, 9.0), ('D1', '', 'WR', 'WR1', 9000, 'DAL', 28, 15.0)]
    a, b = C.load_fc(fc(base, d)), C.load_fc(fc(swap, d))
    lab, ctl = C.controls(a[0], b[0], {'received_at': 't0'}, {'received_at': 't1'}, {'QA', 'QB2'})
    check(lab.startswith('QB_SWAP_ONLY_IDENTIFIED_INPUT_CHANGE'), f'a pure QB swap (only QB rows differ) is labelled so: {lab[:40]}')
    moved = [r if r[0] != 'D1' else ('D1', '', 'WR', 'WR1', 9400, 'DAL', 28, 15.0) for r in swap]
    lab, _ = C.controls(a[0], C.load_fc(fc(moved, d))[0], {'received_at': 't0'}, {'received_at': 't1'}, {'QA', 'QB2'})
    check('NON_QB_SALARY_CHANGED' in lab and lab.startswith('OBSERVED_VERSION_DIFFERENCE'), 'a non-QB salary change confounds')
    veg = [r if r[5] != 'TB' else (*r[:6], 17.5, r[7]) for r in swap]
    lab, _ = C.controls(a[0], C.load_fc(fc(veg, d))[0], {'received_at': 't0'}, {'received_at': 't1'}, {'QA', 'QB2'})
    check('FC_VEGAS_TEAM_TOTAL_CHANGED' in lab, 'a moved FC Vegas total confounds (FC is market-informed)')
    inj = [r if r[0] != 'W1' else ('W1', 'Q', *r[2:]) for r in swap]
    lab, _ = C.controls(a[0], C.load_fc(fc(inj, d))[0], {'received_at': 't0'}, {'received_at': 't1'}, {'QA', 'QB2'})
    check('NON_QB_INJ_CHANGED' in lab, 'a teammate injury-flag change confounds')
    lab, _ = C.controls(a[0], b[0], {'received_at': None}, {'received_at': 't1'}, {'QA', 'QB2'})
    check('CAPTURE_TIME_UNRECORDED' in lab, 'an FC version with no capture time is never an identified comparison')


def test_dependency_paths():
    p = C.dependency(('W1', 'TB'), {'position': 'WR'}, 'TB', 'DAL')
    check(any(x.startswith('QB3') for x in p) and any(x.startswith('QB4') for x in p), 'a QB-club receiver maps to QB3/QB4')
    check(C.dependency(('DST', 'DAL'), {'position': 'DST'}, 'TB', 'DAL')[0].startswith('QB5'), 'the opposing DST maps to QB5')


if __name__ == '__main__':
    for t in (test_controls, test_dependency_paths):
        print(t.__name__)
        t()
    print(f'{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
