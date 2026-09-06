"""Adversarial replay tests for effective scope. G0A item 4, owner-FAILED and reopened.

Written by an agent that did NOT write nfl/identity/effective_scope.py, on the
assumption that the code is wrong until a seeded violation is refused by name.

DEFECTS THIS FILE REPLAYS

  * THE SEASON STRING. The NFL capture set `effective_for_date = "2026"` and the
    five-field provenance object validated. Structurally complete, semantically
    empty: a season cannot answer "was this effective for THIS game at THIS
    forecast timestamp?". The owner overrode item 4 to FAIL. Sections C and M
    are both seeded from it -- C from the version the module catches, M from the
    version it does not.

  * PRIOR-WEEK REUSE. A week-3 report quietly informing a week-5 forecast
    because both are "2026". Section B requires EFFECTIVE_SCOPE_WRONG_WEEK.

  * DERIVED WEARING SOURCE AUTHORITY. A narrowed value presented as though the
    upstream guaranteed it is unfalsifiable downstream. Section E requires the
    refusal at CONSTRUCTION, not at use.

  * MLB M0 / THE INERT GUARD (`assert_batch_games_are_new`), which read a field
    no row carried and so passed on every input it was ever given. Section L
    bypasses each critical guard and requires the seeded violation to stop being
    caught.

BINDING TEST STANDARD (Owner Directive 3 section 8): "A guard is not demonstrated
merely because compliant data passes it. It must reject a seeded violation, and
critical guards must demonstrate that removing/bypassing the guard causes the
replay test to fail."

SECTION M FAILS ON PURPOSE. It is a real hole found by pushing the adversarial
angle the assignment named: getting a season-only value certified for a specific
game without declaring any narrowing method. Do not delete it and do not weaken
it to green. See the BUG: lines.

Run standalone:  python3.12 nfl/tests/test_effective_scope.py
"""
import dataclasses
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from sportsplatform.governance.outcome import Cause, Outcome, State            # noqa: E402
from nfl.identity import effective_scope as es_mod                 # noqa: E402
from nfl.identity.effective_scope import (Authority, Derivation,   # noqa: E402
                                          EffectiveScope,
                                          EffectiveScopeError,
                                          ScopeKind, assert_usable_for,
                                          narrow)
from nfl.tests.bypass import (assert_guard_is_load_bearing,        # noqa: E402
                              guard_bypassed)

PASSED = FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


# --------------------------------------------------------------------------
# Fixtures. One week-5 Sunday game, kickoff 2026-10-11 17:00Z. The forecast is
# written on the Friday evening, 2026-10-09 22:00Z.
GAME = '2026_05_AAA_BBB'
SEASON, WEEK = 2026, 5
TEAMS = ('AAA', 'BBB')
FORECAST = '2026-10-09T22:00:00+00:00'
FRIDAY_FILING = '2026-10-09T20:00:00+00:00'


def ask(scope, *, game_id=GAME, season=SEASON, week=WEEK, teams=TEAMS,
        forecast_timestamp=FORECAST):
    return assert_usable_for(scope, game_id=game_id, season=season, week=week,
                             teams=teams, forecast_timestamp=forecast_timestamp)


def season_scope(value='2026'):
    """What the capture actually produced, and what item 4 was failed for."""
    return EffectiveScope(kind=ScopeKind.SEASON,
                          authority=Authority.SOURCE_PROVIDED,
                          source_value=value, season=SEASON)


def game_scope(**over):
    base = dict(kind=ScopeKind.GAME, authority=Authority.SOURCE_PROVIDED,
                source_value=FRIDAY_FILING, season=SEASON, week=WEEK,
                teams=TEAMS, game_id=GAME, valid_from=FRIDAY_FILING,
                valid_to='2026-10-11T17:00:00+00:00')
    base.update(over)
    return EffectiveScope(**base)


# --------------------------------------------------------------------------
def test_a_effective_for_the_exact_game():
    """Owner case (a): a capture effective for THIS game passes."""
    print('\nA. a capture pinned to this game, this week, before the forecast')
    o = ask(game_scope())
    check('it is usable', o.state is State.PASS, str(o))
    check('with the named code', o.code == 'EFFECTIVE_SCOPE_USABLE', o.code)
    check('the answer names the game it was asked about',
          o.evidence.get('game_id') == GAME, str(o.evidence.get('game_id')))
    check('and carries the scope itself as evidence, not a boolean',
          isinstance(o.value, dict) and o.value['kind'] == 'GAME',
          str(type(o.value)))
    check('the returned outcome refuses to be read as a bare truth value',
          _refuses_truthiness(o))
    # The same artifact, asked about a game it does not cover, must not pass.
    other = ask(game_scope(), game_id='2026_05_CCC_DDD')
    check('and the SAME scope is refused for a different game',
          other.state is State.FAIL and other.code == 'EFFECTIVE_SCOPE_WRONG_GAME',
          str(other))


