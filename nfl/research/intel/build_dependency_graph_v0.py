"""Writes nfl/research/intel/DEPENDENCY_GRAPH_SHOWDOWN_v0.json. Every edge cites the code read on 2026-10-08 (HEAD)."""
import json, pathlib, sys
OUT = pathlib.Path(sys.argv[1])
C = ('IMPLEMENTED_AND_CONSUMED', 'IMPLEMENTED_NOT_CONSUMED', 'INVARIANT_BY_DESIGN', 'MISSING', 'INCORRECT',
     'UNVERIFIED', 'SHADOW_ONLY', 'NOT_MODELLED_BY_OWNER_INSTRUCTION')
E = []
def e(i, src, dst, mech, status, code, evidence, kind, consumers=(), note=''):
    assert status in C, status
    assert kind in ('ACCOUNTING_RULE', 'CAUSAL_HYPOTHESIS', 'STATISTICAL_ASSOCIATION', 'DATA_LINEAGE', 'GOVERNANCE')
    E.append({'id': i, 'from': src, 'to': dst, 'football_mechanism': mech, 'status': status, 'code': code,
              'evidence': evidence, 'relationship_kind': kind, 'downstream_consumers': list(consumers), 'note': note})
# --- identity / availability
e('ID1', 'starter evidence + designations', 'slate state starter flag, availability', 'who may take the snaps',
  'IMPLEMENTED_AND_CONSUMED', 'showdown_slate_state._starter_context; showdown_run_guards.verify_starter_state',
  'nfl/tests/test_showdown_run_guards.py (33/33); P0 pack 45/4/6', 'GOVERNANCE', ('role_state', 'proj_v1'))
e('ID2', 'availability OUT', 'player opportunity = 0', 'an inactive player records no events',
  'IMPLEMENTED_AND_CONSUMED', 'proj_v1.allocate_opportunity (active set); world_accounting_check INACTIVE_NO_EVENTS',
  'nfl/research/accounting/WORLD_ACCOUNTING_*.json: 0 violations', 'ACCOUNTING_RULE', ('showdown_draws',))
e('ID3', 'QB depth/starter', 'QB share of club attempts', 'the starter takes the attempts',
  'IMPLEMENTED_AND_CONSUMED', 'proj_v1.depth_shares; showdown_draws._shares', 'R7 vs Mayfield R4 projections',
  'STATISTICAL_ASSOCIATION', ('sim.game',))
# --- QB -> team
e('QB1', 'starting QB identity', 'club pass/rush attempts, targets, plays', 'QB skill and style move team volume',
  'MISSING', 'proj_v1.team_volume (proj_v1.py:167) takes (panel, env); no QB argument',
  'TB 35.2794 attempts under both scenarios (Perplexity audit; TB_DAL_ISOLATION audit)', 'CAUSAL_HYPOTHESIS',
  ('allocate_opportunity', 'sim.game'), 'QB_CHANGE_EFFECT: in-season replacements +0.92 rush att, outcome-labelled')
e('QB2', 'starting QB identity', 'club scoring centre', 'QB quality moves points',
  'MISSING', 'sim/football_points.expected_points (:68), centre_for_game (:158): club history only',
  'TB centre 20.6765 both scenarios; QB_CHANGE_EFFECT -1.06 [-2.06,-0.02] (outcome-labelled, descriptive)',
  'CAUSAL_HYPOTHESIS', ('allocate_club_td', 'sim.game', 'DST points allowed', 'kicker'))
e('QB3', 'QB completion / depth profile', 'receiver catch probability', 'who throws changes catchability',
  'IMPLEMENTED_NOT_CONSUMED', 'QB completion_rate in projection; showdown_draws._shares supplies receiver catch_rate; '
  'sim/game.py _binom(tgt, catch_rate) (~:515); no "completion" token in showdown_draws or sim/game',
  'grep at HEAD; Perplexity audit', 'CAUSAL_HYPOTHESIS', ('sim.game catches',))
e('QB4', 'QB identity', 'receiver target allocation/depth', 'QBs distribute differently',
  'MISSING', 'proj_v1.allocate_opportunity / group_shares: receiver own history and role only',
  'Egbuka 7.7480 vs 7.7469 targets', 'CAUSAL_HYPOTHESIS', ('sim.game',))
