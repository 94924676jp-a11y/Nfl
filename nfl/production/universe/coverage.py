"""Coverage as game x club x position x support state.

WHY A GAME-LEVEL COUNT IS NOT COVERAGE

Blueprint 6. `2026_02_MIN_CHI` emitted a receiving layer with rows for one
club and none for the other. Every game-level check passed: the layer was
present, its metrics had bytes, its ids were unique and finite, and the row
count looked ordinary because MIN's receivers filled it. One club's rows hid
the other club's absence.

That is why the unit here is the CLUB, not the game. A club with zero emitted
rows at a position its universe says should be playing is a failure whatever
the other club did.

WHAT THIS DOES NOT DO

It does not look at workload, share, snaps or any projected quantity. It
compares WHO THE UNIVERSE EXPECTS against WHO THE MODEL EMITTED, per club and
position, and it fails when the second set is empty where the first is not.
Whether an emitted player got a sensible number is the role model's problem.
"""
from __future__ import annotations

import collections
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.universe import support_state as S           # noqa: E402
from sportsplatform.governance.outcome import Outcome            # noqa: E402

SPEC_VERSION = 'nfl-coverage-contract-1'

#: Positions for which a club is expected to field SOMEONE in every NFL game.
#: A club with an expected player at one of these and no emitted row is a
#: per-club coverage failure. K is excluded: a club can field no kicker in the
#: emitted pool without the football simulation being malformed, and that is
#: already a declared optional layer in the artifact contract.
REQUIRED_CLUB_POSITIONS = ('QB', 'RB', 'WR', 'TE')

#: Required football layer -> the roster positions that layer is ABOUT.
#:
#: A club can be present in the game and absent from a layer. MIN@CHI is the
#: case: CHI's eight emitted players appear ONLY in `gadget_rush` and
#: `dk_scoring`, with zero rows in `receiving` and zero in `rushing`, while
#: MIN has 14 and 5. A union-of-all-layers check sees those eight ids and
#: calls the club covered. The club is not covered -- it is missing from the
#: layers that carry the football.
#:
#: This is still an EXISTENCE test. It asks whether a club has any row in a
#: layer, never how large the numbers in that row are.
LAYER_CLUB_POSITIONS = {
    'receiving': ('WR', 'TE', 'RB', 'FB'),
    'rushing': ('RB', 'FB'),
    'qb': ('QB',),
}


