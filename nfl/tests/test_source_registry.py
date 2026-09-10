"""Adversarial replay tests for the source registry. G0A items 1 and 4.

Written by an agent that did NOT write nfl/capture/registry.py.

DEFECTS THIS FILE REPLAYS

  * THE INVENTED ENDPOINT. nfl.com measured unreachable (000) from this
    environment. The tempting repair is a plausible-looking URL. A guess that
    404s is indistinguishable from a real endpoint that is down, and the
    difference is the whole of item 1. Section B requires a named BLOCKED and no
    URL of any shape.

  * THE MIRROR THAT LOOKED LIKE THE CASCADE. `injuries` is a terminal weekly
    archive. If it were allowed to discharge an inactives target, G0A item 1
    would report itself satisfied while the intraweek cascade was never captured
    at all. Section D seeds exactly that call.

  * THE SEASON STRING (item 4, owner-FAILED). A season may never certify
    game-level usability, and a derived value may never wear source authority.
    Section F requires the honest attribution; section G is where it is not
    honest, and FAILS.

  * MLB M0 / THE INERT GUARD. Section H bypasses each critical guard and
    requires the seeded violation to stop being caught.

BINDING TEST STANDARD (Owner Directive 3 section 8): "A guard is not demonstrated
merely because compliant data passes it. It must reject a seeded violation, and
critical guards must demonstrate that removing/bypassing the guard causes the
replay test to fail."

SECTION G FAILS ON PURPOSE -- three real defects on the production path. Do not
delete it and do not weaken it to green. See the BUG: lines.

Run standalone:  python3.12 nfl/tests/test_source_registry.py
"""
import dataclasses
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from sportsplatform.governance.outcome import Cause, Outcome, State            # noqa: E402
from nfl.capture import registry as reg                            # noqa: E402
from nfl.capture.registry import (BY_NAME, REGISTRY, Reachability,  # noqa: E402
                                  SourceSpec, build_scope,
                                  can_discharge, resolve,
                                  unmet_targets)
from nfl.identity.effective_scope import (Authority,               # noqa: E402
                                          EffectiveScope,
                                          EffectiveScopeError,
                                          ScopeKind,
                                          assert_usable_for)
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


SEASON = 2026
TS = '2026-09-11T20:00:00+00:00'
REACHABLE = [s.name for s in REGISTRY
             if s.reachability is Reachability.REACHABLE]
PENDING = [s.name for s in REGISTRY
           if s.reachability is Reachability.PENDING_ENDPOINT_VERIFICATION]


# --------------------------------------------------------------------------
def test_a_a_reachable_source_resolves_to_a_url():
    print('\nA. a reachable source resolves')
    o = resolve('injuries', SEASON)
    check('it passes', o.state is State.PASS, str(o))
    check('with the named code', o.code == 'SOURCE_RESOLVED', o.code)
    url = o.unwrap()
    check('the value is a URL', isinstance(url, str) and url.startswith('https://'),
          str(url))
    check('and the season is substituted, not left as a template',
          '2026' in url and '{season}' not in url, url)
    check('a different season gives a different URL',
          resolve('injuries', 2025).unwrap() != url)
    for name in REACHABLE:
        r = resolve(name, SEASON)
        check(f'{name} resolves to a concrete URL',
              r.state is State.PASS and r.unwrap().startswith('https://'), str(r))
    check('every reachable source names itself in the evidence',
          all(resolve(n, SEASON).evidence.get('source') == n for n in REACHABLE))


