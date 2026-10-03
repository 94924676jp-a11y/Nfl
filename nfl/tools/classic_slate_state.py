#!/usr/bin/env python3.12
"""Build the POST-shaped slate state for a DraftKings CLASSIC slate, from the DK export and the warehouse.

WHY THIS EXISTS. `proj_v1.build()` and `role_state.build()` read one artifact: a POST-shaped slate
state. The Week-3 classic builder derives from a PRE state built from one relayed evidence chain and
is pinned to that week; `showdown_slate_state` builds the same shape for ONE game. A classic Early
Only slate is several games priced in one pool, so this builds the state across every game in the
export, reusing the showdown builder's own helpers so the two shapes cannot drift:

  universe      `early_only.pool()` -- DraftKings' own export, official ids, roster slots, Game Info
  slate         `early_only.slate()` -- the game set READ from the export, one kickoff, checked
  identity      `proj_v1.resolve_slate_identities` against `player_prior.name_index()`, the
                production resolver; a non-defence player with no football identity REFUSES
  environment   `showdown_slate_state.environment_for` per game, read from TEAM_GAME. It carries
                the schedule's market columns; the football-only arm does not read them, and this
                module records that it carries them rather than hiding it
  availability  the CAPTURED official injury report (`pool_audit.injury_rows`, newest lawful block per
                club, matched by gsis_id, never by name), mapped through the showdown builder's closed
                DESIGNATION_MAP. OUT is REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED (absent, not
                CONFIRMED -- that needs the game-day inactive document); QUESTIONABLE and silence are
                UNKNOWN_ACTIVE_STATE; DOUBTFUL is REPORTED_DOUBTFUL_UNVERIFIED
  usage, depth  `observed_current_season` and `role_state_history.pregame_depth`, weeks < this week

    python3.12 nfl/tools/classic_slate_state.py 2026W4 --as-of 2026-10-03T16:00:00Z

It fetches nothing and models nothing. Every value is read, and every refusal names what is missing.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.salaries import early_only as EO  # noqa: E402
from nfl.production import pool_audit as PA  # noqa: E402
from nfl.production import world_clock as WC  # noqa: E402
from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import player_prior, proj_v1  # noqa: E402
from nfl.tools import showdown_slate_state as SS  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'classic-slate-state-1'
STATE_LABEL = 'CLASSIC_PREGAME / OFFICIAL_INJURY_REPORT_CAPTURED / NO_GAME_DAY_INACTIVE_DOCUMENT'
OUT_DIR = _REPO / 'nfl/dfs/salaries'

_REPORT_TO_DESIGNATION = {'out': 'OUT', 'doubtful': 'DOUBTFUL', 'questionable': 'QUESTIONABLE', '': 'NO_DESIGNATION'}


def out_path(slate_id: str) -> pathlib.Path:
    return OUT_DIR / f'DK_{slate_id}_EARLY_STATE.json'


NEXT_HEALTHY_TIER = 'DEPTH_CHART_NEXT_HEALTHY_AFTER_REPORTED_OUT'


def _qb_rank(pos, team, gsis, qb_chart, depth, out_gsis=()):
    """Quarterbacks: rank on the captured chart AMONG QUARTERBACKS NOT REPORTED OUT -- a reported-out
    starter takes no snap, so he vacates the rank rather than holding it. Absent from a chart that
    covers his club: below everyone it lists. Everyone else: the validated usage-history rank."""
    if pos == 'QB' and team in qb_chart:
        order = [g for g in qb_chart[team]['order'] if g not in out_gsis]
        return (order.index(gsis) + 1) if gsis in order else len(order) + 1
    return (depth.get(gsis) or {}).get('pregame_rank') if gsis else None


def _next_healthy_context(pos, team, gsis, qb_chart, out_gsis):
    """Predicted-starter evidence for ONE case: the captured chart's QB1 is reported OUT and this is
    the first quarterback below him who is not. Labelled with its own tier, never as owner-relayed
    or confirmed; it is what the club's own chart says about who is next, read after the report."""
    if pos != 'QB' or team not in qb_chart:
        return {}
    order = qb_chart[team]['order']
    if not order or order[0] not in out_gsis:
        return {}
    healthy = [g for g in order if g not in out_gsis]
    if not healthy or healthy[0] != gsis:
        return {}
    return {'state': NEXT_HEALTHY_TIER, 'in_predicted_starting_group': True,
            'chart_capture': qb_chart[team]['capture_id'], 'chart_dt': qb_chart[team]['dt'],
            'reported_out_ahead_of_him': [g for g in order[:order.index(gsis)]],
            'IS_NOT': ('a confirmed starter. The club has not been heard to name him; its own depth '
                       'chart lists him first among healthy quarterbacks after the official report '
                       'ruled the starter out.')}


