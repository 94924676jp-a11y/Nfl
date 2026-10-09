"""nfl/tools/sim_query.py: every answer is a count over stored worlds, and every refusal is named.

Fixtures are synthetic worlds written by the PRODUCTION writer (classic_slate_run._write_worlds) into a temp dir, so
the format under test is the one the runs publish and the expected counts are known by construction (no gitignored
data). One further test reads the committed TB@DAL 2026W5 OFFICIAL worlds and recounts an answer straight from the
raw arrays; if those files are absent it records BLOCKED, never a pass.

Covered: exact counts and probabilities, binomial SE, conditional probability, AND / OR / NOT, joint table,
quantiles and their order-statistic interval, correlation, INSUFFICIENT_WORLDS, ambiguous / unknown names,
punctuation normalisation, NOT_IN_WORLDS, DRAWS_NOT_LOADED, unknown and unsupported formats, misaligned or
mismatched draws, label inference and conflict, no-eval parsing, Showdown optimal-lineup frequency against a
brute-force recount, SHOWDOWN_ONLY on a Classic worldset, and the CLI's read-only output rule.
"""
import hashlib
import json
import math
import pathlib
import subprocess
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))
import numpy as np  # noqa: E402
from nfl.tools import sim_query as Q, classic_slate_run as CR  # noqa: E402

PASSED = FAILED = BLOCKED = 0
N = 200
TMP = pathlib.Path(tempfile.mkdtemp(prefix='sim_query_test_'))
F = list(CR.WORLD_FIELDS)


def check(ok, msg):
    global PASSED, FAILED
    PASSED, FAILED = (PASSED + 1, FAILED) if ok else (PASSED, FAILED + 1)
    print('  ok  ' if ok else '  FAIL', msg)


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label} -- {why}')


def raises(code, fn, *a, **k):
    try:
        fn(*a, **k)
    except Q.SimQueryError as e:
        return e if e.code == code else None
    return None


# ------------------------------------------------------------------------------------------- fixtures
def _line(**kw):
    return [float(kw.get(f, 0)) for f in F]


def _stat_worlds(extra_game=False):
    w = np.arange(N)
    sw = {
        'Alpha QB|AAA': [_line(pass_att=20 + i % 20, pass_yards=150 + i, pass_td=i % 3) for i in w],
        'Beta RB|AAA': [_line(carries=10 + i % 5, rush_yards=i, rush_td=int(i % 4 == 0), targets=2, receptions=1,
                              rec_yards=5, rec_td=int(i % 5 == 0)) for i in w],
        'Gamma WR|BBB': [_line(targets=i % 7 + 1, receptions=i % 7, rec_yards=10 * (i % 7), rec_td=int(i % 2 == 0))
                         for i in w],
        'Alex Smith|AAA': [_line(targets=1, receptions=i % 2, rec_yards=3 * (i % 2)) for i in w],
        'Alex Smith|BBB': [_line(carries=1, rush_yards=i % 3) for i in w],
        "D.J. O'Neil-Jones|BBB": [_line(targets=3, receptions=2, rec_yards=12.3, rec_td=int(i % 10 == 0)) for i in w],
    }
    gw = {'2026_99_BBB_AAA': {'world_points': {'home': 'AAA', 'away': 'BBB',
                                               'points': [[float(i % 50), 25.0] for i in w]}}}
    if extra_game:
        sw['Delta TE|DDD'] = [_line(targets=4, receptions=i % 4, rec_yards=8 * (i % 4)) for i in w]
        gw['2026_99_CCC_DDD'] = {'world_points': {'home': 'DDD', 'away': 'CCC',
                                                  'points': [[float(i % 30), float(i % 7)] for i in w]}}
    return sw, gw


