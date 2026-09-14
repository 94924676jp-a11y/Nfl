"""The production/live pregame feature builder for the frozen Q9 candidate.

    python3.12 -m nfl.prospective.q9shadow.live_features --parity --season 2024

THIS IS NOT A RESEARCH REFIT. Nothing here fits a coefficient, and nothing
here touches the candidate. It answers exactly one question -- *what are this
player's 25 declared features, as of a stated instant before kickoff?* -- and
the answer must be the same one the historical builder would have produced.

HOW PARITY IS OBTAINED, AND WHY IT IS BY CONSTRUCTION RATHER THAN BY EFFORT

The obvious implementation is a second pipeline that recomputes trailing
target frequency, participation EWMA, share-given-positive, prior depth,
trailing snap share and role class for a live team-week. That is a
reimplementation, and a reimplementation drifts.

So this builder does not recompute any of them. It appends LIVE-SHAPED ROWS
to the historical panel -- one per player, carrying pregame inputs only and
`appeared`, `snap`, `targets` explicitly None -- and then runs the historical
builder's OWN attach functions over the union:

    Q6F.attach_role_class      trailing snap share, then depth rank
    AUD._own_history           trailing target share
    Q9.attach_hurdle_history   the four h_* features and prior_depth_bucket

Each walks in (season, week, team, player) order and reads STRICTLY EARLIER
rows, and each appends to its history only when `appeared` is truthy. A live
row therefore receives exactly the values the historical builder would have
given it, and contributes nothing to anyone else's history. The parity test
then proves that rather than assuming it.

THE ONE PLACE THE UNION IS NOT ENOUGH, AND IT IS A REAL DEFECT AVOIDED

`Q6F.attach_opportunity` assigns `targets = 0` with basis
`ZERO_BY_ABSENCE_FROM_PANEL` to any row with no panel entry. For a historical
row that is correct -- a player absent from the panel took no part. For an
UNPLAYED game it would fabricate a realised zero for a game that has not
happened, which is the absence-read-as-a-result defect this project pays for
most. Opportunity is therefore attached to the historical rows ONLY, and live
rows carry `opportunity_basis = 'UNPLAYED_NO_OPPORTUNITY'` with every realised
field None.

WHAT MAY AND MAY NOT BE READ

  MAY   depth-chart vintage (rank, position, team), selected point-in-time
        official injury feed (report_status, practice_status)
        the committed historical panel, seasons STRICTLY BEFORE the forecast
        season -- so no outcome of the live season enters at any point

  MAY NOT
        `weekly_rosters.status`, in any form. INA is game-day information:
        of 3,438 INA player-games, 0 recorded a snap. It is refused by name.
        any postgame roster state, any realised outcome of the live season,
        any market quantity.

Because the history window is `season' < season` and never `earlier weeks of
the same season`, NO outcome of the forecast season enters the features at
any point in that season. Combined with coefficients fitted the same way,
that makes the sealed artifact arm **A** under the artifact contract, not
arm B.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State    # noqa: E402
from nfl.production.nonqb import appearance_model as AM                # noqa: E402
from nfl.production.nonqb import appearance_r7 as R7                   # noqa: E402
from nfl.production.nonqb import depth_vintage as DV                   # noqa: E402
from nfl.prospective.q9shadow import candidate as CAND                 # noqa: E402
from nfl.prospective.q9shadow import inputs as IN                      # noqa: E402
from nfl.research.q6 import frame as Q6F                               # noqa: E402
from nfl.research.q8 import audit as AUD                               # noqa: E402
from nfl.research.q9 import hurdle as Q9                               # noqa: E402

SPEC_VERSION = 'q9-live-pregame-feature-builder-1'
HERE = _REPO / 'nfl' / 'prospective' / 'q9shadow'
VINTAGE = _REPO / 'nfl' / 'vintage'
PARITY_OUT = HERE / 'Q9_LIVE_FEATURE_PARITY.json'
MANIFEST = _REPO / 'nfl' / 'vintage_manifest.jsonl'

# The sources this builder may read, and the field each one supplies. A source
# absent from this table cannot be read at all: `assert_sources_permitted`
# refuses the bundle rather than ignoring the extra.
PERMITTED_SOURCES = {
    'depth_charts': ('rank', 'position', 'team'),
    'injuries': ('report_status', 'practice_status'),
    'official_injury_report': ('report_status', 'practice_status'),
    'historical_panel': ('appeared', 'snap', 'targets', 'share_targets'),
}

# Refused by name, with the measurement behind the refusal.
FORBIDDEN_SOURCES = {
    'weekly_rosters': (
        'weekly_rosters.status is game-day information: INA appears after the '
        'roster is submitted, and of 3,438 INA player-games 0 recorded a '
        'snap. It is on the frozen candidate\'s FORBIDDEN_INPUTS list and it '
        'may not enter a feature.'),
    'official_inactives': (
        'the inactive list is published inside 90 minutes of kickoff and is '
        'game-day state. It is an appearance-layer input under its own '
        'governance, never a stage-1 feature.'),
    'pbp': 'play-by-play is the outcome.',
    'player_stats': 'weekly player stats are the outcome.',
}

# Field names on a supplied player descriptor that would carry roster status.
ROSTER_STATUS_FIELDS = ('status', 'roster_status', 'game_status', 'inactive',
                        'is_inactive', 'ina', 'active')

# The realised fields a live row must carry as None. Listed so the guard
# cannot be satisfied by a row that simply omits them.
REALISED_FIELDS = ('appeared', 'snap', 'targets', 'carries', 'share_targets',
                   'share_carries', 'den_targets', 'den_carries')

UNPLAYED = 'UNPLAYED_NO_OPPORTUNITY'


def _sha(text):
    return hashlib.sha256(str(text).encode()).hexdigest()


# ------------------------------------------------------------- the guards
def assert_sources_permitted(sources) -> Outcome:
    """Every named source is on the permitted list, or the build refuses."""
    bad = []
    for s in sorted(set(sources)):
        low = str(s).lower()
        if low in FORBIDDEN_SOURCES:
            bad.append({'source': s, 'why': FORBIDDEN_SOURCES[low]})
        elif low not in PERMITTED_SOURCES:
            bad.append({'source': s,
                        'why': 'not on the permitted source table. A source '
                               'nobody declared cannot be audited.'})
    if bad:
        return Outcome.fail(
            'Q9_LIVE_SOURCE_NOT_PERMITTED',
            f'{len(bad)} source(s) refused: '
            + '; '.join(f'{b["source"]}: {b["why"][:90]}' for b in bad),
            offences=bad)
    return Outcome.ok('Q9_LIVE_SOURCES_PERMITTED', value=sorted(set(sources)))


def assert_no_roster_status(players) -> Outcome:
    """No supplied player descriptor may carry a roster-status field."""
    hits = []
    for q in players or []:
        for k in q:
            if str(k).lower() in ROSTER_STATUS_FIELDS:
                hits.append({'player': q.get('gsis_id'), 'field': k})
    if hits:
        return Outcome.fail(
            'Q9_LIVE_ROSTER_STATUS_SUPPLIED',
            f'{len(hits)} player descriptor field(s) carry roster status: '
            f'{hits[:5]}. {FORBIDDEN_SOURCES["weekly_rosters"]}',
            offences=hits)
    return Outcome.ok('Q9_LIVE_NO_ROSTER_STATUS', value=len(players or []))


def assert_no_live_outcome(rows, season) -> Outcome:
    """Every row of the forecast season must carry no realised value."""
    bad = []
    for r in rows:
        if int(r.get('s', 0)) < int(season):
            continue
        carried = [f for f in REALISED_FIELDS
                   if f not in r or r.get(f) is not None]
        if carried:
            bad.append({'pid': r.get('pid'), 'fields': carried})
    if bad:
        return Outcome.fail(
            'Q9_LIVE_ROW_CARRIES_AN_OUTCOME',
            f'{len(bad)} live row(s) carry or omit a realised field: '
            f'{bad[:3]}. Every realised field must be PRESENT and None -- '
            f'omitting it would let a later `.get` default it to zero, which '
            f'is how an unplayed game acquires a realised result.',
            offences=bad[:20], n=len(bad))
    return Outcome.ok('Q9_LIVE_ROWS_CARRY_NO_OUTCOME', value=len(rows))


def assert_feature_schema_matches_freeze() -> Outcome:
    """The 25-feature schema hash must equal the frozen candidate's."""
    live = _sha('|'.join(Q9.FEATURE_NAMES))[:16]
    fz = CAND.freeze_identity()
    want = (fz or {}).get('feature_schema_sha16')
    if want is None:
        return Outcome.blocked(
            'Q9_FREEZE_ARTIFACT_ABSENT',
            'no freeze artifact, so the feature schema cannot be checked '
            'against the one the candidate was frozen with.',
            cause=Cause.GOVERNANCE)
    if live != want:
        return Outcome.fail(
            'Q9_LIVE_FEATURE_SCHEMA_MISMATCH',
            f'the live builder would feed a {len(Q9.FEATURE_NAMES)}-feature '
            f'schema hashing {live}, and the candidate was frozen against '
            f'{want}. A builder that emits a different schema is building for '
            f'a different candidate.', live=live, frozen=want)
    return Outcome.ok(
        'Q9_LIVE_FEATURE_SCHEMA_MATCHES_FREEZE', value=live,
        detail=f'{len(Q9.FEATURE_NAMES)} features, schema {live}',
        n_features=len(Q9.FEATURE_NAMES))