def test_b_a_pending_endpoint_blocks_and_invents_nothing():
    print('\nB. an unverified endpoint is BLOCKED, never guessed')
    check('there is at least one pending source to test', bool(PENDING),
          str(PENDING))
    for name in PENDING:
        o = resolve(name, SEASON)
        check(f'{name} is BLOCKED', o.state is State.BLOCKED, str(o))
        check(f'{name} is named ENDPOINT_NOT_YET_VERIFIED',
              o.code == 'ENDPOINT_NOT_YET_VERIFIED', o.code)
        check(f'{name} declares cause DEPENDENCY -- an upstream we do not have, '
              f'not a rule refusing us and not a network failure',
              o.evidence.get('cause') == Cause.DEPENDENCY.value,
              str(o.evidence.get('cause')))
        check(f'{name} carries NO url in the value',
              o.value is None, repr(o.value))
        check(f'{name} carries no url-shaped string anywhere in the outcome',
              'http' not in o.detail and 'http' not in str(o.evidence),
              o.detail[:80])
        check(f'{name} cannot be unwrapped into a usable URL',
              _unwrap_raises(o))
        check(f'{name} has no url_template registered at all, so there is '
              f'nothing to leak by accident',
              BY_NAME[name].url_template is None
              and BY_NAME[name].url(SEASON) is None)
        check(f'{name} says WHY a guess is refused',
              'indistinguishable' in o.detail, o.detail[-90:])
        check(f'{name} still reports which targets it is wired to, so the '
              f'blockage is actionable rather than opaque',
              isinstance(o.evidence.get('serves_kinds'), list),
              str(o.evidence))


def _unwrap_raises(o):
    try:
        o.unwrap()
        return False
    except Exception:
        return True


def test_c_an_unregistered_source_blocks():
    print('\nC. an unregistered source is BLOCKED, not silently absent')
    for name in ('nfl_com_injury_report', 'inactives', 'INJURIES', '',
                 'official_injuries', 'espn_depth_charts'):
        o = resolve(name, SEASON)
        check(f'{name!r} is BLOCKED', o.state is State.BLOCKED, str(o))
        check(f'{name!r} is named SOURCE_NOT_IN_REGISTRY',
              o.code == 'SOURCE_NOT_IN_REGISTRY', o.code)
        check(f'{name!r} declares cause GOVERNANCE -- a rule refused it',
              o.evidence.get('cause') == Cause.GOVERNANCE.value,
              str(o.evidence.get('cause')))
    check('and the refusal says undeclared is not clean',
          'not clean' in resolve('whatever', SEASON).detail)
    check('build_scope refuses an unregistered name the same way',
          build_scope('whatever', season=SEASON,
                      source_timestamp=TS).code == 'SOURCE_NOT_IN_REGISTRY')
    check('a near-miss on a REAL name is refused rather than fuzzy-matched',
          resolve('depth_chart', SEASON).code == 'SOURCE_NOT_IN_REGISTRY')


def test_d_a_mirror_poll_cannot_discharge_the_cascade():
    """The one that would let item 1 report itself satisfied while empty."""
    print('\nD. can_discharge: a weekly mirror is not the intraweek cascade')
    check('injuries CANNOT discharge an inactives target',
          can_discharge('injuries', 'inactives') is False,
          'a terminal weekly snapshot discharged a T-90 deadline')
    check('injuries cannot discharge a practice target either',
          can_discharge('injuries', 'practice') is False)
    check('nor a final_status target',
          can_discharge('injuries', 'final_status') is False)
    check('injuries is declared as serving no scheduler target at all',
          BY_NAME['injuries'].serves_kinds == (),
          str(BY_NAME['injuries'].serves_kinds))
    check('and the registry says why in prose a reader can check',
          'terminal weekly snapshot' in BY_NAME['injuries'].note,
          BY_NAME['injuries'].note[:80])
    check('official_inactives CAN discharge inactives',
          can_discharge('official_inactives', 'inactives') is True)
    check('but not a practice target -- wiring is per kind, not per source',
          can_discharge('official_inactives', 'practice') is False)
    check('official_injury_report discharges practice',
          can_discharge('official_injury_report', 'practice') is True)
    check('and final_status',
          can_discharge('official_injury_report', 'final_status') is True)
    check('but NOT inactives -- the cascade report is not the T-90 list',
          can_discharge('official_injury_report', 'inactives') is False)
    for name in ('schedules', 'depth_charts', 'weekly_rosters',
                 'official_transactions'):
        check(f'{name} discharges nothing',
              not any(can_discharge(name, k)
                      for k in ('practice', 'final_status', 'inactives')))
    check('an unregistered source discharges nothing, and does not raise',
          can_discharge('nfl_com', 'inactives') is False)
    check('an unknown KIND discharges nothing either',
          can_discharge('official_inactives', 'kickoff') is False
          and can_discharge('official_inactives', '') is False)
    check('every source that claims to serve a kind serves a kind the '
          'scheduler actually plans',
          all(k in ('practice', 'final_status', 'inactives')
              for s in REGISTRY for k in s.serves_kinds),
          str({s.name: s.serves_kinds for s in REGISTRY}))