def _write(name, extra_game=False, draws_mutator=None, draws_extra=None, proj='a' * 64):
    d = TMP / name
    d.mkdir(parents=True, exist_ok=True)
    sw, gw = _stat_worlds(extra_game)
    wp = d / 'WORLDS.npz'
    CR._write_worlds(wp, sw, gw, proj)
    draws = {}
    for k, v in sw.items():
        a = np.asarray(v)
        draws[k] = [round(float(CR.dk_from_stats(*row)), 3) for row in a]
    draws['Home DST|AAA'] = [float(i % 3) for i in range(N)]
    if draws_mutator:
        draws = draws_mutator(draws)
    doc = {'ARTIFACT': 'TEST_DRAWS', 'n_sims': N, 'projection_sha256': proj, 'draws': draws, **(draws_extra or {})}
    dp = d / 'DRAWS.json'
    dp.write_text(json.dumps(doc))
    return wp, dp, sw


WP, DP, SW = _write('showdown')
WS = Q.load(WP, DP, label='RESEARCH')


# ------------------------------------------------------------------------------------------- tests
def test_a_probability_counts_and_binomial_se():
    a = Q.ask(WS, "P(rush_yards['Beta RB|AAA'] >= 50)")
    check(a['status'] == 'OK' and a['numerator'] == 150 and a['denominator'] == N and a['value'] == 0.75,
          f"P(rush_yards >= 50) = 150/200 = 0.75 ({a['numerator']}/{a['denominator']} = {a['value']})")
    check(abs(a['se'] - math.sqrt(0.75 * 0.25 / N)) < 1e-6, f"binomial SE sqrt(.75*.25/200) ({a['se']})")
    check(a['ci95_wilson'][0] < 0.75 < a['ci95_wilson'][1], f"Wilson interval brackets p ({a['ci95_wilson']})")
    check(a['query'] == "P(rush_yards['Beta RB|AAA'] >= 50)" and a['n_worlds'] == N,
          f"normalised query text and n_worlds ({a['query']!r}, {a['n_worlds']})")
    c = Q.ask(WS, "COUNT(rush_yards['Beta RB|AAA'] < 50)")
    check(c['value'] == 50 and c['kind'] == 'COUNT', f"COUNT(rush_yards < 50) = 50 ({c['value']})")
    e = Q.ask(WS, "P(rush_yards['Beta RB|AAA'] >= 500)")
    check(e['value'] == 0.0 and e['se'] == 0.0 and 'Wilson' in e.get('note', '') and e['ci95_wilson'][1] > 0,
          f"p = 0 carries a nonzero Wilson upper bound, not a bare 0 ({e['ci95_wilson']})")


def test_b_boolean_combinators():
    k = "any_td['Beta RB|AAA'] >= 1"
    a = Q.ask(WS, f'P({k})')
    check(a['numerator'] == 80, f'any_td = rush_td + rec_td: w%4==0 or w%5==0 -> 80 worlds ({a["numerator"]})')
    b = Q.ask(WS, "P(rush_td['Beta RB|AAA'] >= 1 AND rec_td['Beta RB|AAA'] >= 1)")
    check(b['numerator'] == 10, f'AND: w%20==0 -> 10 ({b["numerator"]})')
    o = Q.ask(WS, "P(rush_td['Beta RB|AAA'] >= 1 OR rec_td['Gamma WR|BBB'] >= 1)")
    check(o['numerator'] == 100, f'OR: w%4==0 or w%2==0 -> 100 ({o["numerator"]})')
    n = Q.ask(WS, "P(NOT rush_yards['Beta RB|AAA'] >= 50)")
    check(n['numerator'] == 50, f'NOT -> 50 ({n["numerator"]})')
    p = Q.ask(WS, "P(NOT (rush_td['Beta RB|AAA'] >= 1 OR rec_td['Beta RB|AAA'] >= 1) and rush_yards['Beta RB|AAA'] < 100)")
    exp = sum(1 for i in range(N) if not (i % 4 == 0 or i % 5 == 0) and i < 100)
    check(p['numerator'] == exp, f'parentheses, lower-case keyword, precedence ({p["numerator"]} vs {exp})')
    r = Q.ask(WS, p['query'])
    check(r['query'] == p['query'] and r['numerator'] == p['numerator'] and p['query'].startswith('P(NOT ('),
          f'the normalised text is itself a valid query with the same answer ({p["query"]})')
    j = Q.ask(WS, "JOINT(rush_td['Beta RB|AAA'] >= 1, rec_td['Beta RB|AAA'] >= 1)")
    cells = j['value']
    check(cells['A_and_B']['count'] == 10 and cells['A_and_notB']['count'] == 40
          and cells['notA_and_B']['count'] == 30 and sum(c['count'] for c in cells.values()) == N,
          f'JOINT 2x2 table 10/40/30/120 ({[c["count"] for c in cells.values()]})')
    check(abs(j['lift'] - (10 / 200) / ((50 / 200) * (40 / 200))) < 1e-3, f'lift = P(AB)/(P(A)P(B)) ({j["lift"]})')


