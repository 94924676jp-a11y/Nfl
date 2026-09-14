"""Product quality gates: what may reach a reader, and what may not.

THE CONTRACT THIS IMPLEMENTS, IN ONE LINE
=========================================
"Do not publish nonsense because the simulator completed." A completed
simulation is a statement about the process, not about the numbers. This
module is the only place that turns sealed draws into a PUBLISH / WITHHOLD /
QUARANTINE answer, and it does so from measured facts about the artifact --
never from whether anything raised.

HARD AND SOFT ARE DIFFERENT OBJECTS AND ARE NEVER COMPOSED
==========================================================
A HARD gate WITHHOLDS or QUARANTINES the family or board it fires on. A SOFT
diagnostic FLAGS FOR REVIEW and changes no distribution, no state and no
pointer. The separation is the external contract's, verbatim in intent: a
healthy-QB1 low mean is a prompt to inspect starter probability and exit or
replacement -- it is NOT a yardage floor, and nothing here ever imposes one.
No gate in this file writes into a draw array, clips, renormalises, rescales
or repairs. `test_quality_gates.py` asserts that on the AST.

STRUCTURAL IMPOSSIBILITY BEATS UNUSUAL NUMBER
=============================================
Where a gate could be written either way it is written as a contradiction the
board makes with ITSELF -- a room dealt more carries than its team has, a
count metric whose draws are not integers, a row that is simultaneously the
depth chart's QB1 and a 41% chance of never taking a snap -- rather than as a
percentile. An unusual number is a SOFT diagnostic here, always, because
"unusual" is a property of the reference frame and the frame is small.

EVERY THRESHOLD IS A MEASUREMENT WITH A CITATION
================================================
`GROUNDING` below carries, for each constant, the value, the sample it came
from, and the artifact path it was read out of. There are no tuned constants
in this file. A threshold with no entry in `GROUNDING` fails
`test_quality_gates.py::test_every_threshold_is_grounded`.

WHAT THIS MODULE DOES NOT DO
============================
It does not authorize publication. `nfl.production.authorization.may_publish`
is the only function permitted to say a forecast may be published, and
`board_pointer` consults it separately. Passing every gate here means the
board is not obviously broken; it does not mean anyone said it may be shown.
No sportsbook price is read anywhere in this file: a price is never an input
to a gate.
"""
from __future__ import annotations

import json
import pathlib

import numpy as np

from sportsplatform.governance.outcome import Cause, Outcome
from nfl.product import decomposition as DEC
from nfl.product import metrics as M

SPEC_VERSION = 'nfl-product-quality-gates-1'
_REPO = pathlib.Path(__file__).resolve().parents[2]


# ===========================================================================
# JOB 3 -- THE PRODUCT STATE VOCABULARY
#
# Nine states, declared once. The rule that makes them worth having:
# `carries_a_number` is False for six of them, and a renderer that substitutes
# a number for any of those six has replaced missingness with a fabrication.
# A blank cell looks like a bug and a plausible number looks like a feature;
# the state is the report.
# ===========================================================================
FINAL = 'FINAL'
PRELIMINARY = 'PRELIMINARY'
UNVALIDATED = 'UNVALIDATED'
WITHHELD = 'WITHHELD'
UNAVAILABLE = 'UNAVAILABLE'
DATA_ERROR = 'DATA_ERROR'
MODEL_ERROR = 'MODEL_ERROR'
INSUFFICIENT_EVIDENCE = 'INSUFFICIENT_EVIDENCE'
INELIGIBLE = 'INELIGIBLE'

PRODUCT_STATES = {
    FINAL: {
        'means': 'every input this number depends on is authoritative and '
                 'settled; nothing outstanding can move it',
        'carries_a_number': True, 'publishable': True,
        'note': 'FINAL requires authoritative inactives. It is not reachable '
                'on a board built before the official list exists, and a '
                'board that claims it without one is claiming an input it '
                'does not hold.'},
    PRELIMINARY: {
        'means': 'produced from the best information available at the seal, '
                 'with named inputs still outstanding',
        'carries_a_number': True, 'publishable': True,
        'note': 'the number is shown WITH the outstanding inputs named.'},
    UNVALIDATED: {
        'means': 'produced, and no quality gate has been evaluated against it',
        'carries_a_number': True, 'publishable': False,
        'note': 'distinct from PRELIMINARY: there, gates ran and passed.'},
    WITHHELD: {
        'means': 'produced, and a HARD gate refuses to show it',
        'carries_a_number': False, 'publishable': False,
        'note': 'the number exists and is deliberately not shown. The gate '
                'that withheld it is named to the reader.'},
    UNAVAILABLE: {
        'means': 'no governed layer produces this quantity at all',
        'carries_a_number': False, 'publishable': False,
        'note': 'a standing absence in the model, not an incident. K and DST '
                'are here tonight.'},
    DATA_ERROR: {
        'means': 'an input was missing, empty, or out of its declared schema',
        'carries_a_number': False, 'publishable': False,
        'note': 'the defect is upstream of the model.'},
    MODEL_ERROR: {
        'means': 'the engine produced something structurally impossible',
        'carries_a_number': False, 'publishable': False,
        'note': 'the defect is in the model, not the inputs.'},
    INSUFFICIENT_EVIDENCE: {
        'means': 'a gate could not be evaluated because the evidence it takes '
                 'does not exist',
        'carries_a_number': False, 'publishable': False,
        'note': 'THE STATE THIS VOCABULARY EXISTS FOR. An unevaluated gate is '
                'not a passed gate, and the difference is the whole of the '
                'project Class A defect. Tonight every authoritative-inactive '
                'gate lands here.'},
    INELIGIBLE: {
        'means': 'a governance rule excludes this row or family from the '
                 'product regardless of its numbers',
        'carries_a_number': False, 'publishable': False,
        'note': 'a decision, not a defect.'},
}

# The two states people reach for when they mean the other one.
NOT_A_PASS = (WITHHELD, UNAVAILABLE, DATA_ERROR, MODEL_ERROR,
              INSUFFICIENT_EVIDENCE, INELIGIBLE, UNVALIDATED)