# ------------------------------------------------------- the leakage audit
#
# EVERY FITTED OR HISTORICAL SOURCE THE LIVE PATH TOUCHES, CHECKED FOR A ROW
# FROM THE FORECAST SEASON.
#
# `assert_no_live_outcome` covers the rows this module BUILDS. It says nothing
# about the panels the upstream layers read, and those are where a 2026 result
# would actually enter: the appearance model fits on the R8 enriched frame,
# the team budget on the P4B denominator table, the receiving efficiency on
# the Q7 panel. If any carried a 2026 row, the sealed artifact would be arm B
# whatever it declared.
#
# Measured 2026-09-12 -- R8 frame 2020-2025, denominators 2020-2025, p_R8
# 2022-2025, Q7 receiving 2020-2025: zero 2026 rows anywhere. This function
# re-measures it rather than trusting that note.
LEAKAGE_SOURCES = ('r8_enriched_frame', 'budget_denominators',
                   'appearance_p_r8', 'q7_receiving_panel', 'q6_frame')


def leakage_audit(season=2026) -> Outcome:
    """Refuse if any upstream source carries a row from the forecast season."""
    season = int(season)

    # FAIL CLOSED, PER SOURCE. Each reader is called on its own so one
    # unavailable source cannot take the others down with it AND cannot be
    # skipped: a source that could not be inspected is recorded as
    # NOT_INSPECTABLE and refuses the audit. Absence of inspectable data is
    # not zero leakage -- it is an unanswered question, and this project's
    # rule is that an unanswered question is never a pass.
    def _r8():
        from nfl.production.nonqb import appearance_r8 as R8
        fr = R8.enriched_frame()
        if fr.state is not State.PASS:
            raise RuntimeError(f'enriched_frame {fr.code}')
        return [r['s'] for r in fr.value]

    def _q7():
        from nfl.research.q7 import panel as Q7P
        return [r['season'] for r in Q7P.load_recv()]

    readers = {
        'r8_enriched_frame': _r8,
        'budget_denominators': lambda: [r['season'] for r in AUD.load_denom()],
        'appearance_p_r8': lambda: [k[0] for k in AUD.load_p_r8()],
        'q7_receiving_panel': _q7,
        'q6_frame': lambda: [r['s'] for r in Q6F.load_frame()[0]],
    }
    missing = sorted(set(LEAKAGE_SOURCES) - set(readers))
    if missing:
        return Outcome.fail(
            'Q9_LEAKAGE_AUDIT_SOURCE_NOT_CHECKED',
            f'{missing} are declared upstream sources with no reader. An '
            f'unchecked source is not a clean one.', missing=missing)

    found, counts, uninspectable = {}, {}, {}
    for name, fn in readers.items():
        try:
            seasons = [int(y) for y in fn()]
        except BaseException as exc:                          # noqa: BLE001
            uninspectable[name] = f'{type(exc).__name__}: {exc}'[:200]
            counts[name] = {'inspectable': False,
                            'error': uninspectable[name],
                            'max_season_observed': None,
                            'n_rows': None, 'seasons': None,
                            'n_at_or_after_forecast_season': None}
            continue
        n = sum(1 for y in seasons if y >= season)
        counts[name] = {
            'inspectable': True,
            'n_rows': len(seasons),
            'seasons': sorted(set(seasons)),
            # THE EXACT MAXIMUM, not merely a count above the threshold. A
            # count of zero says nothing about how close the source is to the
            # line; the max says exactly where it stops.
            'max_season_observed': (max(seasons) if seasons else None),
            'min_season_observed': (min(seasons) if seasons else None),
            'n_at_or_after_forecast_season': n,
            'margin_seasons_below_forecast_season': (
                season - max(seasons) if seasons else None),
        }
        if n:
            found[name] = n
    if uninspectable:
        return Outcome.blocked(
            'Q9_LEAKAGE_AUDIT_SOURCE_NOT_INSPECTABLE',
            f'{sorted(uninspectable)} could not be read: {uninspectable}. The '
            f'audit fails closed: a source that cannot be inspected has not '
            f'been shown clean, and reading its absence as zero leakage is '
            f'exactly the absence-as-success defect this project pays for '
            f'most.',
            cause=Cause.DATA, uninspectable=uninspectable,
            inspected={k: v for k, v in counts.items() if v['inspectable']})
    empty = sorted(k for k, v in counts.items() if not v['n_rows'])
    if empty:
        return Outcome.blocked(
            'Q9_LEAKAGE_AUDIT_SOURCE_EMPTY',
            f'{empty} returned zero rows. An empty source cannot demonstrate '
            f'it carries no forecast-season row.', cause=Cause.DATA,
            empty=empty)
    if found:
        return Outcome.fail(
            'Q9_FORECAST_SEASON_ROW_IN_UPSTREAM_SOURCE',
            f'{found} carry rows from {season} or later. A fit or a history '
            f'feature built on them would consume an outcome of the season '
            f'being forecast, and the sealed artifact would be arm B whatever '
            f'it declared.', offences=found, detail_by_source=counts)
    maxes = {k: v['max_season_observed'] for k, v in counts.items()}
    return Outcome.ok(
        'Q9_NO_FORECAST_SEASON_ROW_IN_ANY_UPSTREAM_SOURCE',
        value=counts,
        detail=f'{len(counts)} upstream source(s) inspected, 0 rows from '
               f'{season} or later; max season observed per source '
               f'{maxes}',
        n_sources=len(counts), forecast_season=season,
        max_season_observed=maxes,
        overall_max_season_observed=max(maxes.values()),
        supports_arm='A')