e('QB5', 'QB sack/scramble style', 'opponent DST sacks/takeaways; drive survival', 'pressure-prone QBs feed the DST',
  'MISSING', 'sim/game DST components conditioned on opponent points, not opponent QB events',
  'code read', 'CAUSAL_HYPOTHESIS', ('DST', 'portfolio'))
e('QB6', 'QB own efficiency', 'QB passing yards', 'own YPA prior', 'IMPLEMENTED_AND_CONSUMED',
  'player_prior.hierarchical -> proj_v1.project_player -> classic_slate_run.efficiency_worlds pass factor',
  'Daniels factor 0.736 vs Mayfield 0.911', 'STATISTICAL_ASSOCIATION', ('worlds',),
  'Daniels prior is ARCHETYPE (cohort), not personal evidence')
# --- accounting
e('AC1', 'pass event', 'passer yards == receiver yards', 'one completion credits both', 'INCORRECT',
  'classic_slate_run.efficiency_worlds (:85, scaling :106-124): independent per-player yard factors',
  'WORLD_ACCOUNTING: TB mean gap -29.98 yd (Daniels), +10.06 (Mayfield); transform share -29.87 / +10.14; '
  'audit 100/50 probe reproduced through the real function', 'ACCOUNTING_RULE', ('DK points', 'portfolio'))
e('AC2', 'reception', 'receiving yards / receiving TD', 'yards and a receiving TD require a catch (absent laterals)',
  'INCORRECT', 'sim/game: rec yards split by targets, catches _binom independent, pass TDs allocated by share',
  'WORLD_ACCOUNTING: ~1,500/2,000 worlds have catchless receiving yards; ~500 catchless receiving TDs; '
  'no lateral event exists in the simulator', 'ACCOUNTING_RULE', ('DK points',))
e('AC3', 'interception', 'opposing DST takeaway', 'an INT is the defence\'s takeaway', 'INCORRECT',
  'showdown_slate_run: efficiency_worlds draws INTs from projection int_rate (:109) after raw DST components',
  'WORLD_ACCOUNTING: ~400-540 worlds per club with more INTs than opposing takeaways', 'ACCOUNTING_RULE',
  ('QB DK', 'DST DK', 'captain correlation'))
e('AC4', 'offensive TDs', 'team points', 'points are the sum of scoring events', 'INCORRECT',
  'sim/game score-first centred continuous points; TDs drawn from the centre', 
  'WORLD_ACCOUNTING: 44-83 worlds per club with points < 6 x offensive TDs', 'ACCOUNTING_RULE',
  ('DST points allowed', 'kicker', 'game-script'))
e('AC5', 'raw identities', 'published worlds', 'certification must cover the published arrays', 'INCORRECT',
  'identities_verified_by_the_simulator certifies RAW worlds; transforms follow', 'DRAWS.json metadata',
  'GOVERNANCE', ('READY gate',), 'world_accounting_check now measures the published stage (validation-only)')
e('AC6', 'event-linked world repair', 'production', 'shared event ledger', 'SHADOW_ONLY',
  'nfl/research/coherence EL_S1', 'EVENT_LINKED_WORLD.json: failed conjunctive confirmation', 'ACCOUNTING_RULE')
# --- game state, environment, personnel
e('GS1', 'score / margin', 'pass/rush mix', 'trailing teams pass', 'IMPLEMENTED_AND_CONSUMED',
  'sim/game ~:301-359 (score sampled first, then volume)', 'code read', 'STATISTICAL_ASSOCIATION', ('sim.game',),
  'not sequential: no drive/possession state')
e('GS2', 'drives / possessions / clock', 'scoring and volume', 'scoring emerges from drives', 'MISSING',
  'no possession model on the Showdown path', 'code read', 'CAUSAL_HYPOTHESIS')
e('EN1', 'weather (wind, precipitation, temperature)', 'passing, kicking, scoring', 'environment', 
  'IMPLEMENTED_NOT_CONSUMED', 'TEAM_GAME carries roof/surface/temp/wind (warehouse/team_game.py:336-347); '
  'football_points declares WEATHER NOT_MODELLED; kicker_world declares weather not modelled',
  'grep: no forecasting consumer', 'CAUSAL_HYPOTHESIS')