def test_e_unmet_targets_is_the_machine_readable_reason_item_1_fails():
    """unmet_targets must be EVIDENCE-based, not declaration-based.

    An earlier version computed `met` from the REACHABLE flag. When the official
    sources were marked REACHABLE -- which means "attempt this", not "this
    executor can retrieve it" -- all three perishable targets immediately
    reported as met while nothing had ever been captured. A false green produced
    by a one-word change, which is exactly what this function exists to prevent.
    """
    print('\nE. unmet_targets states, in machine-readable form, why item 1 fails')
    import json as _json, tempfile as _tempfile, os as _os

    u = unmet_targets()
    check('with no evidence supplied, NOTHING may be claimed met',
          u['unmet'] == ['final_status', 'inactives', 'practice']
          and u['met'] == [], str(u))
    check('and it says so rather than implying it',
          'nothing can be claimed met' in u['evidence'], u['evidence'])

    check('the one remaining endpoint-unverified source is named',
          u['pending_sources'] == ['official_transactions'],
          str(u['pending_sources']))
    check('unmet and met partition the needed kinds -- no target is unaccounted',
          sorted(u['unmet'] + u['met']) == ['final_status', 'inactives',
                                            'practice'])
    check('a REACHABLE declaration alone moves nothing: the official sources '
          'are attempted, and still unmet',
          BY_NAME['official_inactives'].reachability
          is Reachability.REACHABLE and 'inactives' in u['unmet'],
          str(u['unmet']))

    # A manifest carrying only mirror captures must still leave every
    # perishable target unmet, because no mirror serves one.
    fd, path = _tempfile.mkstemp(suffix='.jsonl'); _os.close(fd)
    try:
        with open(path, 'w') as fh:
            for src in ('schedules', 'depth_charts', 'injuries'):
                fh.write(_json.dumps({'source': src, 'state': 'PASS'}) + '\n')
        mirrors = unmet_targets(path)
        check('mirror captures do NOT discharge a perishable target',
              mirrors['unmet'] == ['final_status', 'inactives', 'practice'],
              str(mirrors))

        # Add one real capture of a source that IS authorised to serve
        # inactives, and only then does the target leave the unmet list.
        with open(path, 'a') as fh:
            fh.write(_json.dumps({'source': 'official_inactives',
                                  'state': 'PASS'}) + '\n')
        moved = unmet_targets(path)
        check('an ACTUAL capture of official_inactives clears the inactives '
              'target, and only that target',
              moved['unmet'] == ['final_status', 'practice']
              and moved['met'] == ['inactives'], str(moved))

        # A FAILED capture is not a capture.
        with open(path, 'w') as fh:
            fh.write(_json.dumps({'source': 'official_inactives',
                                  'state': 'BLOCKED'}) + '\n')
        blocked = unmet_targets(path)
        check('a BLOCKED capture of the same source discharges nothing',
              blocked['unmet'] == ['final_status', 'inactives', 'practice'],
              str(blocked))
    finally:
        _os.unlink(path)

    check('and with no evidence the real answer is unchanged',
          unmet_targets()['met'] == [])


