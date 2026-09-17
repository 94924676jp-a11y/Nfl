"""Production QB dropback allocation. CANDIDATE -- not promoted.

WHAT THIS FIXES

R4 measured the engine forecasting 2.62 starting quarterbacks per team: D1 team
dropbacks 36.75 against QB-summed 79.76, a ratio of 2.17, with the quarterbacks
out-dropping their own team in 92.7% of draw cells. The QB layer models a
passer's line CONDITIONAL ON BEING THE PRIMARY PASSER and nothing selected
which of the room that was.

GOVERNANCE. This is a new component evaluated on 2022-2024 development data and
it is NOT promoted. `PATH_C_STATE` is not edited by it. It enters the engine as
a REHEARSAL_ONLY candidate, which is the same runtime role every other non-QB
layer already has, and nothing in the engine is publication-eligible while
NFL-1 is unauthorised.

WHY IT IS STILL THE RIGHT THING TO WIRE IN. Two of its properties are separable:
the CRPS improvement is a forecasting claim on development data and is
exploratory; the SIMPLEX CLOSURE is an accounting property that holds by
construction in every draw. The alternative to wiring it in is leaving the
engine at 2.17x, which is not a neutral default.

PREGAME INPUTS, both available for 2026 and neither blocked on injuries:
  1. the captured depth chart -- QB rank per team
  2. last game's primary passer, strictly-earlier ordinal, spanning seasons

Research: nfl/research/qb3/. Pre-registration sha256
be61392619d45f3ad1936ef0512d203d9f415ba92e271aa6010281e707f05a9e
"""
from __future__ import annotations

import bisect
import collections
import csv
import glob
import gzip
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'qb3')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.production.nonqb import vintage_selector as VS  # noqa: E402

SPEC_VERSION = 'qb3-dropback-allocation-candidate-1'
GOVERNANCE = 'CANDIDATE -- evaluated on 2022-2024 development data, NOT promoted'
DEPTH_GLOB = 'depth_charts.*.csv.gz'
KNOWN_LIMITATIONS = {
    'development_data': 'the walk-forward evaluation ran on 2022-2024, which '
                        'are development seasons. No prospective evidence '
                        'exists.',
    'week_1_incumbent': 'for week 1 the previous primary comes from the last '
                        'game of the PRIOR SEASON, so an offseason change of '
                        'starter is the hardest case this layer faces and is '
                        'not separately modelled.',
    'calibration_untested': 'the zero-share calibration table is descriptive. '
                            'No equivalence margin was predeclared and no test '
                            'was run, so it is not called calibrated.',
    'depth_chart_2025_absent': 'the committed depth-chart leaves stop at 2024, '
                               'so the 2025 evaluation fold could not run.',
}

_FIT = {}


def _fit_for(season: int):
    if season in _FIT:
        return _FIT[season]
    import qb3_lib as Q
    frame = Q.build_frame(Q.load_qb_panel(), Q.load_depth())
    par = Q.fit(frame, season)
    if not par['n']:
        return None
    _FIT[season] = (par, frame)
    return _FIT[season]


def cache_clear():
    _FIT.clear()


def dt_max():
    """A sentinel later than any real instant, for ordering unparseable bounds
    last rather than crashing on them."""
    import datetime as _dt
    return _dt.datetime.max.replace(tzinfo=_dt.timezone.utc)


def _depth_chart_vintages():
    """(retrieved_at, path) for every depth-chart capture, oldest first.

    The clock comes from the manifest, which is the only place it is recorded.
    A blob with no manifest row is UNATTRIBUTABLE and is excluded rather than
    guessed at -- an unplaceable capture cannot be shown lawful for any cut.
    """
    import json as _json
    man = _REPO / 'nfl' / 'vintage_manifest.jsonl'
    rows = []
    if man.exists():
        for line in man.read_text().splitlines():
            if line.strip():
                try:
                    rows.append(_json.loads(line))
                except ValueError:
                    continue
    out = []
    for p in sorted(glob.glob(str(_REPO / 'nfl' / 'vintage' / DEPTH_GLOB))):
        h = pathlib.Path(p).name.split('.')[1]
        when = None
        for r in rows:
            if h in _json.dumps(r):
                when = r.get('retrieved_at') or r.get('capture_id')
                break
        if when:
            # PARSED, NOT STRING-COMPARED. The manifest carries BOTH shapes --
            # `2026-09-14T17:39:41.517748Z` and the compact capture-id form
            # `20260910T120717Z` -- and comparing them as strings is wrong in a
            # way that looks like it works: '-' (0x2D) sorts before '0' (0x30),
            # so EVERY compact stamp sorts after EVERY ISO one regardless of
            # date. My first version of this function did exactly that and
            # concluded that 0 of 7 captures were lawful for a 2026-09-11 cut
            # when five of them were.
            t = VS.parse_ts(when)
            if t is not None:
                out.append((t, str(when), p))
    return sorted(out, key=lambda r: r[0])