# -------------------------------------------------------- input provenance
def source_provenance(sources, observed_before, kickoff_utc=None) -> Outcome:
    """Exact timestamp provenance for every source, or a named refusal.

    DELEGATED, AND THE FIRST VERSION SHOWS WHY. This parsed the capture
    manifest itself, required `value.retrieved_at`, and refused every build
    with Q9_LIVE_SOURCE_WITHOUT_PROVENANCE -- because all 128 PASS `injuries`
    captures carry `retrieved_at: null`. The clock is not missing: the capture
    id encodes it, and `nfl.research.shadow.information_set` already falls
    back to it and RECORDS which basis it used. A second copy of that logic
    was strictly worse than the one that exists.

    So selection, the fallback and the basis all come from that module. What
    is added here is the refusal: a source selected with NO usable clock at
    all, or with no blob behind its hash, does not enter a feature.
    """
    from nfl.research.shadow import information_set as ISET
    want = sorted(set(sources))
    feed = [s for s in want if s != 'historical_panel']
    out = {}
    if feed:
        try:
            iset = ISET.build(kickoff_utc or observed_before, sources=feed,
                              observed_before=observed_before)
        except ISET.InformationSetError as exc:
            return Outcome.blocked('Q9_LIVE_INFORMATION_SET_UNAVAILABLE',
                                   str(exc), cause=Cause.DATA)
        chosen = iset.get('sources') or {}
        absent = sorted(set(feed) - set(chosen))
        if absent:
            return Outcome.blocked(
                'Q9_LIVE_SOURCE_WITHOUT_PROVENANCE',
                f'{absent} have no capture observable before '
                f'{observed_before}. A feature built on bytes with no '
                f'retrieval clock cannot assert it existed before the '
                f'forecast, and a blank clock is not a small gap -- it is the '
                f'whole claim.', cause=Cause.DATA, missing=absent,
                observed_before=observed_before)
        for name, rec in sorted(chosen.items()):
            if not rec.get('sha256') or not rec.get('observed_at'):
                return Outcome.blocked(
                    'Q9_LIVE_SOURCE_WITHOUT_PROVENANCE',
                    f'{name} was selected with sha256={rec.get("sha256")!r} '
                    f'and observed_at={rec.get("observed_at")!r}. Both are '
                    f'required.', cause=Cause.DATA, source=name)
            out[name] = {
                'source': name, 'sha256': rec['sha256'],
                'retrieved_at': rec['observed_at'],
                # NAMED, NOT ASSUMED. `retrieved_at` means the manifest
                # recorded a retrieval clock; `capture_id` means it did not
                # and the capture instant was used instead. A reader never has
                # to guess which one a later check compared against.
                'retrieved_at_basis': rec.get('observed_basis'),
                'capture_id': rec.get('capture_id'),
                'blob': rec.get('blob'), 'blob_sha256': rec.get('blob_sha256'),
                'blob_is_derived': rec.get('blob_is_derived'),
                'hours_before_kickoff': rec.get('hours_before_kickoff'),
            }
    if 'historical_panel' in want:
        pth = Q6F.PANEL
        out['historical_panel'] = {
            'source': 'historical_panel',
            'sha256': hashlib.sha256(pth.read_bytes()).hexdigest(),
            # A COMMITTED ARTIFACT, NOT A FETCH. Its clock is the checkout it
            # is read from, recorded as that rather than as a fabricated
            # download time.
            'retrieved_at': observed_before,
            'retrieved_at_basis': 'COMMITTED_ARTIFACT_IN_THIS_CHECKOUT',
            'url': str(pth.relative_to(_REPO)),
            'n_bytes': pth.stat().st_size}
    return Outcome.ok(
        'Q9_LIVE_SOURCE_PROVENANCE_OK', value=out,
        detail=f'{len(out)} source(s), each with sha256 and a named retrieval '
               f'clock at or before {observed_before}',
        n_sources=len(out),
        bases=sorted({v.get('retrieved_at_basis') for v in out.values()}))