# ===========================================================================
# GROUNDING -- every constant this file uses, with the sample it came from.
# ===========================================================================
GROUNDING = {
    'QB1_ZERO_MASS_EVIDENCE_BOUND': {
        'value': 0.0234,
        'measured': 'week-1 depth-chart rank-1 quarterbacks, 2021-2024, '
                    'forward-chained: 0 zero-dropback games in 128. The '
                    'rule-of-three 95% upper bound on a 0/128 rate.',
        'n': 128, 'realised_events': 0,
        'source': 'nfl/research/v2/d5/D5_ZERO_MASS_AUDIT.md#2.3'},
    'QB1_ZERO_MASS_MATERIAL': {
        'value': 0.25,
        'measured': 'on the same 128-game frame the model assigns >= 0.25 '
                    'zero mass to 39.8% of week-1 chart QB1s while the '
                    'realised rate is 0/128. 0.25 is 10.7x the rule-of-three '
                    'bound and is the level at which the model is asserting '
                    'a one-in-four chance of an event never once observed in '
                    'the frame.',
        'n': 128, 'model_frac_at_or_above': 0.398,
        'source': 'nfl/research/v2/d5/D5_ZERO_MASS_AUDIT.md#2.3'},
    'SPLIT_ROOM_BASE_RATE': {
        'value': 0.078,
        'measured': 'share of team-games with two or more passers at >= 5 '
                    'dropbacks: 0.039 historically in week 1 and 0.078 in '
                    'weeks 2+, against 0.000 realised in 2026 week 1 and '
                    '0.333 projected by the model.',
        'model': 0.333, 'realised_2026w1': 0.0, 'hist_w1': 0.039,
        'hist_w2plus': 0.078,
        'source': 'nfl/research/v2/d7/D7_CENTRAL_TENDENCY_SCORECARD.md#3'},
    'TOP_PASSER_SHARE_HISTORICAL': {
        'value': 0.9289,
        'measured': 'mean top-passer share: model 0.7767, realised 2026 wk1 '
                    '0.9898, historical wk1 0.9289, wks 2+ 0.9223. Reported, '
                    'not triggered on -- see SOFT_DIAGNOSTICS.',
        'source': 'nfl/research/v2/d7/D7_CENTRAL_TENDENCY_SCORECARD.md#3'},
    'RUSH_UNOWNED_CORPUS_RANGE': {
        'value': (0.00616, 0.45290), 'mean': 0.24100,
        'measured': '67 sealed team-runs that have a rushing layer: mean '
                    'unowned share 24.100%, range 0.616%-45.290%. The low '
                    'end IS tonight\'s KC board, so the range includes it '
                    'rather than excluding it by rounding. Re-derived '
                    'from the 102 sealed runs on 2026-09-14 and reproducing '
                    'D6 exactly.',
        'n_team_runs': 67,
        'source': 'nfl/research/v2/d6/D6_CONSERVATION_DASHBOARD.md#5'},
    'RUSH_OVERALLOCATION_TOLERANCE': {
        'value': 0.5,
        'measured': 'half a carry. The largest observed over-allocation in '
                    'the sealed corpus is 13.45 carries above the team level '
                    '(ARI_LAC/LAC), three orders above float32 noise, so the '
                    'tolerance separates a real over-deal from rounding and '
                    'is not a materiality judgement.',
        'observed_max_overshoot': 13.447,
        'source': 'nfl/research/v2/d6/D6_CONSERVATION_DASHBOARD.md#5'},
    'COUNT_NONINTEGER_LEAGUE_RATE': {
        'value': 0.6348,
        'measured': "rushing__carries is declared kind:'count' in "
                    'nfl/product/metrics.py and is float64: 243,766 of '
                    '384,000 draw cells are non-integer across the 102 '
                    'sealed runs (63.48%).',
        'source': 'nfl/product/metrics.py + the sealed corpus'},
    'INACTIVE_FORECAST_PARTICIPATION': {
        'value': 0.247,
        'measured': '28 players on an official inactive list who took zero '
                    'snaps carried mean forecast participation 0.247 across '
                    '144 rows, 101 of them with a strictly positive '
                    "projection. ATL's QB1 was listed Out 42.7h before the "
                    'seal and was still projected 19.7 dropbacks.',
        'n_players': 28, 'n_rows': 144, 'realised': 0.0,
        'source': 'nfl/research/v2/d7/D7_CENTRAL_TENDENCY_SCORECARD.md#5'},
}

HARD = 'HARD'
SOFT = 'SOFT'
ROW, FAMILY, BOARD_SCOPE = 'ROW', 'FAMILY', 'BOARD'

QUARANTINE_FAMILY = 'QUARANTINE_FAMILY'
WITHHOLD_BOARD = 'WITHHOLD_BOARD'
WITHHOLD_ROW = 'WITHHOLD_ROW'
FLAG_FOR_REVIEW = 'FLAG_FOR_REVIEW'

PASS = 'PASS'
FIRED = 'FIRED'
NOT_APPLICABLE = 'NOT_APPLICABLE'


