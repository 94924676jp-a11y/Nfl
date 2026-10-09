"""Event-consistent published Showdown worlds (nfl/sim/event_consistent_worlds.py), SHADOW ARM.

Every published-world accounting law that nfl/tools/world_accounting_check.py carries, plus the event laws it does
not (club points as event sums, kicker DK from its events, DST DK from its components, TDs <= catches / carries),
is asserted on a small SYNTHETIC world set built to contain the incumbent's defects: receiving yards and TDs drawn
on targets independently of catches, rushing TDs independent of carries, a QB projection whose yards per attempt
disagrees with his receivers' yards per target, and DST takeaways drawn independently of interceptions.

  a  the synthetic RAW worlds carry the defects (so a clean result below is a repair, not an easy fixture)
  b  NEGATIVE CONTROL: the incumbent's real classic_slate_run.efficiency_worlds on those worlds FAILS the checker
  c  the repaired arm passes every check, non-vacuously (each law measured on every world)
  d  seeded violations on the repaired output are caught (the checker is load-bearing on these worlds)
  e  determinism: same seed -> identical worlds, in-process and across PYTHONHASHSEED; another seed -> different
  f  mean anchoring: club passing yards equal the declared incumbent club mean; INT mean equals int_rate x
     attempts within Monte Carlo error; receivers' yards (receiver anchor) and TDs keep their incumbent means
  g  DK points recomputed from the published stat line equal the published DK (dk_from_stats AND dk_scoring)
  h  kicker_line is kicker_world.draw (same rng, same DK, same events) plus the two-point tries it discards
  i  refusals are named: empty input, missing projection row, unknown anchor
  j  the TB@DAL 2026W5 OFFICIAL shadow repair artifact: zero violations, and its 'before' equals the checker's
     committed reading of the published worlds
"""
import json
import os
import pathlib
import random
import subprocess
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
import numpy as np  # noqa: E402

from nfl.sim import event_consistent_worlds as ECW  # noqa: E402
from nfl.tools import classic_slate_run as CR  # noqa: E402
from nfl.tools import world_accounting_check as WAC  # noqa: E402

PASSED = FAILED = BLOCKED = 0
HOME, AWAY = 'HHH', 'AAA'
POS = {'Q': 'QB', 'Q2': 'QB', 'W1': 'WR', 'W2': 'WR', 'T1': 'TE', 'R1': 'RB', 'R2': 'RB'}
TSH = {'W1': 0.30, 'W2': 0.22, 'T1': 0.18, 'R1': 0.18, 'R2': 0.12}
CATCH = {'W1': 0.64, 'W2': 0.62, 'T1': 0.70, 'R1': 0.78, 'R2': 0.75}
CSH = {'Q': 0.10, 'R1': 0.52, 'R2': 0.30, 'W1': 0.08}
RTD_SH = {'Q': 0.15, 'R1': 0.55, 'R2': 0.30}            # raw rush-TD shares: W1 never gets one (as in game.py)
PTD_SH = {'W1': 0.32, 'W2': 0.20, 'T1': 0.22, 'R1': 0.16, 'R2': 0.10}
#: SYNTHETIC FIXTURE VALUES, chosen for the test and labelled as such -- not model constants. The QB's projected
#: yards per attempt (6.0) deliberately disagrees with his receivers' projected yards per target (9.0), which is
#: the TB@DAL situation (receivers +30 yds over the QB) that makes independent per-player factors break identity.
QB_YPA, REC_YPT, INT_RATE = 6.0, 9.0, 0.025
KICK = {c: {'mix': {'made_mix': {'fg_0_39': 0.5, 'fg_40_49': 0.3, 'fg_50_plus': 0.2},
                    'make_rate': {'fg_0_39': 0.93, 'fg_40_49': 0.80, 'fg_50_plus': 0.65}},
            'rates': {'try_rate_2pt': 0.08, 'two_pt_success': 0.48, 'pat_make_rate': 0.95, 'fg_share': 0.85}}
        for c in (HOME, AWAY)}
OUT = _REPO / 'nfl/research/accounting_repair/TB_DAL_2026W5'


def check(ok, msg):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print('  ok  ', msg)
    else:
        FAILED += 1
        print('  FAIL', msg)
    return ok