e('EN2', 'rest days / short week', 'efficiency, availability', 'fatigue', 'IMPLEMENTED_NOT_CONSUMED',
  'TEAM_GAME rest_days -> showdown_slate_state environment (:110); no consumer', 'grep', 'CAUSAL_HYPOTHESIS')
e('EN3', 'opponent defence', 'club scoring, volume', 'matchup', 'NOT_MODELLED_BY_OWNER_INSTRUCTION',
  'football_points: OPPONENT_ADJUSTMENT NOT_MODELLED (owner item 9)', 'code', 'CAUSAL_HYPOTHESIS', (),
  'an owner decision; re-opening it is an owner question')
e('PE1', 'offensive line availability', 'pressure, sacks, rushing efficiency', 'protection', 'MISSING',
  'no OL token on the Showdown path', 'grep', 'CAUSAL_HYPOTHESIS', (), 'data availability not established')
e('PE2', 'defensive personnel (CB, edge)', 'opponent completion, sacks', 'coverage/pressure', 'MISSING',
  'none', 'grep', 'CAUSAL_HYPOTHESIS', (), 'data availability not established')
e('PE3', 'coach / play caller', 'pace, pass rate, 4th-down policy', 'scheme', 'MISSING', 'none', 'grep',
  'CAUSAL_HYPOTHESIS')
e('PE4', 'in-game injury / relief', 'remaining opportunities', 'replacement owns the rest of the game', 'MISSING',
  'appearance successor is SHADOW_ONLY; no in-game hazard in sim/game', 'code', 'CAUSAL_HYPOTHESIS')
e('PE5', 'RB1 / WR1 / TE1 out', 'teammate shares', 'redistribution among the active set', 'IMPLEMENTED_AND_CONSUMED',
  'proj_v1.allocate_opportunity renormalises shares over active players', 'code read', 'STATISTICAL_ASSOCIATION',
  ('sim.game',), 'redistribution is proportional to history; no scheme/personnel response')
e('RL1', 'role bands', 'one ALPHA per club/position', 'modelling convention', 'IMPLEMENTED_AND_CONSUMED',
  'role_state.ALPHA_LIMIT (:75), demotion (:257-276) with "not a football state" text', 'code read',
  'STATISTICAL_ASSOCIATION', ('proj_v1',), 'a prior, not an NFL law; harm unmeasured; needs its own ablation')
# --- data lineage
e('DL1', 'raw captures', 'historical forecast inputs', 'information available at the cutoff', 'IMPLEMENTED_AND_CONSUMED',
  'nfl/warehouse/point_in_time.py (opt-in manifests)', 'test_point_in_time 32/32; ATL sealed replay 26/26; injection 26/26',
  'DATA_LINEAGE', ('every wired reader',), 'live mode is identity; ordering-by-capture-time (F2b) not done')
e('DL2', 'market (TEAM_GAME lines)', 'production football projection', 'firewall', 'IMPLEMENTED_AND_CONSUMED',
  'showdown runner FOOTBALL_ONLY arm; proj_v1 default arm is MARKET', 'MARKET_FIREWALL_*.json PASS_MARKET_BLIND',
  'GOVERNANCE', (), 'other entrypoints must declare their arm')
# --- DFS
e('DF1', 'published worlds', 'portfolio scoring', 'CPT 1.5x same world', 'IMPLEMENTED_AND_CONSUMED',
  'showdown_portfolio.score_matrix', 'R-series uploads; ATL replay', 'DATA_LINEAGE')
g = {'ARTIFACT': 'FOOTBALL_DEPENDENCY_GRAPH', 'version': 'v0', 'scope': 'Showdown production path, HEAD of 2026-10-08',
     'NOT_IN_SCOPE_YET': ['Classic run_forecast path', 'FanDuel scoring', 'ownership/field models', 'late swap',
                          'Classic optimizer', 'non-QB vintage_selector pipeline', 'prospective/q9 shadow paths'],
     'status_vocabulary': list(C), 'n_edges': len(E),
     'counts': {s: sum(1 for x in E if x['status'] == s) for s in C}, 'edges': E}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(g, indent=1) + '\n')
print(g['counts'])
