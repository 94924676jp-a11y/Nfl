"""FAIR_BASELINE_SCORECARD (mandate b0540a52 phase 3): every forecast against a simple baseline with the SAME information.

    python3.12 nfl/research/benchmark/fair_baseline_scorecard.py > nfl/research/benchmark/FAIR_BASELINE_SCORECARD.json

Reads committed artifacts only (no simulation, no new look at any season):
PLAYER_SCORECARD.json, D1_HOLDOUT_2025.json, D2_DEV_2024.json, D2_LOOK_2025.json, FOUR_ARM_EXPLORATORY.json,
FORECAST_ERROR_ATLAS.json. Each row says which information both sides had and how much the row may be relied on."""
import hashlib
import json
import pathlib

B = pathlib.Path('nfl/research/benchmark')


def load(n):
    p = B / n
    return json.loads(p.read_text()), hashlib.sha256(p.read_bytes()).hexdigest()


ps, ps_h = load('PLAYER_SCORECARD.json')
d1, d1_h = load('D1_HOLDOUT_2025.json')
dv, dv_h = load('D2_DEV_2024.json')
dl, dl_h = load('D2_LOOK_2025.json')
fa, fa_h = load('FOUR_ARM_EXPLORATORY.json')
at, at_h = load('FORECAST_ERROR_ATLAS.json')


def pv(x):
    """paired value + interval from either artifact's shape"""
    if x is None:
        return None
    if 'value' in x:
        return {'diff': x['value'], 'ci95': x['ci95']}
    if 'diff' in x:
        return {'diff': x['diff'], 'ci95': x['ci95']}
    return x


U = ps['UNCONDITIONAL_DFS']
C = ps['CONDITIONAL_GIVEN_PLAYING']
rows = [
    {'id': 'H1', 'question': 'incumbent football core vs naive per-appearance mean, unconditional (0 if absent)',
     'information': 'NO NEWS on either side (no injury reports, no inactives, no markets)', 'seasons': '2024-2025 held out',
     'n': U['overall']['proj']['n'], 'mae': {'incumbent': U['overall']['proj']['mae'], 'naive_STD_U': U['overall']['STD_U']['mae']},
     'incumbent_minus_naive': pv(U['paired_vs_baselines']['STD_U']['mae']), 'reliance': 'HELD_OUT_NO_NEWS', 'source': 'PLAYER_SCORECARD.json'},
    {'id': 'H2', 'question': 'incumbent vs naive, conditional on playing (no appearance discount on either side)',
     'information': 'NO NEWS', 'seasons': '2024-2025 held out', 'n': C['overall']['proj']['n'],
     'mae': {'incumbent': C['overall']['proj']['mae'], 'naive_STD': C['overall']['STD']['mae']},
     'incumbent_minus_naive': pv(C['paired_vs_baselines']['STD']['mae']), 'reliance': 'HELD_OUT_NO_NEWS_CONDITIONAL',
     'source': 'PLAYER_SCORECARD.json'},
    {'id': 'H3', 'question': 'appearance probability: incumbent p_plays vs naive own-history rate (Brier)',
     'information': 'NO NEWS', 'seasons': '2024 development', 'n': at['appearance']['n'],
     'brier': {'incumbent': at['appearance']['incumbent_p_plays']['brier'], 'naive': at['appearance']['naive_rate_before_W']['brier'],
               'constant_base_rate_reference': at['appearance']['REFERENCE_constant_base_rate_brier']},
     'reliance': 'DEVELOPMENT_DESCRIPTIVE', 'source': 'FORECAST_ERROR_ATLAS.json'},
    {'id': 'H4', 'question': 'D2-ROLE (player-level appearance) vs incumbent and vs naive, unconditional',
     'information': 'NO NEWS', 'seasons': '2025, one logged look (PREVIOUSLY_INSPECTED_SEASON)', 'n': dl['n_unconditional'],
     'mae': {'incumbent': dl['mae_unconditional']['incumbent'], 'D2_ROLE': dl['mae_unconditional']['ROLE'], 'naive_STD_U': dl['naive_STD_U_mae']},
     'D2_minus_incumbent': pv(dl['arms']['ROLE']['unconditional_minus_incumbent']),
     'D2_minus_naive': pv(dl['arms']['ROLE']['minus_naive_STD_U']), 'verdict': dl['VERDICT'],
     'reliance': 'ONE_LOOK_NOT_CONFIRMED', 'source': 'D2_LOOK_2025.json'},
    {'id': 'H5', 'question': 'D2-ROLE on 2024 development (all ablations in the source)', 'information': 'NO NEWS',
     'seasons': '2024 development', 'n': dv['n_unconditional'], 'mae': dv['mae_unconditional'], 'naive_STD_U_mae': dv['naive_STD_U_mae'],
     'D2_minus_naive': pv(dv['arms']['ROLE']['minus_naive_STD_U']), 'reliance': 'DEVELOPMENT_DESCRIPTIVE', 'source': 'D2_DEV_2024.json'},
    {'id': 'H6', 'question': 'D1 target shrink vs incumbent and naive', 'information': 'NO NEWS', 'seasons': '2025, look 1',
     'n': d1['n_unconditional'], 'D1_minus_incumbent': pv(d1['unconditional_D1_minus_incumbent']),
     'D1_minus_naive': pv(d1['vs_naive_STD_U']['D1_minus_naive']), 'verdict': d1['VERDICT'],
     'reliance': 'ONE_LOOK_FAILED_BY_RULE', 'source': 'D1_HOLDOUT_2025.json'},
    {'id': 'H7', 'question': 'incumbent vs a NEWS-ADJUSTED naive baseline on historical seasons (arms B1-B3 vs C)',
     'information': 'would need historical pregame injury and inactive vintages', 'status': 'UNAVAILABLE',
     'reason': 'historical injury files have unknown terms and are withheld (RES-010; owner OD-001 decision 5)'},
]
P = fa['pooled']
prospective = {
    'id': 'P1', 'question': 'complete production forecast C vs news-adjusted simple baselines B1/B2/B3 and naive A',
    'information': "EQUAL: every arm uses the slate's own frozen prelock state (the same availability and depth C consumed)",
    'label': fa['LABEL'], 'decision_status': 'INTERIM / NOT A DECISION (PREREG_FOUR_ARM: 30 prospective games from W6)',
    'n_players': P['n_players'], 'n_games': P['n_games'], 'mae': P['mae'],
    'paired_game_blocked': {k: pv(P[k]) for k in ('C_minus_A', 'C_minus_B1', 'C_minus_B2', 'C_minus_B3')},
    'by_slate': {s: {'n_players': v['n_players'], 'n_games': v['n_games'], 'mae': v['mae'],
                     **{k: v[k]['value'] for k in ('C_minus_B1', 'C_minus_B2', 'C_minus_B3')},
                     'NOTE': 'one game: no interval' if v['n_games'] == 1 else None}
                 for s, v in fa['by_slate'].items()},
    'by_position': {p: {k: pv(v[k]) for k in ('C_minus_B1', 'C_minus_B2', 'C_minus_B3')} for p, v in fa['by_position'].items()},
    'with_2026_history': {k: pv(fa['with_2026_history'][k]) for k in ('C_minus_B1', 'C_minus_B2', 'C_minus_B3')},
    'arm_D': fa['D'], 'source': 'FOUR_ARM_EXPLORATORY.json'}