def captured_depth_chart(as_of=None) -> Outcome:
    """QB rank per team from the newest depth chart LAWFUL AT `as_of`.

    SELECTION IS BY CLOCK. IT USED TO BE BY CONTENT-HASH ORDER.

    This read `sorted(glob(...))[-1]` and called it "the newest captured depth
    chart". The filenames carry content hashes, so that is lexicographically
    last by hash and bears no relation to time. On the seven captures in the
    tree hash order and time order happen to agree; nothing makes them agree.
    A capture hashing to `0abc...` taken tomorrow would sort FIRST and never be
    selected; one hashing to `fff...` taken last week would be selected
    forever.

    The cost was real, not theoretical: a forecast written 2026-09-11 was
    served a chart retrieved 2026-09-14 -- three days of future information --
    while FIVE lawful captures for that cut sat unused (09-06, 09-07, 09-08 and
    two on 09-10). `allocate` has carried a correct chronology guard for this
    all along, but no caller passed it a clock until 2026-09-15, so it never
    executed. The guard is the backstop; this is the cause.

    `as_of=None` preserves the previous behaviour for callers that have no cut
    -- it selects the newest by TIME rather than by hash, which is what the old
    docstring always claimed was happening.
    """
    vintages = _depth_chart_vintages()
    if not vintages:
        # No manifest row for any blob: fall back to the raw listing so a
        # missing manifest degrades to the old behaviour rather than to a
        # refusal that hides a capture which does exist.
        fs = sorted(glob.glob(str(_REPO / 'nfl' / 'vintage' / DEPTH_GLOB)))
        if not fs:
            return Outcome.blocked(
                'DEPTH_CHART_NOT_CAPTURED',
                'no depth-chart capture exists in nfl/vintage',
                cause=Cause.DATA)
        p = fs[-1]
    else:
        cut = VS.parse_ts(as_of) if as_of is not None else None
        if as_of is not None and cut is None:
            return Outcome.fail(
                'DEPTH_CHART_CUT_UNPARSEABLE',
                f'as_of={as_of!r} could not be parsed as an instant. '
                f'Refusing rather than silently ignoring the cut.')
        lawful = [r for r in vintages if cut is None or r[0] < cut]
        if not lawful:
            return Outcome.blocked(
                'DEPTH_CHART_NO_LAWFUL_VINTAGE',
                f'every depth-chart capture was retrieved at or after '
                f'{as_of}; the oldest is {vintages[0][1]}. Refusing to serve '
                f'a chart the forecast could not have seen.',
                cause=Cause.DATA, as_of=str(as_of),
                oldest_available=vintages[0][1])
        p = lawful[-1][2]
    rows = list(csv.DictReader(gzip.open(p, 'rt')))
    qb = [r for r in rows if (r.get('pos_abb') or '').upper() == 'QB'
          and r.get('gsis_id')]
    if not qb:
        return Outcome.fail(
            'DEPTH_CHART_NO_QB_ROWS',
            f'{pathlib.Path(p).name} carries {len(rows)} rows and none is a '
            f'quarterback. An empty read is not an empty depth chart.')
    out = collections.defaultdict(dict)
    for r in qb:
        try:
            rank = int(r['pos_rank'])
        except (ValueError, TypeError, KeyError):
            continue
        prev = out[r['team']].get(r['gsis_id'])
        if prev is None or rank < prev:
            out[r['team']][r['gsis_id']] = rank
    dts = sorted({r.get('dt') for r in qb if r.get('dt')})
    # TWO DIFFERENT INSTANTS, PREVIOUSLY ONE NAME.
    #
    # `retrieved_at` here has always been the newest `dt` INSIDE the chart --
    # the vendor's own publication stamp -- not the moment we fetched it. The
    # manifest records the fetch. They differ (09-10T12:01 inside a blob
    # fetched 09-10T12:07) and a reader comparing one against the other gets a
    # mismatch that looks like a bug in the selector.
    #
    # The name is kept because the chronology guard reads it and because the
    # VENDOR stamp is the right bound for leakage -- what matters is when the
    # information existed, not when we happened to collect it. The fetch
    # instant is published beside it under its own name so the two can never
    # again be confused for each other.
    _sel = None
    for _t, _w, _path in _depth_chart_vintages():
        if _path == p:
            _sel = _w
            break
    return Outcome.ok('DEPTH_CHART_OK', value=dict(out),
                      blob=pathlib.Path(p).name, n_teams=len(out),
                      n_qb_rows=len(qb), retrieved_at=(dts[-1] if dts else None),
                      vendor_dt=(dts[-1] if dts else None),
                      capture_retrieved_at=_sel,
                      selected_as_of=str(as_of) if as_of is not None else None)


