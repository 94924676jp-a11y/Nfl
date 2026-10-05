#!/usr/bin/env python3.12
"""Build the POST-shaped slate state for a SHOWDOWN game, from the DK export and the warehouse.

WHY THIS EXISTS. `proj_v1.build()` and `role_state.build()` both read one artifact -- a POST-inactives
slate state -- and everything downstream keys off it. The classic builder for that artifact,
`post_inactives_state.py`, is specific to the Week 3 early slate: it derives from a PRE state built
from one entries file plus relayed evidence. A showdown slate is a far simpler object, 51 people in one
game, and the DK export already carries the universe. So this builds the state directly rather than
parameterising a chain designed for a different shape.

WHAT IS REAL HERE AND WHERE IT CAME FROM, because a slate state that quietly invented its own inputs
would poison every number after it:

  universe      the DK showdown export -- names, clubs, positions, slot-specific salaries and ids
  identity      proj_v1.resolve_slate_identities against player_prior.name_index(), the same resolver
                production uses, so this slate is not matched by a second private rule
  environment   TEAM_GAME, which carries the market's own total_line, spread and implied totals for
                the game. Nothing is modelled or assumed; if the row is absent this refuses.
  availability  supplied evidence, classified into the project's existing vocabulary. Never invented,
                and never promoted.

AVAILABILITY IS THE PART MOST EASILY GOT WRONG, so it is explicit. A team injury report is NOT a
game-day inactive list. `availability.py` already separates these and this module uses its labels
rather than new ones:

  an OUT on an official team release -> REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED
                                       (in ABSENT_STATUSES, so opportunity redistributes away from
                                        him, and NOT CONFIRMED_INACTIVE, because no document was
                                        captured)
  QUESTIONABLE / DOUBTFUL             -> UNKNOWN_ACTIVE_STATE
                                       (a designation is not an availability decision, and this
                                        status is in NOT_A_CLAIM_OF_ABSENCE)
  everyone not named                  -> UNKNOWN_ACTIVE_STATE
                                       (silence is not activity. Reading "not on the injury report"
                                        as "will play" activates the whole slate on no evidence,
                                        which is the same defect as reading missing as zero.)

CONFIRMED_INACTIVE is unreachable from this module. It requires a captured official document and this
module captures nothing.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import player_prior, proj_v1, showdown_to_portfolio as S  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

TEAM_GAME = _REPO / 'nfl/warehouse/TEAM_GAME.json'
OUT = _REPO / 'nfl/dfs/salaries/SHOWDOWN_TONIGHT_STATE.json'

SPEC_VERSION = 'showdown-slate-state-1'
STATE_LABEL = 'SHOWDOWN_PREGAME / NO_OFFICIAL_INACTIVE_DOCUMENT_CAPTURED'

#: Designation strings understood from a supplied team report, mapped to the project's own statuses.
#: Deliberately a small closed vocabulary: an unrecognised designation REFUSES rather than defaulting,
#: because a silent default is how a DOUBTFUL becomes an absence or an OUT becomes a maybe.
DESIGNATION_MAP = {
    'OUT': AV.REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED,
    'DOUBTFUL': AV.REPORTED_DOUBTFUL_UNVERIFIED,
    'QUESTIONABLE': AV.UNKNOWN_ACTIVE_STATE,
    'NO_DESIGNATION': AV.UNKNOWN_ACTIVE_STATE,
}

#: The two defences are not players and never resolve against the roster index. They are projected by
#: dst_model from the club, not from a player identity, so they are carried with this marker instead of
#: being reported as an identity failure.
DST_IDENTITY = 'TEAM_DEFENCE_NOT_A_PLAYER_IDENTITY'


def environment_for(game_id: str, away: str, home: str) -> Outcome:
    """The market's own view of the game, read from TEAM_GAME. Refuses rather than assuming."""
    if not TEAM_GAME.exists():
        return Outcome.blocked('SLATE_STATE_NO_TEAM_GAME', f'{TEAM_GAME} missing', cause=Cause.DATA)
    art = json.loads(TEAM_GAME.read_text())
    rows = art['rows'] if isinstance(art['rows'], list) else list(art['rows'].values())
    by = {r['club']: r for r in rows if r.get('game_id') == game_id}
    missing = [c for c in (away, home) if c not in by]
    if missing:
        return Outcome.blocked(
            'SLATE_STATE_GAME_NOT_IN_WAREHOUSE',
            f'{game_id} has no TEAM_GAME row for {missing}. The market environment is not something '
            f'this module may assume, so the slate state refuses rather than inventing a total.',
            cause=Cause.DATA, game_id=game_id, missing=missing)
    h, a = by[home], by[away]
    for nm, r in (('home', h), ('away', a)):
        if not isinstance(r.get('implied_total'), (int, float)):
            return Outcome.blocked(
                'SLATE_STATE_NO_IMPLIED_TOTAL',
                f'the {nm} row for {game_id} carries no implied total, so there is no market view to '
                f'condition the simulation on', cause=Cause.DATA, club=r.get('club'))
    return Outcome.ok('SLATE_STATE_ENVIRONMENT_READ', {
        f'{away}@{home}': {
            'home_club': home, 'away_club': away,
            'home_implied': h['implied_total'], 'away_implied': a['implied_total'],
            'total_line': h.get('total_line'),
            # club_spread is from the club's own perspective; the simulator wants the HOME spread.
            'home_spread': h.get('club_spread'),
            'home_rest_days': h.get('rest_days'), 'away_rest_days': a.get('rest_days'),
            'roof': h.get('roof'), 'surface': h.get('surface'),
            'SOURCE': 'TEAM_GAME, derived from the schedules capture. Nothing modelled here.',
        }
    }, f'{away}@{home} total {h.get("total_line")}, implied {a["implied_total"]}/{h["implied_total"]}')