headline = {
    'QUESTION (OD-003)': 'does the complete football model beat a news-adjusted simple baseline?',
    'PROSPECTIVE_WITH_NEWS': (f"C beats B1, B2 and B3 on 2026 W4-W5 ({P['n_games']} games, {P['n_players']} players): "
                              f"C-B1 {P['C_minus_B1']['value']:+.2f} {P['C_minus_B1']['ci95']}, "
                              f"C-B3 {P['C_minus_B3']['value']:+.2f} {P['C_minus_B3']['ci95']}. EXPLORATORY; INTERIM / NOT A DECISION."),
    'HISTORICAL_WITH_NEWS': 'UNAVAILABLE (RES-010)',
    'HISTORICAL_NO_NEWS': (f"incumbent core LOSES to naive by {U['paired_vs_baselines']['STD_U']['mae']['diff']:+.2f} "
                           f"{U['paired_vs_baselines']['STD_U']['mae']['ci95']} DK MAE (2024-25); "
                           f"challenger D2-ROLE beats naive by {dl['arms']['ROLE']['minus_naive_STD_U']['diff']:+.2f} "
                           f"{dl['arms']['ROLE']['minus_naive_STD_U']['ci95']} on the 2025 look (not confirmed)"),
    'READING': ('NOT RECONCILED. Prospectively C beats baselines that have the SAME news, while historically, with no news on '
                'either side, the incumbent core loses to naive. Two candidate explanations, neither tested: (a) C converts '
                "news into volume redistribution (an absent teammate's targets and carries move to the players who remain), "
                'which the B arms do not do; (b) 11 games over two weeks, already inspected. APPEAR-D1 explains the '
                'historical deficit; whether the core adds value once news is equal is the W6+ pre-registered question.')}
out = {'artifact': 'FAIR_BASELINE_SCORECARD', 'mandate': 'b0540a52 phase 3', 'HEADLINE_FULL_MODEL_VS_NEWS_BASELINE': headline,
       'historical': rows, 'prospective': prospective,
       'inputs_sha256': {'PLAYER_SCORECARD.json': ps_h, 'D1_HOLDOUT_2025.json': d1_h, 'D2_DEV_2024.json': dv_h,
                         'D2_LOOK_2025.json': dl_h, 'FOUR_ARM_EXPLORATORY.json': fa_h, 'FORECAST_ERROR_ATLAS.json': at_h},
       'NOT_SCORED': {'K_DST': 'no panel actuals for kickers and team defences', 'external_vendors': 'no timestamped archive (RES-011)'}}
print(json.dumps(out, indent=1))
