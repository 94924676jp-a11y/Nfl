"""ONE PUBLICATION SEMANTIC ACROSS EVERY POSITION, asserted on every sealed board.

The board was found mixing two conditioning events. Non-QB rows published an
UNCONDITIONAL pregame expectation -- the mean over every simulated world,
including the worlds where the player never touched the ball. QB rows were
published on a different event, because a quarterback who did not start was
returned to the field in about 93% of those worlds, so his zero-participation
mass was 0.0039 where his own historical cell says 0.0694.

Owner's ruling: the board uses ONE contract, the unconditional one. This module
is the machine-checkable form of it, and it is deliberately POSITION-BLIND --
it reads the position only to report coverage, never to choose a rule.

WHAT IS ASSERTED, for every player on every sealed board
=======================================================
A. THE PUBLISHED MEAN IS THE UNCONDITIONAL DRAW MEAN. `metrics[k]['mean']`
   equals the mean of that player's full draw vector, to the board's own
   display quantum. No metric, no position, is exempt.
B. IT IS NOT THE CONDITIONAL MEAN. Where conditioning on participation moves
   the mean by more than the quantum, the published figure must track the
   unconditional one and DIFFER from the conditional one. Without this, A
   passes vacuously on every player who always participates -- which is most
   of them -- and the check that matters never runs.
C. A ZERO-PARTICIPATION WORLD IS ZERO EVERYWHERE. In every draw where the
   player has no opportunity, every metric he publishes and his DraftKings
   total are 0 AT THE MAXIMUM, not on average.

PARTICIPATION IS THE SUM OF EVERY OPPORTUNITY COLUMN, AND I GOT THIS WRONG FIRST
===============================================================================
I defined it as dropbacks + targets + carries and reported that wide receivers
and tight ends score DraftKings points in worlds where they have none of those
-- Greg Dortch 6.1 points at the maximum across 266 such draws. That is not a
defect. A receiver can carry the ball on a gadget run, whose yards live in
`gadget_rush/{wr,te}_yards` and reach the player through `rushing_total`, and
whose CARRY COUNT is stored nowhere per player. The DK vector sums
`rushing_total/rushing_yards` by construction and is right to.

Adding the column closes it exactly: 19 of 19, 266 of 266, 53 of 53 and 20 of
20 non-zero DK draws are accounted for, and with `rushing_total` at zero as
well the DK maximum is 0.00 on every one of them. The engine was right and my
accounting was short a column -- the same mistake, in the same shape, as the
QB-scramble term in `test_detbuf_conservation`.

WHAT IS NOT ASSERTED
====================
Nothing here says a participation probability is CORRECT. Whether 0.0039 or
0.0694 is the right zero-dropback mass for Josh Allen is a question for the
forward-chained evidence in `nfl/research/qbsem/`, not for a tripwire. This
module asserts only that whatever the model believes, every position publishes
it on the same event.
"""
from __future__ import annotations

import collections
import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.research import sealed_index as SI                        # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []

#: The board rounds a published mean to two decimals, so the largest lawful gap
#: between it and the draw mean is half a quantum. Measured worst case on the
#: DET-BUF GSVU board: 0.005000 exactly, on Amon-Ra St. Brown's receiving yards
#: (77.595 published as 77.59). A tolerance below this fails on rounding and
#: says nothing about semantics.
QUANTUM = 0.005 + 1e-9

#: EVERY column through which a player can acquire an opportunity. `rushing_
#: total` is here because a gadget carry by a receiver has no per-player count
#: anywhere else -- see the module docstring.
OPPORTUNITY = (('qb', 'db'), ('receiving', 'targets'), ('rushing', 'carries'),
               ('rushing_total', 'rushing_yards'), ('kicking', 'fga'),
               ('kicking', 'xpa'))