# --------------------------------------------------- the live slate inputs
def injury_rows(season, observed_before) -> Outcome:
    """The lawful injury vintage as feed rows, or a named refusal.

    THE SET IS NOT FILTERED TO WHAT LOOKS COMPLETE. Every row of the selected
    capture is returned, including rows whose `report_status` is unfilled, and
    the count of those is reported. Dropping them would turn an unfiled
    designation into an absent injury row, which `featurise` then reads as
    `inj_report_available = 0` -- a different claim, and a false one.
    """
    from nfl.research.shadow import information_set as ISET
    try:
        iset = ISET.build(observed_before, sources=['injuries'],
                          observed_before=observed_before)
    except ISET.InformationSetError as exc:
        return Outcome.blocked('Q9_LIVE_INJURY_VINTAGE_UNAVAILABLE', str(exc),
                               cause=Cause.DATA)
    rec = (iset.get('sources') or {}).get('injuries')
    if rec is None or not rec.get('blob'):
        return Outcome.blocked(
            'Q9_LIVE_INJURY_VINTAGE_UNAVAILABLE',
            f'no injuries capture with a stored blob is observable before '
            f'{observed_before}.', cause=Cause.DATA,
            absent=iset.get('absent'))
    path = _REPO / rec['blob']
    rows = []
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', newline='') as fh:
        for r in csv.DictReader(fh):
            try:
                if int(r.get('season') or -1) != int(season):
                    continue
            except (TypeError, ValueError):
                continue
            rows.append(r)
    if not rows:
        return Outcome.blocked(
            'Q9_LIVE_INJURY_VINTAGE_EMPTY_FOR_SEASON',
            f'{path.name} carries no row for {season}. An empty read is an '
            f'error, not a slate with no injuries.', cause=Cause.DATA,
            blob=rec['blob'])
    unfilled = sum(1 for r in rows if not (r.get('report_status') or '').strip())
    return Outcome.ok(
        'Q9_LIVE_INJURY_ROWS_OK', value=rows,
        detail=f'{len(rows)} row(s) for {season} from {path.name}; '
               f'{unfilled} carry no report_status',
        n_rows=len(rows), n_without_report_status=unfilled,
        sha256=rec['sha256'], retrieved_at=rec['observed_at'],
        retrieved_at_basis=rec.get('observed_basis'), blob=rec['blob'])