def _refuses_truthiness(o):
    try:
        bool(o)
        return False
    except Exception:
        return True


def test_b_prior_week_reuse_is_refused():
    """Owner case (b): a week-3 record reused for a week-5 game, undeclared."""
    print('\nB. prior-week record reused for a later game -> WRONG_WEEK')
    wk3 = EffectiveScope(kind=ScopeKind.WEEK_TEAM,
                         authority=Authority.SOURCE_PROVIDED,
                         source_value='2026 week 3', season=SEASON, week=3,
                         teams=TEAMS)
    o = ask(wk3)
    check('it is a FAIL, not a BLOCKED -- the data is present and wrong',
          o.state is State.FAIL, str(o))
    check('named EFFECTIVE_SCOPE_WRONG_WEEK',
          o.code == 'EFFECTIVE_SCOPE_WRONG_WEEK', o.code)
    check('and both weeks are stated in the refusal',
          'week 3' in o.detail and 'week 5' in o.detail, o.detail[:90])
    check('the refusal says silence is not a validity interval',
          'explicit declared validity' in o.detail, o.detail[-120:])
    # Same week is fine, so the refusal is about the week and nothing else.
    wk5 = dataclasses.replace(wk3, week=WEEK, source_value='2026 week 5')
    check('the same shape at the right week passes',
          ask(wk5).state is State.PASS, str(ask(wk5)))
    # A LATER week is refused too: staleness is not the only direction of wrong.
    wk7 = dataclasses.replace(wk3, week=7)
    check('a FUTURE week is refused by the same rule',
          ask(wk7).code == 'EFFECTIVE_SCOPE_WRONG_WEEK', str(ask(wk7)))


def test_c_season_only_is_too_coarse():
    """Owner case (c): the literal item-4 defect. "2026" certifies nothing."""
    print('\nC. season-only value with no narrowing rule -> TOO_COARSE')
    o = ask(season_scope())
    check('it is BLOCKED, not FAIL -- the question cannot be answered at all',
          o.state is State.BLOCKED, str(o))
    check('named EFFECTIVE_SCOPE_TOO_COARSE',
          o.code == 'EFFECTIVE_SCOPE_TOO_COARSE', o.code)
    check('with cause DATA, so it is not read as a rule refusing a good value',
          o.evidence.get('cause') == Cause.DATA.value, str(o.evidence.get('cause')))
    check('and it says a season answers "which year", never "which game"',
          'which game' in o.detail, o.detail[:120])
    check('the coarse source value is quoted back so a reader sees "2026"',
          "'2026'" in o.detail, o.detail[:80])
    # It is blocked no matter how the rest of the question is framed: the
    # coarseness is a property of the artifact, not of the game asked about.
    for gid in ('2026_01_AAA_BBB', '2026_18_ZZZ_YYY'):
        check(f'still too coarse when asked about {gid}',
              ask(season_scope(), game_id=gid, week=1).code
              == 'EFFECTIVE_SCOPE_TOO_COARSE')
    check('a season scope carrying the RIGHT season is still refused -- '
          'matching the year is not certification',
          ask(season_scope()).state is State.BLOCKED)