def test_f_build_scope_attributes_honestly():
    print('\nF. build_scope: source-provided only where the source provides it')
    d = build_scope('depth_charts', season=SEASON, source_timestamp=TS)
    check('depth_charts builds', d.state is State.PASS, str(d))
    ds = d.unwrap()
    check('depth_charts is EXACT_TIMESTAMP -- it genuinely pins its own instant',
          ds.kind is ScopeKind.EXACT_TIMESTAMP, ds.kind.value)
    check('and it is SOURCE_PROVIDED',
          ds.authority is Authority.SOURCE_PROVIDED, ds.authority.value)
    check('with the upstream instant as the source value, not the season',
          ds.source_value == TS, ds.source_value)
    check('and no derivation, because nothing was derived',
          ds.derivation is None, str(ds.derivation))
    check('the effective interval opens at that instant',
          ds.valid_from == TS, str(ds.valid_from))

    for name in ('injuries', 'schedules', 'weekly_rosters'):
        o = build_scope(name, season=SEASON, source_timestamp=TS)
        check(f'{name} builds', o.state is State.PASS, str(o))
        s = o.unwrap()
        check(f'{name} is DERIVED_DETERMINISTIC, not source-provided',
              s.authority is Authority.DERIVED_DETERMINISTIC, s.authority.value)
        check(f'{name} reports is_derived', s.authority.is_derived)
        check(f'{name} carries a derivation method',
              s.derivation is not None and len(s.derivation.method) > 10,
              str(s.derivation))
        check(f'{name} carries evidence for that method',
              len(s.derivation.evidence) > 30, str(s.derivation))
        check(f'{name} names Last-Modified as the boundary it actually used',
              'Last-Modified' in s.derivation.method, s.derivation.method)
        check(f'{name} keeps the coarse source value -- the season, verbatim',
              s.source_value == '2026', s.source_value)
        check(f'{name} did NOT overwrite the source value with the timestamp',
              s.source_value != TS)
        check(f'{name} narrows to DATE_INTERVAL and dates the interval',
              s.kind is ScopeKind.DATE_INTERVAL and s.valid_from == TS,
              f'{s.kind.value} {s.valid_from}')
        check(f'{name} says the SOURCE kind was coarser than the result',
              BY_NAME[name].source_scope_kind is ScopeKind.SEASON)
    check('no built scope is ever SOURCE_PROVIDED while carrying a derivation',
          all(not (s.authority is Authority.SOURCE_PROVIDED and s.derivation)
              for s in _built_scopes()))
    check('and the season-scoped mirrors are still refused for game-level use, '
          'because DATE_INTERVAL from a season is not a game certificate',
          build_scope('injuries', season=SEASON,
                      source_timestamp=TS).unwrap().week is None)


def _built_scopes():
    out = []
    for s in REGISTRY:
        try:
            o = build_scope(s.name, season=SEASON, source_timestamp=TS)
        except Exception:
            continue
        if o.state is State.PASS:
            out.append(o.value)
    return out


# --------------------------------------------------------------------------
def _fake_narrow(scope, **kw):
    """A narrow() that fabricates source authority. Bypass only."""
    return EffectiveScope(kind=kw['kind'], authority=Authority.SOURCE_PROVIDED,
                          source_value=scope.source_value, season=scope.season,
                          valid_from=kw.get('valid_from'))