def player_set(season, week, team, observed_before) -> Outcome:
    """The RB/WR/TE pool for one team-week, from the depth-chart vintage.

    WEEKLY ROSTERS ARE NOT USED FOR THIS, ON PURPOSE. The roster file is where
    `status == INA` lives, and the safest way not to read a forbidden column
    is not to open the file. The depth chart supplies identity, position and
    rank, which is everything the feature schema needs.
    """
    cap = DV.captured([team], observed_before)
    if cap.state is not State.PASS:
        return cap
    out = []
    for pid, v in sorted(cap.value.items()):
        rank, pos = (v[0], v[1]) if isinstance(v, (tuple, list)) else (v, None)
        if R7._pos(pos) not in Q6F.POSITIONS:
            continue
        out.append({'gsis_id': pid, 'position': R7._pos(pos), 'team': team})
    if not out:
        return Outcome.blocked(
            'Q9_LIVE_EMPTY_PLAYER_SET',
            f'the depth-chart vintage lists no {"/".join(Q6F.POSITIONS)} for '
            f'{team} before {observed_before}. An empty pool is a refusal, '
            f'not an allocation over nobody.', cause=Cause.DATA, team=team)
    return Outcome.ok(
        'Q9_LIVE_PLAYER_SET_OK', value=out,
        detail=f'{team}: {len(out)} {"/".join(Q6F.POSITIONS)} from the depth '
               f'vintage',
        team=team, n_players=len(out),
        rank_by_pid={q['gsis_id']: (cap.value[q['gsis_id']][0]
                                    if isinstance(cap.value[q['gsis_id']],
                                                  (tuple, list))
                                    else cap.value[q['gsis_id']])
                     for q in out},
        depth_chosen=cap.evidence.get('chosen'))


def build_team_week(season, week, team, observed_before,
                    kickoff_utc=None) -> Outcome:
    """The whole live path for one team-week: pool, injuries, features."""
    ps = player_set(season, week, team, observed_before)
    if ps.state is not State.PASS:
        return ps
    ir = injury_rows(season, observed_before)
    if ir.state is not State.PASS:
        return ir
    b = build(season, week, ps.value, observed_before,
              kickoff_utc=kickoff_utc, injuries_rows=ir.value,
              rank_by_pid=ps.evidence['rank_by_pid'])
    if b.state is not State.PASS:
        return b
    ev = dict(b.evidence)
    ev.update({'team': team,
               'n_injury_rows': ir.evidence['n_rows'],
               'n_injury_rows_without_report_status':
                   ir.evidence['n_without_report_status'],
               'depth_chosen': ps.evidence.get('depth_chosen')})
    return Outcome.ok(b.code, value=b.value, detail=b.detail, **ev)


# --------------------------------------------------------- the build itself
# MEMOISED PER SEASON. The processed panel is a pure function of the committed
# frame and the season cut, and a live slate calls this once per TEAM-WEEK --
# 26 times for a 13-game Sunday. Recomputing `attach_opportunity` over 33,000
# rows each time made a slate take minutes for no reason.
#
# SAFE TO REUSE EVEN THOUGH THE ATTACH FUNCTIONS MUTATE. `attach_role_class`,
# `_own_history` and `attach_hurdle_history` recompute every field they set
# from strictly earlier rows, and a live row never enters anyone's history
# because `appeared` is None. So a second call over the same cached rows
# produces the same historical values it produced the first time.
_HIST = {}


def cache_clear():
    _HIST.clear()


def _historical(season):
    """The committed panel, processed exactly as the research path does.

    Restricted to seasons STRICTLY BEFORE `season`, so no outcome of the
    forecast season can enter a feature at any point in that season.
    """
    key = int(season)
    if key in _HIST:
        return _HIST[key]
    rows, ev = Q6F.load_frame()
    rows = [r for r in rows if r['s'] < key]
    if not rows:
        return None, ev
    rows, _ = Q6F.attach_opportunity(rows)
    _HIST[key] = (rows, ev)
    return _HIST[key]


def live_rows(season, week, players, rank_by_pid, inj):
    """One live-shaped row per player. Pregame inputs only, realised None."""
    out = []
    for q in players:
        pid = q.get('gsis_id')
        if not pid:
            raise ValueError(
                'Q9_LIVE_IDENTITY_UNRESOLVED: a player carries no gsis_id. '
                'Fuzzy name matching is forbidden here as it is everywhere '
                'else in this repository.')
        team = q.get('team')
        d = inj.get((int(season), int(week), team, pid))
        r = {'s': int(season), 'w': int(week), 't': team, 'pid': pid,
             'pos': R7._pos(q.get('position')),
             'rank': rank_by_pid.get(pid),
             'inj_status': d['report_status'] if d else None,
             'inj_practice': d['practice_status'] if d else None,
             'inj_available': 1 if d is not None else 0,
             'opportunity_basis': UNPLAYED,
             'is_live_row': True}
        for f in REALISED_FIELDS:
            r[f] = None
        out.append(r)
    return out