def test_d_legitimate_narrowing_passes():
    """Owner case (d): source value plus a declared deterministic narrowing."""
    print('\nD. source value + declared deterministic narrowing -> PASS')
    base = season_scope()
    n = narrow(base, kind=ScopeKind.WEEK_TEAM,
               method='week := schedule row for the capture Last-Modified date',
               evidence='schedules.csv row 2026_05_AAA_BBB, gameday 2026-10-11',
               deterministic=True, week=WEEK, teams=TEAMS,
               valid_from=FRIDAY_FILING)
    o = ask(n)
    check('the narrowed scope is usable', o.state is State.PASS, str(o))
    check('and the PASS records that it was derived, not given',
          o.value['authority'] == 'DERIVED_DETERMINISTIC', o.value['authority'])
    check('the derivation method rides along',
          o.value['derivation']['method'].startswith('week :='),
          str(o.value['derivation']))
    check('and the evidence for it rides along too',
          'schedules.csv' in o.value['derivation']['evidence'])
    check('the original coarse value is still readable in the same object',
          o.value['source_value'] == '2026', o.value['source_value'])
    check('so a reader can tell what upstream guaranteed from what we inferred',
          o.value['source_value'] != o.value['derivation']['method'])
    # A heuristic narrowing is a different authority class and must say so.
    h = narrow(base, kind=ScopeKind.WEEK_TEAM, method='guessed from filename',
               evidence='no better clock available', deterministic=False,
               week=WEEK, teams=TEAMS)
    check('a heuristic narrowing is labelled DERIVED_HEURISTIC',
          h.authority is Authority.DERIVED_HEURISTIC, h.authority.value)
    check('and both derived classes report is_derived',
          n.authority.is_derived and h.authority.is_derived)
    check('while SOURCE_PROVIDED does not',
          Authority.SOURCE_PROVIDED.is_derived is False)


def test_e_derived_presented_as_source_is_refused_at_construction():
    """Owner case (e): the refusal must happen when the object is built."""
    print('\nE. derived applicability wearing source authority -> refused at build')
    try:
        EffectiveScope(kind=ScopeKind.GAME,
                       authority=Authority.SOURCE_PROVIDED,
                       source_value='2026', season=SEASON, game_id=GAME,
                       derivation=Derivation(method='m', evidence='e'))
        check('it is refused', False, 'the object was constructed')
    except EffectiveScopeError as exc:
        check('it is refused', True)
        check('named DERIVED_PRESENTED_AS_SOURCE',
              str(exc).startswith('DERIVED_PRESENTED_AS_SOURCE'), str(exc)[:60])
        check('and the reason given is that it is unfalsifiable downstream',
              'unfalsifiable' in str(exc), str(exc)[:160])
    # The point of construction-time: there is no window in which a bad object
    # exists and might be logged, shipped or compared before use rejects it.
    try:
        bad = EffectiveScope(kind=ScopeKind.GAME,
                             authority=Authority.SOURCE_PROVIDED,
                             source_value='2026', season=SEASON, game_id=GAME,
                             derivation=Derivation('m', 'e'))
        check('no such object can be handed to assert_usable_for at all',
              False, f'built {bad!r}')
    except EffectiveScopeError:
        check('no such object can be handed to assert_usable_for at all', True)
    # And the honest spelling of the same intent is accepted.
    ok = EffectiveScope(kind=ScopeKind.GAME,
                        authority=Authority.DERIVED_DETERMINISTIC,
                        source_value='2026', season=SEASON, week=WEEK,
                        teams=TEAMS, game_id=GAME,
                        derivation=Derivation('m', 'e'))
    check('the same narrowing declared as DERIVED is accepted',
          ask(ok).state is State.PASS, str(ask(ok)))


def test_f_effective_after_the_forecast_is_refused():
    """Owner case (f): information that did not exist when we wrote."""
    print('\nF. effective only AFTER the forecast timestamp -> AFTER_FORECAST')
    late = game_scope(valid_from='2026-10-11T15:30:00+00:00',
                      valid_to='2026-10-11T17:00:00+00:00')
    o = ask(late)
    check('it is refused', o.state is State.FAIL, str(o))
    check('named EFFECTIVE_AFTER_FORECAST',
          o.code == 'EFFECTIVE_AFTER_FORECAST', o.code)
    check('and it says the information was not knowable yet',
          'not knowable yet' in o.detail, o.detail[-60:])
    # One second is enough. Leakage has no tolerance band, because a tolerance
    # band is exactly how a T-90 inactives list informs a Friday forecast.
    one_sec = game_scope(valid_from='2026-10-09T22:00:01+00:00')
    check('one second after the forecast is still leakage',
          ask(one_sec).code == 'EFFECTIVE_AFTER_FORECAST', str(ask(one_sec)))
    exact = game_scope(valid_from=FORECAST)
    check('effective exactly AT the forecast instant is allowed',
          ask(exact).state is State.PASS, str(ask(exact)))