def blocked(msg):
    global BLOCKED
    BLOCKED += 1
    print('  BLOCKED', msg)


def _multi(n, shares, rng):
    keys = list(shares)
    out = dict.fromkeys(keys, 0)
    tot = sum(shares.values())
    for _ in range(int(n)):
        u, acc = rng.random() * tot, 0.0
        for k in keys:
            acc += shares[k]
            if u <= acc:
                out[k] += 1
                break
        else:
            out[keys[-1]] += 1
    return out


def synthetic(n=400, seed=7):
    """(art, rows_by_key): a raw-simulator-shaped world set with the incumbent's defects built in."""
    rng = random.Random(seed)
    sd = {f'{p}|{c}': [] for c in (HOME, AWAY) for p in POS}
    csw = {HOME: [], AWAY: []}
    dcomp = {f'D|{c}': [] for c in (HOME, AWAY)}
    wp = []
    for _ in range(n):
        pts = {c: max(0.0, rng.gauss(23.0, 9.0)) for c in (HOME, AWAY)}
        wp.append((pts[HOME], pts[AWAY]))
        for c in (HOME, AWAY):
            dcomp[f'D|{c}'].append([float(rng.randrange(0, 5)), float(rng.randrange(0, 4)),
                                    1.0 if rng.random() < 0.08 else 0.0, 1.0 if rng.random() < 0.03 else 0.0])
        for c in (HOME, AWAY):
            pa = rng.randrange(25, 45)
            tg = pa - rng.randrange(0, 3)
            q2 = rng.randrange(1, 6) if rng.random() < 0.1 else 0
            qatt = {'Q': pa - q2, 'Q2': q2}
            tgt = _multi(tg, TSH, rng)
            rec = {k: sum(1 for _ in range(tgt[k]) if rng.random() < CATCH[k]) for k in TSH}
            ypa = rng.uniform(5.0, 8.5)
            ry = {k: tgt[k] * ypa * rng.uniform(0.5, 1.5) for k in TSH}      # yards on TARGETS, not catches
            cy = sum(ry.values())
            td = max(0, int(round((pts[c] - 3.0 + rng.gauss(0.0, 4.0)) / 6.5)))
            n_pass = sum(1 for _ in range(td) if rng.random() < 0.6)
            ptd = _multi(n_pass, PTD_SH, rng)                                   # independent of catches
            qtd = _multi(n_pass, {k: float(v) for k, v in qatt.items() if v > 0}, rng)
            car = _multi(rng.randrange(18, 32), CSH, rng)
            rtd = _multi(td - n_pass, RTD_SH, rng)                              # independent of carries
            csw[c].append((pts[c], td))
            for p in POS:
                k = f'{p}|{c}'
                if POS[p] == 'QB':
                    sd[k].append((float(qatt[p]), cy * qatt[p] / pa, float(qtd.get(p, 0)), float(car.get(p, 0)),
                                  car.get(p, 0) * rng.uniform(2.0, 6.0), float(rtd.get(p, 0)), 0.0, 0.0, 0.0, 0.0))
                else:
                    sd[k].append((0.0, 0.0, 0.0, float(car.get(p, 0)), car.get(p, 0) * rng.uniform(2.0, 6.0),
                                  float(rtd.get(p, 0)), float(tgt[p]), float(rec[p]), ry[p], float(ptd[p])))
    rows = {}
    for k, v in sd.items():
        p = k.split('|')[0]
        a = np.asarray(v)
        att, car, tg = a[:, 0].mean(), a[:, 3].mean(), a[:, 6].mean()
        r = {'name': p, 'team': k.split('|')[1], 'position': POS[p], 'dk_points': 10.0,
             'carries': car, 'targets': tg, 'receptions': tg * CATCH.get(p, 0.0),
             'td': {'rec_td': a[:, 9].mean() + 0.01 * (POS[p] != 'QB'), 'rush_td': a[:, 5].mean() + 0.02 * (p == 'W1')},
             'conditional_volume': {'carries': car, 'rush_yards': car * 4.2, 'targets': tg,
                                    'receptions': (tg * CATCH[p]) if p in CATCH else None,
                                    'rec_yards': (tg * REC_YPT) if p in CATCH else None,
                                    'pass_attempts': att, 'pass_yards': att * QB_YPA if POS[p] == 'QB' else None}}
        rows[k] = r
    draws = {k: [CR.dk_from_stats(*w, 0) for w in v] for k, v in sd.items()}
    for c in (HOME, AWAY):
        draws[f'K|{c}'] = [0.0] * n
        draws[f'D|{c}'] = [0.0] * n
    art = {'STAT_FIELDS': CR.STAT_FIELDS, 'stat_draws': sd, 'club_scoring_worlds': csw, 'dst_components': dcomp,
           'world_points': {'home': HOME, 'away': AWAY, 'points': wp},
           'kickers': {f'K|{c}': {'mean': 0.0} for c in (HOME, AWAY)}, 'draws': draws}
    return art, rows