def build(season, week, players, observed_before, kickoff_utc=None,
          injuries_rows=None, rank_by_pid=None, sources=None) -> Outcome:
    """The 25 declared features for one live team-week, or a named refusal."""
    season, week = int(season), int(week)
    sources = sorted(set(sources or ('depth_charts', 'injuries',
                                     'historical_panel')))
    for g in (assert_sources_permitted(sources),
              assert_no_roster_status(players),
              assert_feature_schema_matches_freeze()):
        if g.state is not State.PASS:
            return g

    prov = source_provenance(sources, observed_before, kickoff_utc)
    if prov.state is not State.PASS:
        return prov

    # ---- depth rank, selected point-in-time by the production selector
    if rank_by_pid is None:
        teams = sorted({q.get('team') for q in players if q.get('team')})
        if not teams:
            return Outcome.fail('Q9_LIVE_NO_TEAMS',
                                'no player carries a team')
        clock = R7._parse(observed_before) or R7._parse(kickoff_utc)
        if clock is None:
            return Outcome.fail(
                'Q9_LIVE_NO_CLOCK',
                'neither observed_before nor kickoff_utc was supplied, so the '
                'depth chart could not be selected point-in-time and the '
                'newest capture would silently have been used')
        cap = DV.captured(teams, clock)
        if cap.state is not State.PASS:
            return cap
        rank_by_pid = {pid: v[0] for pid, v in cap.value.items()}

    # ---- the injury block
    if injuries_rows is None:
        return Outcome.blocked(
            'Q9_LIVE_INJURY_ROWS_NOT_SUPPLIED',
            'no injury feed rows were supplied. The three injury features are '
            'not optional and an absent report is not a healthy one: an '
            'unfiled designation may not be defaulted. This is the same '
            'refusal the appearance layer makes as INJURY_REPORT_INCOMPLETE.',
            cause=Cause.DATA)
    inj = AM.parse_injuries_rows(injuries_rows, season)

    hist, frame_ev = _historical(season)
    if not hist:
        return Outcome.blocked(
            'Q9_LIVE_NO_PRIOR_SEASON_PANEL',
            f'the committed panel holds no row before {season}, so no history '
            f'feature can be computed without reading the forecast season.',
            cause=Cause.DATA)

    try:
        live = live_rows(season, week, players, rank_by_pid, inj)
    except ValueError as exc:
        code, _, detail = str(exc).partition(': ')
        return Outcome.fail(code, detail)

    guard = assert_no_live_outcome(live, season)
    if guard.state is not State.PASS:
        return guard

    # ---- THE HISTORICAL BUILDER'S OWN FUNCTIONS, over the union.
    union = hist + live
    union = Q6F.attach_role_class(union)
    union = AUD._own_history(union)
    union = Q9.attach_hurdle_history(union)
    out = [r for r in union if r.get('is_live_row')]

    # The projection guard is preserved, not re-derived: the rows leave here
    # ready for `IN.project_feature_row`, and the featuriser still sees only
    # the ten keys it reads.
    pg = IN.assert_projection_excludes_outcomes()
    if pg.state is not State.PASS:
        return pg

    return Outcome.ok(
        'Q9_LIVE_FEATURE_ROWS_OK', value=out,
        detail=f'{len(out)} live row(s) for {season} week {week}; history '
               f'from {len({r["s"] for r in hist})} prior season(s)',
        spec_version=SPEC_VERSION,
        season=season, week=week, n_players=len(out),
        history_seasons=sorted({r['s'] for r in hist}),
        n_history_rows=len(hist),
        feature_schema_sha16=_sha('|'.join(Q9.FEATURE_NAMES))[:16],
        n_features=len(Q9.FEATURE_NAMES),
        source_provenance=prov.value,
        sources=sources,
        observed_before=observed_before,
        n_with_a_depth_rank=sum(1 for r in out if r['rank'] is not None),
        n_with_an_injury_row=sum(1 for r in out if r['inj_available']),
        frame_spec_version=frame_ev.get('spec_version'),
        no_forecast_season_outcome_consumed=True,
        arm='A',
        arm_reason=('history is restricted to seasons strictly before the '
                    'forecast season, so no outcome of the forecast season '
                    'enters a feature at any point in that season'))


# -------------------------------------------------------------- the parity
FEATURE_NAMES = Q9.FEATURE_NAMES


def _vector(r, budget_z=0.0):
    return Q9.featurise(IN.project_feature_row(r), budget_z)


# THE WINDOW IN WHICH THE TWO BUILDERS ARE BOTH DEFINED.
#
# MEASURED, AND IT IS WEEK 1. The historical builder's history window is every
# strictly earlier row in the panel, INCLUDING earlier weeks of the same
# season. The live builder's window is seasons strictly before the forecast
# season, because the owner's requirement is "no 2026 outcomes" and an earlier
# 2026 week is a 2026 outcome.
#
# At week 1 those two windows are the same set, and parity is exact. From week
# 2 they are different sets by construction, and the live builder is REQUIRED
# to be the smaller one. Measured over 2024 weeks 1-3, 96 team-games: 634 of
# 1,429 players differ, and every differing feature is one of the four history
# features.
#
# That is not a builder defect and it must not be repaired by widening the
# live window -- that would consume the forecast season's outcomes. It is a
# consequence of the rule, and the consequence is that a live feature vector
# at week 8 is built on prior seasons only. Whether that is the intended
# trade, or whether a frozen prequential rule admitting strictly-earlier 2026
# weeks is wanted instead, is an owner decision and is recorded as one rather
# than chosen here.
PARITY_WINDOW_WEEKS = (1,)

# THE FEATURES THE HISTORY WINDOW DRIVES, DERIVED FROM THE SCHEMA RATHER THAN
# TYPED. The first version typed nine names, misspelled one
# (`recent_participation_ewma_missing` for `recent_participation_missing`) and
# omitted the three `role_*` features -- so the containment check read False
# for a divergence that was in fact entirely inside the history block. The
# role class comes from TRAILING SNAP SHARE, which is history, and only falls
# back to the depth chart when no trail exists; it belongs here.
_HISTORY_PREFIXES = ('prior_', 'recent_participation', 'is_cold_start',
                     'role_')
HISTORY_FEATURES = tuple(
    n for n in Q9.FEATURE_NAMES
    if any(n.startswith(pfx) for pfx in _HISTORY_PREFIXES))

