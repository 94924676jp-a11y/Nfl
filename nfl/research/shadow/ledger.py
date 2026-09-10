"""The permanent, machine-readable per-game shadow evaluation ledger.

One row per scored quantity. Append-only. Every row carries the seal hashes, so
a row can never be read as evidence about a forecast other than the one that
was actually sealed.

ATTRIBUTION IS A RULE, NOT A JUDGEMENT CALL

The owner asked for a clear separation of a genuine model miss from an in-game
state change and from a missing pregame input. Assigning those by eye after
seeing the errors is exactly how a post-hoc excuse gets written into a ledger,
so each class is decided by a stated predicate evaluated on the data:

  NO_FORECAST_MISSING_PREGAME_INPUT
      the engine produced no distribution for this quantity, and the stage
      that would have produced it refused with a named code. Carried as a row
      so an absent forecast is visible beside a real outcome.

  IN_GAME_STATE_CHANGE
      the entity is a quarterback whose ROLE CHANGED during the game -- he
      threw, but was not his team's passer throughout, so he either left or
      entered -- on a team where a passer is recorded injured in the
      play-by-play text. It covers the departing starter and the replacement
      alike, because one event disrupts both forecasts. A role change with no
      injury recorded is reported separately as
      IN_GAME_ROLE_CHANGE_NO_INJURY_RECORDED rather than folded in.

  WITHIN_DISTRIBUTION
      the actual fell inside the forecast's central 90% interval.

  MODEL_MISS
      everything else: the forecast was produced, the entity played the whole
      game, and the actual still fell outside the 90% interval.

A quantity scored against a SURROGATE actual is never classified at all. It
carries basis SURROGATE and no proper score, because a CRPS against a
different quantity would look like evidence and be none.
"""
from __future__ import annotations

import collections
import json
import re

_INJ = re.compile(r'([A-Z]{2,3})-\d+-([A-Z]\.[A-Za-z\'\-]+) was injured '
                  r'during the play', re.I)


def passer_changes(rows) -> dict:
    """team -> the ordered distinct passers and whether the passer changed."""
    seq = collections.defaultdict(list)
    for r in sorted(rows, key=lambda x: int(x['play_id'])):
        pid = r.get('passer_player_id') or ''
        pos = r.get('posteam') or ''
        if pid and pos:
            if not seq[pos] or seq[pos][-1][0] != pid:
                seq[pos].append((pid, r.get('passer_player_name') or '',
                                 int(r['play_id'])))
    out = {}
    for t, s in seq.items():
        out[t] = {'segments': [{'gsis_id': a, 'name': b, 'from_play_id': c}
                               for a, b, c in s],
                  'changed': len({a for a, _b, _c in s}) > 1}
    return out


def injured_in_game(rows) -> dict:
    """name-fragment -> the play it happened on, straight from the text."""
    out = {}
    for r in rows:
        for team, nm in _INJ.findall(r.get('desc') or ''):
            out.setdefault((team, nm), int(r['play_id']))
    return out


def role_changed(changes) -> dict:
    """gsis_id -> did this quarterback's role change DURING the game.

    THE FIRST VERSION OF THIS RULE WAS WRONG IN BOTH DIRECTIONS AND THE
    ERRORS ARE INSTRUCTIVE. It asked whether the play-by-play text named THIS
    quarterback as injured, which credited the departing starter and left the
    REPLACEMENT classified as a model miss -- yet the replacement's forecast
    is disrupted by exactly the same event, and more severely. It also fired
    for quarterbacks who never took a snap, on nothing but their team having
    used two passers, so a correct near-zero forecast for a third-string
    quarterback was recorded as a role change.

    The predicate is now a property of the passing sequence itself: a
    quarterback's role changed if he threw at all and was not the team's
    passer for the whole of it -- he was not the first passer, or not the
    last. That is true of the starter who leaves and of the replacement who
    enters, and false of a backup who never appeared.
    """
    out = {}
    for _t, d in changes.items():
        segs = d['segments']
        if not segs:
            continue
        first, last = segs[0]['gsis_id'], segs[-1]['gsis_id']
        for s in segs:
            out[s['gsis_id']] = not (s['gsis_id'] == first
                                     and s['gsis_id'] == last)
    return out


def team_qb_injured(changes, injuries) -> set:
    """Teams where a quarterback who actually threw is recorded as injured."""
    hurt = set()
    for team, d in changes.items():
        names = {s['name'] for s in d['segments']}
        for (t, n) in injuries:
            if t == team and n in names:
                hurt.add(team)
    return hurt


def classify(entity_kind, team, gsis_id, covered90, basis,
             changed_role, injured_teams) -> str:
    if basis == 'SURROGATE':
        return 'NOT_CLASSIFIED_SURROGATE_ACTUAL'
    if basis == 'NO_FORECAST':
        return 'NO_FORECAST_MISSING_PREGAME_INPUT'
    if entity_kind == 'qb' and changed_role.get(gsis_id):
        return ('IN_GAME_STATE_CHANGE' if team in injured_teams
                else 'IN_GAME_ROLE_CHANGE_NO_INJURY_RECORDED')
    return 'WITHIN_DISTRIBUTION' if covered90 else 'MODEL_MISS'