def _publish_lines(lines, points, dcomp, draws=None):
    """Write 11-field stat lines in the published format and return the scenario dir."""
    d = pathlib.Path(tempfile.mkdtemp(prefix='ecw_'))
    CR._write_worlds(d / 'SHOWDOWN_X_WORLDS.npz', lines, {'G': {'world_points': {'home': HOME, 'away': AWAY,
                                                                                    'points': points}}}, None)
    dr = draws or {k: [CR.dk_from_stats(*w) for w in v] for k, v in lines.items()}
    (d / 'SHOWDOWN_X_DRAWS.json').write_text(json.dumps({'draws': dr, 'dst_components': dcomp}))
    return d


def _build(seed=11, anchor=ECW.ANCHOR_QB, n=400):
    art, rows = synthetic(n=n)
    o = ECW.build(art, rows, INT_RATE, seed, club_pass_anchor=anchor, kicker_inputs=KICK)
    return art, rows, o


_CACHE = {}


def _repaired(anchor=ECW.ANCHOR_QB):
    if anchor not in _CACHE:
        art, rows, o = _build(anchor=anchor)
        d = pathlib.Path(tempfile.mkdtemp(prefix='ecw_pub_'))
        if o.state.value == 'PASS':
            ECW.publish(o.value, d, 'X', game_id='G')
        _CACHE[anchor] = (art, rows, o, d)
    return _CACHE[anchor]


def test_a_synthetic_raw_worlds_carry_the_defects():
    art, rows = synthetic()
    lines = {k: [tuple(w) + (0.0,) for w in v] for k, v in art['stat_draws'].items()}
    d = _publish_lines(lines, art['world_points']['points'], art['dst_components'])
    r = WAC.check(d)['VIOLATED']
    x = ECW.event_checks(d)['VIOLATED']
    check(r.get('YDS_WITHOUT_CATCH', 0) > 0, f"raw: receiving yards without a catch present ({r.get('YDS_WITHOUT_CATCH')})")
    check(r.get('REC_TD_WITHOUT_CATCH', 0) > 0, f"raw: receiving TD without a catch present ({r.get('REC_TD_WITHOUT_CATCH')})")
    check(x.get('RUSH_TD_LE_CARRIES', 0) > 0, f"raw: rushing TD without a carry present ({x.get('RUSH_TD_LE_CARRIES')})")
    check(x.get('REC_TD_LE_RECEPTIONS', 0) > 0, f"raw: more receiving TDs than catches present ({x.get('REC_TD_LE_RECEPTIONS')})")


def test_b_negative_control_incumbent_independent_factors_fail():
    art, rows = synthetic()
    _dk, worlds, _eff = CR.efficiency_worlds(art['stat_draws'], rows, INT_RATE, 99)
    d = _publish_lines(worlds, art['world_points']['points'], art['dst_components'])
    r = WAC.check(d)
    v = r['VIOLATED']
    check(v.get(f'{HOME}:PASS_YDS_EQ_REC_YDS', 0) > 0.9 * 400 and v.get(f'{AWAY}:PASS_YDS_EQ_REC_YDS', 0) > 0.9 * 400,
          f'the incumbent independent yard factors break PASS_YDS == REC_YDS in nearly every world '
          f"({v.get(f'{HOME}:PASS_YDS_EQ_REC_YDS')}, {v.get(f'{AWAY}:PASS_YDS_EQ_REC_YDS')} of 400)")
    md = r['checks'][f'{HOME}:PASS_YDS_EQ_REC_YDS']['mean_diff']
    check(md < -10, f'  and in the direction the fixture implies: QB 6.0/att vs receivers 9.0/target -> mean diff {md}')
    check(v.get(f'{HOME}:INT_LE_OPP_TAKEAWAYS', 0) + v.get(f'{AWAY}:INT_LE_OPP_TAKEAWAYS', 0) > 0,
          'the incumbent per-attempt INT draw throws interceptions the opposing DST never took away')
    check(v.get('YDS_WITHOUT_CATCH', 0) > 0, '  and the raw yards-without-catch defect passes straight through it')