#: A conditional mean must move by more than this before check B demands that
#: the published figure be distinguishable from it. Below it the two events
#: agree to the board's own precision and there is nothing to discriminate.
MATERIAL = 0.02


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def not_executed(label, why):
    NOT_EXECUTED.append((label, why))
    print(f'  ..   NOT_EXECUTED {label} -- {why}')


def _load(d):
    d = pathlib.Path(d)
    board = json.load(open(d / 'board.json'))
    man = json.load(open(d / 'player_draws_manifest.json'))
    z = SI.load_draws(d)
    rid = {k: (v.get('row_ids') or []) for k, v in man['layers'].items()}
    return board, rid, {k: np.asarray(z[k], float) for k in z.files}


def _get(rid, arrays, layer, metric, pid):
    ids = rid.get(layer) or []
    key = f'{layer}__{metric}'
    if pid not in ids or key not in arrays:
        return None
    return arrays[key][ids.index(pid)]


def audit_board(d, tally):
    """Every player on one board. `tally` accumulates across the corpus."""
    audit_loaded(str(d), *_load(d), tally)


def audit_loaded(d, board, rid, arrays, tally):
    """The audit proper, over ALREADY-LOADED bytes.

    Split out from `audit_board` so a seeded violation can be fed through the
    exact code path the corpus uses. A tripwire nobody has shown will trip is
    not evidence of anything.
    """
    for p in board.get('players') or []:
        pid, pos = p.get('gsis_id'), (p.get('position') or '?')
        tally['positions'][pos] += 1

        vol = None
        for lay, met in OPPORTUNITY:
            v = _get(rid, arrays, lay, met, pid)
            if v is None:
                continue
            v = np.abs(v)
            vol = v if vol is None else vol + v
        if vol is None:
            tally['no_opportunity_column'].append((str(d), pid, pos))
            continue
        zero = vol <= 0

        for k, spec in (p.get('metrics') or {}).items():
            if '/' not in k:
                continue
            lay, met = k.split('/', 1)
            a = _get(rid, arrays, lay, met, pid)
            if a is None:
                tally['metric_without_array'].append((str(d), pid, k))
                continue
            pub = spec.get('mean')
            if pub is None:
                continue
            tally['n_metrics'] += 1
            tally['positions_scored'].add(pos)

            # A. published == UNCONDITIONAL
            dev = abs(float(a.mean()) - float(pub))
            if dev > QUANTUM:
                tally['A'].append((str(d), pid, pos, k, float(pub),
                                   round(float(a.mean()), 6), round(dev, 6)))

            # B. and NOT the conditional, wherever the two differ materially
            if zero.any() and (~zero).any():
                cond = float(a[~zero].mean())
                if abs(cond - float(a.mean())) > MATERIAL:
                    tally['n_discriminating'] += 1
                    if abs(cond - float(pub)) <= QUANTUM:
                        tally['B'].append((str(d), pid, pos, k, float(pub),
                                           round(float(a.mean()), 6),
                                           round(cond, 6)))

            # C. zero-opportunity worlds are zero AT THE MAXIMUM
            if zero.any():
                mx = float(np.abs(a[zero]).max())
                if mx > 0:
                    tally['C'].append((str(d), pid, pos, k, round(mx, 6),
                                       int(zero.sum())))

        dk = _get(rid, arrays, 'dk_scoring', 'dk_points', pid)
        if dk is not None and zero.any():
            tally['n_dk'] += 1
            mx = float(np.abs(dk[zero]).max())
            if mx > 0:
                tally['C'].append((str(d), pid, pos, 'dk_scoring/dk_points',
                                   round(mx, 6), int(zero.sum())))

    # KICKERS ARE MODELLED AND NOT PUBLISHED, AND THE FIRST VERSION OF THIS
    # MODULE MISSED THEM BECAUSE IT ONLY WALKED `board['players']`.
    #
    # Every board computes a `kicking` layer -- DET-BUF carries two rows,
    # fga/fgm/xpa/xpm/dk_points/offensive_td, means 1.88/1.59/2.48/2.36/8.13
    # -- and NO sealed board lists a kicker among its players. So K came back
    # NOT_EXECUTED not because the corpus has no kickers but because this
    # module could not see them. That was a gap in the test, and it made the
    # test report a gap in the evidence.
    #
    # The rows are audited straight off the manifest. Check C is the one that
    # applies: there is no published mean to compare against, which IS the
    # defect, and it is recorded in `kicking_unpublished` rather than being
    # silently skipped.
    kids = rid.get('kicking') or []
    for pid in kids:
        tally['positions']['K'] += 1
        vol = None
        for met in ('fga', 'xpa'):
            v = _get(rid, arrays, 'kicking', met, pid)
            if v is not None:
                v = np.abs(v)
                vol = v if vol is None else vol + v
        if vol is None:
            tally['no_opportunity_column'].append((str(d), pid, 'K'))
            continue
        published = any(p.get('gsis_id') == pid
                        for p in (board.get('players') or []))
        if not published:
            tally['kicking_unpublished'].append((str(d), pid))
        zero = vol <= 0
        if not zero.any():
            continue
        tally['positions_scored'].add('K')
        # `offensive_td` IS NOT IN THIS LIST AND THE FIRST VERSION HAD IT.
        #
        # It is the TEAM's offensive touchdowns in that draw, recorded on the
        # kicker's row as the INPUT the kicker model was conditioned on, not
        # as anything the kicker produced. Requiring it to be zero when he
        # has no attempt applies a production rule to an input column, and it
        # fired on four sealed boards.
        #
        # Nor is a zero-attempt draw with touchdowns incoherent. `xpa` tracks
        # `offensive_td` at about 0.86 attempts per touchdown -- means 0.856,
        # 1.768, 2.677, 3.623 at td = 1..4 -- the remainder being two-point
        # tries. P(xpa = 0 | td = 4) is 0.0025, which is a rare world and not
        # an impossible one. The engine was right and my accounting was short
        # a distinction, the same mistake in the same shape as the gadget-rush
        # column above.
        for met in ('fgm', 'xpm', 'dk_points'):
            a = _get(rid, arrays, 'kicking', met, pid)
            if a is None:
                continue
            tally['n_metrics_kicking'] += 1
            mx = float(np.abs(a[zero]).max())
            if mx > 0:
                tally['C_kicking'].append((str(d), pid, f'kicking/{met}',
                                           round(mx, 6), int(zero.sum())))