# ===========================================================================
# THE GATE DECLARATIONS. Data, so that a reader and a test see the same set.
# ===========================================================================
GATES = {
    'HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY': {
        'class': HARD, 'scope': ROW, 'action': WITHHOLD_ROW,
        'asserts': 'a row the board itself labels the depth chart QB1, with '
                   'no withholding designation on any status source it '
                   'carries, does not also carry material probability of '
                   'never taking a snap',
        'structural': 'it is a contradiction between two of the board\'s own '
                      'fields, not a percentile: depth_chart says QB1 and '
                      'P(dropbacks == 0) says he may not play',
        'threshold': 'QB1_ZERO_MASS_MATERIAL',
        'soft_companion': 'QB1_ZERO_MASS_EVIDENCE_BOUND'},
    'QB_ROOM_SPLIT_ANOMALY': {
        'class': HARD, 'scope': FAMILY, 'action': QUARANTINE_FAMILY,
        'asserts': 'the modelled quarterback room does not project a split '
                   'room at a rate the record contradicts',
        'structural': 'not a structural impossibility and it is not written '
                      'as one: it triggers on a forecast probability against '
                      'a measured base rate, and it quarantines only the one '
                      'team\'s QB family',
        'threshold': 'SPLIT_ROOM_BASE_RATE'},
    'ROLE_STATE_SOURCE_CONFLICT': {
        'class': HARD, 'scope': FAMILY, 'action': QUARANTINE_FAMILY,
        'asserts': 'the sources that determine a role state agree, and each '
                   'source the board declares it depends on was actually '
                   'consumed',
        'structural': 'the board is asserting a role while recording that '
                      'the evidence for that role was not ingested, or that '
                      'two sources said different things',
        'threshold': None},
    'AUTHORITATIVE_INACTIVE_NONZERO_OPPORTUNITY': {
        'class': HARD, 'scope': ROW, 'action': WITHHOLD_ROW,
        'asserts': 'no player on an ingested authoritative inactive list '
                   'carries any opportunity mass',
        'structural': 'a player who is officially inactive cannot receive a '
                      'snap. Any positive mass is impossible, not unlikely.',
        'threshold': 'INACTIVE_FORECAST_PARTICIPATION',
        'evidence_required': 'an ingested official inactive list tied to this '
                             'game and both clubs. Without it this gate is '
                             'INSUFFICIENT_EVIDENCE and never PASS.'},
    'RUSH_ACCOUNTING_FAILURE': {
        'class': HARD, 'scope': FAMILY, 'action': QUARANTINE_FAMILY,
        'asserts': 'the rush owners the board names are never dealt more '
                   'carries than their team\'s own carry level, and the '
                   'recovered designed-rush component is never negative',
        'structural': 'sum(owners) > team level is arithmetically impossible '
                      'football. So is a negative count of designed runs.',
        'threshold': 'RUSH_OVERALLOCATION_TOLERANCE'},
    'COUNT_SUPPORT_FAILURE': {
        'class': HARD, 'scope': ROW, 'action': WITHHOLD_ROW,
        'asserts': "every metric declared kind:'count' has integer, "
                   'non-negative draws',
        'structural': 'a count with fractional support cannot occur. Every '
                      'threshold probability published off it -- "10+ '
                      'carries" -- is computed on values the world cannot '
                      'produce.',
        'threshold': None,
        'grounding_ref': 'COUNT_NONINTEGER_LEAGUE_RATE'},
    'IDENTITY_DEPTH_ROLE_CONFLICT': {
        'class': HARD, 'scope': ROW, 'action': WITHHOLD_ROW,
        'asserts': 'a published row resolves to one player: a position the '
                   'product declares, layers that position is allowed to '
                   'draw from, a depth-chart rank whose position tag matches '
                   'that position, and a human-readable name',
        'structural': 'a row that cannot be rendered as a person, or whose '
                      'depth chart and roster disagree about what he plays, '
                      'is not a product row whatever numbers it carries',
        'threshold': None,
        'board_escalation': 'when every row fails the name condition the '
                            'board itself is unrenderable and the finding is '
                            'escalated to WITHHOLD_BOARD'},
    'UNATTRIBUTED_OPPORTUNITY_MASS': {
        'class': HARD, 'scope': FAMILY, 'action': QUARANTINE_FAMILY,
        'asserts': 'a team pool the board publishes shares against has at '
                   'least one modelled owner',
        'structural': 'a pool with positive mass and zero owner rows means '
                      'every share published against it has a denominator no '
                      'row can be checked against; the mass is not merely '
                      'unusual, it is unattributable in principle',
        'threshold': 'RUSH_UNOWNED_CORPUS_RANGE'},
}

# SOFT diagnostics. They FLAG. They never quarantine, never withhold, never
# change a distribution, and -- stated because the external contract states it
# -- they never impose a floor on any yardage or any other quantity.
SOFT_DIAGNOSTICS = {
    'HEALTHY_QB1_ZERO_MASS_ABOVE_EVIDENCE_BOUND': {
        'class': SOFT, 'action': FLAG_FOR_REVIEW,
        'inspect': 'starter probability, and the exit / replacement model',
        'never': 'no yardage floor, no rescaling, no clipping of the zero '
                 'mass. The board keeps the distribution it computed.',
        'threshold': 'QB1_ZERO_MASS_EVIDENCE_BOUND'},
    'HEALTHY_QB1_LOW_CENTRAL_TENDENCY': {
        'class': SOFT, 'action': FLAG_FOR_REVIEW,
        'inspect': 'starter probability and the exit / replacement model -- '
                   'a low mean on a healthy QB1 is nearly always mass moved '
                   'off him, not a view about his passing',
        'never': 'NOT a yardage floor. This diagnostic must never be '
                 'discharged by raising a projection.',
        'threshold': None},
    'ROOM_TOP_SHARE_BELOW_HISTORICAL': {
        'class': SOFT, 'action': FLAG_FOR_REVIEW,
        'inspect': 'the room allocation, against the 0.9289 historical mean',
        'never': 'no reallocation is performed here',
        'threshold': 'TOP_PASSER_SHARE_HISTORICAL'},
    'RUSH_UNOWNED_SHARE_OUTSIDE_CORPUS_RANGE': {
        'class': SOFT, 'action': FLAG_FOR_REVIEW,
        'inspect': "A1's kneel / wr / te / fringe categories, which own the "
                   'residual lawfully and are not sealed as rows',
        'never': 'a positive residual is expected and lawful; it is not a '
                 'defect and is never repaired',
        'threshold': 'RUSH_UNOWNED_CORPUS_RANGE'},
    'DEGENERATE_DISTRIBUTION_WIDTH': {
        'class': SOFT, 'action': FLAG_FOR_REVIEW,
        'inspect': 'whether the middle half of the draws being identical is '
                   'a real point mass or a collapsed allocation',
        'never': 'the distribution is not widened to satisfy this',
        'threshold': None},
}


# ===========================================================================
# FAMILIES THAT DO NOT EXIST IN THE ENGINE AT ALL  (Job 3, K and DST)
#
# Verified against the code, not asserted. `verify_absent_families()` reads
# the product metric registry and refuses to report an absence it cannot see.
# ===========================================================================
ABSENT_FAMILIES = {
    'K': {
        'state': UNAVAILABLE,
        'code': 'NO_KICKING_OR_SCORING_CONTRACT',
        'why': 'the engine models no kicking opportunity and no scoring '
               'contract. nfl/product/metrics.py POSITION_LAYERS declares '
               'only QB, RB, WR and TE; no field-goal, extra-point, kicking '
               'distance or team-points quantity is declared in SUPPORTED, '
               'produced by any production layer, or sealed in any draw '
               'array. The only occurrence of "field goal" in the tree is a '
               'play-type carve-out in nfl/accounting/invariants.py for a '
               'blocked field goal in historical play-by-play.',
        'would_need': ['a team scoring-drive / red-zone conversion layer that '
                       'produces field-goal ATTEMPTS as a distribution, not a '
                       'rate applied to a mean',
                       'a distance distribution for those attempts, since '
                       'make probability is a function of distance and a '
                       'pooled make rate would misstate its own uncertainty',
                       'an extra-point opportunity count, which is a function '
                       'of modelled touchdowns the team layer does not close '
                       '(team_touchdowns_close is already a declared ABSENT '
                       'contract in nfl/product/conservation.py)',
                       'a kicker identity and status feed; kickers are not in '
                       'the roster reduce that reaches the board']},
    'DST': {
        'state': UNAVAILABLE,
        'code': 'NO_OPPONENT_LINKED_DEFENSIVE_LAYER',
        'why': 'no opponent-linked defensive layer exists. The only sack '
               'quantity in the artifact is qb/sacks, which is sacks TAKEN '
               'by the passer on the offensive side of the ledger and is '
               'never credited to a defence. qb/int is interceptions thrown, '
               'not takeaways forced. The single place an opponent is read '
               'at all is coupling_rho at '
               'nfl/production/team_volume_v1.py:364, which couples two '
               "teams' VOLUME and produces no defensive quantity. There is "
               'no points-allowed, yards-allowed, takeaway or defensive-'
               'touchdown distribution anywhere under nfl/production, and '
               'nfl/product/metrics.py declares none.',
        'would_need': ['an offence-defence join so that one team\'s allowed '
                       'stats are the other team\'s produced stats on the '
                       'SAME draw index -- today the two teams are seeded '
                       'independently and the manifest says so '
                       '(draw_index_semantics.across_rows = '
                       'INDEPENDENT_STREAMS_COLUMN_ALIGNED)',
                       'a turnover layer: qb/int exists but fumbles do not, '
                       'and a takeaway count built from interceptions alone '
                       'would be a systematic undercount presented as a '
                       'forecast',
                       'a points-allowed contract, which requires the same '
                       'scoring layer K needs',
                       'special-teams and defensive touchdowns, which no '
                       'layer produces']},
}