def test_h_the_registry_guards_are_load_bearing():
    print('\nH. bypassing each guard lets the seeded violation through')

    # 1. Honest attribution comes from narrow(), not from a comment.
    try:
        assert_guard_is_load_bearing(
            run=lambda: build_scope('injuries', season=SEASON,
                                    source_timestamp=TS),
            module_path='nfl.capture.registry', attr='narrow',
            caught=lambda o: o.value.authority.is_derived,
            replacement=_fake_narrow)
        check('DERIVED attribution depends on narrow()', True)
    except AssertionError as exc:
        check('DERIVED attribution depends on narrow()', False, str(exc)[:200])
    with guard_bypassed('nfl.capture.registry', 'narrow',
                        replacement=_fake_narrow):
        faked = build_scope('injuries', season=SEASON,
                            source_timestamp=TS).unwrap()
    check('with it bypassed, a season string wears SOURCE_PROVIDED authority -- '
          'the item-4 defect, restored',
          faked.authority is Authority.SOURCE_PROVIDED, faked.authority.value)

    # 2. The endpoint refusal depends on the registered reachability, not on
    #    the absence of a url_template: registering a guess would ship it.
    guessed = tuple(dataclasses.replace(
        s, reachability=Reachability.REACHABLE,
        url_template='https://www.nfl.com/transactions/league/{season}/REG1')
        if s.name == 'official_transactions' else s for s in REGISTRY)
    by_name_guessed = {s.name: s for s in guessed}
    try:
        assert_guard_is_load_bearing(
            run=lambda: resolve('official_transactions', SEASON),
            module_path='nfl.capture.registry', attr='BY_NAME',
            caught=lambda o: o.code == 'ENDPOINT_NOT_YET_VERIFIED',
            replacement=by_name_guessed)
        check('ENDPOINT_NOT_YET_VERIFIED depends on the declared reachability',
              True)
    except AssertionError as exc:
        check('ENDPOINT_NOT_YET_VERIFIED depends on the declared reachability',
              False, str(exc)[:200])
    with guard_bypassed('nfl.capture.registry', 'BY_NAME',
                        replacement=by_name_guessed):
        leaked = resolve('official_transactions', SEASON)
    check('and with it bypassed a GUESSED nfl.com URL is handed out as fact',
          leaked.state is State.PASS and 'nfl.com' in leaked.unwrap(),
          str(leaked))

    # 3. The mirror/cascade separation depends on serves_kinds.
    wired = {s.name: (dataclasses.replace(s, serves_kinds=('inactives',))
                      if s.name == 'injuries' else s) for s in REGISTRY}
    try:
        assert_guard_is_load_bearing(
            run=lambda: can_discharge('injuries', 'inactives'),
            module_path='nfl.capture.registry', attr='BY_NAME',
            caught=lambda r: r is False,
            replacement=wired)
        check('the mirror refusal depends on declared serves_kinds', True)
    except AssertionError as exc:
        check('the mirror refusal depends on declared serves_kinds',
              False, str(exc)[:200])
    check('and the real registry is restored after every bypass',
          can_discharge('injuries', 'inactives') is False
          and resolve('official_transactions', SEASON).code
          == 'ENDPOINT_NOT_YET_VERIFIED'
          and resolve('official_inactives', SEASON).code == 'SOURCE_RESOLVED')

    # 4. A REACHABLE source with no template is an inconsistent registration
    #    and must FAIL loudly rather than return None as a URL.
    broken = {s.name: (dataclasses.replace(s,
                                           reachability=Reachability.REACHABLE)
                       if s.name == 'official_transactions' else s)
              for s in REGISTRY}
    with guard_bypassed('nfl.capture.registry', 'BY_NAME', replacement=broken):
        b = resolve('official_transactions', SEASON)
    check('reachable-but-no-template is a named FAIL, never a None URL',
          b.state is State.FAIL and b.code == 'SOURCE_URL_MISSING', str(b))