def test_c_conditional_and_insufficient():
    a = Q.ask(WS, "P(any_td['Beta RB|AAA'] >= 1 | rush_yards['Beta RB|AAA'] >= 100)")
    check(a['status'] == 'OK' and (a['numerator'], a['denominator']) == (40, 100) and a['value'] == 0.4,
          f"conditional 40/100 ({a['numerator']}/{a['denominator']})")
    check(abs(a['se'] - math.sqrt(0.4 * 0.6 / 100)) < 1e-6 and a['kind'] == 'CONDITIONAL_PROBABILITY',
          f"conditional SE uses the conditioning count ({a['se']})")
    s = Q.ask(WS, "P(rush_td['Beta RB|AAA'] >= 1 | rec_td['Beta RB|AAA'] >= 1)")
    check(s['status'] == 'INSUFFICIENT_WORLDS' and s['value'] is None and s['denominator'] == 40,
          f"40 conditioning worlds < 50 -> INSUFFICIENT_WORLDS, no number ({s['status']}, {s['value']})")
    s2 = Q.ask(WS, "P(rush_td['Beta RB|AAA'] >= 1 | rec_td['Beta RB|AAA'] >= 1)", min_worlds=10)
    check(s2['value'] == 0.25, f'the same with a declared floor of 10 -> 10/40 ({s2["value"]})')
    qn = Q.ask(WS, "QUANTILES(rush_yards['Beta RB|AAA'] | rec_td['Beta RB|AAA'] >= 1)")
    check(qn['status'] == 'INSUFFICIENT_WORLDS' and qn['value'] is None, 'conditional quantiles refuse below 50 too')
    z = Q.ask(WS, "P(rush_yards['Beta RB|AAA'] >= 1 | rush_yards['Beta RB|AAA'] > 1000)")
    check(z['status'] == 'INSUFFICIENT_WORLDS' and z['denominator'] == 0, 'an empty condition is INSUFFICIENT, not 0/0')


def test_d_quantiles_mean_corr():
    q = Q.ask(WS, "QUANTILES(rush_yards['Beta RB|AAA'], 0.25, 0.5)")
    v = q['value']
    check(v['0.5']['value'] == 99.5 and v['0.25']['value'] == 49.75,
          f"quantiles of 0..199: median 99.5, q25 49.75 ({v['0.5']['value']}, {v['0.25']['value']})")
    lo, hi = v['0.5']['ci95']
    check(lo < 99.5 < hi and v['0.5']['se'] > 0 and 'order-statistic' in q['se_method'],
          f"order-statistic interval brackets the median ({lo}, {hi}; se {v['0.5']['se']})")
    exp_se = 1.0 / math.sqrt(N) * math.sqrt(0.25) / (1 / N)     # n=200 uniform spacing 1: SE ~ sqrt(q(1-q)/n)/f
    check(abs(v['0.5']['se'] - exp_se) / exp_se < 0.2, f'median SE close to the asymptotic {exp_se:.2f} ({v["0.5"]["se"]})')
    m = Q.ask(WS, "MEAN(rush_yards['Beta RB|AAA'] | rush_yards['Beta RB|AAA'] >= 100)")
    check(m['value'] == 149.5 and m['denominator'] == 100, f'conditional mean 149.5 ({m["value"]})')
    dk_b, dk_g = np.asarray(json.loads(DP.read_text())['draws']['Beta RB|AAA']), \
        np.asarray(json.loads(DP.read_text())['draws']['Gamma WR|BBB'])
    c = Q.ask(WS, "CORR(dk['Beta RB|AAA'], dk_points['Gamma WR|BBB'])")
    check(abs(c['value'] - float(np.corrcoef(dk_b, dk_g)[0, 1])) < 1e-4,
          f'Pearson equals a direct recount from the draws file ({c["value"]})')
    check(c['ci95'][0] < c['value'] < c['ci95'][1] and 'Fisher' in c['se_method'], f'Fisher interval ({c["ci95"]})')
    s = Q.ask(WS, "CORR(dk['Beta RB|AAA'], rush_yards['Beta RB|AAA'])")
    ry = np.array([row[F.index('rush_yards')] for row in SW['Beta RB|AAA']])
    check(abs(s['value'] - float(np.corrcoef(dk_b, ry)[0, 1])) < 1e-4,
          f'DK vs a stat line: Pearson equals a direct recount ({s["value"]})')
    check(bool(raises('ZERO_VARIANCE', Q.ask, WS, "CORR(interceptions['Alpha QB|AAA'], dk['Beta RB|AAA'])")),
          'a constant series raises ZERO_VARIANCE rather than reporting r = 0')