def verify_absent_families() -> dict:
    """Re-derive the K and DST absences from the registry. Never asserted."""
    out = {}
    positions = set(M.POSITION_LAYERS)
    declared = {f'{a}/{b}' for (a, b) in M.SUPPORTED}
    declared |= {f'{a}/{b}' for (a, b) in M.UNSUPPORTED}
    kick_words = ('field_goal', 'fg', 'extra_point', 'xp', 'kick', 'punt')
    def_words = ('sack_made', 'takeaway', 'allowed', 'defensive', 'dst',
                 'points_allowed')
    for fam, words in (('K', kick_words), ('DST', def_words)):
        hits = sorted(m for m in declared
                      if any(w in m.lower() for w in words))
        out[fam] = {
            'position_in_POSITION_LAYERS': fam in positions,
            'declared_metrics_matching': hits,
            'verified_absent': (fam not in positions and not hits),
            'positions_the_product_declares': sorted(positions)}
    return out


# ===========================================================================
# helpers
# ===========================================================================
def _finding(gate, scope, subject, state, why, **measured):
    d = GATES.get(gate) or SOFT_DIAGNOSTICS.get(gate) or {}
    key = d.get('threshold')
    return {'gate': gate, 'class': d.get('class', HARD), 'scope': scope,
            'subject': subject, 'state': state, 'why': why,
            'action': (d.get('action') if state == FIRED else None),
            'threshold_key': key,
            'threshold': (GROUNDING[key]['value'] if key else None),
            'grounding': (GROUNDING[key] if key else None),
            'measured': measured, 'spec_version': SPEC_VERSION}


def _team_of(board) -> dict:
    return {p['gsis_id']: p.get('team') for p in (board.get('players') or [])}


def _rows_for(manifest, layer, team_of, team):
    rows = DEC.rows_of(manifest, layer)
    return {g: i for g, i in rows.items() if team_of.get(g) == team}


def _withholding_status(player) -> str | None:
    """A designation on this row that would explain a zero. None if clean.

    Read from the board row only. A status this board does not carry is
    reported as absent by the caller, not invented here.
    """
    conf = (player.get('confidence') or {}).get('reasons') or {}
    txt = str(conf.get('status_certainty') or '')
    for token in ('OUT', 'DOUBTFUL', 'INACTIVE', 'SUSPENDED',
                  'Out', 'Doubtful', 'Inactive'):
        if token in txt:
            return token
    return None


# ===========================================================================
# THE GATES
# ===========================================================================
def gate_healthy_qb1_zero_opportunity(board, manifest, draws) -> list:
    out = []
    team_of = _team_of(board)
    try:
        qrows = DEC.rows_of(manifest, 'qb')
        db = DEC.matrix(draws, 'qb', 'db')
    except DEC.DecompositionInputError as e:
        return [_finding('HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY', BOARD_SCOPE,
                         'BOARD', INSUFFICIENT_EVIDENCE, str(e))]
    hard = GROUNDING['QB1_ZERO_MASS_MATERIAL']['value']
    soft = GROUNDING['QB1_ZERO_MASS_EVIDENCE_BOUND']['value']
    for p in board.get('players') or []:
        if p.get('depth_chart') != 'QB1' or p['gsis_id'] not in qrows:
            continue
        gid = p['gsis_id']
        pz = float((db[qrows[gid]] == 0).mean())
        status = _withholding_status(p)
        subj = f'{team_of.get(gid)}/{gid}'
        m = {'p_zero_dropbacks': round(pz, 6),
             'withholding_status_on_row': status,
             'mean_dropbacks': round(float(db[qrows[gid]].mean()), 4),
             'ratio_to_evidence_bound': round(pz / soft, 2)}
        if status is not None:
            out.append(_finding(
                'HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY', ROW, subj,
                NOT_APPLICABLE,
                f'the row carries designation {status!r}, so zero mass is '
                f'explained by a status rather than by the room allocation',
                **m))
            continue
        if pz >= hard:
            out.append(_finding(
                'HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY', ROW, subj, FIRED,
                f'the board labels this row QB1 and carries no withholding '
                f'designation for him, and simultaneously assigns '
                f'P(zero dropbacks) = {pz:.4f}. The realised rate of that '
                f'event among week-1 chart QB1s is 0 of 128.', **m))
        else:
            out.append(_finding(
                'HEALTHY_QB1_ZERO_OPPORTUNITY_ANOMALY', ROW, subj, PASS,
                f'P(zero dropbacks) = {pz:.4f} is below the {hard} '
                f'materiality line', **m))
        if soft < pz < hard:
            out.append(_finding(
                'HEALTHY_QB1_ZERO_MASS_ABOVE_EVIDENCE_BOUND', ROW, subj,
                FIRED,
                f'P(zero dropbacks) = {pz:.4f} exceeds the rule-of-three 95% '
                f'upper bound of {soft} on a 0/128 realised rate. Inspect '
                f'starter probability and the exit / replacement model. This '
                f'is NOT a yardage floor and nothing is rescaled.', **m))
    return out