# --------------------------------------------------------------------------
def test_g_BUG_build_scope_fabricates_for_unverified_sources():
    """THREE real defects, all on the production path, all in build_scope.

    BUG 1 -- nfl/capture/registry.py:211-219 raises instead of returning.
      `build_scope('official_injury_report', ...)` constructs an EffectiveScope
      with kind=WEEK_TEAM and no week and no teams, so
      nfl/identity/effective_scope.py:137 raises EffectiveScopeError out of a
      stage boundary that is otherwise Outcome-returning. Every other refusal in
      this module is a named Outcome; this one is an uncaught exception, and it
      is on THE source G0A item 1 depends on. A caller written to the module's
      own contract (`o.state is State.PASS`) never runs.

    BUG 2 -- nfl/capture/registry.py:211-219 ignores reachability entirely.
      `resolve()` refuses to invent an endpoint for a
      PENDING_ENDPOINT_VERIFICATION source; `build_scope()` cheerfully invents
      the SEMANTICS for the same source. For `official_inactives` it returns
      kind=TEAM_GAME, authority=SOURCE_PROVIDED, source_value='2026' -- a claim
      that an upstream we have never successfully contacted told us this record
      is pinned to a team-game. It did not. Nothing was captured.

    BUG 3 -- the consequence, and it is item 4 verbatim.
      That fabricated scope carries a season string and nothing else, yet
      `assert_usable_for` certifies it EFFECTIVE_SCOPE_USABLE for ANY 2026 game
      at ANY forecast timestamp, because the coarseness gate reads the declared
      kind rather than the content (see test_effective_scope.py section M).
      This is the exact path by which "2026" ends up certifying a specific game.

    The fix belongs in registry.py, not here: build_scope should refuse a source
    whose endpoint is unverified (there is no capture to scope), and should
    return a named Outcome rather than raising when the declared kind cannot be
    populated from what it holds.
    """
    print('\nG. BUG: build_scope invents scopes for sources never contacted')

    raised = {}
    built = {}
    for s in REGISTRY:
        try:
            built[s.name] = build_scope(s.name, season=SEASON,
                                        source_timestamp=TS)
        except Exception as exc:
            raised[s.name] = f'{type(exc).__name__}: {str(exc)[:60]}'
    check('BUG registry.py:211 -- build_scope must return an Outcome for every '
          'registered source, never raise',
          not raised, str(raised))

    fabricated = sorted(
        name for name, o in built.items()
        if o.state is State.PASS
        and o.value.authority is Authority.SOURCE_PROVIDED
        and BY_NAME[name].reachability is not Reachability.REACHABLE)
    check('BUG registry.py:211-219 -- no SOURCE_PROVIDED scope may be built '
          'for a source whose endpoint is unverified: nothing was captured, so '
          'there is no source value to attribute',
          not fabricated,
          f'{fabricated} got SOURCE_PROVIDED scopes while resolve() refuses '
          f'them as ENDPOINT_NOT_YET_VERIFIED')

    inact = built.get('official_inactives')
    if inact is not None and inact.state is State.PASS:
        sc = inact.value
        usable = assert_usable_for(sc, game_id='2026_17_ZZZ_YYY', season=SEASON,
                                   week=17, teams=('ZZZ', 'YYY'),
                                   forecast_timestamp='2027-01-01T00:00:00+00:00')
        check('BUG registry.py:211-219 + effective_scope.py:187 -- the '
              'fabricated inactives scope, whose entire content is the season '
              'string, must not certify an arbitrary game at an arbitrary time',
              usable.state is not State.PASS,
              f'source_value={sc.source_value!r} kind={sc.kind.value} '
              f'authority={sc.authority.value} week={sc.week} teams={sc.teams} '
              f'game_id={sc.game_id} valid_from={sc.valid_from} -> '
              f'{usable.state.value}[{usable.code}]')

    # Context, so the finding cannot be read as a style complaint.
    # FIXED: they now agree. resolve() refuses to invent an endpoint and
    # build_scope() refuses to invent the semantics for the same source --
    # refusing the URL while fabricating the meaning was the same defect in
    # different clothes.
    check('resolve() and build_scope() now AGREE: both refuse an unverified '
          'source',
          resolve('official_transactions', SEASON).state is State.BLOCKED
          and built['official_transactions'].state is State.BLOCKED,
          f"resolve={resolve('official_transactions', SEASON).code} "
          f"build_scope={built['official_transactions'].code}")
    # depth_charts pins its own instant via an upstream `dt` column. The two
    # official pages pin theirs differently but just as legitimately: a rendered
    # page IS effective at the moment the origin produced it. What none of them
    # may claim is a week or a team, which is a property of a PARSED ROW and not
    # of a captured page.
    stamped = sorted(s.name for s in REGISTRY
                     if s.source_scope_kind is ScopeKind.EXACT_TIMESTAMP
                     and s.reachability is Reachability.REACHABLE)
    check('the sources that pin an instant are exactly the dt series and the '
          'two rendered official pages',
          stamped == ['depth_charts', 'official_inactives',
                      'official_injury_report'], str(stamped))
    check('and NO source claims a week or a team at capture time, because a '
          'captured page has neither',
          not [s.name for s in REGISTRY
               if s.source_scope_kind in (ScopeKind.WEEK_TEAM,
                                          ScopeKind.TEAM_GAME)],
          str([s.name for s in REGISTRY
               if s.source_scope_kind in (ScopeKind.WEEK_TEAM,
                                          ScopeKind.TEAM_GAME)]))
    check('and the raising source is the one item 1 depends on, which is why '
          'this is not cosmetic',
          BY_NAME['official_injury_report'].serves_kinds
          == ('practice', 'final_status'))



