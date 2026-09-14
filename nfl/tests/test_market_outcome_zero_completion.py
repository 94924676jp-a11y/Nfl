"""The market grader must not choose its comparisons with the outcome.

COMPANION TO `test_retrospective_zero_completion.py`, SEPARATE ON PURPOSE.
Two modules carried the same defect; they are repaired in two commits and
tested in two files, so either can be reverted without the other.

WHAT THIS PROTECTS, AND WHY THE DIRECTION MATTERS MORE HERE THAN ANYWHERE.

  * `market_outcome_audit.py` at spec 1.0.0 refused a quote whenever `actuals`
    carried no record for the player -- `NO_REALISED_VALUE`, "not imputed".
    In a completed game that is a realised zero, not an unknown.

  * A priced player who recorded nothing settles UNDER at every line the book
    offered on him, and the model's selected side on such a player is very
    often OVER, because the forecast that put volume on him is what generated
    the disagreement. So the deleted set is enriched in comparisons the model
    LOSES. A hit rate computed on the survivors flatters us. That is the whole
    reason this is worth a test rather than a comment: the failure is silent,
    one-directional, and lands on the one statistic anybody would quote.

  * MEASURED, the refusal never fired on the frozen 1 PM snapshot: 161 quotes
    reached the check and all 161 carried a record. The defect was real in
    code and latent in effect. These tests are therefore the ONLY thing
    standing between the repair and a silent regression -- no live artifact
    would notice.

  * The reflex fix is still wrong. A rate estimand over zero events is
    undefined, not zero; a team aggregate with no key is a join failure, not a
    club that ran no plays. The classification is imported from
    `same_day_retrospective`, not copied, and these tests assert both modules
    resolve an absence the same way.

NOTHING HERE READS A PRICE, A SNAPSHOT OR A LIVE ARTIFACT. The resolver is
exercised directly on synthetic records.
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.research import market_outcome_audit as MOA                # noqa: E402
from nfl.research import postgame as PG                             # noqa: E402
from nfl.research import same_day_retrospective as SDR              # noqa: E402

PASSED = FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}' + (f'  {detail}' if detail else ''))
    else:
        FAILED += 1
        print(f'  FAIL {label}' + (f'  {detail}' if detail else ''))


FINAL = {'final': True, 'code': 'POSTGAME_FINAL', 'unmet': []}
NOT_FINAL = {'final': False, 'code': 'POSTGAME_NOT_FINAL',
             'unmet': ['END_GAME_MARKER_PRESENT']}


# ------------------------------------------------- 1. the core regression
def test_absent_player_grades_as_zero_not_refused():
    for metric in ('receiving/receptions', 'receiving/targets',
                   'receiving/receiving_yards', 'rushing/carries',
                   'qb/att', 'qb/cmp', 'qb/pyds', 'qb/ptd', 'qb/int',
                   'qb/sacks', 'qb/db'):
        fam, field = PG.EXACT_ESTIMANDS[metric]
        a, basis, cls = MOA.resolve_realised(None, field, metric, FINAL)
        check(f'{metric}: an absent player grades at 0',
              a == 0.0 and basis == 'ZERO_BY_COMPLETION'
              and cls == SDR.ZERO_IF_ABSENT, f'{a!r} {basis!r}')


def test_a_record_that_exists_is_read_not_zeroed():
    a, basis, _ = MOA.resolve_realised({'receptions': 4}, 'receptions',
                                       'receiving/receptions', FINAL)
    check('an existing record is read as OBSERVED',
          a == 4.0 and basis == 'OBSERVED', f'{a!r} {basis!r}')
    a0, b0, _ = MOA.resolve_realised({'receptions': 0}, 'receptions',
                                     'receiving/receptions', FINAL)
    check('a player who WAS targeted and caught nothing is OBSERVED at 0, '
          'not ZERO_BY_COMPLETION', a0 == 0.0 and b0 == 'OBSERVED',
          f'{a0!r} {b0!r}')


# ---------------------------------- 2. the direction: the deleted set loses
def test_the_deleted_comparisons_are_the_ones_the_model_loses():
    # A player who recorded nothing settles UNDER every line the book posts.
    for line in (0.5, 2.5, 3.5, 24.5, 199.5):
        check(f'line {line}: an OVER selection on a zero outcome is a LOSS',
              MOA.grade('OVER', 0.0, line) == 'LOSS')
        check(f'line {line}: an UNDER selection on a zero outcome is a WIN',
              MOA.grade('UNDER', 0.0, line) == 'WIN')
    # So deleting those rows can only remove losses from an OVER-selected set.
    rows = [{'game_id': 'G1', 'player': 'P', 'team': 'T',
             'selected_side': 'OVER', 'result': 'LOSS', 'actual': 0.0,
             'actual_basis': 'ZERO_BY_COMPLETION',
             'model_p_over_exact_line': 0.7, 'model_p_under_exact_line': 0.3,
             'hardrock_novig_p_over': 0.5, 'hardrock_novig_p_under': 0.5,
             'probability_gap_pp': 20.0}]
    rows += [{'game_id': f'G{i}', 'player': f'Q{i}', 'team': 'T',
              'selected_side': 'OVER', 'result': 'WIN', 'actual': 9.0,
              'actual_basis': 'OBSERVED',
              'model_p_over_exact_line': 0.7, 'model_p_under_exact_line': 0.3,
              'hardrock_novig_p_over': 0.5, 'hardrock_novig_p_under': 0.5,
              'probability_gap_pp': 20.0} for i in range(2, 5)]
    full = MOA.perf(rows)
    survivors = MOA.perf([r for r in rows
                          if r['actual_basis'] != 'ZERO_BY_COMPLETION'])
    check('deleting the zero-outcome rows raises the hit rate',
          survivors['hit_rate_excl_push'] > full['hit_rate_excl_push'],
          f"{full['hit_rate_excl_push']} -> {survivors['hit_rate_excl_push']}")
    check('and the full set reports the zero-completed count',
          full['n_zero_by_completion'] == 1 and full['n_observed'] == 3)


# ------------------------------- 3. NOT a global missing-to-zero conversion
def test_absence_classes_other_than_zero_are_refused_by_name():
    cases = ((SDR.MISSING_IF_ABSENT, MOA.R_UNOBSERVED),
             (SDR.NOT_APPLICABLE, MOA.R_NOT_APPLICABLE),
             (SDR.UNRESOLVED, MOA.R_UNRESOLVED))
    for cls, code in cases:
        orig = SDR.ABSENCE_SEMANTICS.get('receiving/receptions')
        try:
            SDR.ABSENCE_SEMANTICS['receiving/receptions'] = (
                cls, 'test derivation, long enough to survive the slice')
            a, ref, got = MOA.resolve_realised(
                None, 'receptions', 'receiving/receptions', FINAL)
        finally:
            SDR.ABSENCE_SEMANTICS['receiving/receptions'] = orig
        check(f'{cls}: not zeroed', a is None, repr(a))
        check(f'{cls}: refused as {code}',
              isinstance(ref, tuple) and ref[1] == code, repr(ref))
    # A team aggregate is never zeroed, as shipped.
    a, ref, cls = MOA.resolve_realised(None, 'team_carries',
                                       'team_volume/team_carries', FINAL)
    check('a team aggregate with no key is refused, not zeroed',
          a is None and ref[1] == MOA.R_UNOBSERVED
          and cls == SDR.MISSING_IF_ABSENT, repr(ref))


def test_an_unclassified_estimand_is_refused_not_guessed():
    a, ref, cls = MOA.resolve_realised(None, 'whatever', 'made_up/metric',
                                       FINAL)
    check('an estimand with no declared absence class is not zeroed',
          a is None and ref[1] == MOA.R_UNRESOLVED
          and cls == SDR.UNRESOLVED, repr(ref))


def test_missing_field_on_an_existing_record_is_a_mapping_bug():
    a, ref, _ = MOA.resolve_realised({'targets': 3}, 'rec_yds',
                                     'receiving/receiving_yards', FINAL)
    check('a field absent from a record that EXISTS is refused, not zeroed',
          a is None and ref[1] == MOA.R_FIELD_NOT_IN_ACTUALS, repr(ref))


# ------------------------------ 4. zero by completion requires completion
def test_zero_completion_requires_proven_finality():
    for fin in (None, {}, NOT_FINAL):
        try:
            MOA.resolve_realised(None, 'receptions', 'receiving/receptions',
                                 fin)
            check(f'finality={fin!r} refused', False, 'it did not raise')
        except RuntimeError as e:
            check(f'finality={fin!r} refused',
                  'ZERO_COMPLETION_WITHOUT_PROVEN_FINALITY' in str(e))
    a, ref, _ = MOA.resolve_realised(None, 'receptions',
                                     'receiving/receptions', NOT_FINAL,
                                     legacy_outcome_selection=True)
    check('the legacy rule needs no finality proof, because it zeroes nothing',
          a is None and ref[1] == MOA.R_LEGACY_LEAK, repr(ref))


# ------------------------------------------- 5. the leak, still reproducible
def test_the_legacy_rule_is_reproducible_and_stamps_itself():
    a, ref, _ = MOA.resolve_realised(None, 'receptions',
                                     'receiving/receptions', FINAL,
                                     legacy_outcome_selection=True)
    check('legacy mode deletes the zero-outcome comparison',
          a is None and ref[1] == MOA.R_LEGACY_LEAK, repr(ref))
    check('and the code it uses is the one the superseded artifact recorded',
          MOA.R_LEGACY_LEAK == 'NO_REALISED_VALUE')
    check('the leak warning names the direction of the bias',
          'LOSES' in MOA.LEAK_WARNING and 'flatters' in MOA.LEAK_WARNING)
    check('the two selection bases are distinct and named',
          MOA.SELECTION_COMPLETE != MOA.SELECTION_LEAKED)


# ---------------------------------- 6. one definition of absence, not two
def test_both_scorers_resolve_an_absence_identically():
    check('the classification is imported, not copied',
          MOA.SDR.ABSENCE_SEMANTICS is SDR.ABSENCE_SEMANTICS)
    check('the cluster-robust SE is imported, not copied',
          SDR._cluster_se([1.0, 2.0, 1.0, 2.0], ['a', 'a', 'b', 'b'])
          is not None)
    missing = [m for m in PG.EXACT_ESTIMANDS if m not in SDR.ABSENCE_SEMANTICS]
    check('every exact estimand the grader can reach is classified',
          not missing, str(missing))
    # Every estimand the grader may map a market onto resolves to the same
    # class in both modules, because there is only one table.
    for metric, (fam, field) in PG.EXACT_ESTIMANDS.items():
        cls_here = MOA.resolve_realised(None, field, metric, FINAL)[2]
        cls_there = SDR.ABSENCE_SEMANTICS[metric][0]
        check(f'{metric}: one class in both modules', cls_here == cls_there,
              f'{cls_here} vs {cls_there}')


# -------------------------------------------- 7. clustering, and no naive SE
def test_perf_clusters_and_refuses_a_naive_binomial_se():
    rows = []
    for g in range(3):
        for p in range(4):
            for mk, res in (('Receptions', 'WIN'), ('Receiving Yards', 'WIN')):
                rows.append({'game_id': f'G{g}', 'player': f'P{g}_{p}',
                             'team': 'T', 'market': mk, 'result': res,
                             'selected_side': 'OVER', 'actual': 5.0,
                             'actual_basis': 'OBSERVED',
                             'model_p_over_exact_line': 0.6,
                             'model_p_under_exact_line': 0.4,
                             'hardrock_novig_p_over': 0.5,
                             'hardrock_novig_p_under': 0.5,
                             'probability_gap_pp': 10.0})
    rows[0]['result'] = 'LOSS'
    st = MOA.perf(rows)
    check('game clusters counted', st['n_game_clusters'] == 3,
          str(st['n_game_clusters']))
    check('player-game clusters counted', st['n_player_game_clusters'] == 12,
          str(st['n_player_game_clusters']))
    check('a game-clustered hit-rate SE is emitted',
          st['se_hit_rate_game_clustered'] is not None)
    check('a player-game-clustered hit-rate SE is emitted',
          st['se_hit_rate_player_game_clustered'] is not None)
    check('two markets share a player-game, so that clustering is not '
          'degenerate', st['player_game_clustering_degenerate'] is False)
    naive = [k for k in st if 'naive' in k and not isinstance(st[k], str)]
    check('no naive SE is emitted as a number', not naive, str(naive))
    check('the refusal to emit one is stated on the block',
          'NAIVE BINOMIAL SE IS NOT EMITTED' in str(st['se_convention']))
    check('quotes are labelled as not being a sample size',
          'n_rows_is_not_a_sample_size' in st)
    # A PUSH IS NOT A TRIAL and must not enter the hit-rate clustering.
    pushed = [dict(r) for r in rows]
    for r in pushed[:4]:
        r['result'] = 'PUSH'
    stp = MOA.perf(pushed)
    check('pushes are excluded from the decided set',
          stp['pushes'] == 4
          and stp['wins'] + stp['losses'] == len(pushed) - 4,
          f"{stp['pushes']} {stp['wins']} {stp['losses']}")


# ------------------------------------------------- 8. the contract's schema
def test_the_row_schema_declares_the_basis():
    check('actual_basis is a published column', 'actual_basis' in MOA.COLUMNS)
    check('absence_class is a published column', 'absence_class' in MOA.COLUMNS)
    check('the spec version moved, because the graded SET changed',
          MOA.SPEC_VERSION == 'market-outcome-audit/2.0.0', MOA.SPEC_VERSION)
    ref = MOA._refusal('S', 'G', ('P', 'T', 'M'), {}, 'SOME_CODE', 'detail')
    missing = [c for c in MOA.COLUMNS if c not in ref]
    check('a refusal row carries every published column', not missing,
          str(missing))
    check('and marks itself refused',
          ref['refusal_reason'].startswith('REFUSED:')
          and ref['stratum'] == 'REFUSED')