def test_c_repaired_arm_passes_every_check_non_vacuously():
    art, rows, o, d = _repaired()
    if not check(o.state.value == 'PASS', f'the arm builds ({o.state.value}[{o.code}] {o.detail})'):
        return
    r = WAC.check(d)
    check(r['VIOLATED'] == {}, f"world_accounting_check: no violation ({r['VIOLATED']})")
    need = [f'{c}:{x}' for c in (HOME, AWAY) for x in ('PASS_YDS_EQ_REC_YDS', 'PASS_TD_EQ_REC_TD', 'TARGETS_LE_ATTEMPTS',
                                                       'INT_LE_OPP_TAKEAWAYS', 'POINTS_GE_6_PER_TD')]
    need += ['REC_LE_TARGETS', 'YDS_WITHOUT_CATCH', 'REC_TD_WITHOUT_CATCH', 'INT_LE_ATTEMPTS', 'DK_FROM_PUBLISHED']
    have = r['checks']
    check(all(k in have and have[k]['of'] >= 400 for k in need),
          f'  every law was measured on every world ({[k for k in need if k not in have or have[k]["of"] < 400]})')
    wi = sum(have[f'{c}:INT_LE_OPP_TAKEAWAYS'].get('worlds_with_ints', 0) for c in (HOME, AWAY))
    check(wi > 100, f'  the INT law is not vacuous: {wi} club-worlds carry an interception')
    check(have['DK_FROM_PUBLISHED']['players'] == 14, f"  DK recomputed for all 14 skill players ({have['DK_FROM_PUBLISHED']['players']})")
    x = ECW.event_checks(d)
    check(x['VIOLATED'] == {} and x['NOT_MEASURABLE'] == [],
          f"event laws (points = event sum, kicker/DST DK from events, TD <= catches/carries): {x['VIOLATED']} "
          f"not measurable {x['NOT_MEASURABLE']}")
    ev = o.value['scoring_events']
    tds = sum(sum(ev[c]['off_td']) for c in (HOME, AWAY))
    fgs = sum(sum(ev[c]['fg_made']) for c in (HOME, AWAY))
    check(tds > 500 and fgs > 100, f'  the point law is not vacuous: {tds:.0f} offensive TDs, {fgs:.0f} FGs')
    for k, v in o.value['stat_worlds'].items():
        a = np.asarray(v)
        if POS[k.split('|')[0]] != 'QB':
            if not check(bool(((a[:, 9] <= a[:, 7]) & ((a[:, 8] == 0) | (a[:, 7] > 0))).all()),
                         f'  {k}: rec TD <= receptions and yards only with a catch, every world'):
                break