def test_i_the_capture_source_carries_the_content_markers_it_is_judged_by():
    """The guard the egress block hid, and the executor that found it.

    registry.SourceSpec defines content_markers and both official sources set
    it, but capture_vintage.Source -- a SEPARATE dataclass -- did not declare
    the field and _sources() did not copy it, so the html content check read
    an attribute that was not there. In this executor nfl.com is unreachable,
    so the fetch failed long before the guard ran and every capture reported a
    clean BLOCKED[NO_EGRESS] over a broken guard. The executor that CAN fetch
    hit it instead: official_inactives and official_injury_report both came
    back FAIL[SOURCE_RAISED] with "AttributeError: 'Source' object has no
    attribute 'content_markers'" at 2026-09-10T23:04Z, inside the T-90 window.

    An unreachable code path is not a working one. This test runs the wiring
    with no network at all, which is the only reason it can stand here.
    """
    from nfl.tools import capture_vintage as CV

    check('capture_vintage.Source declares content_markers at all',
          'content_markers' in
          {f.name for f in dataclasses.fields(CV.Source)})

    built = {s.name: s for s in CV._sources(2026)}
    spec_by_name = {sp.name: sp for sp in REGISTRY}
    checked = 0
    for name, src in built.items():
        spec = spec_by_name.get(name)
        want = tuple(getattr(spec, 'content_markers', ()) or ())
        check(f'  {name}: markers carried across from the registry',
              tuple(src.content_markers) == want,
              f'{src.content_markers!r} != {want!r}')
        checked += 1
    check('every built source was compared', checked > 0, str(checked))

    check('and the inactives page is judged by its OWN subject word',
          built['official_inactives'].content_markers == ('inactive',)
          if 'official_inactives' in built else True,
          str(built.get('official_inactives')))

    # THE GUARD MUST ALSO RUN, not merely be populated. Reaching the attribute
    # is what raised in production, so reach it the same way the html branch
    # does and require no exception.
    for name, src in built.items():
        if src.content_kind != 'html':
            continue
        markers = src.content_markers or ('questionable',)
        check(f'  {name}: the html content check can read its vocabulary',
              isinstance(markers, tuple) and len(markers) >= 1,
              repr(markers))



if __name__ == '__main__':
    test_a_a_reachable_source_resolves_to_a_url()
    test_b_a_pending_endpoint_blocks_and_invents_nothing()
    test_c_an_unregistered_source_blocks()
    test_d_a_mirror_poll_cannot_discharge_the_cascade()
    test_e_unmet_targets_is_the_machine_readable_reason_item_1_fails()
    test_f_build_scope_attributes_honestly()
    test_h_the_registry_guards_are_load_bearing()
    test_g_BUG_build_scope_fabricates_for_unverified_sources()
    test_i_the_capture_source_carries_the_content_markers_it_is_judged_by()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
