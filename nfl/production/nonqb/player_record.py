"""The player output contract: one coherent record per supported player-game.

THE RULE THAT SHAPES EVERYTHING HERE

    An unsupported metric is EXPLICITLY ABSENT WITH A REASON.
    It is never emitted as zero.

Zero is a forecast. It says the player will gain no rushing yards. "We have no
governed control for rushing yards" says something completely different, and a
consumer that cannot tell the two apart will average them together. This
module makes that confusion impossible: every metric is either a distribution
with its own spec identity and governance state, or an `ABSENT` entry naming
the reason and the missing decision.

Every present metric carries: draw count, mean, p10, p50, p90, the spec version
that produced it, its governance state, and the run identity. A number without
those is not auditable and this contract will not emit one.
"""
from __future__ import annotations

import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
from nfl.production.nonqb import eligibility as EL                # noqa: E402

CONTRACT_VERSION = 'nfl-player-record-1'

# What each position is expected to carry. A metric listed here and not
# produced must appear as ABSENT with a reason -- silence is not permitted
# either.
EXPECTED = {
    'QB': ('dropbacks', 'attempts', 'completions', 'passing_yards',
           'passing_td', 'interceptions', 'sacks', 'rush_opportunity',
           'rushing_yards', 'rushing_td'),
    'WR': ('appearance', 'participation', 'targets', 'receptions',
           'receiving_yards', 'receiving_td'),
    'TE': ('appearance', 'participation', 'targets', 'receptions',
           'receiving_yards', 'receiving_td'),
    'RB': ('appearance', 'participation', 'targets', 'receptions',
           'receiving_yards', 'receiving_td', 'carries', 'rushing_yards',
           'rushing_td'),
}

# Governance state per metric, derived from the eligibility matrix rather than
# written by hand, so a metric cannot claim a state its subsystem does not have.
METRIC_LAYER = {
    'appearance': 'appearance', 'participation': 'participation',
    'targets': 'targets_carries', 'carries': 'targets_carries',
    'receptions': 'receiving_conversion',
    'receiving_yards': 'receiving_conversion',
    'receiving_td': 'td_layer', 'rushing_td': 'td_layer',
    'rushing_yards': 'rushing_conversion',
    'dropbacks': 'qb_layer', 'attempts': 'qb_layer',
    'completions': 'qb_layer', 'passing_yards': 'qb_layer',
    'passing_td': 'qb_layer', 'interceptions': 'qb_layer',
    'sacks': 'qb_layer', 'rush_opportunity': 'qb_layer',
}

_MATRIX = None


def _governance(metric):
    global _MATRIX
    if _MATRIX is None:
        _MATRIX = EL.matrix({})
    layer = METRIC_LAYER.get(metric)
    m = _MATRIX.get(layer, {})
    return {'layer': layer, 'subsystem': m.get('subsystem'),
            'owner_state': m.get('owner_state'),
            'research_state': m.get('research_state'),
            'publication_eligible': m.get('publication_eligible', False)}


def summarise(draws, spec_version, metric, run_id, **extra) -> dict:
    """One metric's distribution, with everything needed to audit it."""
    a = np.asarray(draws, float).reshape(-1)
    if a.size == 0:
        raise ValueError(f'{metric}: an empty draw vector is not a '
                         f'distribution')
    return {'status': 'PRESENT', 'n_draws': int(a.size),
            'mean': float(a.mean()),
            'p10': float(np.quantile(a, 0.10)),
            'p50': float(np.quantile(a, 0.50)),
            'p90': float(np.quantile(a, 0.90)),
            'spec_version': spec_version, 'governance': _governance(metric),
            'run_id': run_id, **extra}


def absent(metric, reason, run_id, **extra) -> dict:
    """An unsupported metric. NEVER a zero."""
    return {'status': 'ABSENT', 'reason': reason, 'n_draws': 0,
            'mean': None, 'p10': None, 'p50': None, 'p90': None,
            'spec_version': None, 'governance': _governance(metric),
            'run_id': run_id, **extra}