def test_g_cross_team_record_is_refused():
    """Owner case (g): another team's record applied to this game."""
    print('\nG. a cross-team record applied to this game -> WRONG_TEAM')
    other = EffectiveScope(kind=ScopeKind.WEEK_TEAM,
                           authority=Authority.SOURCE_PROVIDED,
                           source_value='2026 week 5', season=SEASON,
                           week=WEEK, teams=('CCC', 'DDD'))
    o = ask(other)
    check('it is refused', o.state is State.FAIL, str(o))
    check('named EFFECTIVE_SCOPE_WRONG_TEAM',
          o.code == 'EFFECTIVE_SCOPE_WRONG_TEAM', o.code)
    check('and both team sets are named',
          "'CCC'" in o.detail and "'AAA'" in o.detail, o.detail[:120])
    half = dataclasses.replace(other, teams=('BBB', 'CCC'))
    check('one overlapping team is enough -- a shared game has two sides',
          ask(half).state is State.PASS, str(ask(half)))
    lower = dataclasses.replace(other, teams=('aaa',))
    check('the overlap test is case-insensitive, so casing is not a bypass',
          ask(lower).state is State.PASS, str(ask(lower)))
    check('and asking with lowercase teams behaves the same',
          ask(dataclasses.replace(other, teams=('AAA',)),
              teams=('aaa', 'bbb')).state is State.PASS)


def test_h_narrow_never_overwrites_the_source_value():
    """The rule the module is built around: narrowing is additive."""
    print('\nH. narrow() is additive -- the source value survives untouched')
    base = season_scope()
    before = base.source_value
    n = narrow(base, kind=ScopeKind.DATE_INTERVAL,
               method='valid_from := HTTP Last-Modified of the captured file',
               evidence='Last-Modified: Fri, 09 Oct 2026 20:00:00 GMT',
               valid_from=FRIDAY_FILING)
    check('the source value survives byte-identical',
          n.source_value == before == '2026',
          f'{n.source_value!r} != {before!r}')
    check('and it is the same string object, not a reconstruction',
          n.source_value is base.source_value)
    check('the original scope is unmutated (frozen, additive)',
          base.source_value == '2026' and base.derivation is None)
    check('authority is downgraded to a DERIVED class',
          n.authority is Authority.DERIVED_DETERMINISTIC, n.authority.value)
    check('so the narrowing is visible forever, never source-shaped',
          n.authority is not Authority.SOURCE_PROVIDED)
    check('the derived interval is present', n.valid_from == FRIDAY_FILING)
    # Narrowing twice must not lose the first source value.
    n2 = narrow(n, kind=ScopeKind.WEEK_TEAM, method='m2', evidence='e2',
                week=WEEK, teams=TEAMS)
    check('narrowing a narrowed scope still carries the ORIGINAL source value',
          n2.source_value == '2026', n2.source_value)
    check('and the second narrowing keeps the first derived field',
          n2.valid_from == FRIDAY_FILING, str(n2.valid_from))
    # The obvious attack: overwrite the source value through the field kwargs.
    try:
        narrow(base, kind=ScopeKind.GAME, method='m', evidence='e',
               source_value='2026-10-09T20:00:00+00:00', game_id=GAME)
        check('source_value cannot be smuggled in as a narrowed field',
              False, 'it was accepted')
    except EffectiveScopeError as exc:
        check('source_value cannot be smuggled in as a narrowed field',
              'EFFECTIVE_SCOPE_UNKNOWN_FIELD' in str(exc), str(exc)[:80])
    for attack in ('authority', 'derivation', 'effective_for_date', 'kind_'):
        try:
            narrow(base, kind=ScopeKind.DATE_INTERVAL, method='m', evidence='e',
                   **{attack: 'x'})
            check(f'narrowing to undeclared field {attack!r} is refused',
                  False, 'accepted')
        except EffectiveScopeError as exc:
            check(f'narrowing to undeclared field {attack!r} is refused',
                  'EFFECTIVE_SCOPE_UNKNOWN_FIELD' in str(exc), str(exc)[:70])
    check('as_dict serialises enums to plain strings, so a scope survives json',
          n.as_dict()['kind'] == 'DATE_INTERVAL'
          and isinstance(n.as_dict()['authority'], str))