def previous_primary_detail(season: int, week: int) -> dict:
    """team -> {'pid', 'ordinal', 'is_season_opener'}.

    THE SEASON BOUNDARY IS A FACT ABOUT THE GAP, NOT ABOUT `week == 1`.
    A club whose previous ordinal belongs to an earlier season is crossing the
    boundary whether or not this game is labelled week 1 -- postponements and
    international openers both break that equivalence. The audit
    (QB3_WEEK1_INCUMBENT_AUDIT.json) measured what crossing it costs: the
    previous primary is then a week-18 quarterback, and 40.1% of team-seasons
    end with a primary who is not that season's modal starter.

    This is DIAGNOSIS CARRIED ONTO THE ARTIFACT. It changes no probability and
    no draw; it records which configuration produced them so a reader, and the
    market comparator, can tell a contaminated room from a clean one.
    """
    import qb3_lib as Q
    rows = Q.load_qb_panel()
    tg = Q.team_games(rows)
    prim, by_team = {}, collections.defaultdict(list)
    for (t, o), v in tg.items():
        prim[(t, o)] = Q.primary_of(v)
        by_team[t].append(o)
    cut = season * 100 + week
    out = {}
    for t, oo in by_team.items():
        oo.sort()
        i = bisect.bisect_left(oo, cut)
        if i <= 0:
            out[t] = {'pid': None, 'ordinal': None, 'is_season_opener': None}
            continue
        po = oo[i - 1]
        out[t] = {'pid': prim.get((t, po)), 'ordinal': po,
                  'is_season_opener': (po // 100) != season}
    return out


#: The newest ordinal the incumbency panel may trail the forecast ordinal by,
#: in weeks, before the state is STALE rather than merely historical. One: a
#: week-W forecast must be able to see week W-1. Not a tuning knob -- it is the
#: definition of "the previous game is the previous game".
PANEL_MAX_TRAIL_WEEKS = 1


def panel_freshness(season: int, week: int) -> Outcome:
    """Can the incumbency panel see the forecast week`s PREVIOUS game?

    THE ASSERTION THIS FILE WAS MISSING. `previous_primary_detail` takes the
    most recent ordinal strictly before the cut and is correct. It has no way
    to notice that the most recent ordinal is nine months old, so a week-2
    forecast silently inherited 2025 week 18 for all 32 clubs and every one of
    them was classed a season opener. Nothing refused, because nothing asked.

    Measured 2026-09-17: `panel_p3.csv.gz` holds 2020-2025 with a maximum
    ordinal of 202518 and ZERO rows for 2026.

    A week-1 forecast legitimately crosses a season boundary and is NOT stale.
    Any later week whose panel cannot reach week W-1 IS, and returns a named
    BLOCKED rather than a silent answer.
    """
    import qb3_lib as Q
    rows = Q.load_qb_panel()
    if not rows:
        return Outcome.blocked(
            'PANEL_EMPTY',
            'the incumbency panel holds no rows at all. An empty panel is an '
            'error, not a season boundary.', cause=Cause.DATA)
    newest = max(r['ord'] for r in rows)
    cut = int(season) * 100 + int(week)
    ev = {'newest_panel_ordinal': newest, 'forecast_ordinal': cut,
          'max_trail_weeks': PANEL_MAX_TRAIL_WEEKS,
          'seasons_in_panel': sorted({r['ord'] // 100 for r in rows})}
    if int(week) <= 1:
        return Outcome.ok(
            'PANEL_FRESHNESS_NOT_APPLICABLE_AT_A_SEASON_OPENER',
            value=dict(ev),
            detail='week 1 crosses a season boundary by definition, so the '
                   'previous ordinal belonging to an earlier season is the '
                   'correct answer and not a staleness finding.', **ev)
    need = int(season) * 100 + (int(week) - PANEL_MAX_TRAIL_WEEKS)
    if newest >= need:
        return Outcome.ok('PANEL_FRESH', value=dict(ev),
                          detail=f'newest panel ordinal {newest} reaches the '
                                 f'required {need}', **ev)
    return Outcome.blocked(
        'PANEL_STALE_CURRENT_SEASON_STATE',
        f'the incumbency panel`s newest ordinal is {newest} and a '
        f'{season} week {week} forecast requires at least {need}. Every club '
        f'will therefore inherit a previous primary from {newest // 100} '
        f'week {newest % 100} and be classed a season opener in a week that '
        f'is not one. This is STALE CURRENT-SEASON STATE, not a season '
        f'boundary.', cause=Cause.DATA, **ev)


QB3_CONFIGURATIONS = ('AGREE', 'DISAGREE', 'NO_PREV_PRIMARY_IN_ROOM')

#: The two conditions `is_season_opener` conflated, named apart.
BOUNDARY_CAUSES = ('SEASON_OPENER', 'STALE_CURRENT_SEASON_STATE',
                   'UNDETERMINED')


def _boundary_defect_id(opener, season, week):
    if not opener:
        return None
    if week is None:
        return 'QB3_WEEK1_SEASON_BOUNDARY'
    return ('QB3_WEEK1_SEASON_BOUNDARY' if int(week) <= 1
            else 'QB_STALE_CURRENT_SEASON_STATE')


def qb3_configuration(trip, prev_detail, season=None, week=None) -> dict:
    """How the depth chart and the incumbent signal stand to each other.

    `trip` is the production room: [(pid, rank, was_prev_primary)].

    THE DEFECT LABEL NAMED ONE CONDITION AND FIRED ON TWO. `is_season_opener`
    is true whenever the previous ordinal belongs to an earlier season, and
    that happens for two entirely different reasons:

      * the forecast IS a season opener -- a real boundary, correctly named
        QB3_WEEK1_SEASON_BOUNDARY;
      * the forecast is week 2 or later and the PANEL has no current-season
        rows -- stale state wearing a boundary's clothes. Calling that a
        "week1 specification defect" hid it for an entire week of forecasts.

    `season`/`week` separate them. Without them the old id is kept, because a
    caller that cannot say which week it is must not be told which of the two
    it has.
    """
    top = [x for x in trip if x[1] == 1]
    if any(x[2] for x in top):
        cfg = 'AGREE'
    elif any(x[2] for x in trip if x[1] != 1):
        cfg = 'DISAGREE'
    else:
        cfg = 'NO_PREV_PRIMARY_IN_ROOM'
    d = prev_detail or {}
    opener = d.get('is_season_opener')
    return {
        'configuration': cfg,
        'is_season_opener': opener,
        'prev_primary_pid': d.get('pid'),
        'prev_primary_ordinal': d.get('ordinal'),
        'depth_chart_qb1': top[0][0] if top else None,
        'n_qb_in_room': len(trip),
        # THE CONTAMINATION CONDITION, STATED ONCE AND NAMED.
        # Measured week-1 bias of the chart QB1's share against realised, all
        # three configurations, team-clustered and all excluding zero:
        # AGREE -0.1098, DISAGREE -0.4420, NO_PREV -0.3611. Every week-1 room
        # is affected; DISAGREE and NO_PREV are affected severely.
        'week1_specification_defect': bool(opener),
        # KEPT so every sealed artifact keeps the id it recorded.
        'defect_id': (_boundary_defect_id(opener, season, week)
                      if opener else None),
        'defect_id_legacy': 'QB3_WEEK1_SEASON_BOUNDARY' if opener else None,
        'boundary_cause': (None if not opener else
                           ('SEASON_OPENER' if (week is not None and
                                                int(week) <= 1)
                            else ('STALE_CURRENT_SEASON_STATE'
                                  if week is not None else 'UNDETERMINED'))),
        'defect_basis': (
            'nfl/research/qb3/QB3_WEEK1_INCUMBENT_AUDIT.json. The previous '
            'primary comes from the prior season\'s final game, which is the '
            'game a club is most likely to rest its starter in, so the '
            'incumbent signal can name a rested or replaced quarterback and '
            'dilute the current QB1.' if opener else None),
    }


def previous_primary(season: int, week: int) -> dict:
    """team -> the gsis_id of the primary passer of its last game, strictly
    earlier by ordinal and spanning seasons."""
    import qb3_lib as Q
    rows = Q.load_qb_panel()
    tg = Q.team_games(rows)
    prim, by_team = {}, collections.defaultdict(list)
    for (t, o), v in tg.items():
        prim[(t, o)] = Q.primary_of(v)
        by_team[t].append(o)
    cut = season * 100 + week
    out = {}
    for t, oo in by_team.items():
        oo.sort()
        i = bisect.bisect_left(oo, cut)
        out[t] = prim.get((t, oo[i - 1])) if i > 0 else None
    return out


# WHAT AN UNRESOLVED OFFICIAL NAME CAN AND CANNOT TELL US.
#
# Owner ruling 2026-09-13, narrowing `no_unresolved_identity` from "no
# unresolved inactive name of any position" to "no unresolved identity capable
# of affecting the QB room". A defensive tackle the roster vintage does not
# carry cannot hold a dropback, and refusing QB enforcement over him was
# conservative past the point of being informative.
#
# THE SOURCE'S POSITION IS USED FOR EXACTLY ONE DECISION: can this unresolved
# name touch the quarterback room? It is NEVER used to invent a gsis_id, never
# used to resolve the name, and never used to satisfy non-QB completeness --
# the name stays unresolved everywhere it was unresolved before.
QB_POSITION_TOKENS = frozenset({'QB'})

# Positions the official reports actually use. Membership is EXACT and
# uppercase: a token that is not in either set is UNKNOWN, and unknown fails
# closed. This is a frozenset and not a substring test because 'QB' sits
# inside strings like 'QB/WR' that are genuinely ambiguous and must not be
# read as either one.
KNOWN_NON_QB_POSITIONS = frozenset({
    'RB', 'FB', 'F', 'HB', 'WR', 'TE',
    'OL', 'OT', 'OG', 'G', 'C', 'T',
    'DL', 'DE', 'DT', 'NT', 'EDGE',
    'LB', 'ILB', 'MLB', 'OLB',
    'CB', 'S', 'SS', 'FS', 'DB',
    'K', 'P', 'LS',
})

UNRESOLVED_CLASSES = ('EXPLICIT_NON_QB', 'EXPLICIT_QB', 'UNKNOWN_POSITION',
                      'AMBIGUOUS_POSITION')


def classify_unresolved_position(pos) -> str:
    """One unresolved official name -> may it touch the quarterback room?

    EXPLICIT_NON_QB    the source named a position, and it is not a QB one
    EXPLICIT_QB        the source named QB
    UNKNOWN_POSITION   no position, or one this vocabulary does not know
    AMBIGUOUS_POSITION more than one position, e.g. 'QB/WR'

    Only EXPLICIT_NON_QB clears. The other three fail closed, because "we do
    not know what he plays" and "he plays quarterback" have the same
    consequence for a quarterback-room claim.
    """
    if pos is None:
        return 'UNKNOWN_POSITION'
    s = str(pos).strip().upper()
    if not s:
        return 'UNKNOWN_POSITION'
    if any(ch in s for ch in '/,|&+') or len(s.split()) > 1:
        return 'AMBIGUOUS_POSITION'
    if s in QB_POSITION_TOKENS:
        return 'EXPLICIT_QB'
    if s in KNOWN_NON_QB_POSITIONS:
        return 'EXPLICIT_NON_QB'
    return 'UNKNOWN_POSITION'


def unresolved_qb_room_risk(provenance) -> dict:
    """Do any unresolved official names put the QB room in doubt?

    Reads `unmapped_detail` -- a list of {name, team, source_position} kept by
    the ingestion artifact. When the artifact records unresolved names but no
    per-name detail, every one of them is UNKNOWN_POSITION and enforcement
    fails closed: an older artifact that cannot answer the question is not an
    artifact that answers it favourably.
    """
    prov = dict(provenance or {})
    n_unmapped = prov.get('n_unmapped')
    detail = prov.get('unmapped_detail')
    if n_unmapped in (None, 0) and not detail:
        return {'blocks_qb_enforcement': n_unmapped is None,
                'n_unresolved': 0 if n_unmapped == 0 else None,
                'blocking': [], 'cleared': [],
                'reason': ('no unresolved official name' if n_unmapped == 0
                           else 'the artifact does not report whether any '
                                'official name went unresolved')}
    if detail is None:
        names = list(prov.get('unmapped') or [])
        detail = [{'name': n, 'source_position': None} for n in names] or             [{'name': None, 'source_position': None}] * int(n_unmapped or 0)
    blocking, cleared = [], []
    for e in detail:
        cls = classify_unresolved_position(
            (e or {}).get('source_position'))
        row = {'name': (e or {}).get('name'), 'team': (e or {}).get('team'),
               'source_position': (e or {}).get('source_position'),
               'classification': cls}
        (cleared if cls == 'EXPLICIT_NON_QB' else blocking).append(row)
    return {
        'blocks_qb_enforcement': bool(blocking),
        'n_unresolved': len(detail),
        'blocking': blocking, 'cleared': cleared,
        'reason': ('every unresolved official name is explicitly a non-QB '
                   'position and cannot touch the quarterback room'
                   if not blocking else
                   f'{len(blocking)} unresolved official name(s) could affect '
                   f'the quarterback room'),
        'position_used_only_for': ('deciding whether an unresolved name can '
                                   'affect the QB room. It never resolves an '
                                   'identity and never satisfies non-QB '
                                   'completeness.'),
    }


# The six conditions, named, so a reader can see WHICH one failed rather than
# only that something did. Owner ruling 2026-09-13.
OWNERSHIP_CONDITIONS = (
    'official_inactive_evidence_ingested',
    'evidence_tied_to_this_game_and_team',
    'all_resolved_inactive_qbs_excluded',
    'no_unresolved_identity',
    'allocation_passes_accounting',
    'forecast_generated_after_enforcement',
)


def ownership_verdict(teams, out, inact, zeroed, closure_dev,
                      provenance=None) -> dict:
    """May this allocation claim `qb_inactive_ownership_enforced`?

    THE FLAG THIS REPLACES HAD NO WRITER. `qb_inactive_ownership_enforced` was
    READ in nfl/product/daily_board.py and SET NOWHERE in the repository, so
    QB_INACTIVE_NOT_CONSUMED could never clear on any board -- before or after
    consuming an official list. Measured 2026-09-13: New Orleans consumed the
    league's list, Zach Wilson's projection went to exactly zero, his share
    redistributed, and every row still carried the contamination flag.

    The answer is a governed STATE, not a suppression. All six conditions must
    hold and each is recorded with what it was judged on, so "true" is always
    auditable and "false" always names the reason. Nothing here can be set by a
    caller: the verdict is computed from the allocation that just ran.

    CONSERVATIVE ON IDENTITY, DELIBERATELY. An official name that resolved to
    no rostered player might be a quarterback this roster vintage does not
    carry. We cannot tell from a name alone, so an unresolved name refuses
    enforcement for that game rather than being assumed harmless. Reported,
    never guessed.
    """
    prov = dict(provenance or {})
    c = {}
    # READ FROM THE PROVENANCE ONLY, AND THIS IS A TIGHTENING.
    #
    # It previously read `bool(inact) or bool(post_inactives_complete)`, so a
    # caller who merely PASSED an inactive id satisfied it without any record
    # that the list had been ingested. That masked a real defect on
    # 2026-09-13: all four afternoon boards asserted
    # `official_inactive_evidence_ingested: true` while their provenance block
    # said `no INACTIVES_INGESTION.json for this game`. The condition is about
    # EVIDENCE, and an argument is not evidence of its own provenance.
    c['official_inactive_evidence_ingested'] = bool(
        prov.get('post_inactives_complete'))
    c['evidence_tied_to_this_game_and_team'] = bool(
        prov.get('game_id') and prov.get('teams')
        and set(teams) <= set(prov.get('teams') or ()))
    in_room = {t: [p for p in v['pids'] if p in inact] for t, v in out.items()}
    excluded = {t: sorted(zeroed.get(t, [])) for t in out}
    c['all_resolved_inactive_qbs_excluded'] = all(
        sorted(in_room[t]) == excluded[t] for t in out)
    n_unmapped = prov.get('n_unmapped')
    # NARROWED 2026-09-13 BY OWNER RULING, AND NARROWED IN ONE DIRECTION ONLY.
    # The condition is about identities that could affect the QUARTERBACK
    # ROOM, not about every unresolved name on the official list. An
    # unresolved name the source explicitly calls a non-QB position cannot
    # hold a dropback; an unresolved QB, or one whose position is missing,
    # unknown or ambiguous, still refuses.
    risk = unresolved_qb_room_risk(prov)
    c['no_unresolved_identity'] = not risk['blocks_qb_enforcement']
    c['allocation_passes_accounting'] = bool(
        out) and float(closure_dev) <= 1e-6
    # The enforcement ran inside THIS allocation, so any forecast built from
    # its value is built after it by construction. It is stated rather than
    # assumed because a later reader cannot re-derive it from the board alone.
    c['forecast_generated_after_enforcement'] = True
    enforced = all(c[k] for k in OWNERSHIP_CONDITIONS)
    return {
        'enforced': enforced,
        'conditions': {k: bool(c[k]) for k in OWNERSHIP_CONDITIONS},
        'failed_conditions': [k for k in OWNERSHIP_CONDITIONS if not c[k]],
        'inactive_qbs_in_modelled_room': {t: sorted(v) for t, v in
                                          in_room.items() if v},
        'inactive_qbs_excluded': {t: v for t, v in excluded.items() if v},
        'n_unmapped_official_names': n_unmapped,
        'unmapped_official_names': prov.get('unmapped'),
        'unresolved_qb_room_risk': risk,
        'closure_max_dev': float(closure_dev),
        'game_id': prov.get('game_id'),
        'spec_version': SPEC_VERSION,
        'what_true_means': (
            'the official list for BOTH clubs was ingested and tied to this '
            'game, every officially inactive quarterback the model carries was '
            'excluded from the allocation BEFORE the draw, no official name '
            'went unresolved, the shares close, and the forecast was built '
            'from this allocation.'),
        'what_true_does_not_mean': (
            'it does not mean no quarterback is inactive, and it does not '
            'mean the projection is right. It means the inactive evidence was '
            'consumed by the mechanism that owns the share.'),
    }


# THE V2 ALLOCATOR IS AVAILABLE HERE AND IS OFF BY DEFAULT.
#
# `qb_room_v2` replaces the mechanism that put a 0.412 zero-dropback mass on
# Patrick Mahomes on the sealed DEN@KC board (see nfl/research/v2/r1/). It is
# reachable from this function by ONE argument and nothing else changes: with
# `allocator='qb3'` the code below is the code that ran before, argument for
# argument, and the suite asserts the output is bit-identical.
#
# IT IS OFF BECAUSE OF WHAT IT NEEDS, NOT BECAUSE OF WHAT IT IS. V2's estimand
# is an INTEGER DROPBACK COUNT, so it needs the team's dropback draws, and this
# function is called before team volume is drawn. Turning it on therefore
# requires the caller to pass `team_dropback_draws`, which today only
# `football_engine` holds -- and that file belongs to another workstream. The
# flag exists so integration is a flag flip and a plumbing change rather than a
# rewrite, and so that leaving it off is a visible decision rather than an
# absence.
# `qb_room_v2_sem` is QBSEM: the same room with P(relieves | not starter)
# conditioned on the starter cell. It is a SEPARATE NAME rather than a flag
# so that `_qb_allocator`, which production reads back from the value that
# was actually passed, names the mechanism that ran. It was missing from
# this tuple on the first GSVUQ run and the pipeline refused the whole board
# with QB_ALLOCATOR_UNKNOWN -- the guard doing exactly its job.
ALLOCATORS = ('qb3', 'qb_room_v2', 'qb_room_v2_sem')
V2_ALLOCATORS = ('qb_room_v2', 'qb_room_v2_sem')


def allocate(season, week, teams, qb_players, m=200, seed=20260908,
             kickoff_utc=None, written_at=None, inactive_ids=None,
             inactive_provenance=None, allocator='qb3',
             team_dropback_draws=None) -> Outcome:
    """team -> (pids, shares (n_qb, m)). Shares sum to 1 in every draw.

    OFFICIALLY INACTIVE QUARTERBACKS OWN NOTHING, AND THIS IS WHERE THAT IS
    ENFORCED.

    `official_inactive_ids` used to reach the non-QB engine only
    (run_forecast.py:713). The QB path never saw it, so on the sealed SF@LA
    board Kurtis Rourke held 0.90 dropbacks and Ty Simpson 0.73 while both
    were on the league's inactive list -- about 2.5% of each team's dropbacks
    allocated to quarterbacks who were not dressed, and not redistributed to
    the men who actually played.

    The repair is here rather than downstream because this is the earliest
    causal point: the share is the thing that is wrong. Zeroing the inactive
    rows and renormalising the remainder leaves R2's largest-remainder
    apportionment completely untouched -- it simply receives the correct pool.
    A downstream subtraction would have been a second mechanism papering over
    the first.
    """
    if allocator not in ALLOCATORS:
        return Outcome.fail(
            'QB_ALLOCATOR_UNKNOWN',
            f'{allocator!r} is not one of {ALLOCATORS}. An unknown allocator '
            f'is refused rather than silently falling back to the default.')
    if allocator in V2_ALLOCATORS and not team_dropback_draws:
        return Outcome.blocked(
            'QB_ROOM_V2_NEEDS_TEAM_DROPBACKS',
            'qb_room_v2 allocates INTEGER dropback counts, so it needs the '
            'team dropback draws. They were not supplied. Refusing rather '
            'than allocating a share it cannot make integral.',
            cause=Cause.DEPENDENCY)
    f = _fit_for(season)
    if f is None:
        return Outcome.blocked(
            'QB_ALLOCATION_NOT_FITTED',
            f'no cell could be fitted on seasons before {season}',
            cause=Cause.DATA)
    par, _frame = f
    # THE CUT REACHES THE SELECTOR, not just the guard below.
    #
    # Previously the selector had no clock and the guard caught the result
    # after the fact -- which turns a recoverable situation into a refusal
    # whenever a lawful older capture exists. Passing the tighter of the two
    # bounds lets the selector pick that capture, and leaves the guard as the
    # backstop it should be rather than the only line of defence.
    _bounds = [b for b in (written_at, kickoff_utc) if b]
    _cut = min(_bounds, key=lambda b: (VS.parse_ts(b) or dt_max())) \
        if _bounds else None
    dc = captured_depth_chart(as_of=_cut)
    if dc.state is not State.PASS:
        return dc
    got = dc.evidence.get('retrieved_at')
    for label, bound in (('kickoff', kickoff_utc), ('written_at', written_at)):
        if bound and got and str(got) >= str(bound):
            return Outcome.fail(
                'DEPTH_CHART_CHRONOLOGY_FAILURE',
                f'the depth chart was retrieved at {got}, which is not '
                f'strictly before {label} {bound}')
    import qb3_lib as Q
    prev_detail = previous_primary_detail(season, week)
    prev = {k: v.get('pid') for k, v in prev_detail.items()}
    # THE FRESHNESS VERDICT TRAVELS WITH THE ALLOCATION. Recorded, never
    # swallowed: a stale panel produces a board whose every room is a
    # season-opener room, and before this the artifact said nothing about it.
    _fresh = panel_freshness(season, week)
    _fresh_ev = {'state': _fresh.state.value, 'code': _fresh.code,
                 'detail': _fresh.detail,
                 **{k: v for k, v in _fresh.evidence.items() if k != 'value'}}
    qb3_cfg = {}
    by_team = collections.defaultdict(list)
    for q in qb_players:
        if q.get('gsis_id'):
            by_team[q.get('team')].append(q['gsis_id'])
    inact = set(inactive_ids or ())
    zeroed = {}
    cell_relief_ev = {}
    out, ev = {}, {'teams_without_a_depth_chart': [],
                   'n_qb_by_team': {}, 'unranked_players': 0}
    for t in teams:
        room = dc.value.get(t) or {}
        pids = by_team.get(t, [])
        if not room:
            ev['teams_without_a_depth_chart'].append(t)
        # A ROSTERED QB WITH NO DEPTH RANK IS RANKED LAST, NOT DROPPED. Dropping
        # him would quietly shrink the room; ranking him last says what we know.
        trip = []
        for pid in pids:
            r = room.get(pid)
            if r is None:
                ev['unranked_players'] += 1
                r = 3
            trip.append((pid, min(int(r), 3), int(prev.get(t) == pid)))
        if not trip:
            continue
        pid_list = [x[0] for x in trip]
        mask = np.array([p in inact for p in pid_list]) if inact \
            else np.zeros(len(pid_list), bool)
        if mask.all() and len(pid_list):
            return Outcome.fail(
                'QB_ALLOCATION_ALL_QUARTERBACKS_INACTIVE',
                f'{t}: every rostered quarterback is on the official '
                f'inactive list, so there is nobody to receive the '
                f'team dropback share. Refusing rather than dividing '
                f'by zero or leaving the share with a player who is '
                f'not dressed.',
                team=t, n_qb=len(pid_list))
        # ELIGIBILITY CONDITIONS THE DRAW. IT DOES NOT EDIT ITS RESULT.
        #
        # MEASURED 2026-09-13, ON THE FIRST SUNDAY THIS PATH CARRIED A REAL
        # INACTIVE LIST. The previous wiring drew the room UNCONDITIONED, then
        # zeroed the inactive rows and renormalised what was left. That cannot
        # work, and not at the margin: `Q.allocate` samples the primary's share
        # from an empirical pool whose modal value is exactly 1.0 -- 77.7% of
        # the (rank 1, previous primary) pool and 44.2% of (rank 1, not
        # previous primary). Those draws are ONE-HOT. If the drawn primary is
        # the inactive quarterback, zeroing his row leaves the column at
        # exactly zero and the renormalisation is 0/0.
        #
        # Indianapolis measured 20.8% of draws in that state with Riley Leonard
        # inactive, so the refusal was certain. New Orleans measured 0.0% with
        # Zach Wilson inactive AT THIS SEED and would have refused on 13 of 40
        # seeds -- the board that survived did so by luck, which is the part
        # worth saying out loud.
        #
        # THIS IS A WIRING REPAIR, NOT A NEW MODEL. `p_primary` is the
        # probability that a quarterback is the game's primary passer. A player
        # who is not dressed cannot be the primary passer, so that probability
        # is zero by the definition of the event rather than by any modelling
        # choice -- the old code asserted exactly that, it just asserted it
        # after sampling, where it is arithmetically undefined. Restricting a
        # categorical to a subset of its support IS conditioning it: no
        # parameter is refit, no coefficient is added, no distributional family
        # changes, and the primary's empirical share pool is untouched.
        #
        # PARITY IS STRUCTURAL. With no inactive quarterback the eligible room
        # IS the room, the same call is made with the same arguments, and the
        # output is bit-identical. The suite asserts it.
        elig = [x for x in trip if not (inact and x[0] in inact)]
        if allocator in V2_ALLOCATORS:
            # QBSEM IS ITS OWN ALLOCATOR NAME, not a flag on the old one, so
            # `_qb_allocator` -- which production reads back from the value
            # actually passed -- names the mechanism that ran.
            S_e, _cr = _v2_shares(season, week, t, elig, prev_detail.get(t), m,
                                  seed, team_dropback_draws,
                                  cell_relief=(allocator == 'qb_room_v2_sem'))
            if _cr is not None:
                cell_relief_ev[t] = _cr
        else:
            S_e = Q.allocate(par, elig, m=m, seed=seed,
                             ordinal=season * 100 + week, team=t)
        if mask.any():
            pos = {pid: i for i, (pid, _, _) in enumerate(trip)}
            S = np.zeros((len(trip), m))
            for j, (pid, _, _) in enumerate(elig):
                S[pos[pid], :] = S_e[j, :]
            zeroed.setdefault(t, []).extend(
                [p for p, mk in zip(pid_list, mask) if mk])
            # RETAINED, AND MEANT TO BE UNREACHABLE. A guard removed once it
            # stops firing cannot tell you when the thing it guarded against
            # comes back.
            col = S.sum(0)
            if float(np.min(col)) <= 0.0:
                return Outcome.fail(
                    'QB_ALLOCATION_ZERO_ACTIVE_SHARE',
                    f'{t}: after conditioning on the officially eligible '
                    f'quarterback room at least one draw still has no share. '
                    f'Allocated mass may never be dropped.',
                    team=t)
        else:
            S = S_e
        out[t] = {'pids': pid_list, 'shares': S,
                  'ranks': [x[1] for x in trip],
                  'was_prev_primary': [x[2] for x in trip]}
        qb3_cfg[t] = qb3_configuration(trip, prev_detail.get(t),
                                       season=season, week=week)
        ev['n_qb_by_team'][t] = len(trip)
    if not out:
        return Outcome.fail(
            'QB_ALLOCATION_EMPTY',
            'no team received a quarterback allocation; an empty allocation '
            'is not an allocation')
    worst = max(float(np.abs(v['shares'].sum(0) - 1.0).max())
                for v in out.values())
    if worst > 1e-6:
        return Outcome.fail(
            'QB_ALLOCATION_DOES_NOT_CLOSE',
            f'the shares of some team do not sum to 1 (worst {worst:.2e}). '
            f'Closure is the property this layer exists for.')
    own = ownership_verdict(teams, out, inact, zeroed, worst,
                            inactive_provenance)
    return Outcome.ok('QB_ALLOCATION_OK', value=out,
                      spec_version=SPEC_VERSION, governance=GOVERNANCE,
                      allocator=allocator,
                      qb_inactive_ownership_enforced=own['enforced'],
                      qb_inactive_ownership=own,
                      qb3_configuration=qb3_cfg,
                      panel_freshness=_fresh_ev,
                      # QBSEM: the rates that RAN and the sparse-cell
                      # fallbacks, per team. Empty on every other allocator.
                      cell_relief=cell_relief_ev or None,
                      n_inactive_qb_zeroed=sum(len(v) for v in zeroed.values()),
                      inactive_qb_zeroed=zeroed,
                      n_teams=len(out), closure_max_dev=worst,
                      depth_chart_blob=dc.evidence['blob'],
                      depth_chart_retrieved_at=got,
                      cells_fitted=len(par['n']),
                      trained_on_seasons_before=season,
                      warnings=[f'known limitation: {k}'
                                for k in KNOWN_LIMITATIONS])


def _v2_shares(season, week, team, elig, prev_detail, m, seed, tdb,
               cell_relief=False):
    """`qb_room_v2` counts, expressed as the share matrix this function returns.

    The division is by the SAME integer team total the counts were allocated
    from, so a caller that multiplies these shares by its own team dropback
    draws recovers the integer counts up to its own rounding -- and exactly,
    under R2's `rint` apportionment.
    """
    from nfl.production.nonqb import qb_room_v2 as V2
    import numpy as _np
    par = V2.fit_for_ordinal(season * 100 + week)
    room = [{'pid': p, 'rank': V2.rank_bucket(r), 'was_prev_primary': int(w)}
            for p, r, w in elig]
    V = _np.asarray(tdb[team] if isinstance(tdb, dict) else tdb, float)[:m]
    al = V2.allocate_dropbacks(par, room, V, seed=seed,
                               ordinal=season * 100 + week, team=team,
                               is_opener=bool((prev_detail or {}).get(
                                   'is_season_opener')),
                               cell_relief=bool(cell_relief))
    N = _np.maximum(al['team_dropbacks_int'], 1)
    # QBSEM's own evidence travels with the shares so the artifact can record
    # the rates that ran and the sparse-cell fallbacks, rather than the flag
    # that was requested.
    return al['db'] / N[None, :], al.get('cell_relief')