# The complement, asserted non-empty so the containment check cannot pass by
# every feature being called a history feature.
SOURCE_FEATURES = tuple(n for n in Q9.FEATURE_NAMES
                        if n not in HISTORY_FEATURES)


def parity(season=2024, n_team_games=12) -> dict:
    """The live builder against the historical builder, same inputs.

    THREE QUESTIONS, ASKED SEPARATELY, BECAUSE THEY HAVE DIFFERENT ANSWERS.

    BUILDER_PARITY   inside the window where both builders are defined --
                     week 1 -- and handed the SAME pregame inputs, does the
                     live builder produce the same 25 numbers? This is a
                     statement about code and it must be exact.
    WINDOW_DIVERGENCE outside that window, HOW does it differ and is the
                     difference confined to the history features? A
                     difference anywhere else would be a defect; a difference
                     confined to history is the no-outcome rule showing up
                     where it must.
    SOURCE_AGREEMENT does the live VINTAGE agree with what the historical
                     panel recorded for those same inputs? A statement about
                     DATA. Conflating it with the first would let a feed
                     difference be read as a builder defect or the reverse.
    """
    rows, _ = Q6F.load_frame()
    rows = [r for r in rows if r['s'] <= int(season)]
    rows, _ = Q6F.attach_opportunity(rows)
    rows = Q6F.attach_role_class(rows)
    rows = AUD._own_history(rows)
    rows = Q9.attach_hurdle_history(rows)
    by = collections.defaultdict(list)
    for r in rows:
        if r['s'] == int(season):
            by[(r['s'], r['w'], r['t'])].append(r)
    keys = sorted(by)[:n_team_games]

    # PLAYERS HOLDING TWO ROWS IN ONE WEEK ARE EXCLUDED, AND COUNTED.
    #
    # Measured, not assumed: the union frame carries a player under BOTH his
    # old and his new team in a transaction week -- 00-0035215 appears in 2024
    # week 1 as BAL and as BUF. `Q9.attach_hurdle_history` walks
    # (season, week, team, player) and appends to a player's history as soon
    # as it passes an appeared row, so the BAL row counts as prior history for
    # the BUF row IN THE SAME WEEK: 42 prior appeared games against 43.
    #
    # That is the frozen historical builder's behaviour. It is NOT repaired
    # here: `attach_hurdle_history` is inside the frozen candidate's hashed
    # module, so changing it would be a candidate mutation, which this task
    # forbids. It is recorded under `same_week_duplicate_players` instead.
    #
    # A live builder is defined per TEAM-GAME and is handed one team's
    # players, so it cannot reproduce a value that depends on the same
    # player's row for a DIFFERENT team in the same week. Those rows are
    # therefore outside "where both are defined", excluded by name, and
    # counted so the exclusion cannot hide a real mismatch.
    per_week = collections.defaultdict(collections.Counter)
    for r in rows:
        per_week[(r['s'], r['w'])][r['pid']] += 1
    dup = {(s_, w_, pid) for (s_, w_), c in per_week.items()
           for pid, n in c.items() if n > 1}

    compared = mismatched = excluded = 0
    mismatches, detail, dup_detail = [], [], []
    out_compared = out_differing = 0
    out_features = collections.Counter()
    for k in keys:
        g = by[k]
        s, w, t = k
        players = [{'gsis_id': r['pid'], 'position': r['pos'], 'team': t}
                   for r in g]
        rank_by_pid = {r['pid']: r.get('rank') for r in g}
        inj_rows = [{'season': s, 'week': w, 'team': t,
                     'gsis_id': r['pid'],
                     'report_status': r.get('inj_status') or '',
                     'practice_status': r.get('inj_practice') or ''}
                    for r in g if r.get('inj_available')]
        b = build(s, w, players, observed_before='2026-09-12T00:00:00Z',
                  injuries_rows=inj_rows, rank_by_pid=rank_by_pid,
                  sources=('depth_charts', 'injuries', 'historical_panel'))
        if b.state is not State.PASS:
            detail.append({'team_game': f'{s}-{w}-{t}',
                           'state': b.state.value, 'code': b.code,
                           'detail': (b.detail or '')[:200]})
            continue
        live_by = {r['pid']: r for r in b.value}
        diffs_here = 0
        for r in g:
            lr = live_by.get(r['pid'])
            if lr is None:
                continue
            if (r['s'], r['w'], r['pid']) in dup:
                excluded += 1
                if len(dup_detail) < 20:
                    dup_detail.append({
                        'team_game': f'{s}-{w}-{t}', 'pid': r['pid'],
                        'historical_h_appeared_games': r['h_appeared_games'],
                        'live_h_appeared_games': lr['h_appeared_games']})
                continue
            a, c = _vector(r), _vector(lr)
            diff_names = [FEATURE_NAMES[i] for i in range(len(a))
                          if a[i] != c[i]]
            if int(w) not in PARITY_WINDOW_WEEKS:
                # OUTSIDE THE WINDOW. Counted separately and never folded into
                # the parity number, because the two builders are reading
                # different history sets there by design.
                out_compared += 1
                if diff_names:
                    out_differing += 1
                    out_features.update(diff_names)
                continue
            compared += 1
            if diff_names:
                mismatched += 1
                diffs_here += 1
                if len(mismatches) < 20:
                    mismatches.append({
                        'team_game': f'{s}-{w}-{t}', 'pid': r['pid'],
                        'differing_features': [
                            {'feature': FEATURE_NAMES[i],
                             'historical': a[i], 'live': c[i]}
                            for i in range(len(a)) if a[i] != c[i]]})
        detail.append({'team_game': f'{s}-{w}-{t}', 'n_players': len(g),
                       'n_compared': len(live_by), 'n_differing': diffs_here})

    # SOURCE_AGREEMENT, measured against the live vintage where it exists.
    src = {'state': 'NOT_MEASURED'}
    teams = sorted({k[2] for k in keys})
    cap = DV.captured(teams, '2026-09-12T00:00:00Z')
    if cap.state is State.PASS:
        vint = {pid: v[0] for pid, v in cap.value.items()}
        panel = {r['pid']: r.get('rank') for k in keys for r in by[k]}
        both = [p for p in panel if p in vint]
        agree = sum(1 for p in both if panel[p] == vint[p])
        src = {'state': 'MEASURED', 'n_in_both': len(both),
               'n_agreeing': agree,
               'agreement_rate': (round(agree / len(both), 4)
                                  if both else None),
               'note': ('the 2026 depth vintage against a historical panel '
                        'rank is a DATA comparison across seasons and is '
                        'expected to disagree. It is reported so a feed '
                        'difference is never read as a builder defect.')}
    else:
        src = {'state': f'{cap.state.value}[{cap.code}]'}

    return {
        'artifact': 'NFL_Q9_LIVE_FEATURE_PARITY',
        'spec_version': SPEC_VERSION,
        'season': season, 'n_team_games': len(keys),
        'n_players_compared': compared,
        'n_players_differing': mismatched,
        'same_week_duplicate_players': {
            'n_excluded': excluded,
            'n_in_season': len({d for d in dup if d[0] == int(season)}),
            'why': ('the union frame carries a player under both teams in a '
                    'transaction week, and the frozen history walk counts the '
                    'first row as prior history for the second IN THE SAME '
                    'WEEK. A per-team-game live builder cannot see the other '
                    'team\'s row, so these are outside "where both are '
                    'defined".'),
            'not_repaired_because': (
                'attach_hurdle_history is inside the frozen candidate\'s '
                'hashed module; changing it would be a candidate mutation.'),
            'examples': dup_detail,
        },
        'builder_parity': ('EXACT' if compared and not mismatched
                           else 'NOT_EXACT' if compared else 'NOT_MEASURED'),
        'parity_window_weeks': list(PARITY_WINDOW_WEEKS),
        'window_divergence': {
            'n_compared_outside_window': out_compared,
            'n_differing_outside_window': out_differing,
            'differing_features': dict(out_features),
            'confined_to_history_features': bool(
                set(out_features) <= set(HISTORY_FEATURES)),
            'history_features': list(HISTORY_FEATURES),
            'non_history_features_that_differed': sorted(
                set(out_features) - set(HISTORY_FEATURES)),
            'containment_check_is_not_vacuous': bool(SOURCE_FEATURES),
            'n_non_history_features': len(SOURCE_FEATURES),
            'cause': ('the historical builder\'s history window includes '
                      'earlier weeks of the same season; the live builder\'s '
                      'is seasons strictly before the forecast season, '
                      'because an earlier week of the forecast season is an '
                      'outcome of the forecast season.'),
            'not_a_defect_because': (
                'the live window is the SMALLER one and is required to be. '
                'Widening it to obtain parity would consume the forecast '
                'season\'s outcomes, which this task forbids.'),
            'decided_by': 'OWNER',
            'open_owner_decision': (
                'prior-seasons-only all season (arm A, features go stale as '
                'the season progresses) versus a frozen prequential rule '
                'admitting strictly-earlier weeks of the forecast season '
                '(arm B, parity at every week). Implemented as arm A per the '
                'directive; recorded as a decision rather than chosen here.'),
        },
        'feature_schema_sha16': _sha('|'.join(FEATURE_NAMES))[:16],
        'n_features': len(FEATURE_NAMES),
        'mismatches': mismatches,
        'team_games': detail,
        'source_agreement': src,
        'what_is_claimed': (
            'given the SAME pregame inputs, the live builder reproduces the '
            'historical builder exactly. That is a statement about code. '
            'Whether the live feed agrees with the panel is a separate, '
            'measured question reported under source_agreement.'),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--parity', action='store_true')
    ap.add_argument('--season', type=int, default=2024)
    ap.add_argument('--team-games', type=int, default=12)
    a = ap.parse_args(argv)
    print(assert_feature_schema_matches_freeze())
    if a.parity:
        out = parity(a.season, a.team_games)
        PARITY_OUT.write_text(json.dumps(out, indent=1, default=str) + '\n')
        print(f"written         : {PARITY_OUT}")
        print(f"team-games      : {out['n_team_games']}")
        print(f"players compared: {out['n_players_compared']}")
        print(f"differing       : {out['n_players_differing']}")
        print(f"excluded (dup)  : "
              f"{out['same_week_duplicate_players']['n_excluded']}")
        wd = out['window_divergence']
        print(f"outside window  : {wd['n_differing_outside_window']} of "
              f"{wd['n_compared_outside_window']} differ; confined to "
              f"history features: {wd['confined_to_history_features']}")
        print(f"builder parity  : {out['builder_parity']}")
        print(f"source agreement: {out['source_agreement']}")
        for m in out['mismatches'][:3]:
            print(f"  {m['team_game']} {m['pid']}: "
                  f"{m['differing_features'][:3]}")
        return 0 if out['builder_parity'] == 'EXACT' else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