def gate_qb_room_split(board, manifest, draws) -> list:
    out = []
    team_of = _team_of(board)
    try:
        db = DEC.matrix(draws, 'qb', 'db')
    except DEC.DecompositionInputError as e:
        return [_finding('QB_ROOM_SPLIT_ANOMALY', BOARD_SCOPE, 'BOARD',
                         INSUFFICIENT_EVIDENCE, str(e))]
    thr = GROUNDING['SPLIT_ROOM_BASE_RATE']['value']
    hist = GROUNDING['TOP_PASSER_SHARE_HISTORICAL']['value']
    for team in sorted(board.get('teams') or []):
        rows = _rows_for(manifest, 'qb', team_of, team)
        subj = f'{team}/qb'
        if not rows:
            out.append(_finding('QB_ROOM_SPLIT_ANOMALY', FAMILY, subj,
                                INSUFFICIENT_EVIDENCE,
                                'no quarterback rows are sealed for this team'))
            continue
        sub = db[sorted(rows.values())]
        p_split = float(((sub >= 5).sum(0) >= 2).mean())
        tot = np.maximum(sub.sum(0), 1e-9)
        top_share = float((sub.max(0) / tot).mean())
        m = {'p_two_or_more_qbs_at_5plus_dropbacks': round(p_split, 6),
             'mean_top_passer_share': round(top_share, 6),
             'room_size': int(sub.shape[0]),
             'historical_base_rate_w2plus': thr,
             'realised_2026_week1': 0.0,
             'ratio_to_base_rate': round(p_split / thr, 2)}
        if p_split > thr:
            out.append(_finding(
                'QB_ROOM_SPLIT_ANOMALY', FAMILY, subj, FIRED,
                f'this room projects a two-passer game with probability '
                f'{p_split:.4f}, {p_split / thr:.1f}x the highest measured '
                f'base rate ({thr} in weeks 2+; 0.039 in week 1; 0.000 '
                f'realised in 2026 week 1).', **m))
        else:
            out.append(_finding('QB_ROOM_SPLIT_ANOMALY', FAMILY, subj, PASS,
                                f'{p_split:.4f} is within the measured base '
                                f'rate', **m))
        if top_share < hist:
            out.append(_finding(
                'ROOM_TOP_SHARE_BELOW_HISTORICAL', FAMILY, subj, FIRED,
                f'mean top-passer share {top_share:.4f} is below the '
                f'historical week-1 mean {hist}. Reported for inspection of '
                f'the room allocation; nothing is reallocated here.', **m))
    return out


def gate_role_state_source_conflict(board, manifest, draws) -> list:
    """Sources that determine a role state must agree AND must have been read."""
    out = []
    own = board.get('qb_inactive_ownership') or {}
    ready = board.get('readiness') or {}
    vint = board.get('vintage_selection') or {}
    refusals = vint.get('refusals') or []
    failed = list(own.get('failed_conditions') or [])
    for team in sorted(board.get('teams') or []):
        subj = f'{team}/qb'
        r = ready.get(team) or {}
        conflicts = []
        if failed and not own.get('enforced', False):
            conflicts.append(
                f'the board publishes a quarterback room whose inactive '
                f'ownership mechanism reports enforced=False with failed '
                f'conditions {failed}; the role state shown is therefore not '
                f'sourced from the authority the board names as its own')
        if r.get('state') and r['state'] != 'READY':
            conflicts.append(
                f'the readiness source for {team} is {r["state"]}: '
                f'{r.get("reason", "")}')
        for ref in refusals:
            conflicts.append(
                f'a perishable role input was refused: {ref.get("input")} '
                f'-> {ref.get("code")}')
        m = {'inactive_ownership_enforced': bool(own.get('enforced', False)),
             'failed_conditions': failed,
             'readiness_state': r.get('state'),
             'vintage_refusals': [x.get('code') for x in refusals]}
        if conflicts:
            out.append(_finding('ROLE_STATE_SOURCE_CONFLICT', FAMILY, subj,
                                FIRED, ' AND '.join(conflicts), **m))
        else:
            out.append(_finding('ROLE_STATE_SOURCE_CONFLICT', FAMILY, subj,
                                PASS, 'every role-state source the board '
                                      'names was consumed and agrees', **m))
    return out


def gate_authoritative_inactive(board, manifest, draws, inactives=None) -> list:
    """Fires on impossible mass. Without an ingested list it does NOT pass."""
    own = board.get('qb_inactive_ownership') or {}
    ingested = bool(own.get('enforced')) or bool(inactives)
    if not ingested:
        return [_finding(
            'AUTHORITATIVE_INACTIVE_NONZERO_OPPORTUNITY', BOARD_SCOPE,
            'BOARD', INSUFFICIENT_EVIDENCE,
            'no authoritative inactive list is ingested for this game, so '
            'this gate has no evidence to evaluate. It is NOT passed. The '
            'measured cost of treating it as passed: 28 officially inactive '
            'players carried mean forecast participation 0.247 with 101 of '
            '144 rows strictly positive, and one club\'s QB1 was projected '
            '19.7 dropbacks 42.7 hours after being listed Out.',
            failed_conditions=list(own.get('failed_conditions') or []),
            ingested_list=None)]
    out = []
    team_of = _team_of(board)
    listed = set(inactives or own.get('inactive_qbs_in_modelled_room') or {})
    for p in board.get('players') or []:
        gid = p['gsis_id']
        if gid not in listed:
            continue
        mass = 0.0
        for layer, metric in (('qb', 'db'), ('receiving', 'targets'),
                              ('rushing', 'carries')):
            rows = DEC.rows_of(manifest, layer)
            if gid in rows:
                try:
                    v = DEC.matrix(draws, layer, metric)[rows[gid]]
                except DEC.DecompositionInputError:
                    continue
                mass = max(mass, float((np.asarray(v) > 0).mean()))
        subj = f'{team_of.get(gid)}/{gid}'
        m = {'p_any_opportunity': round(mass, 6), 'on_official_list': True}
        if mass > 0:
            out.append(_finding(
                'AUTHORITATIVE_INACTIVE_NONZERO_OPPORTUNITY', ROW, subj,
                FIRED,
                f'this player is on the ingested official inactive list and '
                f'carries opportunity in {mass:.1%} of draws. An inactive '
                f'player cannot take a snap; this is impossible mass, not '
                f'unlikely mass.', **m))
        else:
            out.append(_finding(
                'AUTHORITATIVE_INACTIVE_NONZERO_OPPORTUNITY', ROW, subj,
                PASS, 'on the official list and carries zero mass', **m))
    return out