def test_d_seeded_violations_on_repaired_output_are_caught():
    art, rows, o, d = _repaired()
    if o.state.value != 'PASS':
        check(False, 'arm did not build')
        return
    lines = {k: [list(w) for w in v] for k, v in o.value['stat_worlds'].items()}
    k, w = next((k, w) for k, v in lines.items() for w, x in enumerate(v) if x[9] > 0)
    lines[k][w][7] = 0
    dd = _publish_lines({a: [tuple(x) for x in b] for a, b in lines.items()}, o.value['world_points']['points'],
                        o.value['dst_components'])
    v = WAC.check(dd)['VIOLATED']
    check(v.get('REC_TD_WITHOUT_CATCH') == 1 and v.get('YDS_WITHOUT_CATCH', 0) <= 1,
          f'deleting one TD-scorer\'s receptions is caught ({v})')
    lines = {k: [list(w) for w in v] for k, v in o.value['stat_worlds'].items()}
    q = f'Q|{HOME}'
    w = next(i for i, x in enumerate(lines[q]) if x[1] > 50)
    lines[q][w][1] += 25.0
    dd = _publish_lines({a: [tuple(x) for x in b] for a, b in lines.items()}, o.value['world_points']['points'],
                        o.value['dst_components'])
    check(WAC.check(dd)['VIOLATED'].get(f'{HOME}:PASS_YDS_EQ_REC_YDS') == 1, '25 QB yards nobody caught are caught')
    _dk, inc, _e = CR.efficiency_worlds(art['stat_draws'], rows, INT_RATE, 99)
    lines = {k: [list(x) for x in v] for k, v in o.value['stat_worlds'].items()}
    for k in lines:
        for i, x in enumerate(lines[k]):
            x[10] = inc[k][i][10]
    dd = _publish_lines({a: [tuple(x) for x in b] for a, b in lines.items()}, o.value['world_points']['points'],
                        o.value['dst_components'])
    v = WAC.check(dd)['VIOLATED']
    check(v.get(f'{HOME}:INT_LE_OPP_TAKEAWAYS', 0) + v.get(f'{AWAY}:INT_LE_OPP_TAKEAWAYS', 0) > 0,
          f'BYPASS: putting back the incumbent per-attempt INTs fails INT <= opposing takeaways ({v})')
    pts = [(p[0] - 6.0, p[1]) for p in o.value['world_points']['points']]
    dd = _publish_lines(o.value['stat_worlds'], pts, o.value['dst_components'])
    (dd / 'SHOWDOWN_X_DRAWS.json').write_text(json.dumps({'draws': o.value['draws'], 'dst_components':
                                                          o.value['dst_components'],
                                                          'scoring_events': o.value['scoring_events'],
                                                          'club_scoring_worlds': o.value['club_scoring_worlds'],
                                                          'account': o.value['account']}))
    x = ECW.event_checks(dd)['VIOLATED']
    check(x.get(f'{HOME}:POINTS_EQ_EVENT_SUM') == 400, f'BYPASS: club points that are not the event sum are caught ({x})')


def _digest(res):
    import hashlib
    blob = json.dumps({k: res[k] for k in ('stat_worlds', 'draws', 'world_points', 'scoring_events')},
                      sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


_DIGEST_SNIPPET = (
    'import sys; sys.path.insert(0, {repo!r}); sys.path.insert(0, {tests!r})\n'
    'import test_event_consistent_worlds as T\n'
    'art, rows, o = T._build(seed=11, n=120)\n'
    'print(T._digest(o.value))\n')


def test_e_determinism_under_a_fixed_seed():
    a = _build(seed=11, n=120)[2]
    b = _build(seed=11, n=120)[2]
    c = _build(seed=12, n=120)[2]
    if not check(all(x.state.value == 'PASS' for x in (a, b, c)), 'three builds'):
        return
    da, db, dc = _digest(a.value), _digest(b.value), _digest(c.value)
    check(da == db, f'same seed -> byte-identical worlds, draws, points and events ({da[:12]})')
    check(da != dc, f'  a different seed -> different worlds ({dc[:12]})')
    code = _DIGEST_SNIPPET.format(repo=str(_REPO), tests=str(_REPO / 'nfl/tests'))
    outs = []
    for hs in ('1', '777'):
        env = {**os.environ, 'PYTHONHASHSEED': hs}
        p = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, env=env, cwd=str(_REPO))
        outs.append(p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr[-300:])
    check(outs[0] == outs[1] == da, f'  and identical in fresh interpreters under PYTHONHASHSEED 1 and 777 ({outs})')