def _games_in_warehouse(season, pairs, gameday=None):
    """One unplayed warehouse game per slate pairing, disambiguated by the export's own date.

    Division rivals meet twice, so a club pair alone can name two unplayed games (2026: NE/BUF in
    weeks 4 and 13). The DK export states the kickoff date; the schedule capture states each game's
    day. The pair is matched on BOTH, never on a guessed week.
    """
    art = json.loads(SS.TEAM_GAME.read_text()) if SS.TEAM_GAME.exists() else {'rows': []}
    rows = art['rows'] if isinstance(art['rows'], list) else list(art['rows'].values())
    day_of = {}
    if gameday:
        sc = WC.schedule(season)
        if sc.state.value == 'PASS':
            day_of = {r['game_id']: r.get('gameday') for r in sc.value}
    found, missing = {}, []
    for away, home in pairs:
        cand = sorted({r['game_id'] for r in rows if r.get('season') == season
                       and {r.get('club'), r.get('opponent')} == {away, home}
                       and r.get('points') is None
                       and (not gameday or day_of.get(r['game_id']) == gameday)})
        if len(cand) != 1:
            missing.append({'away': away, 'home': home, 'candidates': cand})
            continue
        wk = next(r['week'] for r in rows if r.get('game_id') == cand[0])
        found[(away, home)] = (cand[0], int(wk))
    return found, missing


def captured_qb_depth(as_of: str) -> dict:
    """The quarterback order on the newest depth-chart capture lawful at `as_of`, per club.

    WHY QUARTERBACKS AND WHY THE CAPTURE. Usage-history depth (`pregame_depth`) is what the
    forward-chained evaluation validated, and it is kept for every other position. For the
    quarterback room it fails in exactly the case that matters on a live slate: the starter is
    reported OUT and the backup order was set this week. Measured on 2026 week 4: Chicago's
    captured chart moved Tyson Bagent to QB2 on 2026-10-03 (Case Keenum through 10-02), and Tampa's
    lists Jalon Daniels at QB2, while usage history ranked Keenum and Easton Stick -- a practice-squad
    quarterback on no Tampa chart -- first. The football sanity gate caught the downstream leak.

    Returns {club: {'order': [gsis_id, ...], 'dt': ..., 'capture_id': ...}}. Read-only.
    """
    import gzip as _gz, csv as _csv, os as _os
    cut = as_of.replace('-', '').replace(':', '')[:15] + 'Z'
    best = None
    for ln in open(_REPO / 'nfl' / 'vintage_manifest.jsonl'):
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get('source') != 'depth_charts' or r.get('state') != 'PASS':
            continue
        cid = str(r.get('capture_id') or '')
        b = (r.get('value') or {}).get('blob')
        if cid <= cut and b and _os.path.exists(_REPO / b) and (best is None or cid > best[0]):
            best = (cid, b)
    if best is None:
        return {}
    rows = list(_csv.DictReader(_gz.open(_REPO / best[1], 'rt')))
    out = {}
    for club in {x['team'] for x in rows}:
        q = [x for x in rows if x['team'] == club and x.get('pos_abb') == 'QB']
        if not q:
            continue
        last = max(x['dt'] for x in q)
        order = [x['gsis_id'] for x in sorted((x for x in q if x['dt'] == last),
                                              key=lambda x: int(x['pos_rank']))]
        out[club] = {'order': order, 'dt': last, 'capture_id': best[0]}
    return out