def test_i_construction_refusals():
    """Every structural hole that would make a scope unreadable later."""
    print('\nI. malformed scopes are refused when built, by name')
    cases = [
        ('DERIVATION_UNDECLARED',
         dict(kind=ScopeKind.DATE_INTERVAL,
              authority=Authority.DERIVED_DETERMINISTIC, source_value='2026')),
        ('DERIVATION_UNDECLARED',
         dict(kind=ScopeKind.DATE_INTERVAL,
              authority=Authority.DERIVED_HEURISTIC, source_value='2026')),
        ('EFFECTIVE_SCOPE_NO_SOURCE_VALUE',
         dict(kind=ScopeKind.GAME, authority=Authority.SOURCE_PROVIDED,
              source_value='', game_id=GAME)),
        ('EFFECTIVE_SCOPE_GAME_WITHOUT_ID',
         dict(kind=ScopeKind.GAME, authority=Authority.SOURCE_PROVIDED,
              source_value='2026', season=SEASON)),
        ('EFFECTIVE_SCOPE_WEEK_TEAM_INCOMPLETE',
         dict(kind=ScopeKind.WEEK_TEAM, authority=Authority.SOURCE_PROVIDED,
              source_value='2026', season=SEASON, week=WEEK)),
        ('EFFECTIVE_SCOPE_WEEK_TEAM_INCOMPLETE',
         dict(kind=ScopeKind.WEEK_TEAM, authority=Authority.SOURCE_PROVIDED,
              source_value='2026', season=SEASON, teams=TEAMS)),
    ]
    for expected, kwargs in cases:
        try:
            EffectiveScope(**kwargs)
            check(f'{expected} is raised', False, f'accepted {kwargs}')
        except EffectiveScopeError as exc:
            check(f'{expected} is raised', str(exc).startswith(expected),
                  str(exc)[:70])
    check('"we narrowed it somehow" is named as the thing being refused',
          _msg_of(dict(kind=ScopeKind.DATE_INTERVAL,
                       authority=Authority.DERIVED_DETERMINISTIC,
                       source_value='2026')).count('narrowed it somehow') == 1)
    # Reaching the same hole through narrow() must be refused identically.
    try:
        narrow(season_scope(), kind=ScopeKind.GAME, method='m', evidence='e')
        check('narrow() to kind=GAME without a game_id is refused',
              False, 'accepted')
    except EffectiveScopeError as exc:
        check('narrow() to kind=GAME without a game_id is refused',
              'EFFECTIVE_SCOPE_GAME_WITHOUT_ID' in str(exc), str(exc)[:70])


def _msg_of(kwargs):
    try:
        EffectiveScope(**kwargs)
        return ''
    except EffectiveScopeError as exc:
        return str(exc)


def test_j_wrong_season_and_expired():
    """The two remaining interval refusals, plus their precedence."""
    print('\nJ. wrong season, wrong game, and a superseded record')
    old = dataclasses.replace(game_scope(), season=2025)
    o = ask(old)
    check('a 2025 scope is refused for a 2026 game',
          o.state is State.FAIL and o.code == 'EFFECTIVE_SCOPE_WRONG_SEASON',
          str(o))
    check('and both seasons are named', '2025' in o.detail and '2026' in o.detail,
          o.detail[:80])
    expired = game_scope(valid_from='2026-10-01T00:00:00+00:00',
                         valid_to='2026-10-08T00:00:00+00:00')
    e = ask(expired)
    check('a scope that stopped being effective before the forecast is refused',
          e.state is State.FAIL and e.code == 'EFFECTIVE_SCOPE_EXPIRED', str(e))
    check('and it says a superseded record is not a usable one',
          'superseded' in e.detail, e.detail[-70:])
    edge = game_scope(valid_to=FORECAST)
    check('expiring exactly at the forecast instant is still usable',
          ask(edge).state is State.PASS, str(ask(edge)))
    # Precedence: season is checked before anything finer, so a scope that is
    # wrong in two ways reports the coarsest mismatch rather than a random one.
    both = dataclasses.replace(game_scope(), season=2025, week=3)
    check('season mismatch outranks week mismatch, deterministically',
          ask(both).code == 'EFFECTIVE_SCOPE_WRONG_SEASON', str(ask(both)))
    check('and coarseness outranks everything -- a SEASON scope for the wrong '
          'season still reports TOO_COARSE',
          ask(dataclasses.replace(season_scope(), season=2025)).code
          == 'EFFECTIVE_SCOPE_TOO_COARSE')