def assess(universe_rows, *, emitted_ids=None,
           emitted_by_layer=None) -> Outcome:
    """PLAYER_COVERAGE, PER_CLUB_POSITION_COVERAGE, PER_CLUB_LAYER_COVERAGE.

    `emitted_by_layer` maps layer name -> the gsis_ids that layer emitted.
    Supplying it turns on the per-club-per-layer check; omitting it leaves
    that gate NOT_EVALUATED rather than silently passing.
    """
    emitted_ids = set(emitted_ids or ())
    if emitted_by_layer is None and emitted_ids:
        emitted_by_layer = None
    if not universe_rows:
        return Outcome.fail(
            'COVERAGE_UNIVERSE_EMPTY',
            'no universe rows were supplied, so coverage would be vacuously '
            'satisfied. An unchecked board is not a checked one.')

    # 1. EVERY EXPECTED PLAYER ACCOUNTED FOR. `unaccounted` is a player the
    #    universe expects on the field for whom the model wrote nothing AND
    #    for whom no reason was recorded. With the states closed and assigned
    #    by precedence this should be empty by construction; it is computed
    #    anyway, because a guard that cannot fail is not a guard.
    expected = [r for r in universe_rows
                if r['support_state'] in S.EXPECTED_TO_PLAY]
    unaccounted = [r for r in expected
                   if r['support_state'] == S.PROJECTED
                   and r['gsis_id'] not in emitted_ids]
    unsupported = [r for r in universe_rows
                   if r['support_state'] == S.MODEL_UNSUPPORTED]

    # 2. PER CLUB x POSITION. The cell, not the game.
    grid, offences = {}, []
    clubs = sorted({r['team'] for r in universe_rows})
    for club in clubs:
        grid[club] = {}
        for pos in REQUIRED_CLUB_POSITIONS:
            cell = [r for r in universe_rows
                    if r['team'] == club and r['roster_position'] == pos]
            exp = [r for r in cell if r['support_state'] in S.EXPECTED_TO_PLAY]
            emi = [r for r in cell if r['gsis_id'] in emitted_ids]
            by_state = collections.Counter(r['support_state'] for r in cell)
            grid[club][pos] = {
                'n_on_roster': len(cell), 'n_expected_to_play': len(exp),
                'n_emitted': len(emi), 'by_support_state': dict(by_state)}
            if exp and not emi:
                offences.append({
                    'club': club, 'position': pos,
                    'code': 'PER_CLUB_POSITION_NOT_COVERED',
                    'n_expected_to_play': len(exp), 'n_emitted': 0,
                    'why': f'{club} has {len(exp)} player(s) the universe '
                           f'expects to play at {pos} and the model emitted '
                           f'NO row for any of them. Another club having '
                           f'{pos} rows does not cover this one.'})

    # 3. PER CLUB x LAYER. A club absent from a layer the football runs
    #    through is uncovered even when its players appear somewhere else.
    layer_grid, layer_gate = {}, 'PER_CLUB_LAYER_COVERAGE_NOT_EVALUATED'
    if emitted_by_layer is not None:
        for lay, positions in sorted(LAYER_CLUB_POSITIONS.items()):
            ids = set((emitted_by_layer or {}).get(lay) or ())
            layer_grid[lay] = {}
            for club in clubs:
                exp = [r for r in universe_rows
                       if r['team'] == club
                       and r['roster_position'] in positions
                       and r['support_state'] in S.EXPECTED_TO_PLAY]
                emi = [r for r in universe_rows
                       if r['team'] == club and r['gsis_id'] in ids]
                layer_grid[lay][club] = {'n_expected_to_play': len(exp),
                                         'n_emitted_in_layer': len(emi)}
                if exp and not emi:
                    offences.append({
                        'club': club, 'layer': lay,
                        'code': 'PER_CLUB_LAYER_NOT_COVERED',
                        'n_expected_to_play': len(exp),
                        'n_emitted_in_layer': 0,
                        'why': f'{club} has {len(exp)} player(s) the '
                               f'universe expects to play at '
                               f'{"/".join(positions)} and NO row in the '
                               f'{lay!r} layer. The other club having rows '
                               f'there does not cover this one.'})
        layer_gate = ('PER_CLUB_LAYER_COVERAGE_COMPLETE'
                      if not [o for o in offences if o.get('layer')]
                      else 'PER_CLUB_LAYER_COVERAGE_INCOMPLETE')

    player_gate = ('PLAYER_COVERAGE_COMPLETE' if not unaccounted
                   else 'PLAYER_COVERAGE_INCOMPLETE')
    club_gate = ('PER_CLUB_POSITION_COVERAGE_COMPLETE' if not offences
                 else 'PER_CLUB_POSITION_COVERAGE_INCOMPLETE')
    value = {
        'spec_version': SPEC_VERSION,
        'game_id': universe_rows[0].get('game_id'),
        'clubs': clubs,
        'PLAYER_COVERAGE': player_gate,
        'PER_CLUB_POSITION_COVERAGE': club_gate,
        'PER_CLUB_LAYER_COVERAGE': layer_gate,
        'layer_grid': layer_grid,
        'n_universe': len(universe_rows),
        'n_expected_to_play': len(expected),
        'n_emitted': len(emitted_ids),
        'n_unaccounted': len(unaccounted),
        'n_model_unsupported': len(unsupported),
        'model_unsupported': [
            {'gsis_id': r['gsis_id'], 'player': r['display_name'],
             'team': r['team'], 'position': r['roster_position'],
             'roster_status': r['roster_status'],
             'why': r['support_state_why']} for r in unsupported],
        'grid': grid,
        'offences': offences,
        'support_state_counts': dict(collections.Counter(
            r['support_state'] for r in universe_rows)),
    }
    if offences or unaccounted:
        return Outcome.fail(
            'COVERAGE_INCOMPLETE',
            f'{len(offences)} club-position cell(s) uncovered and '
            f'{len(unaccounted)} expected player(s) unaccounted for. '
            f'A game is not complete because one club filled the row count.',
            value=value, **{k: v for k, v in value.items()
                            if k in ('PLAYER_COVERAGE',
                                     'PER_CLUB_POSITION_COVERAGE',
                                     'PER_CLUB_LAYER_COVERAGE',
                                     'offences', 'n_unaccounted')})
    return Outcome.ok(
        'COVERAGE_COMPLETE', value=value,
        detail=f'every club x position cell with an expected player has at '
               f'least one emitted row across {len(clubs)} club(s); '
               f'{len(unsupported)} player(s) named MODEL_UNSUPPORTED',
        PLAYER_COVERAGE=player_gate,
        PER_CLUB_POSITION_COVERAGE=club_gate,
        PER_CLUB_LAYER_COVERAGE=layer_gate,
        n_model_unsupported=len(unsupported))


def assert_no_inactive_survives(universe_rows, *, emitted_ids=None) -> Outcome:
    """Officially inactive players must own nothing in the playable output.

    Computed from EMITTED ids, not from the fixture's intent: a fixture can
    declare a player excluded and a layer still write him.
    """
    emitted_ids = set(emitted_ids or ())
    declared = [r for r in universe_rows
                if r['support_state'] == S.OFFICIALLY_INACTIVE]
    if not declared:
        return Outcome.ok(
            'NO_OFFICIAL_INACTIVE_EVIDENCE',
            value={'n_declared': 0, 'survivors': []},
            detail='no player in this universe carries an official inactive '
                   'declaration, so no intersection was computed and the '
                   'board is NOT certified inactive-clean',
            certified=False)
    survivors = [{'gsis_id': r['gsis_id'], 'player': r['display_name'],
                  'team': r['team']}
                 for r in declared if r['gsis_id'] in emitted_ids]
    if survivors:
        return Outcome.fail(
            'OFFICIALLY_INACTIVE_PLAYER_IN_PLAYABLE_BOARD',
            f'{len(survivors)} officially inactive player(s) own emitted '
            f'rows', value={'n_declared': len(declared),
                            'survivors': survivors},
            survivors=survivors, certified=False)
    return Outcome.ok(
        '0_OFFICIALLY_INACTIVE_PLAYERS_IN_PLAYABLE_BOARD',
        value={'n_declared': len(declared), 'survivors': []},
        detail=f'{len(declared)} declared inactive id(s) intersected with '
               f'{len(emitted_ids)} emitted id(s); none survived',
        certified=True)