def build(slate_id: str, *, as_of: str, official_inactives=None, confirmed_starters=None,
          write: bool = True) -> Outcome:
    files = EO.slate_files(slate_id)
    po = EO.pool(files['entries_blob'], files['entries_sha'])
    if po.state.value != 'PASS':
        return po
    if not po.evidence.get('sha256_matches_declared'):
        return Outcome.fail('CLASSIC_STATE_EXPORT_HASH_MISMATCH',
                            f'{files["entries_blob"]} does not hash to its manifest row',
                            cause=Cause.DATA)
    sl = EO.slate(po.value, expected_kickoff=files['kickoff'])
    if sl.state.value != 'PASS':
        return sl
    pool_rows = po.value
    pairs = [(SS.S.corpus_team(a), SS.S.corpus_team(h)) for a, h in sl.value]
    season = int(files['kickoff'].split('/')[2][:4])
    mm, dd, yy = files['kickoff'].split(' ')[0].split('/')
    games, missing = _games_in_warehouse(season, pairs, gameday=f'{yy}-{mm}-{dd}')
    if missing:
        return Outcome.blocked('CLASSIC_STATE_GAME_NOT_IN_WAREHOUSE',
                               f'{len(missing)} slate game(s) have no single unplayed warehouse game',
                               cause=Cause.DATA, missing=missing)
    weeks = sorted({w for _, w in games.values()})
    if len(weeks) != 1:
        return Outcome.fail('CLASSIC_STATE_GAMES_SPAN_WEEKS', f'slate games sit in weeks {weeks}')
    week = weeks[0]

    # FRESHNESS FIRST. The slate-relative verdict: every game this week's forecast consumes is scored.
    fr = WC.for_target(season, week, as_of=as_of)
    if fr.state.value != 'PASS':
        return fr

    env = {}
    for (away, home), (gid, _w) in sorted(games.items()):
        e = SS.environment_for(gid, away, home)
        if e.state.value != 'PASS':
            return e
        env.update(e.value)

    flat = {r['dk_id']: {'name': r['dk_name'], 'team': r['team'], 'position': r['dk_pos']}
            for r in pool_rows}
    ids, unresolved, suffixed = proj_v1.resolve_slate_identities({'players': flat},
                                                                 player_prior.name_index())
    unresolved_nondst = [u for u in unresolved if u.get('position') != 'DST']
    # A classic pool prices deep reserves the football identity index may not know (a practice-squad
    # call-up, a rookie with no snap). They are NOT dropped and NOT invented: each is carried with a
    # named refusal state so the board shows him as non-playable, and the count is in the evidence.
    unresolved_ids = {u.get('dk_id') for u in unresolved_nondst}

    teams = sorted({t for p in pairs for t in p})
    inj = PA.injury_rows(season, week, set(teams), as_of)
    if inj.state.value != 'PASS':
        return inj
    by_gsis = inj.value or {}

    po2 = player_prior.load_panel()
    if po2.state.value != 'PASS':
        return po2
    obs = SS.observed_current_season(po2.value, season, max(1, week - 1))
    from nfl.tools import role_state_history as RSH
    depth = RSH.pregame_depth(po2.value, player_prior.position_index(), season, week)
    qb_chart = captured_qb_depth(as_of)

    officials = {n.strip() for n in (official_inactives or ())}
    game_of = {}
    for r in pool_rows:
        gid, _ = games[(SS.S.corpus_team(r['away']), SS.S.corpus_team(r['home']))]
        game_of[r['dk_id']] = gid
    players, status_counts, desig_counts = {}, collections.Counter(), collections.Counter()
    out_gsis = {g for g, r in by_gsis.items() if (r.get('report_status') or '').strip().lower() == 'out'}
    for r in pool_rows:
        dk_id, nm, team, pos = r['dk_id'], r['dk_name'], r['team'], r['dk_pos']
        rec = ids.get(dk_id) or {}
        gsis = None if pos == 'DST' else (rec.get('gsis_id') or None)
        ir = by_gsis.get(gsis) if gsis else None
        report = ((ir or {}).get('report_status') or '').strip().lower()
        designation = _REPORT_TO_DESIGNATION.get(report)
        if designation is None:
            return Outcome.fail('CLASSIC_STATE_DESIGNATION_UNKNOWN',
                                f'{nm}: report_status {report!r} is outside the closed vocabulary',
                                known=sorted(_REPORT_TO_DESIGNATION))
        if nm in officials:
            status, tier = AV.REPORTED_INACTIVE_HIGH_CONFIDENCE, AV.TIER_AGGREGATOR_REPORTED
        elif ir is not None:
            status, tier = SS.DESIGNATION_MAP[designation], AV.TIER_OFFICIAL_RELEASE_CITED
        else:
            status, tier = AV.UNKNOWN_ACTIVE_STATE, AV.TIER_NONE
        if dk_id in unresolved_ids:
            status, tier = AV.UNKNOWN_ACTIVE_STATE, AV.TIER_NONE
        status_counts[status] += 1
        if ir is not None:
            desig_counts[designation] += 1
        players[dk_id] = {
            'name': nm, 'team': team, 'position': pos, 'game_id': game_of[dk_id],
            'opponent': r['home'] if team == r['away'] else r['away'],
            'salary': r['salary'], 'dk_id': dk_id, 'roster_position': r['roster_position'],
            'flex_eligible': r['flex_eligible'],
            'identity': (SS.DST_IDENTITY if pos == 'DST' else
                         ('IDENTITY_UNRESOLVED_NOT_PROJECTED' if dk_id in unresolved_ids else rec)),
            'gsis_id': gsis,
            'observed_2026': (obs.get(gsis) or {}) if gsis else {},
            'depth_rank': _qb_rank(pos, team, gsis, qb_chart, depth, out_gsis),
            'depth_detail': ((depth.get(gsis) or {}) if gsis else {}),
            'depth_source': (('DEPTH_CHART_CAPTURED ' + qb_chart[team]['capture_id'])
                             if pos == 'QB' and team in qb_chart else
                             'PREGAME_USAGE_HISTORY'),
            'current_availability': {
                'status': status, 'tier': tier, 'designation': designation if ir is not None else None,
                'practice_status': (ir or {}).get('practice_status'),
                'injury': (ir or {}).get('report_primary_injury'),
                'IS_NOT': ('a game-day inactive decision unless the status is CONFIRMED_INACTIVE, '
                           'which requires a captured official document'),
            },
            'predicted_lineup_context': (SS._starter_context(nm, team, confirmed_starters)
                                         or _next_healthy_context(pos, team, gsis, qb_chart, out_gsis)),
        }

    out = {
        'artifact': 'CLASSIC_SLATE_STATE', 'spec_version': SPEC_VERSION, 'state_label': STATE_LABEL,
        'slate_id': slate_id, 'built_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'as_of': as_of, 'season': season, 'week': week, 'kickoff': files['kickoff'],
        'games': {gid: {'away': a, 'home': h} for (a, h), (gid, _w) in sorted(games.items())},
        'export': str(pathlib.Path(files['entries_blob']).relative_to(_REPO)),
        'export_sha256': files['entries_sha'],
        'freshness': {'code': fr.code, **{k: fr.evidence.get(k) for k in (
            'n_games_consumed', 'n_games_scored', 'same_week_games_already_played')}},
        'environment': {'games': env,
                        'CARRIES_MARKET_COLUMNS': ('TEAM_GAME carries the schedule capture\'s spread, '
                                                   'total and implied totals. The football-only arm '
                                                   '(proj_v1 MARKET_ARM) does not read them; they are '
                                                   'here so the market arm and the comparison can.')},
        'players': players,
        'identity': {'n_pool': len(pool_rows),
                     'n_resolved': sum(1 for v in players.values() if v.get('gsis_id')),
                     'n_team_defences': sum(1 for v in players.values() if v['identity'] == SS.DST_IDENTITY),
                     'n_unresolved_not_projected': len(unresolved_ids),
                     'unresolved': [{'dk_id': u.get('dk_id'), 'name': u.get('name'), 'team': u.get('team'),
                                     'position': u.get('position')} for u in unresolved_nondst],
                     'n_suffix_matched': len(suffixed or ())},
        'availability_summary': dict(status_counts),
        'injury_report': {'source': 'pool_audit.injury_rows (captured official report, newest lawful block per club)',
                          'retrieved_at': sorted({p['retrieved_at'] for p in inj.evidence['provenance'].values()}),
                          'designations_on_slate_players': dict(desig_counts),
                          'clubs_with_no_game_designation': sorted(
                              t for t, n in inj.evidence['n_report_status_filled'].items() if n == 0),
                          'clubs_with_no_filed_block': inj.evidence['clubs_with_no_filed_block']},
        'official_inactives': {'n_supplied': len(officials), 'STATUS_IF_SUPPLIED': AV.REPORTED_INACTIVE_HIGH_CONFIDENCE,
                               'CAPTURED_DOCUMENT': None,
                               'STATE': 'NOT_YET_PUBLISHED' if not officials else 'APPLIED'},
        'depth': {'source': 'role_state_history.pregame_depth for every position except QB; QB order from '
                            'the newest captured depth chart lawful at as_of (see captured_qb_depth)',
                  'qb_chart': {c: {'dt': v['dt'], 'capture_id': v['capture_id']} for c, v in qb_chart.items()
                               if c in teams},
                  'arm': 'PREGAME -- completed weeks only for usage; current-week capture for QB order',
                  'n_players_with_a_depth_rank': sum(1 for v in players.values() if isinstance(v.get('depth_rank'), int))},
        'observed_usage': {'season': season, 'through_week': max(1, week - 1),
                           'n_players_with_observed_usage': sum(
                               1 for v in players.values() if (v.get('observed_2026') or {}).get('weeks_played'))},
        'WHAT_IS_MODELLED_HERE': 'nothing. This is a state artifact; every value is read or supplied.',
    }
    if not players:
        return Outcome.blocked('CLASSIC_STATE_EMPTY_INPUT', 'no players', cause=Cause.EMPTY_INPUT)
    if write:
        out_path(slate_id).write_text(json.dumps(out, indent=2))
    return Outcome.measured('CLASSIC_SLATE_STATE_BUILT', out, n_measured=len(players),
                            what='DK pool rows carried into the slate state',
                            detail=f'{len(players)} players, {len(games)} games, week {week}',
                            path=str(out_path(slate_id).relative_to(_REPO)), week=week,
                            availability=dict(status_counts),
                            n_unresolved_not_projected=len(unresolved_ids))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--as-of', required=True)
    ap.add_argument('--official-inactives', help='JSON list of names from a CAPTURED official list')
    a = ap.parse_args()
    oi = json.loads(pathlib.Path(a.official_inactives).read_text()) if a.official_inactives else None
    o = build(a.slate_id, as_of=a.as_of, official_inactives=oi)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    for k in ('availability', 'n_unresolved_not_projected', 'path'):
        if k in (o.evidence or {}):
            print(f'  {k}: {o.evidence[k]}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