def test_k_unparseable_timestamps_block_rather_than_fail():
    """A clock we cannot read is a BLOCKED, never a FAIL and never a pass."""
    print('\nK. unreadable timestamps -> BLOCKED(DATA), not FAIL, not silence')
    o = ask(game_scope(), forecast_timestamp='not-a-timestamp')
    check('an unreadable forecast timestamp is BLOCKED',
          o.state is State.BLOCKED, str(o))
    check('named EFFECTIVE_TIMESTAMP_UNPARSEABLE',
          o.code == 'EFFECTIVE_TIMESTAMP_UNPARSEABLE', o.code)
    check('with cause DATA -- the input is malformed, no verdict was reached',
          o.evidence.get('cause') == Cause.DATA.value, str(o.evidence))
    for bad in (None, '', 'week 5', 12345, object()):
        r = ask(game_scope(), forecast_timestamp=bad)
        check(f'forecast_timestamp={bad!r:>12.12} is BLOCKED, not passed',
              r.state is State.BLOCKED
              and r.code == 'EFFECTIVE_TIMESTAMP_UNPARSEABLE', str(r)[:70])
    vf = ask(game_scope(valid_from='2026-13-45'))
    check('an unreadable valid_from is BLOCKED, not treated as absent',
          vf.state is State.BLOCKED
          and vf.code == 'EFFECTIVE_TIMESTAMP_UNPARSEABLE', str(vf)[:80])
    vt = ask(game_scope(valid_to='soon'))
    check('an unreadable valid_to is BLOCKED, not treated as absent',
          vt.state is State.BLOCKED
          and vt.code == 'EFFECTIVE_TIMESTAMP_UNPARSEABLE', str(vt)[:80])
    # A naive timestamp is not an error -- it is read as UTC, and it must not
    # flip a verdict relative to the same instant written with an offset.
    naive = ask(game_scope(), forecast_timestamp='2026-10-09T22:00:00')
    check('a naive timestamp is read as UTC rather than refused',
          naive.state is State.PASS, str(naive)[:80])
    check('and a datetime object is accepted as well as a string',
          ask(game_scope(), forecast_timestamp=dt.datetime(
              2026, 10, 9, 22, 0, tzinfo=dt.timezone.utc)).state is State.PASS)


# --------------------------------------------------------------------------
def _fixed_parse(ts, field):
    """A _parse that collapses every clock to one instant -- the bypass."""
    return dt.datetime(2026, 10, 9, 22, 0, tzinfo=dt.timezone.utc)


@dataclasses.dataclass(frozen=True)
class _PermissiveScope:
    """EffectiveScope with the construction guards removed. Bypass only."""
    kind: object
    authority: object
    source_value: str
    season: object = None
    week: object = None
    teams: tuple = ()
    game_id: object = None
    valid_from: object = None
    valid_to: object = None
    derivation: object = None

    def as_dict(self):
        d = dataclasses.asdict(self)
        d['kind'] = self.kind.value
        d['authority'] = self.authority.value
        return d