def gate_rush_accounting(board, manifest, draws) -> list:
    """Over-allocation and negative designed rush. Arithmetic, not taste."""
    out = []
    team_of = _team_of(board)
    tol = GROUNDING['RUSH_OVERALLOCATION_TOLERANCE']['value']
    lo, hi = GROUNDING['RUSH_UNOWNED_CORPUS_RANGE']['value']
    for team in sorted(board.get('teams') or []):
        subj = f'{team}/rushing'
        qrows = _rows_for(manifest, 'qb', team_of, team)
        rrows = _rows_for(manifest, 'rushing', team_of, team)
        trows = DEC.rows_of(manifest, 'team_volume')
        if team not in trows or not qrows:
            out.append(_finding('RUSH_ACCOUNTING_FAILURE', FAMILY, subj,
                                INSUFFICIENT_EVIDENCE,
                                'no team carry level or no quarterback rows '
                                'are sealed for this team'))
            continue
        try:
            ro = DEC.matrix(draws, 'qb', 'rush_opp')[sorted(qrows.values())]
            scr = DEC.matrix(draws, 'qb', 'scr')[sorted(qrows.values())]
            lev = DEC.matrix(draws, 'team_volume', 'team_carries')[trows[team]]
        except DEC.DecompositionInputError as e:
            out.append(_finding('RUSH_ACCOUNTING_FAILURE', FAMILY, subj,
                                INSUFFICIENT_EVIDENCE, str(e)))
            continue
        RO, SC = ro.sum(0), scr.sum(0)
        DES = RO - SC
        n_neg = int((DES < -1e-9).sum())
        if rrows:
            RB = DEC.matrix(draws, 'rushing',
                            'carries')[sorted(rrows.values())].sum(0)
        else:
            RB = np.zeros_like(np.asarray(lev, float))
        owners = np.asarray(RB, float) + np.asarray(SC, float) \
            + np.asarray(DES, float)
        over = owners - np.asarray(lev, float)
        n_over = int((over > tol).sum())
        resid = float((np.asarray(lev, float) - owners).mean()
                      / max(float(np.asarray(lev, float).mean()), 1e-9))
        m = {'n_draws': int(np.asarray(lev).size),
             'draws_over_allocated': n_over,
             'max_over_allocation_carries': round(float(over.max()), 4),
             'draws_with_negative_designed_rush': n_neg,
             'mean_unowned_share': round(resid, 6),
             'corpus_range': [lo, hi],
             'rb_rows_sealed': len(rrows)}
        if n_over or n_neg:
            bits = []
            if n_over:
                bits.append(
                    f'{n_over} of {m["n_draws"]} draws deal the named rush '
                    f'owners MORE carries than the team\'s own carry level, '
                    f'by up to {over.max():.2f} carries')
            if n_neg:
                bits.append(f'{n_neg} draws recover a NEGATIVE designed-rush '
                            f'count')
            out.append(_finding('RUSH_ACCOUNTING_FAILURE', FAMILY, subj,
                                FIRED, '; '.join(bits) + '. Both are '
                                'arithmetically impossible, independent of '
                                'any view about the forecast.', **m))
        else:
            out.append(_finding('RUSH_ACCOUNTING_FAILURE', FAMILY, subj, PASS,
                                'no draw over-allocates the carry level and '
                                'no designed-rush count is negative', **m))
        if rrows and not (lo <= resid <= hi):
            out.append(_finding(
                'RUSH_UNOWNED_SHARE_OUTSIDE_CORPUS_RANGE', FAMILY, subj,
                FIRED,
                f'mean unowned rush share {resid:.4f} is outside the sealed '
                f'corpus range [{lo}, {hi}] over 67 team-runs. A positive '
                f'residual is lawful -- A1\'s kneel / wr / te / fringe own '
                f'it -- so this flags for inspection and repairs nothing. '
                f'Note also that a SMALL mean residual is cancellation, not '
                f'closure: the boards with the smallest means carry the '
                f'largest over-allocation counts.', **m))
    return out


def gate_count_support(board, manifest, draws) -> list:
    """A metric declared a count whose draws are not counts."""
    out = []
    team_of = _team_of(board)
    for (layer, key), spec in sorted(M.SUPPORTED.items()):
        if spec.get('kind') != 'count':
            continue
        try:
            arr = np.asarray(DEC.matrix(draws, layer, key), float)
            rows = DEC.rows_of(manifest, layer)
        except DEC.DecompositionInputError:
            continue                      # layer absent: other gates own that
        for gid, i in sorted(rows.items(), key=lambda kv: kv[1]):
            v = arr[i]
            n_frac = int((v != np.round(v)).sum())
            n_neg = int((v < 0).sum())
            subj = f'{team_of.get(gid)}/{gid}/{layer}/{key}'
            m = {'metric': f'{layer}/{key}', 'declared_kind': 'count',
                 'dtype': str(arr.dtype), 'n_draws': int(v.size),
                 'non_integer_cells': n_frac, 'negative_cells': n_neg,
                 'league_rate_for_this_metric':
                     GROUNDING['COUNT_NONINTEGER_LEAGUE_RATE']['value']
                     if f'{layer}/{key}' == 'rushing/carries' else None}
            if n_frac or n_neg:
                out.append(_finding(
                    'COUNT_SUPPORT_FAILURE', ROW, subj, FIRED,
                    f'{layer}/{key} is declared kind=\'count\' in '
                    f'nfl/product/metrics.py and carries {n_frac} '
                    f'non-integer and {n_neg} negative draw cells out of '
                    f'{v.size}. Every threshold probability published off '
                    f'this row is computed on support the world cannot '
                    f'produce.', **m))
            else:
                out.append(_finding('COUNT_SUPPORT_FAILURE', ROW, subj, PASS,
                                    f'{layer}/{key} draws are integer and '
                                    f'non-negative', **m))
    return out