def test_e_club_points_margin_total_winner():
    m = Q.ask(WS, "P(margin['AAA'] >= 20)")
    check(m['numerator'] == 20, f"margin AAA = (w%50) - 25 >= 20 -> 20 worlds ({m['numerator']})")
    m2 = Q.ask(WS, "P(margin['bbb'] <= -20)")
    check(m2['numerator'] == 20, f'the opponent side, lower-case club ({m2["numerator"]})')
    w = Q.ask(WS, "P(wins['AAA'])")
    t = Q.ask(WS, "P(tie['AAA'])")
    lb = Q.ask(WS, "P(wins['BBB'])")
    check((w['numerator'], t['numerator'], lb['numerator']) == (96, 4, 100) and w['numerator'] + t['numerator'] + lb['numerator'] == N,
          f"wins/tie/loses partition the worlds: 96/4/100 ({w['numerator']}/{t['numerator']}/{lb['numerator']})")
    to = Q.ask(WS, "P(total['2026_99_BBB_AAA'] > 60)")
    exp = sum(1 for i in range(N) if i % 50 + 25 > 60)
    check(to['numerator'] == exp and Q.ask(WS, "P(total['AAA'] > 60)")['numerator'] == exp,
          f'total by game id and by club ({to["numerator"]} vs {exp})')
    x = Q.ask(WS, "P(dk['Beta RB|AAA'] > dk['Gamma WR|BBB'])")
    dr = json.loads(DP.read_text())['draws']
    exp = sum(1 for a, b in zip(dr['Beta RB|AAA'], dr['Gamma WR|BBB']) if a > b)
    check(x['numerator'] == exp, f'value-vs-value comparison ({x["numerator"]} vs {exp})')
    check(bool(raises('CLUB_NOT_FOUND', Q.ask, WS, "P(margin['ZZZ'] >= 1)")), 'an unknown club is refused by name')


def test_f_names_exact_or_refused():
    e = raises('PLAYER_AMBIGUOUS', Q.ask, WS, "P(rush_yards['Alex Smith'] >= 1)")
    check(bool(e) and e.evidence['candidates'] == ['Alex Smith|AAA', 'Alex Smith|BBB'],
          f"two Alex Smiths -> PLAYER_AMBIGUOUS listing both ({e and e.evidence})")
    a = Q.ask(WS, "P(rush_yards['alex smith|bbb'] >= 1)")
    check(a['numerator'] == sum(1 for i in range(N) if i % 3 >= 1), 'the club disambiguates; case is normalised')
    n = Q.ask(WS, "P(rec_td['dj oneil jones'] >= 1)")
    check(n['numerator'] == 20 and "O'Neil-Jones" in n['query'],
          f"punctuation normalisation only: 'dj oneil jones' -> the exact key ({n['query']})")
    nf = raises('PLAYER_NOT_FOUND', Q.ask, WS, "P(rush_yards['Alex Smyth'] >= 1)")
    check(bool(nf) and 'Alex Smith|AAA' in nf.evidence['candidates'],
          f'a misspelling is NOT guessed; candidates are listed ({nf and nf.evidence})')
    nf2 = raises('PLAYER_NOT_FOUND', Q.ask, WS, "P(rush_yards['Beta'] >= 1)")
    check(bool(nf2), 'a partial name is not a match')