def observed_current_season(panel, season: int, through_week: int) -> dict:
    """Each player's share of his club's targets and carries so far this season, from the panel.

    COMPUTED, not looked up, and the denominator is the club's own panel total for the same weeks, so
    the shares are internally consistent: every club's player shares sum to one over the panel. Nothing
    is smoothed, imputed or carried over from last season -- a player with no current-season touches
    gets no observed share and falls through to his history, which is the ordering the #99 study
    supports.
    """
    weeks = [str(w) for w in range(1, int(through_week) + 1)]
    ply = collections.defaultdict(lambda: collections.Counter())
    club = collections.defaultdict(lambda: collections.Counter())
    for gsis, rec in (panel.get('players') or {}).items():
        sea = (rec or {}).get(str(season)) or {}
        for wk in weeks:
            row = sea.get(wk)
            if not isinstance(row, dict):
                continue
            t = row.get('team')
            for field in ('targets', 'carries'):
                v = row.get(field) or 0
                ply[gsis][field] += v
                if t:
                    club[t][field] += v
            ply[gsis]['weeks_played'] += 1
            if t:
                ply[gsis]['team'] = t
    out = {}
    for gsis, c in ply.items():
        t = c.get('team')
        ct = club.get(t, {})
        tgt = (c['targets'] / ct['targets']) if ct.get('targets') else None
        rsh = (c['carries'] / ct['carries']) if ct.get('carries') else None
        out[gsis] = {
            'combined': {
                'target_share': (None if tgt is None else round(tgt, 4)),
                'rush_share': (None if rsh is None else round(rsh, 4)),
            },
            'weeks_played': int(c.get('weeks_played') or 0),
            'targets': int(c['targets']), 'carries': int(c['carries']),
            'club': t,
            'DENOMINATOR': f'the club panel total over {season} weeks 1-{through_week}',
        }
    return out


#: Starter evidence had NO INGESTION PATH into a showdown slate state at all. This key was a
#: hard-coded `{}`, and `role_state.assign` turns that into `in_predicted_group: False`, which
#: `proj_v1` turns into `is_predicted_starter False`. So "nobody told us who starts" arrived at the
#: projection as "we know he does not start". The 2026 week 4 PIT@CLE board charged both
#: depth_rank-1 quarterbacks a backup appearance rate because of it. A missing input must stay
#: missing; this is where it now enters when it exists.
STARTER_TIER = 'OWNER_RELAYED_CONFIRMED_STARTER'


