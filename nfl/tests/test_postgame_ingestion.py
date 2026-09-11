"""Automatic postgame ingestion: estimands, idempotency, provenance.

WHAT THESE TESTS PROTECT.

  * ESTIMAND MATCHING. A forecast of offensive snaps scored against a count
    of play-by-play rows produces a number that looks like skill and measures
    a definition. Only EXACT matches are scored; everything else is refused
    BY NAME, including the metric behind the largest miss in the manual
    review.
  * A MISSING FIELD IS NOT A ZERO. The first version defaulted any field the
    realised record did not carry to 0.0, and scored Puka Nacua's 74
    receiving yards as 0 -- CRPS 12.02 became 43.11 and nothing objected.
    A missing PLAYER is a realised zero; a missing FIELD is a mapping bug.
  * IDEMPOTENCY. Re-running on unchanged outcome bytes must add nothing.
  * THE QB ROOM. Scored beside the individuals, summed across DRAWS rather
    than across means, with in-game replacement flagged separately from
    pregame allocation error.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sportsplatform.governance.outcome import State                  # noqa: E402
from nfl.research import postgame as PG                              # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


def _ledger():
    if not PG.LEDGER.exists():
        return []
    return [json.loads(l) for l in PG.LEDGER.read_text().splitlines()
            if l.strip()]


def test_a_mismatched_estimands_are_refused_by_name():
    for metric in ('team_volume/team_off_snaps',
                   'team_volume/team_dropbacks_part',
                   'rushing/rushing_yards'):
        check(f'  {metric} is refused, not scored',
              metric in PG.REFUSED_ESTIMANDS and metric not in
              PG.EXACT_ESTIMANDS, metric)
    check('  and each refusal carries a reason',
          all(len(v) > 40 for v in PG.REFUSED_ESTIMANDS.values()))
    check('team_off_snaps names the snap-count mismatch specifically',
          'snap' in PG.REFUSED_ESTIMANDS['team_volume/team_off_snaps'].lower())
    check('rushing yards is refused as NOT MODELLED, not as a bad estimand',
          'NOT_MODELLED' in PG.REFUSED_ESTIMANDS['rushing/rushing_yards'])
    check('no refused metric is also in the exact map',
          not (set(PG.REFUSED_ESTIMANDS) & set(PG.EXACT_ESTIMANDS)),
          str(set(PG.REFUSED_ESTIMANDS) & set(PG.EXACT_ESTIMANDS)))
    check('team_carries IS scored, because it is EXACT',
          'team_volume/team_carries' in PG.EXACT_ESTIMANDS)


def test_b_the_receiving_yards_field_maps_to_the_realised_key():
    """The specific mis-mapping that scored 74 yards as 0."""
    fam, field = PG.EXACT_ESTIMANDS['receiving/receiving_yards']
    check('receiving yards maps to the key the actuals dict really uses',
          field == 'rec_yds', field)
    rows = _ledger()
    nac = [r for r in rows if r.get('gsis_id') == '00-0039075'
           and r.get('metric') == 'receiving/receiving_yards'
           and 'V1_CANDIDATE_R8' in str(r.get('sealed_dir'))]
    if not nac:
        print('  ..   no scored ledger row for that player; skipped')
        return
    check('  and the realised value is the real one, not zero',
          abs(nac[0]['actual'] - 74.0) < 1e-6, str(nac[0]['actual']))


def test_c_the_automatic_scoring_reproduces_the_manual_review():
    """Declared tolerances: actual exact, mean 0.02, CRPS 0.05."""
    rows = [r for r in _ledger()
            if r.get('game_id') == '2026_01_SF_LA'
            and 'post_inactives_V1_CANDIDATE_R8' in str(r.get('sealed_dir'))
            and r.get('entity') == 'player']
    if not rows:
        print('  ..   SF@LA R8 not in the ledger; skipped')
        return
    manual = {
        ('00-0026498', 'qb/att'): (25, 30.27, 3.71),
        ('00-0026498', 'qb/pyds'): (155, 221.63, 41.35),
        ('00-0037834', 'qb/att'): (34, 26.71, 3.77),
        ('00-0037834', 'qb/pyds'): (205, 210.50, 21.97),
        ('00-0039075', 'receiving/receptions'): (5, 5.44, 0.75),
        ('00-0039075', 'receiving/receiving_yards'): (74, 71.00, 12.02),
        ('00-0033280', 'rushing/carries'): (10, 13.64, 2.14),
        ('00-0037840', 'rushing/carries'): (11, 10.84, 1.34),
    }
    for (pid, metric), (a, mu, c) in manual.items():
        hit = [r for r in rows if r.get('gsis_id') == pid
               and r.get('metric') == metric]
        if not hit:
            check(f'  {pid} {metric} present in the ledger', False)
            continue
        r = hit[0]
        check(f'  {pid} {metric.split("/")[-1]} reproduces the manual review',
              abs(r['actual'] - a) < 1e-6 and abs(r['mean'] - mu) < 0.02
              and abs(r['crps'] - c) < 0.05,
              f"act {r['actual']} mean {r['mean']:.2f} crps {r['crps']:.2f}")


def test_d_the_qb_room_is_scored_beside_the_individuals():
    rows = [r for r in _ledger() if r.get('entity') == 'qb_room']
    if not rows:
        print('  ..   no qb_room rows; skipped')
        return
    check('the room is its own entity', rows, f'{len(rows)} rows')
    sea = [r for r in rows if r.get('team') == 'SEA'
           and r.get('metric') == 'qb/att'
           and r.get('game_id') == '2026_01_NE_SEA']
    if sea:
        r = sea[0]
        check('  Seattle room attempts are scored',
              abs(r['actual'] - 24.0) < 1e-6, str(r['actual']))
        check('  the room CRPS is far better than either individual',
              r['crps'] < 5.0, f"room {r['crps']:.2f} vs Darnold 17.12 / "
                               f"Lock 18.19")
        check('  and in-game replacement is flagged on the row',
              r['in_game_replacement'] is True)
        check('    classified apart from pregame allocation',
              'IN_GAME_REPLACEMENT' in str(
                  (r.get('replacement_detail') or {}).get('classification')),
              str((r.get('replacement_detail') or {}).get('classification')))
    ne = [r for r in rows if r.get('team') == 'NE'
          and r.get('game_id') == '2026_01_NE_SEA']
    if ne:
        check('  a game with no replacement is NOT flagged',
              all(r['in_game_replacement'] is False for r in ne))


def test_e_rerunning_on_unchanged_bytes_adds_nothing():
    rows = _ledger()
    if not rows:
        print('  ..   empty ledger; skipped')
        return
    keys = [PG._row_key(r) for r in rows]
    check('every ledger row is unique by its identity key',
          len(keys) == len(set(keys)),
          f'{len(keys)} rows, {len(set(keys))} keys')
    res = PG.append_rows(rows)
    check('  re-appending the whole ledger adds nothing',
          res['added'] == 0, str(res))
    check('  and reports the duplicates it avoided',
          res['duplicates_avoided'] == len(rows), str(res))


def test_f_the_row_key_separates_a_revision_from_a_duplicate():
    base = {'game_id': 'G', 'entity': 'player', 'gsis_id': 'P',
            'metric': 'qb/att', 'sealed_dir': '/x', 'outcome_sha16': 'aaa'}
    same = dict(base)
    revised = dict(base, outcome_sha16='bbb')
    other_seal = dict(base, sealed_dir='/y')
    check('identical rows share a key', PG._row_key(base) == PG._row_key(same))
    check('  a REVISED outcome file is a new row, not a duplicate',
          PG._row_key(base) != PG._row_key(revised))
    check('  and a different sealed forecast is a different row',
          PG._row_key(base) != PG._row_key(other_seal))


def test_g_provenance_is_preserved_for_every_stored_outcome():
    provs = sorted(PG.STORE.glob('*.provenance.json'))
    if not provs:
        print('  ..   no stored outcome yet; skipped')
        return
    d = json.loads(provs[-1].read_text())
    for k in ('source_url', 'retrieved_at', 'sha256', 'games', 'blob',
              'source_name', 'source_rank'):
        check(f'  provenance carries {k}', k in d and d[k] is not None, k)
    check('  the stored blob is content-addressed by that hash',
          d['sha256'][:16] in d['blob'], d['blob'])
    check('  and the clocks are not conflated',
          'source_timestamp_note' in d)


def test_h_only_the_top_rank_source_is_scoreable():
    top = PG.SOURCES[0]
    check('the authoritative source is rank 1 and scoreable',
          top['rank'] == 1 and top['scoreable'] is True, str(top['name']))
    lower = [s for s in PG.SOURCES if s['rank'] > 1]
    check('  every lower-rank source is recorded but NOT scoreable',
          lower and all(not s['scoreable'] for s in lower),
          str([s['name'] for s in lower]))


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed in this module')


if __name__ == '__main__':
    for fn in sorted(k for k in dict(globals()) if k.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