def test_g_not_in_worlds_and_unknown_field():
    for f in ('first_td', 'td_order', 'snaps', 'longest_reception'):
        e = raises('NOT_IN_WORLDS', Q.ask, WS, f"P({f}['Beta RB|AAA'] >= 1)")
        check(bool(e), f'{f} -> NOT_IN_WORLDS (never approximated)')
    d = raises('NOT_IN_WORLDS', Q.ask, WS, "P(rush_yards['Home DST|AAA'] >= 1)")
    check(bool(d), 'a DST has DK draws but no stat line -> NOT_IN_WORLDS')
    ok = Q.ask(WS, "P(dk['Home DST|AAA'] >= 2)")
    check(ok['numerator'] == sum(1 for i in range(N) if i % 3 >= 2), 'but its dk_points can be asked')
    check(bool(raises('UNKNOWN_FIELD', Q.ask, WS, "P(rushyards['Beta RB|AAA'] >= 1)")), 'a typo is UNKNOWN_FIELD')
    nod = Q.load(WP, None, label='RESEARCH')
    check(bool(raises('DRAWS_NOT_LOADED', Q.ask, nod, "P(dk['Beta RB|AAA'] >= 1)")),
          'dk_points without a DRAWS.json -> DRAWS_NOT_LOADED')
    check(Q.ask(nod, "P(rush_yards['Beta RB|AAA'] >= 50)")['numerator'] == 150, 'stat queries still work without draws')