def _new_tally():
    return {'A': [], 'B': [], 'C': [], 'n_metrics': 0, 'n_dk': 0,
            'n_discriminating': 0, 'positions': collections.Counter(),
            'positions_scored': set(), 'no_opportunity_column': [],
            'metric_without_array': [], 'C_kicking': [],
            'n_metrics_kicking': 0, 'kicking_unpublished': []}


_CORPUS = None


def _corpus():
    global _CORPUS
    if _CORPUS is None:
        _CORPUS = _new_tally()
        dirs = [pathlib.Path(f).parent for f in SI.live_draw_files()]
        _CORPUS['dirs'] = dirs
        for d in dirs:
            try:
                audit_board(d, _CORPUS)
            except Exception as e:                       # noqa: BLE001
                _CORPUS.setdefault('errors', []).append((str(d), repr(e)[:200]))
    return _CORPUS


def _seed(kind, m=200):
    """A one-player board that satisfies every contract, then breaks ONE.

    The background is CONSTRUCTED to pass, so a test that seeds a violation is
    changing one thing against a known-good baseline rather than measuring the
    accumulated state of a real board.
    """
    rng = np.random.default_rng(7)
    tgt = np.where(rng.random(m) < 0.30, 0.0, rng.integers(1, 9, m).astype(float))
    yds = np.where(tgt > 0, tgt * 9.0, 0.0)
    dk = yds * 0.1 + tgt * 0.0
    arrays = {'receiving__targets': np.stack([tgt]),
              'receiving__receiving_yards': np.stack([yds]),
              'dk_scoring__dk_points': np.stack([dk])}
    rid = {'receiving': ['X'], 'dk_scoring': ['X']}
    board = {'players': [{'gsis_id': 'X', 'position': 'WR', 'metrics': {
        'receiving/targets': {'mean': round(float(tgt.mean()), 2)},
        'receiving/receiving_yards': {'mean': round(float(yds.mean()), 2)}}}]}
    met = board['players'][0]['metrics']
    if kind == 'A':
        met['receiving/receiving_yards']['mean'] = round(
            float(yds.mean()) + 1.0, 2)
    elif kind == 'B':
        # the CONDITIONAL mean -- the exact defect this module exists for
        met['receiving/receiving_yards']['mean'] = round(
            float(yds[tgt > 0].mean()), 2)
        met['receiving/targets']['mean'] = round(
            float(tgt[tgt > 0].mean()), 2)
    elif kind == 'C':
        arrays['dk_scoring__dk_points'] = np.stack([
            np.where(tgt > 0, dk, 4.5)])
    return board, rid, arrays