def test_f_mean_anchoring():
    art, rows, o, _d = _repaired(ECW.ANCHOR_QB)
    _ar, _rw, o2, _d2 = _repaired(ECW.ANCHOR_REC)
    if not check(o.state.value == 'PASS' and o2.state.value == 'PASS', 'both anchors build'):
        return
    _dk, inc, _e = CR.efficiency_worlds(art['stat_draws'], rows, INT_RATE, 11 + 99)
    I = {k: np.asarray(v) for k, v in inc.items()}
    for res, anchor in ((o.value, ECW.ANCHOR_QB), (o2.value, ECW.ANCHOR_REC)):
        S = {k: np.asarray(v) for k, v in res['stat_worlds'].items()}
        for c in (HOME, AWAY):
            qb = [k for k in S if k.endswith('|' + c) and POS[k.split('|')[0]] == 'QB']
            rc = [k for k in S if k.endswith('|' + c) and k not in qb]
            new = sum(S[k][:, 1] for k in qb)
            want = (sum(I[k][:, 1].mean() for k in qb) if anchor == ECW.ANCHOR_QB
                    else sum(I[k][:, 8].mean() for k in rc))
            check(abs(new.mean() - want) <= 1e-9 * max(1.0, want),
                  f'{anchor} {c}: club passing yards mean {new.mean():.4f} == declared incumbent club mean {want:.4f}')
            check(np.allclose(new, sum(S[k][:, 8] for k in rc), atol=1e-9), f'  {c}: and QB yards == receiver yards per world')
            att = sum(S[k][:, 0] for k in qb)
            ints = sum(S[k][:, 10] for k in qb)
            se = (ints.var() / len(ints)) ** 0.5
            check(abs(ints.mean() - INT_RATE * att.mean()) <= 4 * se,
                  f'  {c}: INT mean {ints.mean():.4f} vs int_rate x attempts {INT_RATE * att.mean():.4f} '
                  f'(4 MC SE = {4 * se:.4f})')
            raw = {k: np.asarray(art['stat_draws'][k]) for k in S if k.endswith('|' + c)}
            n_pass = np.maximum(sum(raw[k][:, 2] for k in qb), sum(raw[k][:, 9] for k in rc))
            check(np.array_equal(sum(S[k][:, 9] for k in rc), n_pass) and np.array_equal(sum(S[k][:, 2] for k in qb), n_pass),
                  f'  {c}: every drawn passing TD is on a catch and on a passer (club count unchanged)')
            ctd = np.array([t for _p, t in art['club_scoring_worlds'][c]], dtype=float)
            check(np.array_equal(sum(S[k][:, 2] + S[k][:, 5] for k in S if k.endswith('|' + c)), ctd),
                  f'  {c}: offensive TDs on player lines == the world\'s club TDs')
            car = {k: S[k][:, 3] for k in raw}
            check(all(np.allclose(np.where(car[k] > 0, I[k][:, 4], 0.0), S[k][:, 4]) for k in raw),
                  f'  {c}: rushing yards are the incumbent\'s per-carry anchored yards')
        if anchor == ECW.ANCHOR_REC:
            bad = []
            for k in S:
                if POS[k.split('|')[0]] == 'QB':
                    continue
                d = S[k][:, 8] - I[k][:, 8]
                se = d.std() / len(d) ** 0.5
                if abs(d.mean()) > 4 * se + 1e-9:
                    bad.append((k, round(d.mean(), 3), round(4 * se, 3)))
            check(not bad, f'  receiver anchor: every receiver\'s mean yards within 4 paired MC SE of the incumbent ({bad})')
        tdbad = []
        for k in S:
            for j, f in ((9, 'rec_td'), (5, 'rush_td')):
                d = S[k][:, j] - np.asarray(art['stat_draws'][k])[:, j]
                se = d.std() / len(d) ** 0.5
                if abs(d.mean()) > 4 * se + 0.02:
                    tdbad.append((k, f, round(d.mean(), 3)))
        check(not tdbad, f'  {anchor}: TD means stay within 4 paired SE (+0.02 for redistributed unallocated TDs) of raw ({tdbad})')


def test_g_dk_recomputed_from_published_stat_line():
    from nfl.product import dk_scoring as DK
    _a, _r, o, d = _repaired()
    if o.state.value != 'PASS':
        check(False, 'arm did not build')
        return
    worst = 0.0
    for k, v in o.value['stat_worlds'].items():
        a = np.asarray(v)
        p = DK.skill_points(len(a), pass_yds=a[:, 1], pass_td=a[:, 2], ints=a[:, 10], rush_yds=a[:, 4],
                            rush_td=a[:, 5], rec=a[:, 7], rec_yds=a[:, 8], rec_td=a[:, 9])
        worst = max(worst, float(np.abs(p - np.asarray(o.value['draws'][k])).max()))
    check(worst < 1e-9, f'nfl/product/dk_scoring.skill_points on the stat line == published DK (max diff {worst})')
    r = WAC.check(d)['checks']['DK_FROM_PUBLISHED']
    check(r['violations'] == 0 and r['players'] == 14 and r['of'] == 14 * 400,
          f"world_accounting_check DK_FROM_PUBLISHED on the stored (0.1-yd) lines: {r['violations']} of {r['of']}")