def test_h_parser_is_closed():
    for bad in ("P(__import__('os') >= 1)", "P(rush_yards['Beta RB|AAA'] >= 1); import os",
                "EVAL(rush_yards['Beta RB|AAA'])", "P(rush_yards['Beta RB|AAA'])", "P(1 >= 0)",
                "P(rush_yards['Beta RB|AAA'] >= 1", "QUANTILES(rush_yards['Beta RB|AAA'], 1.5)"):
        check(bool(raises('QUERY_PARSE_ERROR', Q.ask, WS, bad)), f'refused by the parser: {bad!r}')
    import ast
    src = (_REPO / 'nfl/tools/sim_query.py').read_text()
    calls = {n.func.id for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    check(not ({'eval', 'exec', 'compile', '__import__'} & calls), f'no eval/exec/compile in the module')


def test_i_format_refusals():
    p = TMP / 'junk.npz'
    np.savez(p, foo=np.zeros(3))
    check(bool(raises('UNKNOWN_WORLDS_FORMAT', Q.load, p, label='RESEARCH')), 'foreign arrays -> UNKNOWN_WORLDS_FORMAT')
    t = TMP / 'text.npz'
    t.write_text('not a zip')
    check(bool(raises('UNKNOWN_WORLDS_FORMAT', Q.load, t, label='RESEARCH')), 'a non-npz file -> UNKNOWN_WORLDS_FORMAT')
    s = TMP / 'X_STATS.npz'
    np.savez_compressed(s, **{'A B|AAA': np.zeros((5, 10)), 'C D|BBB': np.zeros((5, 10))})
    check(bool(raises('UNSUPPORTED_WORLDS_FORMAT', Q.load, s, label='RESEARCH')),
          'the showdown_draws *_STATS.npz sidecar is named and refused')
    z = np.load(WP)
    bad = TMP / 'int32.npz'
    np.savez_compressed(bad, stats=z['stats'].astype(np.int32), points=z['points'], meta=z['meta'])
    check(bool(raises('UNKNOWN_WORLDS_FORMAT', Q.load, bad, label='RESEARCH')), 'int32 stats -> UNKNOWN_WORLDS_FORMAT')
    meta = json.loads(z['meta'].tobytes())
    del meta['yard_scale']
    bm = TMP / 'nometa.npz'
    np.savez_compressed(bm, stats=z['stats'], points=z['points'],
                        meta=np.frombuffer(json.dumps(meta).encode(), dtype=np.uint8))
    check(bool(raises('UNKNOWN_WORLDS_FORMAT', Q.load, bm, label='RESEARCH')), 'meta without yard_scale is refused')


def test_j_draws_alignment_and_mismatch():
    def shuffle(d):
        rng = np.random.default_rng(7)
        return {k: list(rng.permutation(v)) for k, v in d.items()}
    wp, dp, _ = _write('misaligned', draws_mutator=shuffle)
    check(bool(raises('DRAWS_WORLDS_MISALIGNED', Q.load, wp, dp, label='RESEARCH')),
          'draws on a different world order -> DRAWS_WORLDS_MISALIGNED')
    wp2, dp2, _ = _write('projmismatch')
    doc = json.loads(dp2.read_text())
    doc['projection_sha256'] = 'b' * 64
    dp2.write_text(json.dumps(doc))
    check(bool(raises('WORLDS_DRAWS_MISMATCH', Q.load, wp2, dp2, label='RESEARCH')),
          'a different projection_sha256 -> WORLDS_DRAWS_MISMATCH')
    wp3, dp3, _ = _write('short', draws_mutator=lambda d: {k: v[:-1] for k, v in d.items()})
    check(bool(raises('WORLDS_DRAWS_MISMATCH', Q.load, wp3, dp3, label='RESEARCH')), 'a short draw list is refused')
    check(WS.provenance['dk_alignment']['agreement'] == 1.0, f"aligned fixture agrees 1.0 ({WS.provenance['dk_alignment']})")


def test_k_provenance_and_labels():
    p = WS.provenance
    check(p['worlds_sha256'] == hashlib.sha256(WP.read_bytes()).hexdigest()
          and p['draws_sha256'] == hashlib.sha256(DP.read_bytes()).hexdigest(), 'sha256 of both inputs recorded')
    check(p['n_worlds'] == N and p['projection_sha256'] == 'a' * 64 and p['format'] == 'WORLDS_NPZ_V1'
          and p['layout'] == 'SHOWDOWN' and p['read_only'] is True, 'n_worlds, projection_sha256, format, layout')
    check(Q.ask(WS, "P(wins['AAA'])")['provenance'] is p, 'every answer carries the provenance')
    check(bool(raises('LABEL_UNRESOLVED', Q.load, WP, DP)), 'a temp path with no marker -> LABEL_UNRESOLVED, not a guess')
    wp, dp, _ = _write('shadowarm', draws_extra={'ARM': 'EVENT_CONSISTENT_SHADOW', 'SHADOW_ONLY': 'research arm'})
    check(Q.load(wp, dp).label == 'SHADOW', 'a draws ARM marked SHADOW infers SHADOW')
    check(bool(raises('LABEL_CONFLICT', Q.load, wp, dp, label='PRODUCTION')), 'a SHADOW arm cannot be labelled PRODUCTION')
    off = TMP / 'nfl/dfs/salaries/x/OFFICIAL'
    off.mkdir(parents=True, exist_ok=True)
    (off / 'W.npz').write_bytes(WP.read_bytes())
    check(Q.load(off / 'W.npz').label == 'PRODUCTION', 'an OFFICIAL path infers PRODUCTION')
    sbs = Q.ask_side_by_side([WS, Q.load(wp, dp)], "P(first_td['Beta RB|AAA'] >= 1)")
    check([r['status'] for r in sbs] == ['REFUSED', 'REFUSED'] and sbs[1]['model_label'] == 'SHADOW'
          and sbs[0]['code'] == 'NOT_IN_WORLDS', 'side by side records each refusal with its label')


def _brute_optimal(draws, lineups):
    cpt, flex = {}, {}
    for w in range(N):
        sc = [1.5 * draws[c][w] + sum(draws[f][w] for f in fl) for c, fl in lineups]
        best = max(sc)
        win = [j for j, s in enumerate(sc) if abs(s - best) <= 1e-9]
        for j in win:
            c, fl = lineups[j]
            cpt[c] = cpt.get(c, 0) + 1 / len(win)
            for f in fl:
                flex[f] = flex.get(f, 0) + 1 / len(win)
    return cpt, flex


def test_l_optimal_lineup_frequency():
    names = {'Alpha QB|AAA': 'Alpha QB', 'Beta RB|AAA': 'Beta RB', 'Gamma WR|BBB': 'Gamma WR',
             "D.J. O'Neil-Jones|BBB": "D.J. O'Neil-Jones", 'Home DST|AAA': 'Home DST'}
    lineups = [('Beta RB|AAA', ['Alpha QB|AAA', 'Gamma WR|BBB', "D.J. O'Neil-Jones|BBB", 'Home DST|AAA', 'Alex Smith|AAA']),
               ('Alpha QB|AAA', ['Beta RB|AAA', 'Gamma WR|BBB', "D.J. O'Neil-Jones|BBB", 'Home DST|AAA', 'Alex Smith|BBB']),
               ('Gamma WR|BBB', ['Beta RB|AAA', 'Alpha QB|AAA', "D.J. O'Neil-Jones|BBB", 'Home DST|AAA', 'Alex Smith|AAA'])]
    csvp = TMP / 'CANDIDATES.csv'
    rows = ['captain,flex']
    for c, fl in lineups:
        rows.append(f'{names[c]},' + ' / '.join(f if f.startswith('Alex') else names[f] for f in fl))
    csvp.write_text('\n'.join(rows) + '\n')
    o = Q.optimal_frequency(WS, csvp)
    dr = {k: list(map(float, v)) for k, v in json.loads(DP.read_text())['draws'].items()}
    cpt, flex = _brute_optimal(dr, lineups)
    pp = o['per_player']
    ok = all(abs(pp[k]['cpt_worlds'] - cpt.get(k, 0)) < 1e-6 and abs(pp[k]['flex_worlds'] - flex.get(k, 0)) < 1e-6
             for k in pp)
    check(ok, f'CPT and FLEX world counts equal a brute-force per-world recount ({ {k: (v["cpt_worlds"], v["flex_worlds"]) for k, v in pp.items()} })')
    check(abs(sum(v['cpt_share'] for v in pp.values()) - 1.0) < 1e-6
          and abs(sum(v['flex_share'] for v in pp.values()) - 5.0) < 1e-6, 'CPT shares sum to 1 and FLEX to 5')
    b = pp['Beta RB|AAA']
    check(abs(b['cpt_se'] - math.sqrt(b['cpt_share'] * (1 - b['cpt_share']) / N)) < 1e-6, 'binomial SE on each share')
    check(o['players_in_draws_not_in_pool'] == [] or all(k not in pp for k in o['players_in_draws_not_in_pool']),
          'players outside the pool are listed, not given a share')
    bad = TMP / 'BAD.csv'
    bad.write_text('captain,flex\nBeta RB,Alpha QB / Gamma WR\n')
    check(bool(raises('CANDIDATE_INVALID', Q.optimal_frequency, WS, bad)), 'a 3-player lineup is refused')
    amb = TMP / 'AMB.csv'
    amb.write_text('captain,flex\nBeta RB,Alpha QB / Gamma WR / Home DST / Alex Smith / D.J. O\'Neil-Jones\n')
    check(bool(raises('PLAYER_AMBIGUOUS', Q.optimal_frequency, WS, amb)), 'an ambiguous candidate name is refused')
    wpc, dpc, _ = _write('classic', extra_game=True)
    wc = Q.load(wpc, dpc, label='RESEARCH')
    check(wc.layout == 'CLASSIC' and bool(raises('SHOWDOWN_ONLY', Q.optimal_frequency, wc, csvp)),
          'a two-game (Classic) worldset refuses Showdown optimal frequency')
    t = Q.ask(wc, "P(total['CCC'] >= 30)")
    check(t['numerator'] == sum(1 for i in range(N) if i % 30 + i % 7 >= 30), 'Classic: per-game total by club')


def test_m_cli_read_only():
    env_py = sys.executable
    r = subprocess.run([env_py, str(_REPO / 'nfl/tools/sim_query.py'), str(WP), '--draws', str(DP), '--label',
                        'RESEARCH', '--query', "P(rush_yards['Beta RB|AAA'] >= 50)", '--out', str(TMP / 'o.json')],
                       capture_output=True, text=True, timeout=120)
    out = json.loads((TMP / 'o.json').read_text()) if (TMP / 'o.json').exists() else {}
    check(r.returncode == 0 and out.get('answers', [[{}]])[0][0].get('numerator') == 150,
          f'CLI answers and writes --out ({r.returncode}, {r.stderr[-200:]})')
    before = hashlib.sha256(DP.read_bytes()).hexdigest()
    r2 = subprocess.run([env_py, str(_REPO / 'nfl/tools/sim_query.py'), str(WP), '--draws', str(DP), '--label',
                         'RESEARCH', '--query', "P(wins['AAA'])", '--out', str(DP)], capture_output=True, text=True,
                        timeout=120)
    check(r2.returncode == 2 and 'OUTPUT_REFUSED' in r2.stderr and hashlib.sha256(DP.read_bytes()).hexdigest() == before,
          'CLI refuses to write over an input file')
    r3 = subprocess.run([env_py, str(_REPO / 'nfl/tools/sim_query.py'), str(WP), '--label', 'RESEARCH', '--query',
                         "P(snaps['Beta RB|AAA'] > 1)"], capture_output=True, text=True, timeout=120)
    check(r3.returncode == 2 and 'NOT_IN_WORLDS' in r3.stderr, 'CLI exits 2 with the named refusal')


OFF = _REPO / 'nfl/dfs/salaries/showdown_tb_dal/OFFICIAL'
CAND = _REPO / 'nfl/dfs/salaries/showdown_tb_dal/OFFICIAL_ELIGIBILITY_FIX_R1/SHOWDOWN_TB_DAL_CANDIDATES.csv'


def test_n_real_tb_dal_official():
    wp, dp = OFF / 'SHOWDOWN_TB_DAL_2026W5_WORLDS.npz', OFF / 'SHOWDOWN_TB_DAL_2026W5_DRAWS.json'
    if not (wp.exists() and dp.exists()):
        blocked('real TB@DAL OFFICIAL worlds', f'{wp.relative_to(_REPO)} or its DRAWS.json is absent')
        return
    ws = Q.load(wp, dp)
    check(ws.label == 'PRODUCTION' and ws.n_worlds == 2000 and ws.layout == 'SHOWDOWN',
          f'OFFICIAL loads as PRODUCTION, 2000 worlds, SHOWDOWN ({ws.label}, {ws.n_worlds}, {ws.layout})')
    check(ws.provenance['receipt_check']['state'] == 'MATCH', f"worlds sha256 matches RUN_RECEIPT ({ws.provenance['receipt_check']['state']})")
    check(ws.provenance['dk_alignment']['agreement'] >= Q.ALIGNMENT_FLOOR, 'draws align with the stored stat lines')
    z = np.load(wp)
    meta = json.loads(z['meta'].tobytes())
    i, j = meta['keys'].index('Jalon Daniels|TB'), meta['fields'].index('rush_yards')
    raw = int((z['stats'][i, :, j] >= 500).sum())          # 50 yards in tenths, straight from the stored array
    a = Q.ask(ws, "P(rush_yards['Jalon Daniels|TB'] >= 50)")
    check(a['numerator'] == raw and a['denominator'] == 2000, f'P(Daniels rush >= 50) = raw recount {raw}/2000 ({a["numerator"]})')
    pts = z['points'][0]
    m = Q.ask(ws, "P(margin['DAL'] >= 20)")
    check(m['numerator'] == int((pts[:, 0] - pts[:, 1] >= 20).sum()), 'DAL margin >= 20 equals a raw recount')
    if CAND.exists():
        o = Q.optimal_frequency(ws, CAND)
        check(abs(sum(v['cpt_share'] for v in o['per_player'].values()) - 1.0) < 1e-6 and o['n_candidates'] > 0,
              f"real pool: CPT shares sum to 1 over {o['n_candidates']} candidates")
    else:
        blocked('real optimal frequency', f'{CAND.relative_to(_REPO)} absent')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')
    if PASSED == 0:
        raise AssertionError('this module recorded ZERO checks')


if __name__ == '__main__':
    for n in sorted(k for k in dir() if k.startswith('test_')):
        globals()[n]()
    print(f'{PASSED} passed, {FAILED} failed' + (f', {BLOCKED} blocked' if BLOCKED else ''))
    sys.exit(1 if FAILED else 0)