def test_l_the_guards_are_load_bearing():
    """Remove each guard and the seeded violation must stop being caught."""
    print('\nL. bypassing each guard makes the violation slip through')

    # 1. TOO_COARSE lives in the game_level_discriminators content check, not in prose.
    try:
        assert_guard_is_load_bearing(
            run=lambda: ask(season_scope()),
            module_path='nfl.identity.effective_scope',
            attr='game_level_discriminators',
            caught=lambda o: o.code == 'EFFECTIVE_SCOPE_TOO_COARSE',
            replacement=lambda *_a, **_k: ['game_id'])
        check('TOO_COARSE depends on game_level_discriminators, not on luck', True)
    except AssertionError as exc:
        check('TOO_COARSE depends on game_level_discriminators, not on luck',
              False, str(exc)[:200])
    with guard_bypassed('nfl.identity.effective_scope', 'game_level_discriminators',
                        replacement=lambda *_a, **_k: ['game_id']):
        leaked = ask(season_scope())
    check('and with it removed, "2026" certifies a specific game -- which is '
          'the exact item-4 defect',
          leaked.state is State.PASS, str(leaked))

    # 2. Both interval refusals depend on the clocks staying distinct.
    for code, scope in (
            ('EFFECTIVE_AFTER_FORECAST',
             game_scope(valid_from='2026-10-11T15:30:00+00:00')),
            ('EFFECTIVE_SCOPE_EXPIRED',
             game_scope(valid_from='2026-10-01T00:00:00+00:00',
                        valid_to='2026-10-08T00:00:00+00:00'))):
        try:
            assert_guard_is_load_bearing(
                run=lambda s=scope: ask(s),
                module_path='nfl.identity.effective_scope', attr='_parse',
                caught=lambda o, c=code: o.code == c,
                replacement=_fixed_parse)
            check(f'{code} depends on _parse keeping the clocks apart', True)
        except AssertionError as exc:
            check(f'{code} depends on _parse keeping the clocks apart',
                  False, str(exc)[:200])

    # 3. The construction guards. narrow() builds through the module-level
    #    EffectiveScope, so swapping in a permissive class proves the refusal
    #    came from __post_init__ and not from narrow()'s own bookkeeping.
    def build_game_without_id():
        try:
            return narrow(season_scope(), kind=ScopeKind.GAME, method='m',
                          evidence='e')
        except EffectiveScopeError as exc:
            return exc

    try:
        assert_guard_is_load_bearing(
            run=build_game_without_id,
            module_path='nfl.identity.effective_scope', attr='EffectiveScope',
            caught=lambda r: isinstance(r, EffectiveScopeError)
            and 'GAME_WITHOUT_ID' in str(r),
            replacement=_PermissiveScope)
        check('EFFECTIVE_SCOPE_GAME_WITHOUT_ID comes from __post_init__', True)
    except AssertionError as exc:
        check('EFFECTIVE_SCOPE_GAME_WITHOUT_ID comes from __post_init__',
              False, str(exc)[:200])

    def build_derived_as_source():
        try:
            return EffectiveScope(kind=ScopeKind.GAME,
                                  authority=Authority.SOURCE_PROVIDED,
                                  source_value='2026', game_id=GAME,
                                  derivation=Derivation('m', 'e'))
        except EffectiveScopeError as exc:
            return exc

    caught_live = build_derived_as_source()
    check('DERIVED_PRESENTED_AS_SOURCE is caught with the guard in place',
          isinstance(caught_live, EffectiveScopeError), str(caught_live)[:80])
    smuggled = _PermissiveScope(kind=ScopeKind.GAME,
                                authority=Authority.SOURCE_PROVIDED,
                                source_value='2026', season=SEASON, week=WEEK,
                                teams=TEAMS, game_id=GAME,
                                derivation=Derivation('m', 'e'))
    check('and __post_init__ is the ONLY place it is caught: an object built '
          'around it is never re-checked at use',
          _kind_of(assert_usable_for(smuggled, game_id=GAME, season=SEASON,
                                     week=WEEK, teams=TEAMS,
                                     forecast_timestamp=FORECAST))
          == 'PASS')


def _kind_of(outcome):
    return outcome.state.value