def gate_identity_depth_role(board, manifest, draws, names=None) -> list:
    """One row must resolve to one renderable person."""
    out = []
    names = names or {}
    n_rows = 0
    n_nameless = 0
    for p in board.get('players') or []:
        gid = p.get('gsis_id')
        n_rows += 1
        pos = p.get('position')
        dr = p.get('depth_chart')
        layers = set(p.get('layers') or [])
        name = p.get('name') or names.get(gid)
        problems = []
        if not name:
            n_nameless += 1
            problems.append(
                'the row carries no human-readable name. board.build never '
                'joins one: nfl/product/names.py exists and is used by the '
                'market tools, and the board does not call it, while the '
                'reduced roster vintage the board DOES read drops full_name '
                'in its reduce_cols. A board that renders a gsis_id where a '
                'person belongs is not a product row.')
        if not pos or pos == 'UNKNOWN':
            problems.append('the roster does not resolve a position for this '
                            'row, so no position contract applies to it')
        elif pos not in M.POSITION_LAYERS:
            problems.append(f'position {pos!r} is not a position the product '
                            f'declares')
        else:
            allowed = set(M.POSITION_LAYERS[pos])
            extra = sorted(layers - allowed)
            if extra:
                problems.append(f'position {pos!r} may draw only from '
                                f'{sorted(allowed)} and this row carries '
                                f'{extra}')
        if dr:
            tag = ''.join(c for c in str(dr) if not c.isdigit())
            if pos and pos != 'UNKNOWN' and tag and tag != pos:
                problems.append(f'the depth chart ranks this row as {dr!r} '
                                f'while the roster calls him a {pos}')
        subj = f'{p.get("team")}/{gid}'
        m = {'position': pos, 'depth_chart': dr, 'layers': sorted(layers),
             'name_resolved': bool(name)}
        if problems:
            out.append(_finding('IDENTITY_DEPTH_ROLE_CONFLICT', ROW, subj,
                                FIRED, ' AND '.join(problems), **m))
        else:
            out.append(_finding('IDENTITY_DEPTH_ROLE_CONFLICT', ROW, subj,
                                PASS, 'identity, position, layers, depth '
                                      'rank and name all resolve and agree',
                                **m))
    if n_rows and n_nameless == n_rows:
        out.append(_finding(
            'IDENTITY_DEPTH_ROLE_CONFLICT', BOARD_SCOPE, 'BOARD', FIRED,
            f'all {n_rows} rows are nameless, so the board cannot be rendered '
            f'for a reader at all. This is escalated from row scope to board '
            f'scope: withholding every row individually and calling what is '
            f'left a board would be a board of nothing.',
            n_rows=n_rows, n_nameless=n_nameless))
        out[-1]['action'] = WITHHOLD_BOARD
    return out


def gate_unattributed_opportunity(board, manifest, draws) -> list:
    """A published pool with positive mass and no owner row at all."""
    out = []
    team_of = _team_of(board)
    pools = (('team_carries', 'rushing', 'carries', 'rushing'),
             ('team_targets', 'receiving', 'targets', 'receiving'),
             ('team_dropbacks_part', 'qb', 'db', 'qb'))
    trows = DEC.rows_of(manifest, 'team_volume')
    for team in sorted(board.get('teams') or []):
        for pool, layer, metric, fam in pools:
            subj = f'{team}/{fam}'
            if team not in trows:
                out.append(_finding('UNATTRIBUTED_OPPORTUNITY_MASS', FAMILY,
                                    subj, INSUFFICIENT_EVIDENCE,
                                    f'no team_volume row for {team}'))
                continue
            try:
                lev = np.asarray(DEC.matrix(draws, 'team_volume',
                                            pool)[trows[team]], float)
            except DEC.DecompositionInputError as e:
                out.append(_finding('UNATTRIBUTED_OPPORTUNITY_MASS', FAMILY,
                                    subj, INSUFFICIENT_EVIDENCE, str(e)))
                continue
            rows = _rows_for(manifest, layer, team_of, team)
            level = float(lev.mean())
            if rows:
                owned = float(np.asarray(
                    DEC.matrix(draws, layer, metric)[sorted(rows.values())],
                    float).sum(0).mean())
            else:
                owned = 0.0
            share = 1.0 - (owned / level) if level > 1e-9 else None
            m = {'pool': f'team_volume/{pool}', 'pool_mean': round(level, 4),
                 'owner_rows_sealed': len(rows),
                 'owned_mean': round(owned, 4),
                 'unattributed_share': (None if share is None
                                        else round(share, 6))}
            if level > 1e-9 and not rows:
                out.append(_finding(
                    'UNATTRIBUTED_OPPORTUNITY_MASS', FAMILY, subj, FIRED,
                    f'the board publishes a {pool} pool of {level:.2f} for '
                    f'{team} and seals ZERO {layer} rows for it. Every share '
                    f'this family would publish has a denominator no row can '
                    f'be checked against, and 100% of the mass is '
                    f'unattributable in principle rather than merely '
                    f'unattributed.', **m))
            else:
                out.append(_finding('UNATTRIBUTED_OPPORTUNITY_MASS', FAMILY,
                                    subj, PASS,
                                    f'{len(rows)} owner row(s) carry '
                                    f'{owned:.2f} of a {level:.2f} pool', **m))
    return out


def soft_degenerate_width(board, manifest, draws) -> list:
    out = []
    for p in board.get('players') or []:
        reasons = (p.get('confidence') or {}).get('reasons') or {}
        why = str(reasons.get('distribution_width') or '')
        if 'degenerate' in why.lower():
            out.append(_finding(
                'DEGENERATE_DISTRIBUTION_WIDTH', ROW,
                f'{p.get("team")}/{p.get("gsis_id")}', FIRED,
                f'the board\'s own confidence component reports: {why}',
                primary_metric=(p.get('confidence') or {}).get(
                    'primary_metric')))
    return out


def soft_healthy_qb1_low_central_tendency(board, manifest, draws) -> list:
    """Low mean on a healthy QB1. Inspect the ROOM, never raise the number."""
    out = []
    try:
        qrows = DEC.rows_of(manifest, 'qb')
        db = DEC.matrix(draws, 'qb', 'db')
    except DEC.DecompositionInputError:
        return out
    team_of = _team_of(board)
    for p in board.get('players') or []:
        gid = p.get('gsis_id')
        if p.get('depth_chart') != 'QB1' or gid not in qrows:
            continue
        i = qrows[gid]
        v = db[i]
        nz = v[v > 0]
        mean_all = float(v.mean())
        mean_cond = float(nz.mean()) if nz.size else None
        if mean_cond and mean_all < 0.9 * mean_cond:
            out.append(_finding(
                'HEALTHY_QB1_LOW_CENTRAL_TENDENCY', ROW,
                f'{team_of.get(gid)}/{gid}', FIRED,
                f'unconditional mean dropbacks {mean_all:.2f} sits '
                f'{100 * (1 - mean_all / mean_cond):.1f}% below the mean over '
                f'draws where he plays ({mean_cond:.2f}). The gap is mass '
                f'moved OFF this passer, so inspect starter probability and '
                f'the exit / replacement model. It is NOT a yardage floor and '
                f'must never be discharged by raising a projection.',
                mean_dropbacks=round(mean_all, 4),
                mean_dropbacks_given_plays=round(mean_cond, 4)))
    return out


_HARD_GATES = (gate_healthy_qb1_zero_opportunity, gate_qb_room_split,
               gate_role_state_source_conflict, gate_rush_accounting,
               gate_count_support, gate_identity_depth_role,
               gate_unattributed_opportunity)