def test_h_kicker_line_is_kicker_world_draw():
    from nfl.tools import kicker_world as KW
    rng = random.Random(5)
    bad = []
    for s in range(300):
        pts, td = rng.uniform(0, 45), rng.randrange(0, 6)
        a, da = ECW.kicker_line(pts, td, KICK[HOME]['mix'], KICK[HOME]['rates'], random.Random(s))
        b, db = KW.draw(pts, td, KICK[HOME]['mix'], KICK[HOME]['rates'], random.Random(s))
        if a != b or any(da[k] != db[k] for k in db):
            bad.append(s)
        if da['tp_att'] != td - da['xp_att'] or da['tp_made'] > da['tp_att']:
            bad.append(('tp', s))
    check(not bad, f'300 seeded draws: same DK and same events as kicker_world.draw, plus consistent 2pt tries ({bad[:5]})')


def test_i_refusals_are_named():
    art, rows = synthetic(n=50)
    o = ECW.build({**art, 'stat_draws': {}}, rows, INT_RATE, 1, kicker_inputs=KICK)
    check(o.state.value == 'FAIL' and o.code == 'EVENT_WORLDS_INPUT_EMPTY', f'empty stat draws refused ({o.code})')
    r2 = dict(rows)
    r2.pop(f'W1|{HOME}')
    o = ECW.build(art, r2, INT_RATE, 1, kicker_inputs=KICK)
    check(o.state.value == 'FAIL' and o.code == 'EVENT_WORLDS_NO_PROJECTION_ROW', f'missing projection row refused ({o.code})')
    o = ECW.build(art, rows, INT_RATE, 1, club_pass_anchor='MIDPOINT', kicker_inputs=KICK)
    check(o.state.value == 'FAIL' and o.code == 'EVENT_WORLDS_ANCHOR_UNKNOWN', f'undeclared anchor refused ({o.code})')
    o = ECW.build(art, rows, INT_RATE, 1, kicker_inputs={})
    check(o.state.value == 'FAIL' and o.code == 'EVENT_WORLDS_NO_KICKER_INPUTS', f'missing kicker inputs refused ({o.code})')


def test_j_tb_dal_official_shadow_repair_artifact():
    rep_p = OUT / 'ACCOUNTING_REPAIR_REPORT.json'
    off = _REPO / 'nfl/dfs/salaries/showdown_tb_dal/WORLD_ACCOUNTING_OFFICIAL.json'
    if not rep_p.exists() or not (OUT / 'EVENT_CONSISTENT').is_dir() or not off.exists():
        blocked(f'{rep_p.relative_to(_REPO)} or the OFFICIAL accounting artifact is absent')
        return
    rep = json.loads(rep_p.read_text())
    official = json.loads(off.read_text())['VIOLATED']
    check(rep['before']['world_accounting_check'] == official,
          f"the report's BEFORE equals the committed checker reading of the published OFFICIAL worlds ({official})")
    check(rep['incumbent_reproduced']['max_abs_dk_diff'] == 0 and rep['incumbent_reproduced']['players'] == 49,
          f"  the incumbent was reproduced exactly from the same inputs ({rep['incumbent_reproduced']})")
    for sub in ('EVENT_CONSISTENT', 'EVENT_CONSISTENT_RECEIVER_ANCHOR'):
        r = WAC.check(OUT / sub)
        check(r['VIOLATED'] == {} and r['n_worlds'] == 2000 and r['checks']['DK_FROM_PUBLISHED']['players'] == 45,
              f"{sub}: world_accounting_check re-run on the stored arrays, no violation ({r['VIOLATED']})")
        x = ECW.event_checks(OUT / sub)
        check(x['VIOLATED'] == {} and x['NOT_MEASURABLE'] == [],
              f"  {sub}: event laws, no violation and nothing unmeasurable ({x['VIOLATED']}, {x['NOT_MEASURABLE']})")


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed')


if __name__ == '__main__':
    for _n, _f in sorted(globals().items()):
        if _n.startswith('test_') and callable(_f):
            print(_n)
            _f()
    print(f'{PASSED} passed, {FAILED} failed, {BLOCKED} blocked')
    sys.exit(1 if FAILED else 0)