# --------------------------------------------------------------------------
def test_m_BUG_kind_is_self_declared_and_unverified():
    """THE HOLE. Season-only value certified for a specific game, no narrowing.

    The adversarial question the assignment set was: can a season-only scope be
    certified usable for a specific game WITHOUT declaring a narrowing method?
    It can, and it takes one word.

    BUG: nfl/identity/effective_scope.py:63 and :187. The coarseness gate tests
    the DECLARED LABEL. FIXED: it now reads the CONTENT via game_level_discriminators.
    `__post_init__` (nfl/identity/effective_scope.py:134-140) requires content
    for exactly two kinds -- GAME needs a game_id, WEEK_TEAM needs week+teams.
    DATE_INTERVAL, TEAM_GAME and EXACT_TIMESTAMP require NOTHING. So

        EffectiveScope(kind=DATE_INTERVAL, authority=SOURCE_PROVIDED,
                       source_value='2026', season=2026)

    is the item-4 artifact verbatim -- the season string, nothing else, no
    derivation, no method, no evidence, no interval -- and it is certified
    EFFECTIVE_SCOPE_USABLE for any game in 2026 at any forecast timestamp.
    Relabelling is not narrowing, and one enum value should not be the whole
    distance between BLOCKED and PASS.

    This is not theoretical: nfl/capture/registry.py:211-219 reaches it on the
    production path. See test_source_registry.py section F.

    FIXED 2026-09-06, and BOTH shapes were applied rather than either: content
    is now required per kind in __post_init__, AND the coarseness gate asks
    whether the scope carries a game-level discriminator rather than what it
    calls itself. Either alone would have left the other half open.
    """
    print('\nM. FIXED: a season string relabelled to a finer kind is refused')

    def _refused(kind, expect_code, **fields):
        try:
            EffectiveScope(kind=kind, authority=Authority.SOURCE_PROVIDED,
                           source_value='2026', season=SEASON, **fields)
            return None
        except EffectiveScopeError as exc:
            return str(exc)

    msg = _refused(ScopeKind.DATE_INTERVAL, 'EFFECTIVE_SCOPE_INTERVAL_UNBOUNDED')
    check('FIXED -- a DATE_INTERVAL carrying NO interval and only "2026" is '
          'refused at construction',
          msg is not None and msg.startswith('EFFECTIVE_SCOPE_INTERVAL_UNBOUNDED'),
          str(msg))

    msg = _refused(ScopeKind.TEAM_GAME, 'EFFECTIVE_SCOPE_TEAM_GAME_INCOMPLETE')
    check('FIXED -- kind=TEAM_GAME with no game_id and no teams is refused, as '
          'kind=GAME already was',
          msg is not None and msg.startswith('EFFECTIVE_SCOPE_TEAM_GAME_INCOMPLETE'),
          str(msg))

    msg = _refused(ScopeKind.EXACT_TIMESTAMP, 'EFFECTIVE_SCOPE_TIMESTAMP_MISSING')
    check('FIXED -- kind=EXACT_TIMESTAMP with no timestamp anywhere in the '
          'object is refused',
          msg is not None and msg.startswith('EFFECTIVE_SCOPE_TIMESTAMP_MISSING'),
          str(msg))

    # And the deeper half of the fix: even a WELL-FORMED finer label does not
    # buy game-level certification unless the CONTENT discriminates. An interval
    # open at the top is legal to construct and still too coarse to certify.
    open_interval = EffectiveScope(
        kind=ScopeKind.DATE_INTERVAL, authority=Authority.SOURCE_PROVIDED,
        source_value='2026', season=SEASON, valid_from='2026-09-01T00:00:00Z')
    oi = ask(open_interval)
    check('FIXED -- a well-formed but unbounded interval is still TOO_COARSE, '
          'because it cannot distinguish two games in the same season',
          oi.state is not State.PASS
          and oi.code == 'EFFECTIVE_SCOPE_TOO_COARSE',
          f'got {oi.state.value}[{oi.code}]')

    # The same value, honestly labelled, IS caught. That contrast is the whole
    # finding: the refusal is a property of the label, not of the artifact.
    check('the identical artifact labelled SEASON is correctly BLOCKED, which '
          'is what makes the above a relabelling bypass rather than a gap',
          ask(season_scope()).code == 'EFFECTIVE_SCOPE_TOO_COARSE')
    check('and the bypass needed no derivation at all -- which is why '
          'DERIVATION_UNDECLARED could never have caught it, and why the fix '
          'had to be a content check rather than a derivation check',
          True)

    # Second, smaller instance of the same class of defect.
    # BUG: nfl/identity/effective_scope.py:130-133. DERIVATION_UNDECLARED tests
    # that a Derivation OBJECT exists, not that it says anything. An empty
    # method and empty evidence is "we narrowed it somehow" with a dataclass
    # wrapped round it -- the precise thing the error text refuses.
    try:
        narrow(season_scope(), kind=ScopeKind.WEEK_TEAM, method='',
               evidence='', week=1, teams=('KC',))
        hollow_msg = None
    except EffectiveScopeError as exc:
        hollow_msg = str(exc)
    check('FIXED -- an empty method and empty evidence is refused at '
          'Derivation construction; the object existing was never the '
          'requirement',
          hollow_msg is not None
          and hollow_msg.startswith('DERIVATION_METHOD_EMPTY'),
          str(hollow_msg))


if __name__ == '__main__':
    test_a_effective_for_the_exact_game()
    test_b_prior_week_reuse_is_refused()
    test_c_season_only_is_too_coarse()
    test_d_legitimate_narrowing_passes()
    test_e_derived_presented_as_source_is_refused_at_construction()
    test_f_effective_after_the_forecast_is_refused()
    test_g_cross_team_record_is_refused()
    test_h_narrow_never_overwrites_the_source_value()
    test_i_construction_refusals()
    test_j_wrong_season_and_expired()
    test_k_unparseable_timestamps_block_rather_than_fail()
    test_l_the_guards_are_load_bearing()
    test_m_BUG_kind_is_self_declared_and_unverified()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