def test_0_the_tripwire_catches_a_seeded_violation():
    print('\n0. the evaluators BEHAVE -- each check catches its own defect')
    t = _new_tally()
    audit_loaded('SEEDED/clean', *_seed('clean'), t)
    check('a constructed board that honours the contract raises nothing',
          not (t['A'] or t['B'] or t['C']),
          f'A={t["A"]} B={t["B"]} C={t["C"]}')
    check('  and it is not silent: the clean board scores its metrics',
          t['n_metrics'] == 2 and t['n_discriminating'] > 0,
          f'{t["n_metrics"]} metric(s), {t["n_discriminating"]} '
          f'discriminating; a background that discriminates nothing would '
          f'make the seeded B below meaningless')
    for kind, why in (('A', 'a published mean that is not the draw mean'),
                      ('B', 'a mean published on the CONDITIONAL event'),
                      ('C', 'DK points in a zero-opportunity world')):
        t2 = _new_tally()
        audit_loaded(f'SEEDED/{kind}', *_seed(kind), t2)
        check(f'{kind} is caught: {why}', bool(t2[kind]),
              f'seeded and NOT detected -- this check cannot fail, so it is '
              f'not a check')
        # A AND B ARE NOT INDEPENDENT AND THE FIRST VERSION OF THIS TEST
        # ASSUMED THEY WERE. Publishing the conditional mean IS a deviation
        # from the unconditional mean, so seeding B must fire A as well; B is
        # the more specific diagnosis of the same violation -- it names WHICH
        # wrong event was used. C is independent of both.
        expect = {'A': {'A'}, 'B': {'A', 'B'}, 'C': {'C'}}[kind]
        fired = {k for k in 'ABC' if t2[k]}
        check(f'  and exactly {sorted(expect)} fire(s), nothing else',
              fired == expect, f'fired {sorted(fired)}, expected '
                               f'{sorted(expect)}')


def test_A_every_published_mean_is_the_unconditional_draw_mean():
    print('\nA. one semantic: the published mean IS the mean of every world')
    t = _corpus()
    if not t.get('dirs'):
        not_executed('the sealed corpus', 'no sealed board carries draws')
        return
    check(f'{len(t["dirs"])} sealed board(s) scanned, '
          f'{t["n_metrics"]} published metric(s)', t['n_metrics'] > 0,
          'a corpus that scores nothing is not evidence')
    check('every published mean equals its unconditional draw mean',
          not t['A'],
          f'{len(t["A"])} deviation(s); worst {t["A"][:3]}')
    check('no board loaded with an error', not t.get('errors'),
          str(t.get('errors', [])[:2]))
    check('every board metric resolves to a draw array',
          not t['metric_without_array'],
          f'{len(t["metric_without_array"])}: {t["metric_without_array"][:3]}')