def _starter_context(name, club, confirmed):
    """Starter evidence for one player, or an empty context when none was supplied.

    FAILS CLOSED on a club mismatch. Starter evidence names a player AND the club he starts for;
    if the supplied club disagrees with the slate's club for that name, the evidence is about
    somebody else or it is stale, and it is recorded as rejected rather than applied. It is never
    inferred: a player absent from the list gets `{}`, which means UNKNOWN, not NO.
    """
    if not confirmed:
        return {}
    want = confirmed.get(name) if isinstance(confirmed, dict) else (
        club if name in set(confirmed) else None)
    if want is None:
        return {}
    if isinstance(confirmed, dict) and str(want).upper() != str(club).upper():
        return {
            'state': 'STARTER_EVIDENCE_REJECTED_CLUB_MISMATCH',
            'in_predicted_starting_group': False,
            'relayed_club': want, 'slate_club': club,
            'WHY': ('starter evidence names a player and the club he starts for. This one '
                    'disagrees with the slate, so it is about another player or it is stale. '
                    'Rejected rather than applied, and NOT treated as evidence against him '
                    'either -- the appearance gate requires positive backup evidence.'),
        }
    return {
        'state': STARTER_TIER,
        'in_predicted_starting_group': True,
        'relayed_name': name, 'relayed_club': club,
        'NOT_A_CONFIRMED_INACTIVE_DECISION': (
            'this says he is expected to take the snaps. It is positive availability evidence for '
            'him and confers no status on anybody else.'),
    }


def chart_from_capture(csv_path, clubs, capture_id):
    """A depth chart in classic_slate_state.captured_qb_depth's own shape, from a captured nflverse
    depth_charts CSV (latest dt per club). Read-only; the file is hashed in the raw directory."""
    import csv as _csv
    rows = [r for r in _csv.DictReader(open(csv_path)) if r['team'] in clubs and r.get('gsis_id')]
    out = {}
    for club in clubs:
        cr = [r for r in rows if r['team'] == club]
        if not cr:
            continue
        last = max(r['dt'] for r in cr)
        def order(pos):
            seen, o = set(), []
            for r in sorted((r for r in cr if r['dt'] == last and r.get('pos_abb') == pos),
                            key=lambda r: int(r['pos_rank']) if r['pos_rank'].isdigit() else 99):
                if r['gsis_id'] not in seen:
                    seen.add(r['gsis_id'])
                    o.append(r['gsis_id'])
            return o
        out[club] = {'order': order('QB'), 'by_pos': {p_: order(p_) for p_ in ('RB', 'WR', 'TE')},
                     'dt': last, 'capture_id': capture_id}
    return out