_SOFT_GATES = (soft_degenerate_width, soft_healthy_qb1_low_central_tendency)


# ===========================================================================
def evaluate(board_dir, *, inactives=None, names=None) -> Outcome:
    """Every gate over one sealed board. PASS means every HARD gate passed.

    The Outcome state says what happened to the EVALUATION; the verdict in the
    evidence says what happens to the BOARD. They are different questions and
    a caller that conflates them gets the wrong one: an evaluation that ran
    cleanly and found eleven hard failures is a successful evaluation.
    """
    try:
        board, manifest, draws = DEC.load(board_dir)
    except DEC.DecompositionInputError as e:
        return Outcome.blocked('QUALITY_GATES_INPUT_MISSING', str(e),
                               cause=Cause.DATA, spec_version=SPEC_VERSION,
                               board_dir=str(board_dir))
    findings = []
    for fn in _HARD_GATES:
        findings.extend(fn(board, manifest, draws)
                        if fn is not gate_identity_depth_role
                        else fn(board, manifest, draws, names=names))
    findings.extend(gate_authoritative_inactive(board, manifest, draws,
                                                inactives=inactives))
    for fn in _SOFT_GATES:
        findings.extend(fn(board, manifest, draws))
    if not findings:
        return Outcome.fail(
            'QUALITY_GATES_EVALUATED_NOTHING',
            f'{board_dir} produced zero findings. A gate set that measured '
            f'nothing has not passed anything; an empty result here is an '
            f'error, not a clean board.', spec_version=SPEC_VERSION)
    v = verdict(findings, board)
    return Outcome.ok('QUALITY_GATES_EVALUATED', value=v,
                      detail=f'{len(findings)} finding(s) over '
                             f'{len(GATES)} hard gate(s) and '
                             f'{len(SOFT_DIAGNOSTICS)} soft diagnostic(s)',
                      findings=findings, verdict=v,
                      run_id=board.get('run_id'),
                      game_id=board.get('game_id'),
                      spec_version=SPEC_VERSION)


def verdict(findings, board=None) -> dict:
    """Compose findings into per-family and board product states."""
    board = board or {}
    hard = [f for f in findings if f['class'] == HARD]
    soft = [f for f in findings if f['class'] == SOFT]
    fired = [f for f in hard if f['state'] == FIRED]
    unevaluable = [f for f in hard if f['state'] == INSUFFICIENT_EVIDENCE]
    withhold_board = any(f['action'] == WITHHOLD_BOARD for f in fired)

    families = {}
    for f in fired:
        if f['scope'] == FAMILY:
            families.setdefault(f['subject'], []).append(f['gate'])
        elif f['scope'] == ROW:
            fam = '/'.join(str(f['subject']).split('/')[:1]) or 'BOARD'
            families.setdefault(f'{fam}/ROWS', []).append(f['gate'])
    rows_withheld = sorted({f['subject'] for f in fired
                            if f['scope'] == ROW})

    absent = {k: dict(v) for k, v in ABSENT_FAMILIES.items()}
    for k in absent:
        absent[k]['verification'] = verify_absent_families()[k]

    if withhold_board:
        state = WITHHELD
        why = ('a board-scope HARD gate fired: the board cannot be rendered '
               'for a reader')
    elif fired:
        state = WITHHELD
        why = (f'{len(fired)} HARD gate finding(s) fired over '
               f'{len(families)} family/families')
    elif unevaluable:
        state = INSUFFICIENT_EVIDENCE
        why = (f'no HARD gate fired and {len(unevaluable)} could not be '
               f'evaluated. An unevaluated gate is not a passed gate.')
    else:
        state = PRELIMINARY
        why = 'every HARD gate evaluated and passed'

    return {
        'spec_version': SPEC_VERSION,
        'run_id': board.get('run_id'), 'game_id': board.get('game_id'),
        'board_state': state, 'why': why,
        'publication_state': 'PRELIMINARY_PROVISIONAL',
        'publication_state_note':
            'FINAL is not reachable without an authoritative inactive list. '
            'No gate result and no green suite can raise it.',
        'hard_fired': [{'gate': f['gate'], 'subject': f['subject'],
                        'action': f['action'], 'why': f['why']}
                       for f in fired],
        'hard_insufficient_evidence': [
            {'gate': f['gate'], 'subject': f['subject'], 'why': f['why']}
            for f in unevaluable],
        'soft_flags': [{'gate': f['gate'], 'subject': f['subject'],
                        'why': f['why']} for f in soft if f['state'] == FIRED],
        'quarantined_families': {k: sorted(set(v))
                                 for k, v in sorted(families.items())},
        'rows_withheld': rows_withheld,
        'unavailable_families': absent,
        'counts': {'findings': len(findings), 'hard': len(hard),
                   'hard_fired': len(fired),
                   'hard_insufficient_evidence': len(unevaluable),
                   'soft': len(soft),
                   'soft_fired': sum(1 for f in soft if f['state'] == FIRED)},
        'soft_never_changes_anything':
            'a SOFT diagnostic flags for review. It does not quarantine, '
            'withhold, rescale, clip or floor anything, and no yardage floor '
            'exists anywhere in this module.',
    }


def render(outcome: Outcome) -> str:
    """Plain text, for a human. Our numbers, our words."""
    if outcome.state.name != 'PASS':
        return f'{outcome.code}: {outcome.detail}'
    v = outcome.evidence['verdict']
    L = [f'QUALITY GATES  {v["game_id"]}  run {v["run_id"]}',
         f'  board state        {v["board_state"]}  -- {v["why"]}',
         f'  publication state  {v["publication_state"]}',
         f'  hard fired         {v["counts"]["hard_fired"]}',
         f'  hard unevaluable   {v["counts"]["hard_insufficient_evidence"]}',
         f'  soft flagged       {v["counts"]["soft_fired"]}', '']
    if v['quarantined_families']:
        L.append('  QUARANTINED:')
        for k, g in v['quarantined_families'].items():
            L.append(f'    {k}: {", ".join(g)}')
    for f in v['hard_insufficient_evidence']:
        L.append(f'  NO EVIDENCE: {f["gate"]} on {f["subject"]}')
    for k, a in v['unavailable_families'].items():
        L.append(f'  UNAVAILABLE {k}: {a["code"]}')
    return '\n'.join(L)


def main(argv=None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print('usage: quality_gates.py <board_dir> [--json]')
        return 2
    o = evaluate(argv[0])
    if '--json' in argv:
        print(json.dumps(o.as_dict(), indent=1, default=str))
    else:
        print(render(o))
    return 0 if o.state.name == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