def test_B_the_published_mean_is_not_the_conditional_mean():
    print('\nB. and it is NOT the conditional-on-participation mean')
    t = _corpus()
    if not t.get('dirs'):
        not_executed('the sealed corpus', 'no sealed board carries draws')
        return
    # Without this the whole module passes vacuously on a corpus of players who
    # always participate. The count is asserted, not assumed.
    check('the corpus contains rows where the two events actually differ',
          t['n_discriminating'] > 0,
          f'{t["n_discriminating"]} metric(s) with |conditional - '
          f'unconditional| > {MATERIAL}; zero means this module proves nothing')
    check('on every one of them the published figure is the unconditional one',
          not t['B'],
          f'{len(t["B"])} metric(s) published on the CONDITIONAL event: '
          f'{t["B"][:3]}')


def test_C_a_world_with_no_opportunity_is_zero_everywhere():
    print('\nC. zero opportunity => zero everywhere, at the MAXIMUM')
    t = _corpus()
    if not t.get('dirs'):
        not_executed('the sealed corpus', 'no sealed board carries draws')
        return
    check('no metric is non-zero in a draw where its owner had no opportunity',
          not t['C'],
          f'{len(t["C"])} violation(s): {t["C"][:3]}')
    check(f'{t["n_dk"]} DraftKings row(s) carried a zero-opportunity draw to '
          f'check', t['n_dk'] > 0,
          'DK was never exercised, so the scoring layer is unchecked here')
    check('every player exposes at least one opportunity column',
          not t['no_opportunity_column'],
          f'{len(t["no_opportunity_column"])}: '
          f'{t["no_opportunity_column"][:3]}')


def test_D_the_contract_is_exercised_on_every_position():
    print('\nD. position coverage -- the rule is one rule, so it must be '
          'exercised on all of them')
    t = _corpus()
    if not t.get('dirs'):
        not_executed('the sealed corpus', 'no sealed board carries draws')
        return
    print(f'       board rows by position: {dict(sorted(t["positions"].items()))}')
    got = t['positions_scored']
    for pos in ('QB', 'RB', 'WR', 'TE'):
        check(f'{pos} is scored somewhere in the sealed corpus', pos in got,
              f'scored positions: {sorted(got)}')
    check(f'K is scored somewhere in the sealed corpus '
          f'({t["n_metrics_kicking"]} kicking metric(s))', 'K' in got,
          f'scored positions: {sorted(got)}')
    check('  and a kicker with no attempt scores nothing, at the maximum',
          not t['C_kicking'],
          f'{len(t["C_kicking"])} violation(s): {t["C_kicking"][:3]}')
    # THE DEFECT THIS TEST EXISTS TO SURFACE, STATED NOT PASSED. Every board
    # computes a kicking layer and no board publishes a kicker among its
    # players, so `n_players` undercounts by the size of the kicking room and
    # BOARD.md renders no kicking section. It is named here because a test
    # that quietly worked around it would hide it.
    if t['kicking_unpublished']:
        not_executed(
            'every modelled kicker appears on the board that modelled him',
            f'{len(t["kicking_unpublished"])} kicking row(s) are computed and '
            f'sealed but absent from `board["players"]`, so they carry no '
            f'published mean for checks A and B to test. '
            f'{t["kicking_unpublished"][:2]}')
    else:
        check('every modelled kicker appears on the board that modelled him',
              True)


if __name__ == '__main__':
    for fn in (test_0_the_tripwire_catches_a_seeded_violation,
               test_A_every_published_mean_is_the_unconditional_draw_mean,
               test_B_the_published_mean_is_not_the_conditional_mean,
               test_C_a_world_with_no_opportunity_is_zero_everywhere,
               test_D_the_contract_is_exercised_on_every_position):
        fn()
    print(f'\n{PASSED} passed, {FAILED} failed, '
          f'{len(NOT_EXECUTED)} NOT_EXECUTED')
    raise SystemExit(1 if FAILED else 0)