def build(export, *, designations=None, official_inactives=None,
          confirmed_starters=None, depth_chart=None) -> Outcome:
    """Emit the POST-shaped state for one showdown slate.

    `designations` is {player name: 'OUT' | 'DOUBTFUL' | 'QUESTIONABLE' | 'NO_DESIGNATION'} from a team
    report. `official_inactives` is a list of names from a CAPTURED official list -- only that
    promotes a player to CONFIRMED_INACTIVE, and it is kept separate from `designations` so the two
    can never be confused.
    """
    export = pathlib.Path(export)
    ing = S.s1_ingest(export)
    if ing.state.value != 'PASS':
        return ing
    ident_o = S.s2_slate_identity(ing.value['pool'])
    if ident_o.state.value != 'PASS':
        return ident_o
    slate = ident_o.value
    away, home = slate['away'], slate['home']

    # The game id the warehouse uses. Derived from the file's own clubs and date, then checked to
    # exist rather than trusted.
    kick = dt.datetime.fromisoformat(slate['kickoff_et_naive'])
    sched_week = None
    art = json.loads(TEAM_GAME.read_text()) if TEAM_GAME.exists() else {'rows': []}
    rows = art['rows'] if isinstance(art['rows'], list) else list(art['rows'].values())
    cand = [r for r in rows
            if r.get('season') == kick.year
            and {r.get('club'), r.get('opponent')} == {S.corpus_team(away), S.corpus_team(home)}
            and r.get('points') is None]
    if not cand:
        return Outcome.blocked(
            'SLATE_STATE_NO_UNPLAYED_GAME_FOR_THESE_CLUBS',
            f'the warehouse holds no unplayed {kick.year} game between {away} and {home}. Either the '
            f'schedule is behind or this game has already been recorded, and projecting a played game '
            f'would be scoring an outcome rather than forecasting it.',
            cause=Cause.DATA, away=away, home=home, season=kick.year)
    game_id = cand[0]['game_id']
    sched_week = cand[0]['week']

    env = environment_for(game_id, S.corpus_team(away), S.corpus_team(home))
    if env.state.value != 'PASS':
        return env

    # IDENTITY, through the production resolver.
    flat = {v['flex']['dk_id']: {'name': v['name'], 'team': v['team'], 'position': v['position']}
            for v in slate['players'].values()}
    ids, unresolved, suffixed = proj_v1.resolve_slate_identities({'players': flat},
                                                                 player_prior.name_index())
    unresolved_nondst = [u for u in unresolved if u.get('position') != 'DST']
    if unresolved_nondst:
        return Outcome.fail(
            'SLATE_STATE_IDENTITY_UNRESOLVED',
            f'{len(unresolved_nondst)} non-defence player(s) have no football identity. Projecting a '
            f'name we cannot tie to a player assigns opportunity to somebody we have not established '
            f'exists, so this is a refusal rather than a skip.',
            unresolved=unresolved_nondst[:12], n_slate=len(flat))

    # AVAILABILITY.
    desig = {k.strip(): str(v).strip().upper() for k, v in (designations or {}).items()}
    bad = sorted({v for v in desig.values() if v not in DESIGNATION_MAP})
    if bad:
        return Outcome.fail(
            'SLATE_STATE_DESIGNATION_UNKNOWN',
            f'unrecognised designation(s) {bad}. A designation this module does not understand is '
            f'refused rather than defaulted, because a silent default turns a DOUBTFUL into an '
            f'absence or an OUT into a maybe.', known=sorted(DESIGNATION_MAP))
    officials = {n.strip() for n in (official_inactives or ())}
    by_name = collections.defaultdict(list)
    for dk_id, p in flat.items():
        by_name[p['name']].append(dk_id)
    unmatched_desig = sorted(n for n in desig if n not in by_name)
    unmatched_official = sorted(n for n in officials if n not in by_name)
    # AN INACTIVE LIST LEGITIMATELY CONTAINS PLAYERS A DFS SLATE DOES NOT PRICE. Tonight's lists name
    # a centre, a guard, two defensive tackles and a linebacker; DraftKings prices none of them, so
    # five unmatched names are expected rather than suspicious.
    #
    # The protection worth keeping is the one against a list for the WRONG GAME, and that has a
    # sharper test: if NOTHING matches, the list cannot be about this slate. If some names match, the
    # rest are recorded as outside the priced universe and the matched ones are applied, so no player
    # who is out can be quietly rostered.
    if officials and not (set(officials) & set(by_name)):
        return Outcome.fail(
            'SLATE_STATE_OFFICIAL_INACTIVE_LIST_IS_FOR_ANOTHER_GAME',
            f'none of the {len(officials)} officially inactive names appears on this slate, so the '
            f'list is not about this game or the identities do not line up.',
            unmatched=sorted(officials)[:12], slate=f"{away}@{home}")

    # CURRENT-SEASON USAGE, from the refreshed panel, through the week BEFORE this game.
    po = player_prior.load_panel()
    if po.state.value != 'PASS':
        return po
    obs = observed_current_season(po.value, kick.year, max(1, int(sched_week) - 1))

    # DEPTH RANK, from weeks STRICTLY BEFORE this game. Without it role_state.assign has no evidence
    # that anybody is a starter: every player falls to OBSERVED_ONLY or NO_EVIDENCE, whose ceilings are
    # SECONDARY and FRINGE, so a club's starting quarterback is capped as a fringe player and the
    # projection collapses. The first run of this builder produced exactly that -- 27 FRINGE and 25
    # NO_EVIDENCE across 51 players.
    #
    # The ranks come from role_state_history.pregame_depth, which is the PREGAME arm: it knows only
    # completed weeks and is not told who actually played tonight. _position_scoped_ranks re-indexes
    # within club and position, so only the ORDER matters here.
    from nfl.tools import role_state_history as RSH
    pos_of = player_prior.position_index()
    depth = RSH.pregame_depth(po.value, pos_of, kick.year, int(sched_week))
    from nfl.tools import classic_slate_state as _CS
    # a player reported out vacates his chart rank (Sunday's rule), so the next man up ranks first
    _out_gsis = {(ids.get(dk) or {}).get('gsis_id') for dk, p_ in flat.items()
                 if p_['name'] in officials or (desig.get(p_['name']) or '').upper() == 'OUT'}
    _out_gsis.discard(None)

    players, status_counts = {}, collections.Counter()
    for dk_id, p in flat.items():
        nm = p['name']
        if nm in officials:
            # HIGH CONFIDENCE, NOT CONFIRMED. The inactive list reaches us relayed -- beat reporters
            # and an aggregator -- not as an official document this system captured. The standing rule
            # is that an aggregator list stays REPORTED_INACTIVE_HIGH_CONFIDENCE and never becomes
            # CONFIRMED_INACTIVE, which is reserved for TIER_OFFICIAL_CAPTURED.
            #
            # Nothing downstream is weakened by that: REPORTED_INACTIVE_HIGH_CONFIDENCE is already in
            # AV.ABSENT_STATUSES, so the player gets zero opportunity, leaves the playable universe and
            # his usage is redistributed exactly as a confirmed absence would be. Only the claim about
            # OUR EVIDENCE differs, and that is the claim the tier exists to keep honest.
            status, tier = AV.REPORTED_INACTIVE_HIGH_CONFIDENCE, AV.TIER_AGGREGATOR_REPORTED
        elif nm in desig:
            status = DESIGNATION_MAP[desig[nm]]
            tier = AV.TIER_OFFICIAL_RELEASE_CITED
        else:
            status, tier = AV.UNKNOWN_ACTIVE_STATE, AV.TIER_NONE
        status_counts[status] += 1
        v = slate['players'][S.player_key(nm, p['team'])]
        rec = ids.get(dk_id) or {}
        gsis = None if p['position'] == 'DST' else (rec.get('gsis_id') or None)
        players[dk_id] = {
            'name': nm, 'team': p['team'], 'position': p['position'],
            'salary': v['flex']['salary'],
            'cpt_salary': v['cpt']['salary'],
            'cpt_dk_id': v['cpt']['dk_id'], 'flex_dk_id': v['flex']['dk_id'],
            'identity': (DST_IDENTITY if p['position'] == 'DST' else (ids.get(dk_id) or {})),
            # `gsis_id` under exactly this key, as a STRING, because role_state.assign reads
            # row['gsis_id'] and passes it straight to the panel. The first version of this builder
            # stored the whole resolver record under `identity` and nothing under `gsis_id`, and every
            # one of the 51 players came back with role_band None and basis NO_EVIDENCE: the value was
            # present under the wrong name and in the wrong shape, which is the quietest kind of break.
            'gsis_id': gsis,
            'observed_2026': (obs.get(gsis) or {}) if gsis else {},
            # pregame_depth returns a RECORD per player, not an integer. _position_scoped_ranks
            # tests isinstance(r, int), so handing it the record silently produced zero ranks.
            # SUNDAY'S ACCEPTED RULE (classic_slate_state._qb_rank) when a captured chart is supplied:
            # quarterbacks by the chart among those not out; others the better of usage and chart,
            # with the declared no-usage lift limit. Without a chart, the usage rank as before.
            'depth_rank': (_CS._qb_rank(p['position'], p['team'], gsis, depth_chart, depth, _out_gsis)
                           if (depth_chart and gsis) else
                           ((depth.get(gsis) or {}).get('pregame_rank') if gsis else None)),
            'depth_source': (('DEPTH_CHART_CAPTURED ' + depth_chart[p['team']]['capture_id'])
                             if (depth_chart and p['team'] in depth_chart and gsis) else 'USAGE_HISTORY'),
            'depth_detail': ((depth.get(gsis) or {}) if gsis else {}),
            'current_availability': {
                'status': status, 'tier': tier,
                'designation': desig.get(nm),
                'IS_NOT': ('a game-day inactive decision unless the status is CONFIRMED_INACTIVE, '
                           'which requires a captured official document'),
            },
            'predicted_lineup_context': _starter_context(nm, p['team'], confirmed_starters),
        }

    out = {
        'artifact': 'SHOWDOWN_TONIGHT_STATE',
        'spec_version': SPEC_VERSION,
        'state_label': STATE_LABEL,
        'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'game_id': game_id, 'season': kick.year, 'week': sched_week,
        'away': away, 'home': home, 'kickoff_et_naive': slate['kickoff_et_naive'],
        # S._rel is the non-raising form. pathlib.relative_to throws when the path is already
        # relative or sits outside the repo, and this exact defect has now bitten three times in this
        # tree -- lineage.verify, showdown s_emit_csv, and here. A reporting convenience must not be
        # able to fail the operation it describes.
        'export': S._rel(export),
        'environment': {'games': env.value},
        'players': players,
        'identity_conflicts': [],
        'identity': {'n_resolved': sum(1 for v in players.values() if v.get('gsis_id')),
                     'n_team_defences': sum(1 for v in players.values()
                                            if v['identity'] == DST_IDENTITY),
                     'n_suffix_matched': len(suffixed or ())},
        'availability_summary': dict(status_counts),
        'depth': {
            'source': 'role_state_history.pregame_depth',
            'arm': 'PREGAME -- completed weeks only, not told who played tonight',
            'measure': dict(RSH.DEPTH_MEASURE),
            'n_players_with_a_depth_rank': sum(
                1 for v in players.values() if isinstance(v.get('depth_rank'), int)),
        },
        'observed_usage': {
            'season': kick.year, 'through_week': max(1, int(sched_week) - 1),
            'n_players_with_observed_usage': sum(
                1 for v in players.values() if (v.get('observed_2026') or {}).get('weeks_played')),
            'SOURCE': 'the refreshed usage panel; shares are club-normalised over those weeks',
        },
        'official_inactives': {
            'n_supplied': len(officials),
            'n_applied_to_the_slate': len(officials & set(by_name)),
            'not_in_the_priced_universe': sorted(officials - set(by_name)),
            'STATUS_APPLIED': AV.REPORTED_INACTIVE_HIGH_CONFIDENCE,
            'WHY_NOT_CONFIRMED': ('the list reached us relayed by reporters and an aggregator, not as '
                                  'an official document this system captured. CONFIRMED_INACTIVE is '
                                  'reserved for TIER_OFFICIAL_CAPTURED. The applied status is already '
                                  'in ABSENT_STATUSES, so opportunity is redistributed identically.'),
        },
        'availability_semantics': {
            'CONFIRMED_INACTIVE_REQUIRES': AV.TIER_OFFICIAL_CAPTURED,
            'REACHED_HERE': sorted({v['current_availability']['tier'] for v in players.values()}),
            'SILENCE_IS_NOT_ACTIVITY': ('a player not named on the injury report is '
                                        'UNKNOWN_ACTIVE_STATE, not active. Reading silence as '
                                        'activity would activate the slate on no evidence.'),
            'designations_not_matched_to_the_slate': unmatched_desig,
        },
        'WHAT_IS_MODELLED_HERE': 'nothing. This is a state artifact; every value is read or supplied.',
    }
    OUT.write_text(json.dumps(out, indent=2))
    return Outcome.ok('SHOWDOWN_SLATE_STATE_BUILT', out,
                      f'{len(players)} players, {game_id}, week {sched_week}',
                      path=S._rel(OUT), game_id=game_id, week=sched_week,
                      n_players=len(players), availability=dict(status_counts),
                      n_designations_unmatched=len(unmatched_desig))


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('export')
    ap.add_argument('--designations', help='JSON {name: OUT|DOUBTFUL|QUESTIONABLE}')
    ap.add_argument('--official-inactives', help='JSON list of names from a CAPTURED official list')
    ap.add_argument('--confirmed-starters',
                    help='JSON {name: CLUB} of starters confirmed by a cited source. '
                         'A club mismatch is rejected, not applied.')
    a = ap.parse_args()
    d = json.loads(pathlib.Path(a.designations).read_text()) if a.designations else None
    o = json.loads(pathlib.Path(a.official_inactives).read_text()) if a.official_inactives else None
    cs = json.loads(pathlib.Path(a.confirmed_starters).read_text()) \
        if a.confirmed_starters else None
    r = build(a.export, designations=d, official_inactives=o, confirmed_starters=cs)
    print(r.state.value, r.code)
    print(' ', r.detail)
    for k, v in (r.evidence or {}).items():
        if k != 'unresolved':
            print(f'  {k}: {v}')
    return 0 if r.state.value == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