def build(evaluation: dict, rows) -> list:
    """The ledger rows for one evaluated game."""
    changes = passer_changes(rows)
    injuries = injured_in_game(rows)
    seal = evaluation['seal']
    base = {'game_id': evaluation['game_id'],
            'kickoff_utc': evaluation['kickoff_utc'],
            'written_at': evaluation['written_at'],
            'model_configuration': evaluation['model_configuration'],
            'exploratory': True, 'promoted': False,
            'prospective_eligible': False,
            'forecast_seal_sha256':
                seal['files']['nfl/research/shadow/g1_ne_sea/'
                              'forecast_artifact.json'],
            'outcome_sha256': seal['outcome_sha256']}

    # Whose role changed mid-game, and on which teams that followed an
    # injury -- both read off the passing sequence, not off the errors.
    changed_role = role_changed(changes)
    injured_teams = team_qb_injured(changes, injuries)
    full = {}
    for pid, q in evaluation['quarterbacks'].items():
        tl = q.get('timeline')
        full[pid] = bool(tl and tl['first_qtr'] <= 1 and tl['last_qtr'] >= 4
                         and not changed_role.get(pid))

    out = []
    for key, s in sorted(evaluation['team_environment'].items()):
        team, met = key.split('|')
        basis = s.get('actual_basis', 'EXACT')
        cov = (s.get('coverage') or {}).get('90%', {}).get('covered')
        out.append({**base, 'level': 'team_environment', 'entity': team,
                    'entity_name': team, 'metric': met, 'basis': basis,
                    'forecast_mean': s['mean'], 'forecast_sd': s['sd'],
                    'forecast_percentiles': s['percentiles'],
                    'actual': s.get('actual'),
                    'crps': s.get('crps'),
                    'mid_pit': (s.get('pit') or {}).get('mid_pit'),
                    'coverage': s.get('coverage'),
                    'outside_sample_support':
                        s.get('outside_sample_support'),
                    'attribution': classify('team', team, team,
                                            cov, basis, changed_role,
                                            injured_teams)})

    for team, b in sorted(evaluation.get('team_qb_aggregate', {}).items()):
        for met, s in sorted(b['metrics'].items()):
            cov = s['coverage']['90%']['covered']
            out.append({**base, 'level': 'team_qb_aggregate', 'entity': team,
                        'entity_name': team, 'metric': met, 'basis': 'EXACT',
                        'forecast_mean': s['mean'], 'forecast_sd': s['sd'],
                        'forecast_percentiles': s['percentiles'],
                        'actual': s['actual'], 'crps': s['crps'],
                        'mid_pit': s['pit']['mid_pit'],
                        'coverage': s['coverage'],
                        'outside_sample_support':
                            s['outside_sample_support'],
                        'attribution': classify('team', team, team, cov,
                                                'EXACT', changed_role,
                                                injured_teams)})

    qb_team = {}
    for k, v in evaluation['depth_chart'].items():
        t, pos, _r = k.split('|')
        if pos == 'QB':
            qb_team[v] = t
    for pid, q in sorted(evaluation['quarterbacks'].items()):
        for met, s in sorted(q['metrics'].items()):
            if 'pit' not in s:
                continue
            cov = s['coverage']['90%']['covered']
            out.append({**base, 'level': 'quarterback', 'entity': pid,
                        'entity_name': q['name'], 'team': qb_team.get(pid),
                        'metric': met, 'basis': 'EXACT',
                        'played': q['played'],
                        'played_full_game': full.get(pid),
                        'forecast_mean': s['mean'], 'forecast_sd': s['sd'],
                        'forecast_percentiles': s['percentiles'],
                        'actual': s['actual'], 'crps': s['crps'],
                        'mid_pit': s['pit']['mid_pit'],
                        'coverage': s['coverage'],
                        'outside_sample_support':
                            s['outside_sample_support'],
                        'thresholds': s.get('thresholds'),
                        'role_changed_in_game':
                            bool(changed_role.get(pid)),
                        'attribution': classify(
                            'qb', qb_team.get(pid), pid, cov, 'EXACT',
                            changed_role, injured_teams)})

    # THE OUTCOMES THE ENGINE PRODUCED NO FORECAST FOR. Omitting them would
    # make the ledger read as though the game contained only what was
    # modelled.
    for pid, v in sorted(evaluation['skill_actuals_no_forecast_produced']
                         .items()):
        for met, val in (('targets', v['targets']),
                         ('receptions', v['receptions']),
                         ('rec_yds', v['rec_yds']),
                         ('carries', v['carries']),
                         ('rush_yds', v['rush_yds'])):
            out.append({**base, 'level': 'skill_player', 'entity': pid,
                        'entity_name': v['name'], 'team': v['team'],
                        'metric': met, 'basis': 'NO_FORECAST',
                        'forecast_mean': None, 'forecast_sd': None,
                        'forecast_percentiles': None, 'actual': val,
                        'crps': None, 'mid_pit': None, 'coverage': None,
                        'refusal': 'appearance stage returned '
                                   'INJURY_REPORT_CHRONOLOGY_FAILURE, so the '
                                   'whole non-QB chain was NOT_APPLICABLE',
                        'attribution': 'NO_FORECAST_MISSING_PREGAME_INPUT'})
    return out


def dumps(rows) -> str:
    return ''.join(json.dumps(r, sort_keys=True, default=str) + '\n'
                   for r in rows)
