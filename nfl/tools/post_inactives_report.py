#!/usr/bin/env python3.12
"""Nine-game post-inactives evidence report. Football truth, not recommendations.

The owner's instruction is explicit: "Do not turn this into player recommendations yet.
This is still the football-truth/evidence layer." So the correlation section states
*mechanisms* -- which outcomes move together and why -- and never says to play anybody.
There is no projection in this repository to rank players with: `feature_build` is
STAGE_DECLARED_UNIMPLEMENTED and the draw layer refuses, so a ranking here would be
this module inventing one.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import redistribution as RD  # noqa: E402
from nfl.tools import state_compare as SC  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

POST = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
OUT_MD = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.md'
GAMES = ('CAR@CLE', 'CIN@PIT', 'HOU@IND', 'KC@MIA', 'LAC@BUF',
         'NE@JAX', 'NYJ@DET', 'SEA@WAS', 'TEN@NYG')


def _n(v):
    return v if isinstance(v, (int, float)) else 0.0


def _top(rows, key, n=5, positions=None):
    sel = [r for r in rows if positions is None or r['position'] in positions]
    def val(r):
        return _n(((r.get('observed_2026') or {}).get('combined') or {}).get(key))
    sel = [r for r in sel if val(r) > 0]
    return [(r['name'], val(r), r['current_availability']['status'])
            for r in sorted(sel, key=lambda r: -val(r))[:n]]


def game_findings(art):
    players = list(art['players'].values())
    by_club = {}
    for p in players:
        by_club.setdefault(p['team'], []).append(p)
    trees = art['redistribution']
    env = art['environment']
    out = {}
    for game in GAMES:
        away, home = game.split('@')
        clubs = {}
        for club in (away, home):
            rows = by_club.get(club, [])
            club_trees = {k: t for k, t in trees.items() if t['club'] == club}
            reported_out = [(p['name'], p['position'], p['salary'],
                             p['current_availability']['status'],
                             p['current_availability']['evidence_tier'])
                            for p in rows
                            if p['current_availability']['status']
                            in AV.ABSENT_STATUSES]
            reported_in = [(p['name'], p['position'], p['salary'],
                            p['current_availability']['evidence_tier'],
                            (p.get('workload_limitation') or {}).get('detail'))
                           for p in rows
                           if p['current_availability']['status']
                           in AV.PRESENT_STATUSES]
            unresolved = sum(1 for p in rows
                             if p['current_availability']['status']
                             in AV.NOT_A_CLAIM_OF_ABSENCE)
            predicted = [p['name'] for p in rows
                         if (p.get('predicted_lineup_context') or {})
                         .get('in_predicted_starting_group')]
            qb_rows = [p for p in rows if p['position'] == 'QB']
            qb_change = [k for k, t in club_trees.items() if t['position'] == 'QB']
            clubs[club] = {
                'reported_inactive_that_matter': sorted(
                    reported_out, key=lambda t: -t[2]),
                'reported_available': sorted(reported_in, key=lambda t: -t[2]),
                'n_dk_rows_unresolved': unresolved,
                'UNRESOLVED_MEANS': (
                    f'{unresolved} DK rows for this club are UNKNOWN_NOT_RELAYED: the '
                    f'inactive list exists but was not enumerated to us, so they are '
                    f'neither active nor out.'),
                'rotowire_predicted_group': predicted,
                'PREDICTED_IS_NOT_CONFIRMED': (
                    'a six-man predicted group is a projection of who starts, not a '
                    'declaration, and it says nothing about the rest of the roster.'),
                'observed_w1_w2': {
                    'backfield_carries': _top(rows, 'carries', 5, ('RB', 'QB')),
                    'receiving_targets': _top(rows, 'targets', 6, ('WR', 'TE', 'RB')),
                    'snap_leaders': _top(rows, 'offense_snaps', 6),
                    'red_zone_opportunities': _top(rows, 'rz_opportunities', 5),
                },
                'OBSERVED_IS_HISTORY': (
                    'weeks 1-2 counts. What these players DID, not what they will do, '
                    'and a two-game sample is not a stable tendency.'),
                'routes': 'UNKNOWN_SOURCE_UNAVAILABLE',
                'role_changes_from_todays_absences': {
                    k: {'vacated': t['vacated'],
                        'same_group_ranked': [c['name'] for c in
                                              t['candidates_same_position_group'][:4]],
                        'adjacent_ranked': [c['name'] for c in
                                            t['candidates_adjacent_position_group'][:3]],
                        'inheritance': t['inheritance'],
                        'competing_non_player_sinks': t['competing_non_player_sinks'],
                        'newly_relevant': t['newly_relevant_candidates'],
                        'concentration_gainers': t['concentration_gainer_candidates']}
                    for k, t in club_trees.items()},
                'qb_implications': {
                    'qb_absence_in_this_club': qb_change or None,
                    'dk_qbs_in_pool': [(p['name'], p['salary'],
                                        p['current_availability']['status'])
                                       for p in sorted(qb_rows,
                                                       key=lambda r: -r['salary'])],
                    'note': ('a quarterback change moves pass efficiency, designed '
                             'rushing, sack rate and turnover distribution together. '
                             'None of those is a reallocation between receivers, and '
                             'the rushing profile of the replacement is his own.'
                             if qb_change else
                             'no reported quarterback absence for this club.'),
                    'qb_layer_warning': (
                        'the held QB layer is a PRE-R2 conditional intermediate that '
                        'contains no 2026 information. It is not a week-3 per-player '
                        'expectation and is not used here.'),
                },
                'dst_implications': {
                    'answer': 'NOT_QUANTIFIED',
                    'mechanism': (
                        'opposing DST expectation moves through the other club and its '
                        'quarterback identity, protection and script. Where a '
                        'quarterback absence is reported the direction is arguable; '
                        'the magnitude is not established by held evidence, and '
                        'defensive touchdowns stay tail outcomes rather than base '
                        'expectations.'),
                },
            }
        e = (env.get('games') or {}).get(game, {})
        flag = (env.get('weather_flags') or {}).get(game)
        out[game] = {
            'clubs': clubs,
            'environment': e,
            'weather_flag': flag,
            'ENVIRONMENT_IS_THE_MARKET': (
                'spread and total are the numbers of the market, and the implied totals are '
                'arithmetic from them. None of it is a projection of ours, and we have '
                'none for it to agree or disagree with.'),
            'remaining_uncertainty': _uncertainty(game, clubs, flag),
            'correlation_mechanisms': _correlation(game, clubs),
            'NOT_RECOMMENDATIONS': (
                'the section above names which outcomes move together and why. It does '
                'not rank or recommend any player, and there is no projection in this '
                'repository with which to do so.'),
        }
    return out


def _uncertainty(game, clubs, flag):
    bits = []
    for club, c in clubs.items():
        if c['n_dk_rows_unresolved']:
            bits.append(f'{club}: {c["n_dk_rows_unresolved"]} DK rows still '
                        f'UNKNOWN_NOT_RELAYED')
        for k, t in c['role_changes_from_todays_absences'].items():
            bits.append(f'{k}: inheritance {t["inheritance"]} across '
                        f'{len(t["same_group_ranked"])} same-group candidates')
        for name, pos, sal, tier, note in c['reported_available']:
            if note:
                bits.append(f'{club} {name}: reported available AND reported limited -- '
                            f'availability resolved, workload not')
    bits.append('routes and route participation UNKNOWN_SOURCE_UNAVAILABLE for every '
                'player in this game')
    if flag and flag.get('status') == 'MATERIAL':
        bits.append(f'weather MATERIAL: {flag.get("precipitation_pct")}% precipitation, '
                    f'{flag.get("wind_mph")} mph, source confidence '
                    f'{flag.get("source_confidence")}')
    return bits


def _correlation(game, clubs):
    away, home = game.split('@')
    out = []
    for club in (away, home):
        c = clubs[club]
        opp = home if club == away else away
        qb = next((n for n, s, st in c['observed_w1_w2']['snap_leaders']
                   if any(n == q[0] and True for q in c['qb_implications']
                          ['dk_qbs_in_pool'])), None)
        catchers = [n for n, v, st in c['observed_w1_w2']['receiving_targets']
                    if st not in AV.ABSENT_STATUSES][:3]
        backs = [n for n, v, st in c['observed_w1_w2']['backfield_carries']
                 if st not in AV.ABSENT_STATUSES][:2]
        out.append({
            'club': club, 'opponent': opp,
            'positive_within_club': (
                f'{club} pass volume links its quarterback to {catchers} through shared '
                f'team dropbacks. They also compete for the same targets and the same '
                f'touchdowns, so the link is positive on volume and negative on '
                f'allocation at the same time.' if catchers else None),
            'quarterback_and_own_back': (
                f'{club} quarterback and {backs} share goal-line and short-yardage '
                f'carries, so their scoring paths overlap rather than simply add.'
                if backs else None),
            'back_and_own_dst': (
                f'{backs[0]} and the {club} DST both express the same branch -- {club} '
                f'leads, {opp} throws, pressure and turnovers rise, carries follow. '
                f'That link is only real where the back\'s opportunity is rushing-led '
                f'rather than receiving-led.' if backs else None),
            'opposing_bring_back': (
                f'a {opp} player supports a {club} stack only in the branch where {opp} '
                f'scores enough to keep {club} throwing. Which {opp} player depends on '
                f'the script, and is not automatically the running back.'),
            'NO_JOINT_DISTRIBUTION_HELD': (
                'these are mechanisms, stated from observed usage and the market. '
                'Quantifying which of them dominates needs the joint simulation layer, '
                'which is blocked at feature_build.'),
        })
    return out


def run():
    if not POST.exists():
        return Outcome.fail('POST_STATE_ABSENT', f'{POST.name} not built')
    art = json.loads(POST.read_text())
    findings = game_findings(art)
    if len(findings) != 9:
        return Outcome.fail('GAME_COVERAGE_INCOMPLETE',
                            f'{len(findings)} games, expected 9')
    art['game_findings'] = findings
    POST.write_text(json.dumps(art, indent=2) + '\n')
    return Outcome.ok('GAME_REPORT_BUILT', findings, f'{len(findings)} games',
                      n_games=len(findings))


def main() -> int:
    r = run()
    print(r)
    return 0 if r.state is State.PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())


# --- markdown ----------------------------------------------------------------
def _fmt_vac(v):
    if v.get('observed_state') == RD.UNKNOWN_NO_ROW:
        return '**UNKNOWN_NO_OBSERVED_ROW** (not zero)'
    return (f'{_n(v["offense_snaps"]):.0f} snaps · {_n(v["carries"]):.0f} car · '
            f'{_n(v["targets"]):.0f} tgt · {_n(v["rz_opportunities"]):.0f} rz · '
            f'{_n(v["gl_opportunities"]):.0f} gl · routes UNKNOWN')


def markdown(art, cmp_value):
    L = []
    w = L.append
    w('# DK Week 3 Early Only — POST-INACTIVES football state')
    w('')
    w(f'**State:** `{art["state_label"]}`  ')
    w(f'**Built:** {art["generated_at_utc"]} · **Kickoff:** '
      f'{(art.get("slate") or {}).get("kickoff_utc")}  ')
    w(f'**Spec:** `{art["spec_version"]}`')
    w('')
    w('## Read this before quoting anything below')
    w('')
    w(f'**What this is.** {art["WHAT_THIS_IS"]}')
    w('')
    w(f'**What this is not.** {art["WHAT_THIS_IS_NOT"]}')
    w('')
    c = art['COMPLETENESS']
    w(f'**The gap that dominates everything else.** {c["why_it_matters"]}')
    w('')
    w(f'| lists populated per the source | {c["lists_populated_per_source"]} |')
    w('|---|---|')
    w(f'| lists enumerated to this repository | **{c["lists_enumerated_to_this_repository"]}** |')
    for k, v in sorted(art['availability_counts'].items(), key=lambda kv: -kv[1]):
        w(f'| `{k}` | {v} |')
    w('')
    w('## PRE → POST semantic diff')
    w('')
    w(cmp_value['AVAILABILITY_COUNT_SEMANTICS'])
    w('')
    w('This is **not** `baseline_diff.py`. That module compares DraftKings salary, '
      'roster position, club and display name, and raises `IDENTITY_REGRESSED` as a '
      'FAIL — point it at a post-inactives comparison and a roster churn reads as a '
      'defect in our own chain while a salary move sits in the same list as a player '
      'being ruled out. This comparator separates availability, role, opportunity, '
      'redistribution, newly-relevant and environment, and quarantines every '
      'DraftKings or third-party field change with `football_change: false`.')
    w('')
    w('| club | player | $ | from | to | tier | document held |')
    w('|---|---|--:|---|---|---|---|')
    for a in cmp_value['availability_changes']:
        w(f'| {a["club"]} | {a["player"]} | {a["salary"]} | `{a["from_status"]}` | '
          f'`{a["to_status"]}` | {a["to_tier"]} | '
          f'{"yes" if a["document_held"] else "**no**"} |')
    w('')
    q = cmp_value['NON_FOOTBALL_CHANGES_QUARANTINED']
    w(f'**Quarantined non-football changes: {q["n"]}.** '
      f'**Opportunity drift: {len(cmp_value["opportunity_changes"])}** — observed weeks '
      f'1–2 is history and must be identical across both passes, so a non-zero count '
      f'here would be a builder defect rather than football.')
    w('')
    w('### Guards')
    w('')
    for name, g in cmp_value['guards'].items():
        w(f'- `{name}` → **{g["state"]}** `{g["code"]}`')
    w('')
    w('## Redistribution')
    w('')
    w('No share of any vacancy is assigned to anybody. Every tree carries '
      '`UNRESOLVED_DISTRIBUTION`, a candidate ranking whose basis is stated, and the '
      'non-player sinks that compete with every candidate.')
    w('')
    w('| vacancy | pos | $ | vacated (observed W1–2) | same-group ranked | competing sinks |')
    w('|---|---|--:|---|---|--:|')
    for key, t in sorted(art['redistribution'].items()):
        same = ', '.join(c['name'] for c in t['candidates_same_position_group'][:3])
        w(f'| **{key}** | {t["position"]} | {t["salary"]} | {_fmt_vac(t["vacated"])} | '
          f'{same} | {len(t["competing_non_player_sinks"])} |')
    w('')
    w(f'**Newly relevant (reserve, the role may not exist):** '
      f'{", ".join(art["newly_relevant_players"])}')
    w('')
    w(f'**Concentration gainers (established, the role may get denser):** '
      f'{", ".join(art["concentration_gainers"])}')
    w('')
    w(art['NEWLY_RELEVANT_VS_CONCENTRATION'])
    w('')
    w('## Environment')
    w('')
    w('| game | change | detail |')
    w('|---|---|---|')
    for e in cmp_value['environment_changes']:
        bits = '; '.join(f'{k} {m["from"]} → {m["to"]}'
                         for k, m in (e.get('moved') or {}).items()) or '—'
        w(f'| {e["game"]} | {e["change"]} | {bits} |')
    w('')
    w('The market moved on five of nine games. That is information about the market. '
      'There is no projection of ours for it to agree or disagree with.')
    w('')
    w('## The nine games')
    for game, gf in art['game_findings'].items():
        w('')
        w(f'### {game}')
        e = gf['environment']
        w('')
        w(f'{e.get("spread")} · total {e.get("total")} · implied '
          f'{e.get("away_implied")} / {e.get("home_implied")} · {e.get("weather")}'
          + (f'  ·  **weather {gf["weather_flag"]["status"]}**'
             if gf.get('weather_flag') else ''))
        for club, cc in gf['clubs'].items():
            w('')
            w(f'**{club}** — {cc["n_dk_rows_unresolved"]} DK rows still unresolved')
            if cc['reported_inactive_that_matter']:
                w('')
                w('| reported OUT | pos | $ | tier |')
                w('|---|---|--:|---|')
                for n, pos, sal, st, tier in cc['reported_inactive_that_matter']:
                    w(f'| {n} | {pos} | {sal} | {tier} |')
            av = [x for x in cc['reported_available']]
            if av:
                w('')
                w('reported available: ' + '; '.join(
                    f'{n} (${sal}{", LIMITED" if note else ""})'
                    for n, pos, sal, tier, note in av))
            w('')
            w('observed W1–2 — carries: ' + ', '.join(
                f'{n} {v:.0f}' for n, v, st in
                cc['observed_w1_w2']['backfield_carries']) or '—')
            w('')
            w('observed W1–2 — targets: ' + ', '.join(
                f'{n} {v:.0f}' for n, v, st in
                cc['observed_w1_w2']['receiving_targets']) or '—')
            for k, t in cc['role_changes_from_todays_absences'].items():
                w('')
                w(f'*{k}* vacates {_fmt_vac(t["vacated"])} → ranked '
                  f'{", ".join(t["same_group_ranked"][:3])}; inheritance '
                  f'`{t["inheritance"]}`')
                if t['newly_relevant']:
                    w(f'  newly relevant: {", ".join(t["newly_relevant"])}')
        w('')
        w('**Remaining uncertainty**')
        for u in gf['remaining_uncertainty']:
            w(f'- {u}')
        w('')
        w('**Correlation mechanisms** (mechanisms only — no recommendation, and no '
          'joint distribution held to weigh them)')
        for cm in gf['correlation_mechanisms']:
            for fld in ('positive_within_club', 'quarterback_and_own_back',
                        'back_and_own_dst', 'opposing_bring_back'):
                if cm.get(fld):
                    w(f'- *{cm["club"]}* — {cm[fld]}')
    w('')
    w('## What is still blocked')
    w('')
    pb = art['proprietary_projection_board']
    w(f'**No projection board exists.** `{pb["code"]}`. {pb["detail"]}')
    w('')
    w('So the 48-entry portfolio stops here, at the scientific stop condition the '
      'instructions themselves set: a defensible player-outcome model, a joint game '
      'simulator, an ownership model and a contest-field model are all unavailable, '
      'and FantasyCruncher is not a substitute for any of them.')
    w('')
    w('## Preserved corrections')
    w('')
    oc = art['OBSERVED_2026_CORRECTION_PRESERVED']
    w(f'{oc["finding"]}  Named examples: {", ".join(oc["named_examples"])}. '
      f'{oc["consequence"]} {oc["not_altered"]}')
    w('')
    w('## Identity')
    w('')
    for ic in art['identity_conflicts']:
        w(f'- **{ic["id"]}** — {ic["status"]}. {ic["resolution"]}')
    w('')
    return '\n'.join(L) + '\n'


def emit_markdown():
    art = json.loads(POST.read_text())
    c = SC.run()
    if c.state is not State.PASS:
        return c
    OUT_MD.write_text(markdown(art, c.value))
    return Outcome.ok('MARKDOWN_WRITTEN', str(OUT_MD.relative_to(_REPO)),
                      f'{OUT_MD.stat().st_size} bytes')
