"""PregameSlateState v0 represents today's football truth without changing it.

The acceptance test of this slice is EQUIVALENCE, not plausibility. Two
artifacts are not equivalent because their player counts match; they are
equivalent when every field the new object claims to preserve carries the
same value, player by player, against the governed builder that produces the
truth today.

So the comparison here is driven by the UNIVERSE'S OWN KEYS. Every key
`player_universe.build` emits must be either mapped to a typed field on
PlayerState or present in `extra`, and the test fails on any key that is
silently dropped. A field-by-field report is printed either way.
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import evidence as EV                      # noqa: E402
from nfl.production.state import registry as FR                       # noqa: E402
from nfl.production.state import slate_state as SS                    # noqa: E402
from nfl.production.universe import player_universe as PU             # noqa: E402

PASSED = FAILED = 0

#: The frozen fixture. Chosen because it is the only shape this checkout can
#: actually produce: see `test_the_fixture_is_stated_honestly`.
SEASON, WEEK = 2026, 2
GAME = '2026_02_CAR_ATL'
CUT = '2026-09-22T23:00:00Z'


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok     {what}')
    else:
        FAILED += 1
        print(f'  FAIL   {what}')


def _axis_value(a):
    return None if a is None else a.value


#: universe key -> how PlayerState carries it. A callable takes PlayerState.
FIELD_MAP = {
    'gsis_id': lambda p: p.gsis_id,
    'display_name': lambda p: p.display_name,
    'team': lambda p: p.team,
    'opponent': lambda p: p.opponent,
    'game_id': lambda p: p.game_id,
    'roster_position': lambda p: _axis_value(p.football_position),
    'roster_status': lambda p: _axis_value(p.roster_status),
    'injury_report_status': lambda p: _axis_value(p.injury_report_status),
    'injury_practice_status': lambda p: _axis_value(p.injury_practice_status),
    'offensive_depth_rank': lambda p: _axis_value(p.offensive_depth),
    'special_teams_role': lambda p: _axis_value(p.special_teams_depth),
    'depth_listings': lambda p: p.depth_listings,
    'support_state': lambda p: p.support_state,
    'support_state_why': lambda p: p.support_state_why,
    'evidence_tier': lambda p: p.evidence_tier,
}
#: keys carried verbatim in `extra` rather than promoted to a typed field
EXTRA_KEYS = ('football_name', 'roster_depth_chart_position',
              'roster_status_abbr', 'jersey_number', 'years_exp',
              'rookie_year', 'pfr_id', 'espn_id', 'depth_pos_abb',
              'depth_rank', 'depth_dt', 'offensive_depth_state',
              'officially_inactive')
#: keys the state deliberately does not carry as a player field, with reasons
DECLARED_NOT_CARRIED = {
    'season': 'top-level on PregameSlateState, not repeated per player',
    'week': 'top-level on PregameSlateState',
    'information_cut': 'top-level on PregameSlateState',
    'salary_identity_state': 'a DFS identity axis, carried as dfs_position '
                             'when a salary export is supplied',
}


def _pair(**kw):
    u = PU.build(SEASON, WEEK, GAME, CUT, **kw)
    s = SS.build_one_game(SEASON, WEEK, GAME, CUT, **kw)
    return u, s


# -- 1. equivalence ---------------------------------------------------------
def test_every_universe_key_is_accounted_for():
    u, s = _pair()
    ok(u.state.name == 'PASS' and s.state.name == 'PASS',
       f'both builders succeed: {u.code} / {s.code}')
    keys = set()
    for r in u.value:
        keys |= set(r)
    known = set(FIELD_MAP) | set(EXTRA_KEYS) | set(DECLARED_NOT_CARRIED)
    orphan = sorted(keys - known)
    ok(not orphan,
       f'every key player_universe emits is mapped, in extra, or declared '
       f'not carried; orphans: {orphan}')
    stale = sorted(known - keys - set(DECLARED_NOT_CARRIED))
    ok(not stale,
       f'and the map names no key the universe does not emit: {stale}')


def test_field_by_field_equivalence():
    u, s = _pair()
    state = s.value
    urows = {r['gsis_id']: r for r in u.value}
    prows = {p.gsis_id: p for p in state.players}
    ok(set(urows) == set(prows),
       f'identical player id sets: {len(urows)} vs {len(prows)}')
    report = {}
    for key, get in sorted(FIELD_MAP.items()):
        same = diff = 0
        first = None
        for pid, r in urows.items():
            p = prows.get(pid)
            if p is None:
                continue
            a, b = r.get(key), get(p)
            if a == b:
                same += 1
            else:
                diff += 1
                if first is None:
                    first = (pid, a, b)
        report[key] = (same, diff, first)
        ok(diff == 0,
           f'{key:24s} {same:3d}/{same + diff:3d} identical'
           + ('' if diff == 0 else f'  first mismatch {first}'))
    for key in EXTRA_KEYS:
        same = diff = 0
        for pid, r in urows.items():
            if key not in r:
                continue
            if r[key] == prows[pid].extra.get(key):
                same += 1
            else:
                diff += 1
        ok(diff == 0, f'extra[{key}]{"":<{max(0, 16 - len(key))}} '
                      f'{same:3d}/{same + diff:3d} identical')
    print('  ---- field-by-field report ----')
    for k, (same, diff, _f) in sorted(report.items()):
        print(f'    {k:26s} same={same:3d} diff={diff:3d}')


def test_inactive_handling_is_equivalent():
    """Availability is the field most likely to be quietly reinterpreted, so
    it is compared with a real inactive set supplied, not only with none."""
    u0, _ = _pair()
    ids = sorted(r['gsis_id'] for r in u0.value if r['gsis_id'])[:5]
    u, s = _pair(inactive_ids=set(ids))
    urows = {r['gsis_id']: r for r in u.value}
    prows = {p.gsis_id: p for p in s.value.players}
    bad = [pid for pid in urows
           if urows[pid]['officially_inactive']
           != prows[pid].extra.get('officially_inactive')]
    ok(not bad, f'officially_inactive matches for every player: {len(bad)} '
                f'mismatch(es)')
    bad2 = [pid for pid in ids
            if _axis_value(prows[pid].availability) != 'INACTIVE']
    ok(not bad2, f'and every supplied inactive reads INACTIVE on the '
                 f'availability axis: {len(bad2)} miss(es)')
    others = [p for pid, p in prows.items() if pid not in set(ids)]
    ok(all(_axis_value(p.availability) == 'NOT_ON_INACTIVE_LIST'
           for p in others),
       'everyone else reads NOT_ON_INACTIVE_LIST, which is not ACTIVE')
    sup = [pid for pid in urows
           if urows[pid]['support_state'] != prows[pid].support_state]
    ok(not sup, f'and the support-state classification is unchanged by the '
                f'wrapper: {len(sup)} mismatch(es)')


def test_availability_is_unknown_when_no_inactive_list_is_given():
    _, s = _pair()
    grades = {p.availability.grade for p in s.value.players}
    ok(grades == {EV.UNAVAILABLE},
       f'with no inactive list every availability axis is UNAVAILABLE: '
       f'{grades}')
    ok(all(p.availability.value is None for p in s.value.players),
       'and its value is None -- absence of an inactive list is not a '
       'declaration that everyone is playing')


def test_unavailable_never_becomes_zero():
    _, s = _pair()
    zeros = []
    for p in s.value.players:
        for d in (p.current_season_participation,
                  p.current_season_opportunity,
                  p.historical_participation, p.historical_opportunity):
            for n, a in d.items():
                if a.grade == EV.UNAVAILABLE and a.value == 0:
                    zeros.append((p.gsis_id, n))
    ok(not zeros, f'no UNAVAILABLE axis carries a zero: {len(zeros)} found')
    one = s.value.players[0]
    ok(one.current_season_opportunity['current_season_carries'].value is None,
       'an axis nobody supplied is None, not 0.0')
    ok(one.current_season_participation['routes_run'].grade == EV.UNAVAILABLE,
       'routes_run is UNAVAILABLE from the registry, not from omission')


def test_offensive_and_special_teams_depth_stay_separate():
    _, s = _pair()
    both = [p for p in s.value.players
            if p.special_teams_depth.value is not None]
    ok(both, f'the fixture exercises the case: {len(both)} player(s) carry a '
             f'special-teams role')
    leak = [p.gsis_id for p in both
            if p.offensive_depth.value == p.special_teams_depth.value
            and p.offensive_depth.value is not None]
    ok(not leak,
       f'no player has his special-teams standing answering the offensive '
       f'depth axis: {len(leak)}')
    unknown_off = [p for p in both if p.offensive_depth.value is None]
    ok(all(p.offensive_depth.grade == EV.UNAVAILABLE for p in unknown_off),
       f'{len(unknown_off)} special-teams player(s) with no offensive '
       f'listing read UNAVAILABLE on the offensive axis rather than a rank')
    ok(all(p.declared_starter.grade == EV.UNAVAILABLE for p in unknown_off),
       'and declared_starter is UNKNOWN for them, never False -- "not '
       'listed first" and "we do not know where he is listed" are '
       'different claims')


# -- 2. identity, hashes, PIT ----------------------------------------------
def test_the_state_carries_its_identity():
    _, s = _pair()
    st = s.value
    ok(st.state_version == SS.SPEC_VERSION,
       f'state version: {st.state_version}')
    ok(st.registry_identity == FR.PREGAME.identity(),
       f'registry identity: {st.registry_identity}')
    ok(st.information_cut == CUT, f'information cut: {st.information_cut}')
    for fam in ('weekly_rosters', 'depth_charts', 'injuries', 'schedules'):
        h = (st.source_hashes.get(fam) or {}).get('content_sha256')
        ok(bool(h), f'{fam} carries a content hash: {(h or "")[:16]}')
    ok(st.content_hash().startswith('PSS-'),
       f'state content hash: {st.content_hash()}')


def test_the_content_hash_is_stable_and_sensitive():
    _, a = _pair()
    _, b = _pair()
    ok(a.value.content_hash() == b.value.content_hash(),
       'two builds of the same fixture hash identically, so built_at is '
       'excluded from the hash as intended')
    c = SS.build_one_game(SEASON, WEEK, GAME, CUT).value
    c.players[0].support_state = 'MUTATED_FOR_THIS_TEST'
    ok(c.content_hash() != a.value.content_hash(),
       'and changing one player field changes the hash')


def test_the_registry_identity_moves_when_the_registry_does():
    before = FR.PREGAME.identity()
    r = FR.Registry('probe')
    r.add(name='probe_feature', source_family='weekly_rosters',
          semantic_definition='a probe', pit_rule='none',
          latest_valid_observation='none', required_level=FR.OPTIONAL,
          freshness_sla='none', missing_action=FR.PROCEED,
          fallback=FR.NO_FALLBACK, evidence_grade=EV.DECLARED,
          lifecycle_status=FR.DESCRIPTIVE)
    ok(r.identity() != before,
       'a different registry has a different identity, so a state artifact '
       'records which definitions produced it')
    ok(FR.PREGAME.identity() == before,
       'and building a probe registry did not disturb the production one')


def test_no_sportsbook_field_is_read():
    src = (_REPO / 'nfl/production/state/slate_state.py').read_text()
    tree = ast.parse(src)
    forbidden = set(SS.FORBIDDEN_SCHEDULE_FIELDS) | set(
        SS.POSTGAME_WEATHER_FIELDS)
    # A read looks like row.get('spread_line') or row['spread_line'].
    hits = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == 'get' and n.args \
                and isinstance(n.args[0], ast.Constant) \
                and n.args[0].value in forbidden:
            hits.append(n.args[0].value)
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) \
                and n.slice.value in forbidden:
            hits.append(n.slice.value)
    ok(not hits,
       f'the builder reads no sportsbook or realised-outcome column from the '
       f'schedules vintage: {sorted(set(hits))}')
    _, s = _pair()
    g = s.value.games[0]
    ok(g.weather.grade == EV.UNAVAILABLE and g.weather.value is None,
       'weather is UNAVAILABLE by refusal -- temp and wind in that file are '
       'realised, not forecast')
    ok(g.venue.value and g.roof.value and g.surface.value,
       f'while venue/roof/surface, which are not outcomes, are carried: '
       f'{g.venue.value} / {g.roof.value} / {g.surface.value}')


# -- 3. the lawful-reader boundary -----------------------------------------
def test_only_the_builder_may_select_a_vintage():
    """The invariant for NEW code. Existing production modules are NOT broken
    to satisfy it in this slice -- that is the migration, not the boundary.
    What this forbids is the state layer growing a second reader."""
    pkg = _REPO / 'nfl/production/state'
    offenders = []
    for f in sorted(pkg.glob('*.py')):
        tree = ast.parse(f.read_text())
        names = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                for a in n.names:
                    names.add(a.name)
            elif isinstance(n, ast.Import):
                for a in n.names:
                    names.add(a.name.split('.')[-1])
            elif isinstance(n, ast.Attribute):
                names.add(n.attr)
        if 'vintage_selector' in names or 'select' in names:
            if f.name != 'slate_state.py':
                offenders.append(f.name)
    ok(not offenders,
       f'slate_state.py is the only module in nfl/production/state that '
       f'reaches the vintage selector: offenders {offenders}')
    ok('vintage_selector' in (pkg / 'slate_state.py').read_text(),
       'and it does reach it, so the boundary is real rather than vacuous')


def test_a_selected_capture_whose_bytes_are_absent_refuses_by_name():
    """Eight of eighteen weekly_rosters captures in this checkout store only
    the REDUCED blob, and the universe needs the RAW twin because the reduced
    vintage drops `status`. Selecting one of those produces a
    FileNotFoundError from inside an open(). The builder must refuse first."""
    vintage = _REPO / 'nfl/vintage'
    reduced = {p.name.split('.')[1] for p in vintage.glob('weekly_rosters.*.reduced.csv.gz')}
    raw = {p.name.split('.')[1] for p in vintage.glob('weekly_rosters.*.raw.csv.gz')}
    orphan = reduced - raw
    ok(orphan, f'the fixture exercises the case: {len(orphan)} roster '
               f'capture(s) have no raw blob')
    found = None
    for cut in ('2026-09-05T12:00:00Z', '2026-09-07T15:00:00Z',
                '2026-09-08T12:00:00Z', '2026-09-10T12:00:00Z',
                '2026-09-11T12:00:00Z', '2026-09-12T12:00:00Z'):
        o = SS.select_sources(cut)
        if o.code == 'SOURCE_BLOB_MISSING':
            found = (cut, o)
            break
    ok(found is not None,
       'a cut that selects one of them refuses SOURCE_BLOB_MISSING instead '
       'of raising FileNotFoundError'
       + (f' (at {found[0]})' if found else ''))
    if found:
        ok(found[1].state.name == 'FAIL' and found[1].evidence.get('missing'),
           f'and the refusal names the blob it wanted: '
           f'{found[1].evidence["missing"][0]["needed_blob"].split("/")[-1]}')


def test_a_game_id_that_names_no_game_is_refused():
    """player_universe parses the two clubs out of the id and never checks
    that the game exists, so `2026_02_ATL_CAR` -- the real fixture with its
    clubs the wrong way round -- builds a 159-player universe for a game that
    was never played. The state builder checks the schedule."""
    fake = '2026_02_ATL_CAR'
    u = PU.build(SEASON, WEEK, fake, CUT)
    ok(u.state.name == 'PASS',
       f'the existing universe builder accepts it: {u.code} with '
       f'{u.evidence.get("n_players")} players')
    s = SS.build_one_game(SEASON, WEEK, fake, CUT)
    ok(s.state.name == 'FAIL' and s.code == 'GAME_NOT_IN_SCHEDULE',
       f'the state builder refuses it by name: {s.code}')


# -- 4. the registry refuses what it must ----------------------------------
def _spec(**kw):
    base = dict(name='x', source_family='weekly_rosters',
                semantic_definition='d', pit_rule='p',
                latest_valid_observation='l', required_level=FR.OPTIONAL,
                freshness_sla='s', missing_action=FR.PROCEED,
                fallback=FR.NO_FALLBACK, evidence_grade=EV.DECLARED,
                lifecycle_status=FR.DESCRIPTIVE)
    base.update(kw)
    return FR.FeatureSpec(**base)


def test_the_registry_refuses_an_incomplete_spec():
    for fld in ('semantic_definition', 'pit_rule', 'missing_action',
                'source_family'):
        o = FR.Registry('t').register(_spec(**{fld: ''}))
        ok(o.state.name == 'FAIL' and o.code == 'FEATURE_SPEC_INCOMPLETE',
           f'a spec with no {fld} is refused: {o.code}')
    o = FR.Registry('t').register(_spec(latest_valid_observation=''))
    ok(o.code == 'FEATURE_SPEC_INCOMPLETE',
       'and one with no latest valid observation, because no freshness '
       'check could be written against it')
    o = FR.Registry('t').register(_spec(fallback=''))
    ok(o.code == 'FEATURE_FALLBACK_UNSTATED',
       "a blank fallback is refused -- say 'NONE'")


def test_the_registry_enforces_the_document():
    o = FR.Registry('t').register(_spec(lifecycle_status=FR.CORE))
    ok(o.code == 'FEATURE_MAY_NOT_BE_CORE',
       'nothing may be registered CORE while no NFL experiment has run')
    for st in FR.NOT_AN_INPUT:
        o = FR.Registry('t').register(
            _spec(lifecycle_status=st, required_level=FR.REQUIRED))
        ok(o.code == 'FEATURE_NOT_AN_INPUT',
           f'{st} may not be a required model input')
    o = FR.Registry('t').register(
        _spec(lifecycle_status=FR.REJECTED, required_level=FR.OPTIONAL))
    ok(o.state.name == 'PASS',
       'but it may be registered OPTIONAL, so a diagnostic use stays open')
    o = FR.Registry('t').register(
        _spec(evidence_grade=EV.UNAVAILABLE, missing_action=FR.PROCEED))
    ok(o.code == 'UNAVAILABLE_MAY_NOT_PROCEED_SILENTLY',
       'an UNAVAILABLE feature may not PROCEED silently, which is how an '
       'absence becomes a zero')
    r = FR.Registry('t')
    r.register(_spec())
    o = r.register(_spec())
    ok(o.code == 'FEATURE_ALREADY_REGISTERED',
       'and one feature may not have two definitions')
    o = FR.Registry('t').register(_spec(required_level='SORT_OF'))
    ok(o.code == 'FEATURE_SPEC_VALUE_NOT_DECLARED',
       'an undeclared enum value is refused by name')


def test_the_seeded_registry_is_only_what_the_chain_reads():
    names = FR.PREGAME.names()
    ok(len(names) == 18, f'{len(names)} features seeded')
    ok('routes_run' in names
       and FR.PREGAME.get('routes_run').evidence_grade == EV.UNAVAILABLE,
       'routes_run is present and explicitly UNAVAILABLE rather than absent')
    ok(FR.PREGAME.get('routes_run').missing_action
       == FR.WARN_AND_REDUCE_CONFIDENCE,
       'and missing it warns and reduces confidence rather than proceeding')
    req = FR.PREGAME.required_names()
    ok('current_season_carries' in req and 'team_dropbacks' in req,
       f'{len(req)} REQUIRED features including the usage denominators')
    ok(all(FR.PREGAME.get(n).missing_action == FR.REFUSE for n in req),
       'every REQUIRED feature refuses when missing')
    ok(FR.PREGAME.assert_fallbacks_resolve().state.name == 'PASS',
       'every fallback resolves to a registered feature or says NONE')
    o = FR.PREGAME.require('made_up_feature')
    ok(o.code == 'FEATURE_NOT_REGISTERED',
       'and a feature nobody registered is refused by name')


# -- 5. the artifact --------------------------------------------------------
def test_the_artifact_is_replayable():
    _, s = _pair()
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / 'pregame_slate_state.json'
        w = SS.write(s.value, p)
        ok(w.state.name == 'PASS', f'the artifact writes: {w.code}')
        doc = json.loads(p.read_text())
        for k in ('state_version', 'information_cut', 'registry_identity',
                  'source_hashes', 'state_content_hash', 'freshness'):
            ok(k in doc, f'the artifact carries {k}')
        ok(doc['state_content_hash'] == s.value.content_hash(),
           'and reads back with the hash it was written with')
        ok(len(doc['players']) == len(s.value.players),
           f'{len(doc["players"])} players persisted')
        ok(doc['players'] == sorted(doc['players'],
                                    key=lambda x: x['gsis_id']),
           'players are serialised in canonical id order, so a diff of two '
           'artifacts is a diff of their content')


def test_the_fixture_is_stated_honestly():
    """The fixture is a week-2 game read at a week-3 cut, because this
    checkout holds NO weekly_rosters capture carrying week-2 rows that was
    retrieved before week-2 kickoff. That is a fact about the store, and
    calling this a pre-kickoff fixture would be false."""
    early = PU.build(SEASON, WEEK, GAME, '2026-09-14T16:00:00Z')
    ok(early.state.name != 'PASS',
       f'no lawful universe exists at a pre-kickoff week-2 cut: '
       f'{early.code}')
    late = PU.build(SEASON, WEEK, GAME, CUT)
    ok(late.state.name == 'PASS',
       f'and the cut this suite uses does produce one: '
       f'{late.evidence.get("n_players")} players')
    _, s = _pair()
    ok(s.value.freshness['verdict'] in ('SOURCES_PRESENT', 'DEGRADED'),
       f'the state records a source verdict: {s.value.freshness["verdict"]}')


def main():
    for t in (test_every_universe_key_is_accounted_for,
              test_field_by_field_equivalence,
              test_inactive_handling_is_equivalent,
              test_availability_is_unknown_when_no_inactive_list_is_given,
              test_unavailable_never_becomes_zero,
              test_offensive_and_special_teams_depth_stay_separate,
              test_the_state_carries_its_identity,
              test_the_content_hash_is_stable_and_sensitive,
              test_the_registry_identity_moves_when_the_registry_does,
              test_no_sportsbook_field_is_read,
              test_only_the_builder_may_select_a_vintage,
              test_a_selected_capture_whose_bytes_are_absent_refuses_by_name,
              test_a_game_id_that_names_no_game_is_refused,
              test_the_registry_refuses_an_incomplete_spec,
              test_the_registry_enforces_the_document,
              test_the_seeded_registry_is_only_what_the_chain_reads,
              test_the_artifact_is_replayable,
              test_the_fixture_is_stated_honestly):
        print(f'== {t.__name__}')
        t()
    print(f'\nPASSED {PASSED} FAILED {FAILED}')
    return 1 if FAILED else 0


if __name__ == '__main__':
    sys.exit(main())