def record(player, position, game_id, run_id, metrics: dict) -> dict:
    """One player's record. Every expected metric is present or named absent."""
    exp = EXPECTED.get(position, ())
    out, missing = {}, []
    for k in exp:
        v = metrics.get(k)
        if v is None:
            missing.append(k)
        else:
            out[k] = v
    for k in metrics:
        if k not in exp:
            out[k] = metrics[k]
    return {'gsis_id': player, 'position': position, 'game_id': game_id,
            'run_id': run_id, 'contract_version': CONTRACT_VERSION,
            'metrics': out, 'metrics_not_addressed': missing}


def validate(records) -> Outcome:
    """The contract, enforced. Three ways to fail and they are all named."""
    if not records:
        return Outcome.fail(
            'PLAYER_RECORDS_EMPTY',
            'no player record was produced. An empty record set is not a '
            'forecast, and reporting it as one is how absence becomes success.')
    bad_zero, unaddressed, thin = [], [], []
    for r in records:
        exp = EXPECTED.get(r['position'], ())
        if r['metrics_not_addressed']:
            unaddressed.append({'player': r['gsis_id'],
                                'position': r['position'],
                                'metrics': r['metrics_not_addressed']})
        for k in exp:
            m = r['metrics'].get(k)
            if m is None:
                continue
            if m['status'] == 'ABSENT':
                # AN ABSENT METRIC MAY NOT CARRY A NUMBER. This is the check
                # that stops "unsupported" quietly becoming zero.
                if any(m.get(f) is not None
                       for f in ('mean', 'p10', 'p50', 'p90')) or m['n_draws']:
                    bad_zero.append({'player': r['gsis_id'], 'metric': k,
                                     'why': 'ABSENT yet carries a value'})
                if not m.get('reason'):
                    bad_zero.append({'player': r['gsis_id'], 'metric': k,
                                     'why': 'ABSENT with no reason'})
                continue
            for f in ('n_draws', 'mean', 'p10', 'p50', 'p90', 'spec_version',
                      'run_id'):
                if m.get(f) is None:
                    thin.append({'player': r['gsis_id'], 'metric': k,
                                 'missing_field': f})
            if not (m.get('governance') or {}).get('layer'):
                thin.append({'player': r['gsis_id'], 'metric': k,
                             'missing_field': 'governance'})
    if bad_zero:
        return Outcome.fail(
            'UNSUPPORTED_METRIC_EMITTED_AS_VALUE',
            f'{len(bad_zero)} metric(s) are marked ABSENT yet carry a number '
            f'or carry no reason. Zero is a forecast; absence is not.',
            offences=bad_zero[:10])
    if unaddressed:
        return Outcome.fail(
            'EXPECTED_METRIC_NOT_ADDRESSED',
            f'{len(unaddressed)} record(s) neither produced nor explicitly '
            f'excused an expected metric. Silence is not one of the two '
            f'permitted answers.', offences=unaddressed[:10])
    if thin:
        return Outcome.fail(
            'PLAYER_METRIC_NOT_AUDITABLE',
            f'{len(thin)} present metric(s) lack a required audit field',
            offences=thin[:10])
    n_present = sum(1 for r in records for m in r['metrics'].values()
                    if m['status'] == 'PRESENT')
    n_absent = sum(1 for r in records for m in r['metrics'].values()
                   if m['status'] == 'ABSENT')
    by_pos = {}
    for r in records:
        by_pos[r['position']] = by_pos.get(r['position'], 0) + 1
    return Outcome.ok('PLAYER_RECORDS_VALID', value=len(records),
                      n_records=len(records), n_metrics_present=n_present,
                      n_metrics_absent=n_absent, by_position=by_pos,
                      contract_version=CONTRACT_VERSION)
