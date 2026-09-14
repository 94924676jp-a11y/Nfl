"""The Q9 prospective ledger: what a scored row is, and what it may be counted as.

    python3.12 -m nfl.prospective.q9shadow.ledger --schema
    python3.12 -m nfl.prospective.q9shadow.ledger --score --season 2026

ONE ROW, FULLY IDENTIFIED. Every scored row names its candidate, forecast_id,
game, team, player, metric, cutoff, written_at and outcome hash, because a row
that cannot say which forecast and which realisation it came from cannot
survive an outcome revision or a second candidate.

FOUR COUNTS, NEVER ONE. `ROW`, `PLAYER_GAME`, `TEAM_GAME` and `GAME` are
reported separately, each with its unit declared, and the counting is
delegated to `nfl.research.postgame.accounting` rather than recomputed here.
The directive's sentence is the whole reason: *do not treat thousands of
player rows from one game as thousands of independent samples.* Two arms of
one player-game are a PAIRED comparison and add nothing to any of the four.

FINALITY GATES SCORING, AND IT IS NOT THIS MODULE'S OPINION.
`postgame.game_finality` proves completion from the authoritative bytes and
`postgame.versioned` decides which outcome version is CURRENT. Both are
imported. A game that cannot prove finality produces ZERO scored rows under
the named state POSTGAME_NOT_FINAL; an outcome revision is a NEW row and the
older one stops being current without being deleted.

THE SAMPLE FLOOR IS ALREADY GOVERNED, SO IT IS NOT INVENTED HERE.
`nfl/prospective/PROSPECTIVE_EVALUATION_PROTOCOL.md` section 4 fixes the
floors, in player-game forecasts and eligible weeks. They are transcribed
into `FLOORS` and evaluated by `floor_verdicts`. This module therefore never
reports PROSPECTIVE_SAMPLE_NOT_YET_GOVERNED: the repository contains a
governed threshold and the directive says to use it.

RANDOMIZED PIT, NOT MID-PIT, AND WHY IT MATTERS HERE. Protocol section 9.6
requires that randomized PIT be *not worse*. Q9B measured MID-PIT, which is a
different statistic, so section 9.6 was not evaluable on the development
evidence. This module emits the randomized version, seeded deterministically
per row so it reproduces, and records both so the two are never confused.

A DRY-RUN ROW IS NOT EVIDENCE. `assert_not_dry_run` refuses any artifact
carrying `dry_run: true` or `prospective_evidence: false`. The dry-run proof
exists to show the sealing path works; counting its output as prospective
evidence would make the proof the thing it was proving against.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import pathlib
import sys
import zlib

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State   # noqa: E402
from nfl.prospective.q9shadow import candidate as CAND                # noqa: E402
from nfl.research import postgame as PG                               # noqa: E402
from nfl.research.shadow import score as SC                           # noqa: E402

SPEC_VERSION = 'q9-prospective-ledger-1'
HERE = _REPO / 'nfl' / 'prospective' / 'q9shadow'
LEDGER = HERE / 'Q9_PROSPECTIVE_LEDGER.jsonl'
LEDGER_SCHEMA = HERE / 'Q9_PROSPECTIVE_LEDGER_SCHEMA.json'
METRIC = 'receiving/targets'

# ---------------------------------------------------------------- the row
#
# Each field, and what breaks without it. A schema whose fields are not
# justified gets a field added every time someone wants one.
ROW_FIELDS = {
    'candidate': 'which candidate. Without it two candidates of one game '
                 'merge into one series.',
    'arm': 'which arm of the side-by-side. R8_PRODUCTION and Q9_HURDLE are a '
           'PAIRED comparison on the same player-game, never two samples.',
    'forecast_id': 'which sealed forecast. This is what stops five sealed '
                   'variants of one game from counting as five games.',
    'artifact_id': 'the content hash of the sealed artifact, so a mutated '
                   'artifact cannot be scored as the sealed one.',
    'game_id': 'the GAME unit, and the floor unit.',
    'team': 'the TEAM_GAME unit: the budget this allocation partitions.',
    'entity': 'player / team / room. Part of the version identity, because a '
              'team row and a room row can share a team code.',
    'player_id': 'the PLAYER_GAME unit.',
    'position': 'the stratum protocol section 7 requires, with its own floor.',
    'metric': 'the forecast quantity. One row per metric per arm.',
    'cutoff_utc': 'the consumed clock. A pre- and a post-inactives board of '
                  'one game are different forecasts and are never pooled.',
    'cutoff_basis': 'which field the cutoff came from, so a reader never has '
                    'to guess which clock was enforced.',
    'written_at': 'when the forecast was written. With kickoff, this is the '
                  'claim the whole protocol rests on.',
    'kickoff_utc': 'the deadline written_at had to precede.',
    'outcome_hash': 'which realisation this row was scored against. This is '
                    'what makes an outcome revision detectable rather than '
                    'silent.',
    'outcome_source': 'which authority supplied it. Only rank-1 sources are '
                      'scoreable.',
    'finality_code': 'the proof of completion, or POSTGAME_NOT_FINAL.',
    'prospective_evidence': 'false for a dry-run row. A false row is stored '
                            'and never counted.',
    'promoted': 'always false. Recorded so the artifact asserts it rather '
                'than a reader assuming it.',
    # ---- the forecast, as sealed before kickoff
    'zero_probability': 'P(zero targets) as SEALED, not as recomputed later.',
    'mean_targets': 'the predictive mean as sealed.',
    'n_draws': 'the draw count the numbers came from.',
    # ---- the realisation and the scores
    'actual_targets': 'the realised count from the CURRENT outcome version.',
    'is_zero_actual': '1 if the player recorded no target.',
    'zero_brier': 'the squared error of the zero probability.',
    'zero_log_loss': 'the log score of the zero probability, clipped and the '
                     'clip declared.',
    'marginal_crps': 'CRPS of the full marginal target distribution.',
    'positive_crps': 'CRPS of the positive-target conditional distribution, '
                     'empty when the realisation is zero -- conditioning on '
                     'a positive outcome is not defined at zero.',
    'randomized_pit': 'the randomized PIT value, which is what protocol '
                      'section 9.6 names.',
    'mid_pit': 'the mid-PIT value, recorded beside it so the two statistics '
               'are never mistaken for each other.',
    'pit_seed': 'the deterministic seed the randomisation used, so the '
                'randomized PIT reproduces exactly.',
    'rec_yard_crps': 'downstream receiving-yard CRPS. DIAGNOSTIC ONLY and '
                     'never a promotion criterion.',
    'actual_rec_yds': 'the realised receiving yards, empty when the outcome '
                      'version does not carry them. Never defaulted to zero.',
}

LOG_LOSS_CLIP = 1e-6      # declared, not tuned; symmetric

# Protocol section 4, transcribed. The unit of each floor is stated because a
# floor without a unit is satisfied first by whichever count is largest.
FLOORS = {
    'any_reported_metric': {
        'n_forecasts': 200, 'n_weeks': None,
        'unit': 'eligible player-game forecasts'},
    'any_benchmark_comparison': {
        'n_forecasts': 400, 'n_weeks': 8,
        'unit': 'eligible player-game forecasts and eligible weeks'},
    'any_promotion_decision': {
        'n_forecasts': 800, 'n_weeks': 12,
        'unit': 'eligible player-game forecasts and eligible weeks'},
    'any_position_stratified_claim': {
        'n_forecasts': 200, 'n_weeks': None,
        'unit': 'eligible player-game forecasts within that position'},
}
FLOOR_SOURCE = 'nfl/prospective/PROSPECTIVE_EVALUATION_PROTOCOL.md section 4'
UNDERPOWERED = 'UNDERPOWERED'

# The primary comparison, fixed here rather than chosen after the numbers.
PRIMARY = ('zero_brier', 'zero_log_loss', 'zero_mass_calibration_gap',
           'marginal_crps', 'positive_crps')
DIAGNOSTIC = ('randomized_pit', 'mid_pit', 'rec_yard_crps')

BOOT = 1000
BOOT_SEED = 20260913


def schema():
    """The ledger contract, as an artifact rather than as prose."""
    return {
        'artifact': 'NFL_Q9_PROSPECTIVE_LEDGER_SCHEMA',
        'spec_version': SPEC_VERSION,
        'candidate': CAND.CANDIDATE_NAME,
        'promoted': False, 'shadow_only': True,
        'ledger_path': str(LEDGER.relative_to(_REPO)),
        'append_only': True,
        'row_fields': ROW_FIELDS,
        'version_identity': list(PG.VERSION_IDENTITY),
        'version_identity_note': (
            'one outcome version per identity may be CURRENT. A revision is a '
            'NEW row; the older one is never deleted or rewritten, and its '
            'label is DERIVED from ledger order by postgame.versioned.'),
        'evidence_units': PG.EVIDENCE_UNITS,
        'floor_unit': PG.FLOOR_UNIT,
        'required_counts': ['scoring_rows', 'distinct_player_games',
                            'distinct_team_games', 'distinct_games'],
        'paired_note': PG.PAIRED_NOTE,
        'arm_pairing_note': (
            'R8_PRODUCTION and Q9_HURDLE rows for one player-game are a '
            'paired comparison on shared upstream draws. They add one '
            'player-game to the sample, not two.'),
        'primary_metrics': list(PRIMARY),
        'diagnostic_metrics': list(DIAGNOSTIC),
        'log_loss_clip': LOG_LOSS_CLIP,
        'floors': FLOORS,
        'floor_source': FLOOR_SOURCE,
        'below_floor_state': UNDERPOWERED,
        'below_floor_note': (
            'below a floor a comparison is not a small result -- it is not a '
            'result. The protocol says so and this module reports '
            f'{UNDERPOWERED} rather than a number with a wide interval.'),
        'clustering': {
            'method': 'paired block bootstrap over whole units',
            'units': ['game_id', 'team_game'],
            'n_resamples': BOOT, 'seed': BOOT_SEED,
            'naive_intervals': 'FORBIDDEN by protocol section 6'},
        'finality': {
            'gate': 'nfl.research.postgame.game_finality',
            'signals': [s[0] for s in PG.FINALITY_SIGNALS],
            'not_final_state': PG.NOT_FINAL,
            'note': 'a game that cannot prove finality produces zero scored '
                    'rows. Kickoff having passed is not completion.'},
        'dry_run_rows': 'stored, and never counted as evidence',
        'governance_conflicts_open': {
            'protocol_section_2_completeness': (
                'an eligible forecast requires completeness == COMPLETE; a '
                'single-layer receiving-target artifact is truthfully '
                'PARTIAL_PLAYER_COVERAGE. Owner ruling needed; not resolved '
                'by relabelling.'),
            'G0A': ('G0A stands at 11/12 and protocol section 1 says no '
                    'forecast written before G0A is discharged counts toward '
                    'promotion.'),
        },
    }


def assert_not_dry_run(art) -> Outcome:
    """A dry-run artifact may be read, replayed and never counted."""
    if art.get('dry_run') or art.get('prospective_evidence') is False:
        return Outcome.not_applicable(
            'Q9_LEDGER_DRY_RUN_ROW_NOT_EVIDENCE',
            f'{art.get("forecast_id")} is a dry-run seal '
            f'({art.get("eligibility_verdict")}). It exercises the sealing '
            f'path and is not a forecast, so it contributes to no count and '
            f'to no metric.')
    return Outcome.ok('Q9_LEDGER_ROW_IS_PROSPECTIVE',
                      value=art.get('forecast_id'))


# ------------------------------------------------------------- the scores
def _clip(p):
    return min(max(float(p), LOG_LOSS_CLIP), 1.0 - LOG_LOSS_CLIP)


def zero_scores(p_zero, is_zero):
    """Brier and log loss of the sealed zero probability."""
    p, y = float(p_zero), float(bool(is_zero))
    return (round((p - y) ** 2, 8),
            round(-(y * math.log(_clip(p)) + (1 - y) * math.log(1 - _clip(p))),
                  8))


def crps(draws, y):
    return float(SC.crps(np.asarray(draws, float), float(y)))


def pit_pair(draws, y, seed_text):
    """Randomized PIT and mid-PIT from the same draws, both recorded.

    RANDOMIZED is the statistic protocol section 9.6 names:
        U ~ Uniform(0,1);  PIT = F(y-) + U * (F(y) - F(y-))
    MID-PIT replaces U by 1/2 and is what Q9B measured. They differ, and a
    project that has already lost work to a metric mix-up records both rather
    than one.

    THE SEED IS DERIVED FROM THE ROW, VIA crc32. Python's `hash()` is
    randomised per process, so a PIT seeded from it would not reproduce -- the
    defect `nfl/production/seeds.py` exists to end.
    """
    d = np.asarray(draws, float)
    y = float(y)
    lo = float((d < y).mean())
    at = float((d == y).mean())
    seed = int(zlib.crc32(str(seed_text).encode()) & 0x7FFFFFFF)
    u = float(np.random.default_rng(seed).random())
    return round(lo + u * at, 6), round(lo + 0.5 * at, 6), seed


def score_rows(art, draws, actuals, outcome_hash, outcome_source,
               finality_code) -> list:
    """Every scored row for one sealed artifact, both arms, fully identified.

    `actuals` maps player_id -> {'targets': n, 'rec_yds': y} and comes from
    the CURRENT outcome version. A player absent from it is NOT scored as a
    zero, and a player present without `rec_yds` is not scored on yards:
    that exact substitution -- a missing key defaulted to zero -- is what
    turned a 74-yard game into a scored zero once already.
    """
    # THE SEAL-PATH GATE, AT THE POINT ROWS ARE CREATED.
    #
    # Scoring is where an artifact turns into evidence, so it is where the
    # bypass check belongs. An artifact that did not come through the governed
    # appearance interface produces ZERO rows -- not rows marked non-evidence,
    # zero -- because a row that exists can be miscounted and a row that was
    # never created cannot.
    gate = assert_seal_path_governed(art)
    if gate.state is not State.PASS:
        return []
    rows = []
    pids = list(art['player_ids'])
    summary = {(r['arm'], r['player_id']): r for r in art['player_summary']}
    for arm in CAND.ARMS:
        T = draws[f'{arm}__targets']
        YD = draws.get(f'{arm}__receiving_yards')
        for j, pid in enumerate(pids):
            if pid not in actuals:
                continue
            act = actuals[pid]
            act = act if isinstance(act, dict) else {'targets': act}
            if act.get('targets') is None:
                continue
            y = float(act['targets'])
            s = summary.get((arm, pid)) or {}
            d = T[:, j]
            pos = d[d > 0]
            zb, zl = zero_scores(s.get('zero_probability',
                                       float((d == 0).mean())), y == 0)
            rpit, mpit, pseed = pit_pair(
                d, y, f'{art["forecast_id"]}|{arm}|{pid}|{outcome_hash}')
            rows.append({
                'candidate': CAND.CANDIDATE_NAME, 'arm': arm,
                'forecast_id': art['forecast_id'],
                'artifact_id': art['artifact_id'],
                'game_id': art['game_id'], 'team': art['team'],
                'entity': 'player', 'player_id': pid,
                'position': s.get('position'), 'metric': METRIC,
                'cutoff_utc': art['cutoff']['cutoff_utc'],
                'cutoff_basis': art['cutoff']['cutoff_basis'],
                'written_at': art['written_at'],
                'kickoff_utc': art['kickoff_utc'],
                'outcome_hash': outcome_hash,
                'outcome_source': outcome_source,
                'finality_code': finality_code,
                'prospective_evidence': bool(
                    art.get('prospective_evidence', False)),
                # STAMPED ON THE ROW, NOT ONLY CHECKED AT CREATION.
                # `score_rows` is not the only way a row can reach the
                # ledger -- `append_rows` takes whatever it is given -- so
                # the verdict travels with the row and `accounting` reads it.
                'seal_path_governed': True,
                # THE SHARED COUNTING STAMP, and the reason it is separate
                # from `seal_path_governed`.
                #
                # `accounting` delegates to `postgame.accounting`, which
                # counts only rows stamped `currently_admissible`. Stamping
                # only the q9shadow-specific field silently zeroed every Q9
                # count the moment the postgame gate landed -- the two layers
                # agreed on the policy and disagreed on the field name.
                # `currently_admissible` is the shared gate; `seal_path_
                # governed` records WHY this row earned it.
                'currently_admissible': True,
                'readiness_gate': (art.get('seal_path') or {}).get(
                    'readiness_gate'),
                'promoted': False,
                'zero_probability': s.get('zero_probability'),
                'mean_targets': s.get('mean_targets'),
                'n_draws': int(d.size),
                'actual_targets': y,
                'is_zero_actual': int(y == 0),
                'zero_brier': zb, 'zero_log_loss': zl,
                'marginal_crps': round(crps(d, y), 6),
                'positive_crps': (round(crps(pos, y), 6)
                                  if y > 0 and pos.size else ''),
                'randomized_pit': rpit, 'mid_pit': mpit, 'pit_seed': pseed,
                # DIAGNOSTIC, NOT A CRITERION. The directive is explicit
                # that the downstream receiving-yard output is preserved for
                # diagnosis and is not the primary criterion, and a gain here
                # alone was already declared insufficient in Q9.
                'rec_yard_crps': (
                    round(crps(YD[:, j], float(act['rec_yds'])), 6)
                    if YD is not None and act.get('rec_yds') is not None
                    else ''),
                'actual_rec_yds': act.get('rec_yds'),
            })
    return rows


# -------------------------------------------------------- the accounting
def accounting(rows):
    """The four counts, from the governed counter, plus the arm pairing.

    TWO INDEPENDENT EXCLUSIONS, APPLIED AT THE COUNTER.
      * `prospective_evidence` -- the owner's evidence ruling.
      * `seal_path_governed` -- a row whose artifact did not come through the
        governed appearance interface AND the per-team readiness gate. A row
        that predates the stamp has no verdict, and no verdict is not a pass.
    Both are enforced here as well as at `score_rows`, because a row can
    reach the ledger through `append_rows` without passing `score_rows` at
    all.
    """
    counted = [r for r in rows if r.get('prospective_evidence')
               and r.get('seal_path_governed') is True]
    acc = PG.accounting(counted)
    acc['scoring_rows_including_non_evidence'] = len(list(rows))
    allrows = list(rows)
    acc['rows_excluded_as_non_evidence'] = len(allrows) - len(counted)
    acc['rows_excluded_by_evidence_flag'] = sum(
        1 for r in allrows if not r.get('prospective_evidence'))
    acc['rows_excluded_by_seal_path'] = sum(
        1 for r in allrows if r.get('seal_path_governed') is not True)
    acc['exclusion_note'] = (
        'a row must carry BOTH prospective_evidence and '
        'seal_path_governed to be counted. The two exclusions overlap and '
        'are reported separately so neither can be assumed from the other.')
    acc['distinct_arms'] = sorted({r.get('arm') for r in counted
                                   if r.get('arm')})
    acc['arm_pairing_note'] = schema()['arm_pairing_note']
    # The count the floors are stated in. NOT the row count, and the
    # distinction is the whole reason this function exists.
    acc['eligible_player_game_forecasts'] = acc['distinct_player_games']
    acc['eligible_weeks'] = len({
        (r.get('game_id') or '').split('_')[1] for r in counted
        if (r.get('game_id') or '').count('_') >= 2})
    return acc


def floor_verdicts(acc):
    """Each governed floor, against the count in its own unit."""
    n = int(acc.get('eligible_player_game_forecasts') or 0)
    w = int(acc.get('eligible_weeks') or 0)
    out = {}
    for name, f in FLOORS.items():
        need_n, need_w = f['n_forecasts'], f['n_weeks']
        met = n >= need_n and (need_w is None or w >= need_w)
        out[name] = {
            'floor': f, 'have_forecasts': n, 'have_weeks': w,
            'state': 'MET' if met else UNDERPOWERED,
            'shortfall_forecasts': max(0, need_n - n),
            'shortfall_weeks': (None if need_w is None
                                else max(0, need_w - w)),
            'source': FLOOR_SOURCE,
        }
    return out


def boot_paired(diffs, clusters, n=BOOT, seed=BOOT_SEED):
    """Paired block bootstrap over whole clusters. Naive intervals refused."""
    d = np.asarray(diffs, float)
    if d.size == 0:
        return None
    keys = sorted(set(clusters))
    idx = collections.defaultdict(list)
    for i, c in enumerate(clusters):
        idx[c].append(i)
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n):
        pick = rng.integers(0, len(keys), len(keys))
        sel = [i for k in pick for i in idx[keys[k]]]
        means.append(float(d[sel].mean()))
    means = np.sort(np.asarray(means, float))
    return {'mean': round(float(d.mean()), 8),
            'lo95': round(float(means[int(0.025 * n)]), 8),
            'hi95': round(float(means[int(0.975 * n)]), 8),
            'n_clusters': len(keys), 'n_rows': int(d.size),
            'n_resamples': n, 'seed': seed}


def compare(rows):
    """Q9 against R8 on the primary metrics, paired and clustered.

    Returns the comparison, or the reason it is not a comparison. Below the
    benchmark floor the metrics are computed and reported as UNDERPOWERED
    rather than withheld -- the protocol forbids treating them as a result,
    not looking at them.
    """
    counted = [r for r in rows if r.get('prospective_evidence')]
    acc = accounting(rows)
    floors = floor_verdicts(acc)
    by = {}
    for r in counted:
        by.setdefault((r['game_id'], r['team'], r['player_id']), {})[
            r['arm']] = r
    paired = [v for v in by.values() if set(v) == set(CAND.ARMS)]
    out = {'n_paired_player_games': len(paired),
           'accounting': acc, 'floors': floors,
           'benchmark_floor_state':
               floors['any_benchmark_comparison']['state'],
           'promotion_floor_state':
               floors['any_promotion_decision']['state'],
           'metrics': {}}
    if not paired:
        out['status'] = 'NO_PAIRED_ROWS'
        return out
    a, b = CAND.ARM_PRODUCTION, CAND.ARM_CANDIDATE
    for m in ('zero_brier', 'zero_log_loss', 'marginal_crps',
              'positive_crps'):
        pr = [(v[a], v[b]) for v in paired
              if v[a].get(m) != '' and v[b].get(m) != ''
              and v[a].get(m) is not None and v[b].get(m) is not None]
        if not pr:
            out['metrics'][m] = {'state': 'NO_ROWS'}
            continue
        diffs = [float(y[m]) - float(x[m]) for x, y in pr]
        out['metrics'][m] = {
            'production_mean': round(float(np.mean(
                [float(x[m]) for x, _ in pr])), 8),
            'candidate_mean': round(float(np.mean(
                [float(y[m]) for _, y in pr])), 8),
            'paired_delta_candidate_minus_production':
                round(float(np.mean(diffs)), 8),
            'lower_is_better': True,
            'game_clustered': boot_paired(
                diffs, [x['game_id'] for x, _ in pr]),
            'team_game_clustered': boot_paired(
                diffs, [f'{x["game_id"]}|{x["team"]}' for x, _ in pr]),
            'state': floors['any_benchmark_comparison']['state'],
        }
    # zero-mass calibration gap: predicted zero rate against observed.
    for arm in CAND.ARMS:
        rs = [v[arm] for v in paired]
        pred = float(np.mean([float(r['zero_probability']) for r in rs]))
        obs = float(np.mean([float(r['is_zero_actual']) for r in rs]))
        out['metrics'].setdefault('zero_mass_calibration_gap', {})[arm] = {
            'predicted_zero_rate': round(pred, 6),
            'observed_zero_rate': round(obs, 6),
            'gap_predicted_minus_observed': round(pred - obs, 6)}
    out['metrics']['zero_mass_calibration_gap']['state'] = \
        floors['any_benchmark_comparison']['state']
    # randomized PIT, so protocol section 9.6 is evaluable at all.
    for arm in CAND.ARMS:
        rs = [v[arm] for v in paired]
        out.setdefault('pit', {})[arm] = {
            'randomized_pit_chi2': _pit_chi2(
                [float(r['randomized_pit']) for r in rs]),
            'mid_pit_chi2': _pit_chi2([float(r['mid_pit']) for r in rs]),
            'n': len(rs),
            'note': 'section 9.6 names the RANDOMIZED statistic. Q9B '
                    'measured mid-PIT, which is why the rule was not '
                    'evaluable on the development evidence.'}
    out['status'] = ('COMPARISON_UNDERPOWERED'
                     if floors['any_benchmark_comparison']['state']
                     == UNDERPOWERED else 'COMPARISON_POWERED')
    return out


def _pit_chi2(pits, bins=10):
    if not pits:
        return None
    h, _ = np.histogram(np.clip(np.asarray(pits, float), 0, 1),
                        bins=bins, range=(0, 1))
    e = len(pits) / bins
    return round(float(((h - e) ** 2 / e).sum()), 4)


LEDGER_STATE = HERE / 'Q9_PROSPECTIVE_LEDGER_STATE.json'


# HOW MANY GAMES THE CENSUS COVERS.
#
# `state()` used to attempt every eligible game -- 270 of them, each needing a
# full live feature build before the readiness gate is even reached. That is
# minutes of work to produce a census, and it timed out in practice. The
# census is a REPORTING scope, not a governance one: bounding it changes which
# games are listed, never whether any of them would pass. `census_scope` is
# recorded on the artifact so a bounded census is never read as the season.
CENSUS_GAMES = 16


def state(season=2026, now=None, n_games=CENSUS_GAMES):
    """The ledger as it actually stands, with the reason it stands there.

    AN EMPTY LEDGER IS NOT REPORTED AS A ZERO AND LEFT THERE. This project's
    rule is that an empty read is an error until something says why it is
    empty, so the state artifact carries the live eligibility census beside
    the counts: how many games are ahead of the clock, and the NAMED refusal
    each one produced. A reader then knows whether the ledger is empty because
    nothing has happened yet or because something is broken.
    """
    from nfl.prospective.q9shadow import seal as SEAL
    from nfl.prospective.q9shadow import shadow as SH
    rows = current()
    acc = accounting(rows)
    live = SEAL.seal_season(season, now, SH.LIVE_PREGAME, n_games=n_games)
    census = collections.Counter(
        f'{r["state"]}[{r["code"]}]' for r in (live.get('refusals') or []))
    return {
        'artifact': 'NFL_Q9_PROSPECTIVE_LEDGER_STATE',
        'spec_version': SPEC_VERSION,
        'candidate': CAND.CANDIDATE_NAME,
        'promoted': False, 'prospective_candidate': True,
        'shadow_only': True,
        'season': season,
        'ledger_path': str(LEDGER.relative_to(_REPO)),
        'schema': str(LEDGER_SCHEMA.relative_to(_REPO)),
        'accounting': acc,
        'floors': floor_verdicts(acc),
        'floor_source': FLOOR_SOURCE,
        'sample_governed': True,
        'sample_governed_note': (
            'the repository contains a governed prospective-evidence '
            'threshold (protocol section 4), so this work uses it. '
            'PROSPECTIVE_SAMPLE_NOT_YET_GOVERNED is NOT the applicable state '
            'and is not reported.'),
        'live_eligibility': {
            'status': live.get('status'),
            'census_scope': {
                'n_games_attempted': n_games,
                'note': 'a bounded REPORTING scope covering the next '
                        'eligible kickoffs, not the whole season. Bounding '
                        'the census changes which games are listed, never '
                        'whether any would pass.'},
            'candidate_gate': live.get('candidate_gate'),
            'n_games_ahead_of_clock': live.get('n_eligible_games'),
            'n_sealed': len(live.get('sealed') or []),
            'refusal_census': dict(census),
            'refusal_detail': (live.get('detail') or '')[:600],
            'requirements_for_the_live_path':
                SH.LIVE_PREGAME_REQUIREMENTS,
        },
        'blockers': BLOCKERS,
        'blocker_states': blocker_states(),
        'blocker_independence': (lambda o: {
            'state': f'{o.state.value}[{o.code}]', 'detail': o.detail,
            'n_blockers': o.evidence.get('n_blockers'),
            'n_perturbations': o.evidence.get('n_perturbations'),
            'method': 'each blocker forced CLEARED in turn; every other '
                      'recomputed from its own evaluator and required to be '
                      'unchanged',
        })(assert_blockers_independent()),
        'resolved_blockers': RESOLVED_BLOCKERS,
        'excluded_seals': EXCLUDED_SEALS,
        'blockers_are_independent': (
            'clearing one blocker does not clear any other. Each carries its '
            'own owner, its own remedy and an explicit independent_of list, '
            'and the live feature builder landing is the worked example: it '
            'is implemented, and a live seal is still blocked.'),
        'owner_rulings': OWNER_RULINGS,
        'evidence_state': {
            'forecasts_may_be': ['DRY_RUN', 'DIAGNOSTIC'],
            'section_4_credit': 'NONE',
            'promotion_evidence_accruing': False,
            'condition': ('all three original blockers satisfied AND a '
                          'truthful COMPLETE pre-kickoff artifact sealed. '
                          'Until then nothing accrues, whatever the numbers '
                          'look like.'),
        },
        'stop_rule': STOP_RULE,
    }


# THE OWNER RULINGS THIS LAYER IMPLEMENTS, recorded so the reasoning cannot
# be reconstructed wrongly later.
OWNER_RULINGS = {
    'randomized_pit': {
        'ruling': 'protocol section 9.6 UNCHANGED. Randomized PIT is the '
                  'governing prospective promotion statistic.',
        'q9b_mid_pit': 'DIAGNOSTIC ONLY. It does not satisfy section 9.6.',
        'implementation': 'this module emits the randomized statistic, seeded '
                          'per row through crc32 so it reproduces, and '
                          'records mid-PIT beside it.',
        'protocol_modified': False,
    },
    'completeness': {
        'ruling': 'protocol section 2 UNCHANGED. A PARTIAL_PLAYER_COVERAGE '
                  'artifact may be scored diagnostically, counts toward no '
                  'section-4 floor, and cannot support promotion.',
        'relabelling': 'REFUSED. A single-layer Q9 artifact is not called '
                       'COMPLETE.',
        'route': 'nfl/prospective/q9shadow/complete.py builds the paired '
                 'R8-versus-Q9 artifact across all nine required layers on '
                 'one set of upstream draws, with the target allocation as '
                 'the only divergence. completeness is COMPUTED from '
                 'nfl.research.completeness.forecast_completeness; there is '
                 'no Q9 exemption.',
        'protocol_modified': False,
    },
}

# The things standing between this integration and a countable prospective
# row. Each is named, each is upstream of Q9, and none is something this task
# may route around. THEY ARE INDEPENDENT: clearing one does not imply any
# other is cleared, and `independent_of` on each says so explicitly.
# RESOLVED, AND MOVED OUT OF THE LIVE LIST RATHER THAN LEFT THERE WITH A
# "status: IMPLEMENTED" STRING.
#
# A blocker list whose entries can say "actually this one is done" is not a
# blocker list -- a reader has to parse prose to learn the state, and the
# stale name (`..._UNIMPLEMENTED`) keeps asserting the opposite of the truth.
# So it is recorded here, with its evidence, and `BLOCKERS` holds only what
# actually blocks.
RESOLVED_BLOCKERS = {
    'LIVE_PREGAME_FEATURE_BUILD_UNIMPLEMENTED': {
        'resolved_on': '2026-09-12',
        'resolved_by': 'nfl/prospective/q9shadow/live_features.py',
        'was': 'no pregame feature builder for the live season. '
               'nfl.research.q6.frame.load_frame refuses 2026 rows by design '
               'and production reports feature_build '
               'STAGE_DECLARED_UNIMPLEMENTED.',
        'evidence': {
            'artifact': 'nfl/prospective/q9shadow/Q9_LIVE_FEATURE_PARITY.json',
            'builder_parity': 'EXACT',
            'n_players_compared': 482,
            'n_players_differing': 0,
            'window': 'week 1 -- the window in which both builders are '
                      'defined',
            'runs_on_a_live_game': True,
        },
        'did_not_clear': ['INJURY_REPORT_INCOMPLETE',
                          'COMPLETE_ARTIFACT_LAYERS_ABSENT', 'G0A_11_OF_12'],
        'note': 'this resolution is the worked example of blocker '
                'independence: the builder exists and a live COMPLETE seal is '
                'still impossible.',
    },
}

BLOCKERS = {
    'COMPLETE_ARTIFACT_LAYERS_ABSENT': {
        'owner': 'the production forecast path',
        'what': 'protocol section 2 requires completeness == COMPLETE for an '
                'eligible forecast, and that means all nine required layers '
                'from nfl.research.completeness.LAYERS. The paired shadow '
                'build currently carries the target layer; team_volume, the '
                'three QB layers and carries come from the production run, '
                'and the downstream receiving layers need '
                'frozen_priors.receiving_priors, which refuses on any '
                'historical slice by its own leakage guard '
                '(RECEIVING_FRAME_CARRIES_FORECAST_SEASON; measured: 2026 '
                'PASS, 2025 FAIL, 2024 FAIL).',
        'blocks': 'section-4 credit and any promotion evidence',
        'needs_bytes_from_outside': False,
        'independent_of': ['INJURY_REPORT_INCOMPLETE', 'G0A_11_OF_12'],
        'artifact': 'nfl/prospective/q9shadow/Q9_COMPLETE_SHADOW_PARITY.json',
    },
    'INJURY_REPORT_INCOMPLETE': {
        'owner': 'the agent that holds network egress',
        'independent_of': ['G0A_11_OF_12',
                           'COMPLETE_ARTIFACT_LAYERS_ABSENT'],
        'what': 'the 2026 injury captures carry rows whose report_status is '
                'unfilled, and nfl.production.nonqb.inputs refuses that by '
                'name. An unfiled designation is not an absence of injury '
                'and may not be defaulted to healthy.',
        'blocks': 'the upstream appearance layer, and therefore both arms',
        'needs_bytes_from_outside': True,
        'measured': '12 of the 13 week-1 games still ahead of the clock on '
                    '2026-09-12 carry NOT_APPLICABLE[INJURY_REPORT_'
                    'INCOMPLETE] at the appearance stage; the thirteenth '
                    'carries NOT_APPLICABLE[NONQB_PLAYER_FRAME_INCOMPLETE].',
    },
    'G0A_11_OF_12': {
        'owner': 'governance',
        'independent_of': ['INJURY_REPORT_INCOMPLETE',
                           'COMPLETE_ARTIFACT_LAYERS_ABSENT'],
        'remaining_item_artifact':
            'nfl/prospective/q9shadow/Q9_G0A_REMAINING_ITEM.json',
        'remaining_item': 'item 1 -- kickoff-anchored vintage capture '
                          'scheduled and demonstrably running. Root cause '
                          'EGRESS. No waiver requested.',
        'what': 'protocol section 1 says no forecast written before G0A is '
                'discharged counts toward promotion. '
                'nfl.production.authorization.gate_state reports G0A 11/12.',
        'blocks': 'the countability of any seal, even a valid one',
        'needs_bytes_from_outside': True,
    },
}

STOP_RULE = {
    'source': FLOOR_SOURCE + ' and protocol section 9',
    'rule': 'no promotion on one or two favourable games. The prospective '
            'ledger is built first, and promotion requires every section-9 '
            'condition including an explicit owner decision.',
    'improvised_minimum': False,
    'improvised_minimum_note': (
        'no numeric minimum was invented here. The floors are transcribed '
        'from the protocol, which predates any 2026 result.'),
}


# ==================================================================
# PERMANENT EXCLUSION OF THE GUARD-BYPASS SEALS
# ==================================================================
#
# Six live artifacts were produced by a seal path that called
# `appearance_r8.predict` DIRECTLY, skipping
# `inputs.validate_appearance_inputs` -- the gate that refuses
# INJURY_REPORT_INCOMPLETE. They were deleted from disk and their ledger was
# removed before any was counted.
#
# AN ID BLACKLIST CANNOT BE THE GUARD, AND SAYING SO IS THE POINT. The run log
# printed only the first three forecast_ids and the artifacts are gone, so
# three of the six ids are UNRECOVERABLE. A list that is knowingly incomplete
# must not be presented as the control.
#
# The control is structural instead: every sealed artifact records the
# appearance interface it came through, and `assert_seal_path_governed`
# refuses any artifact that did not come through the governed one -- whatever
# its id, including the three whose ids are lost, and including any future
# bypass nobody has thought of yet. The id list below is an AUDIT RECORD, not
# the mechanism.
EXCLUDED_SEAL_BATCHES = ()          # populated below; see EXCLUDED_SEALS

EXCLUDED_SEALS = {
    'reason': 'SEAL_PATH_BYPASSED_APPEARANCE_INPUT_VALIDATION',
    'defect': 'the seal called nfl.production.nonqb.appearance_r8.predict '
              'directly, which skips '
              'nfl.production.nonqb.inputs.validate_appearance_inputs',
    'discovered_on': '2026-09-12',
    'n_artifacts': 6,
    'permanently_excluded': True,
    'may_ever_count_as_evidence': False,
    'disposition': 'deleted from disk and from the seal ledger before any was '
                   'counted; no metric, no accounting unit and no floor ever '
                   'included one',
    'recoverable_forecast_ids': [
        'Q9SH-fc559f3700c426cc',        # 2026_01_ATL_PIT / ATL
        'Q9SH-a62e9d18be8e7dcc',        # 2026_01_ATL_PIT / PIT
        'Q9SH-caccdcddef4f421d',        # 2026_01_BAL_IND / BAL
    ],
    'unrecoverable_forecast_ids': {
        'n': 3,
        'team_games': ['2026_01_BAL_IND / IND', '2026_01_BUF_HOU / BUF',
                       '2026_01_BUF_HOU / HOU'],
        'why': 'the run printed only the first three ids and the artifacts '
               'were deleted. Recorded as unrecoverable rather than guessed.',
    },
    'the_actual_control': 'assert_seal_path_governed -- a field check on every '
                          'artifact, complete by construction where an id '
                          'list cannot be',
}

# A SECOND BATCH, FOUND BY AUDITING THE FIRST FIX.
#
# The id lists in both batches are HISTORICAL AUDIT EVIDENCE. They are
# explicitly NON-EXHAUSTIVE (batch 1 is missing three ids that cannot be
# recovered) and NON-AUTHORITATIVE. The authoritative control is
# `assert_seal_path_governed`, a field check that does not depend on anyone
# having written an id down.
EXCLUDED_SEALS_2 = {'defect': 'nfl.production.nonqb.layers.appearance consults per-team '
           'readiness ONLY when `teams` is supplied. The seal called '
           'it without `teams`, so it took the slate-wide branch -- '
           'which returned ENGINE_INPUTS_READY while 28 of 32 teams '
           'had every injury row unfilled. Per-team readiness refuses '
           'those teams by name with INJURY_REPORT_INCOMPLETE. '
           'Omitting an argument is not a lighter version of calling '
           'the wrong function; the guard did not run either way.',
 'discovered_by': 'the audit of the live-seal terminal state: 26 of 26 '
                  'team-games sealed with 0 refusals while the injury '
                  'feed carried 159 of 167 rows without a '
                  'report_status',
 'discovered_on': '2026-09-12',
 'disposition': 'deleted from disk and from the seal ledger before any '
                'was counted; every one carried '
                'prospective_evidence=false and entered no metric, '
                'accounting unit or floor',
 'may_ever_count_as_evidence': False,
 'n_artifacts': 26,
 'permanently_excluded': True,
 'reason': 'SEAL_PATH_SKIPPED_PER_TEAM_READINESS_GATE',
 'recoverable_forecast_ids': ['Q9SH-181f9ab1c271d7d0',
                              'Q9SH-a89fe6a34ef8420d',
                              'Q9SH-5a825f68a09f4533',
                              'Q9SH-6dbde3189dc9d335',
                              'Q9SH-5d9b539a48a3a1e0',
                              'Q9SH-979c28f6d8a5c482',
                              'Q9SH-10cf6c9e9ce0b487',
                              'Q9SH-3c110a96a79a752f',
                              'Q9SH-5cc2612eef7536f0',
                              'Q9SH-dd71e69cbc4e0c39',
                              'Q9SH-ddabbff169afd4c3',
                              'Q9SH-cc477d7e0e7e8e5e',
                              'Q9SH-8d7c397191958df0',
                              'Q9SH-5d7006bf14b0d92d',
                              'Q9SH-d0922be3004654d8',
                              'Q9SH-1e3edf9595057481',
                              'Q9SH-100419f74de2eb6c',
                              'Q9SH-b2f2f7405362da1a',
                              'Q9SH-6c2a75d12c019222',
                              'Q9SH-bf7bdc52fad0991b',
                              'Q9SH-ae993c26d891b7b7',
                              'Q9SH-5916e6ff1cd27ac7',
                              'Q9SH-97d343e3e60f685c',
                              'Q9SH-e93a54cb102b89d6',
                              'Q9SH-7e0b63f382042800',
                              'Q9SH-8cfdaea03fa025f3'],
 'the_actual_control': 'assert_seal_path_governed now also requires '
                       'seal_path.readiness_gate == PER_TEAM, so an '
                       'artifact built through the slate-wide branch '
                       'is refused by a field check rather than by an '
                       'id list',
 'unrecoverable_forecast_ids': {'n': 0,
                                'team_games': [],
                                'why': 'the ledger was intact, so all '
                                       '26 ids are recorded'}}

EXCLUDED_SEAL_BATCHES = (EXCLUDED_SEALS, EXCLUDED_SEALS_2)

GOVERNED_APPEARANCE_INTERFACE = 'nfl.production.nonqb.layers.appearance'
PER_TEAM_READINESS_GATE = 'PER_TEAM'


def assert_seal_path_governed(art) -> Outcome:
    """Refuse an artifact that did not come through the governed appearance
    interface, whatever its forecast_id.

    An artifact with NO `seal_path` is refused too. It predates the field, so
    nothing establishes which interface produced it -- and "we cannot tell" is
    not one of the permitted answers for something that would be counted.
    """
    sp = art.get('seal_path')
    if not sp:
        return Outcome.fail(
            'Q9_SEAL_PATH_UNRECORDED',
            f'{art.get("forecast_id")} carries no seal_path, so which '
            f'appearance interface produced it cannot be established. An '
            f'artifact that cannot say how it was built may not be counted.')
    got = sp.get('appearance_interface')
    if got != GOVERNED_APPEARANCE_INTERFACE:
        return Outcome.fail(
            'Q9_SEAL_PATH_NOT_GOVERNED',
            f'{art.get("forecast_id")} came through {got!r} rather than '
            f'{GOVERNED_APPEARANCE_INTERFACE!r}, which skips '
            f'inputs.validate_appearance_inputs. '
            f'{EXCLUDED_SEALS["disposition"]}.',
            appearance_interface=got)
    if sp.get('upstream_test_only'):
        return Outcome.fail(
            'Q9_SEAL_PATH_TEST_ONLY_UPSTREAM',
            f'{art.get("forecast_id")} was built on a TEST_ONLY appearance '
            f'fixture. A fixture-sourced forecast is not a forecast.')
    # THE PER-TEAM READINESS GATE MUST HAVE RUN.
    #
    # Calling the governed interface is necessary and NOT sufficient:
    # `layers.appearance` consults per-team readiness only when `teams` is
    # supplied, and the slate-wide branch it falls back to returned
    # ENGINE_INPUTS_READY on a slate where 28 of 32 teams had every injury row
    # unfilled. Twenty-six artifacts sealed through that branch.
    if sp.get('readiness_gate') != PER_TEAM_READINESS_GATE:
        return Outcome.fail(
            'Q9_SEAL_PATH_READINESS_GATE_NOT_PER_TEAM',
            f'{art.get("forecast_id")} records readiness_gate='
            f'{sp.get("readiness_gate")!r}. The per-team gate is the one that '
            f'refuses INJURY_REPORT_INCOMPLETE; the slate-wide branch does '
            f'not, despite a comment claiming it is more conservative.',
            readiness_gate=sp.get('readiness_gate'))
    return Outcome.ok('Q9_SEAL_PATH_GOVERNED', value=got)


# ==================================================================
# BLOCKER INDEPENDENCE, EVALUATED RATHER THAN DECLARED
# ==================================================================
#
# Each blocker is computed from its OWN source by its own evaluator. Two
# blockers sharing an evaluator would move together, and a declared
# `independent_of` list would then be a claim the code contradicts.
def _eval_complete_layers():
    art = HERE / 'Q9_COMPLETE_SHADOW_PARITY.json'
    if not art.exists():
        return 'BLOCKED', 'no paired-build artifact'
    d = json.loads(art.read_text())
    return (('CLEARED', 'all nine required layers present')
            if d.get('is_eligible_forecast_under_section_2')
            else ('BLOCKED', f'completeness is '
                             f'{d.get("contract_completeness_today")}'))


def _eval_injury_report():
    from nfl.prospective.q9shadow import live_features as LF
    import datetime as _dt
    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    o = LF.injury_rows(2026, now)
    if o.state is not State.PASS:
        return 'BLOCKED', f'{o.code}'
    n = o.evidence.get('n_without_report_status') or 0
    return (('CLEARED', 'every captured row carries a report_status')
            if n == 0 else
            ('BLOCKED', f'{n} captured row(s) carry no report_status'))


def _eval_g0a():
    from nfl.prospective.q9shadow import g0a as G0A
    o = G0A.check()
    return (('CLEARED', o.detail) if o.state is State.PASS
            else ('BLOCKED', f'{o.code}'))


BLOCKER_EVALUATORS = {
    'COMPLETE_ARTIFACT_LAYERS_ABSENT': _eval_complete_layers,
    'INJURY_REPORT_INCOMPLETE': _eval_injury_report,
    'G0A_11_OF_12': _eval_g0a,
}


def blocker_states():
    """Every blocker's state, each from its own source."""
    out = {}
    for name, fn in BLOCKER_EVALUATORS.items():
        try:
            state, detail = fn()
        except Exception as exc:                              # noqa: BLE001
            # AN EVALUATOR THAT CRASHED IS NOT A BLOCKED BLOCKER.
            #
            # The first version returned 'BLOCKED' here, and a missing `State`
            # import then made two of the three blockers read BLOCKED for a
            # NameError -- a code defect wearing a governance state. EVALUATOR
            # _ERROR is its own state so a crash can never be mistaken for a
            # measurement, in either direction.
            state, detail = 'EVALUATOR_ERROR', f'{type(exc).__name__}: {exc}'
        out[name] = {'state': state, 'detail': str(detail)[:300],
                     'evaluator': fn.__name__}
    return out


def assert_blockers_independent() -> Outcome:
    """Clearing one blocker must not change any other's computed state.

    NOT A DECLARATION. Each blocker is forced CLEARED in turn and every OTHER
    blocker is recomputed; a state that moves means the two share a cause and
    the `independent_of` lists are lying. The evaluators are also required to
    be distinct functions, because two names pointing at one evaluator would
    pass the perturbation test while being the same blocker twice.
    """
    names = sorted(BLOCKER_EVALUATORS)
    fns = [BLOCKER_EVALUATORS[n] for n in names]
    # SHARING IS DETECTED BY IDENTITY, NEVER BY VALUE.
    #
    # Two evaluators that happen to return the same answer today are not the
    # same evaluator, and two that return different answers may still be one
    # function behind a wrapper. So three identity tests, each catching a
    # different aliasing shape, and no comparison of returned values anywhere:
    #   id()        the same function object registered twice
    #   __code__    a different wrapper object around the same code
    #   __name__    a rename that leaves both pointing at one definition
    for label, key in (('object identity', id),
                       ('code object', lambda f: f.__code__),
                       ('name', lambda f: f.__name__)):
        seen = {}
        for nm, f in zip(names, fns):
            k = key(f)
            if k in seen:
                return Outcome.fail(
                    'Q9_BLOCKERS_SHARE_AN_EVALUATOR',
                    f'{seen[k]!r} and {nm!r} share an evaluator by {label}. '
                    f'They would move together, so they are one blocker under '
                    f'two names -- regardless of whether their current '
                    f'answers agree.',
                    aliased=[seen[k], nm], by=label)
            seen[k] = nm
    declared = {n: set(BLOCKERS[n]['independent_of']) for n in names
                if n in BLOCKERS}
    incomplete = {n: sorted(set(names) - {n} - d)
                  for n, d in declared.items() if set(names) - {n} - d}
    if incomplete:
        return Outcome.fail(
            'Q9_BLOCKER_INDEPENDENCE_NOT_DECLARED',
            f'{incomplete} are not named in the corresponding '
            f'independent_of lists.', missing=incomplete)

    base = blocker_states()
    broken = {n: v['detail'] for n, v in base.items()
              if v['state'] == 'EVALUATOR_ERROR'}
    if broken:
        return Outcome.fail(
            'Q9_BLOCKER_EVALUATOR_ERROR',
            f'{len(broken)} blocker evaluator(s) raised: {broken}. An '
            f'independence result computed over crashed evaluators would be '
            f'a statement about the crash, not about the blockers.',
            broken=broken)
    moved = []
    saved = dict(BLOCKER_EVALUATORS)
    try:
        for n in names:
            BLOCKER_EVALUATORS[n] = lambda: ('CLEARED', 'forced for the test')
            after = blocker_states()
            for other in names:
                if other == n:
                    continue
                if after[other]['state'] != base[other]['state']:
                    moved.append({'cleared': n, 'also_moved': other,
                                  'from': base[other]['state'],
                                  'to': after[other]['state']})
            BLOCKER_EVALUATORS[n] = saved[n]
    finally:
        BLOCKER_EVALUATORS.clear()
        BLOCKER_EVALUATORS.update(saved)
    if moved:
        return Outcome.fail(
            'Q9_BLOCKERS_NOT_INDEPENDENT',
            f'clearing one blocker moved another: {moved}. They share a '
            f'cause, so clearing one would silently appear to clear the '
            f'other.', moved=moved)
    return Outcome.ok(
        'Q9_BLOCKERS_MECHANICALLY_INDEPENDENT',
        value={'n_blockers': len(names), 'states': base},
        detail=f'{len(names)} blocker(s), {len(set(fns))} distinct '
               f'evaluator(s); forcing each CLEARED in turn moved no other',
        n_blockers=len(names), n_perturbations=len(names))


NON_CLEARED_BLOCKER_STATES = ('BLOCKED', 'EVALUATOR_ERROR')


def promotion_gate() -> Outcome:
    """May promotion or a COMPLETE declaration proceed? Today: no.

    REFUSES ON BOTH NON-CLEARED STATES. `BLOCKED` means the blocker was
    measured and holds; `EVALUATOR_ERROR` means it could not be measured. A
    gate that refused only the first would let a crashed evaluator read as
    permission, which is the same defect as an unfilled injury designation
    read as an absence of injury.

    This function cannot return PASS while any blocker is non-cleared, and it
    has no argument, flag or override that changes that.
    """
    st = blocker_states()
    bad = {n: v['state'] for n, v in st.items()
           if v['state'] in NON_CLEARED_BLOCKER_STATES}
    if bad:
        return Outcome.blocked(
            'Q9_PROMOTION_REFUSED_BLOCKERS_NOT_CLEARED',
            f'{len(bad)} blocker(s) are not cleared: {bad}. '
            f'BLOCKED means measured and holding; EVALUATOR_ERROR means not '
            f'measured at all. Neither is permission.',
            cause=Cause.GOVERNANCE, blockers=bad, states=st)
    return Outcome.blocked(
        'Q9_PROMOTION_STILL_REQUIRES_AN_OWNER_DECISION',
        'every blocker is cleared, and that is not promotion. Protocol '
        'section 9 requires the section-4 floors, a Holm-Bonferroni-corrected '
        'CRPS win, randomized PIT not worse, and an explicit owner decision '
        'that no code path can produce.',
        cause=Cause.GOVERNANCE, states=st)


def append_rows(rows, path=None):
    """Append-only. Nothing on disk is rewritten, ever."""
    p = pathlib.Path(path or LEDGER)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'a') as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True, default=str) + '\n')
    return len(rows)


def load(path=None):
    p = pathlib.Path(path or LEDGER)
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def current(path=None):
    """CURRENT outcome versions only, by the governed supersession rule."""
    return PG.current_rows(rows=load(path))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--schema', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--state', action='store_true')
    ap.add_argument('--season', type=int, default=2026)
    a = ap.parse_args(argv)
    if a.schema:
        sch = schema()
        LEDGER_SCHEMA.write_text(json.dumps(sch, indent=1, default=str) + '\n')
        print(f'schema written: {LEDGER_SCHEMA}')
        print(f'  row fields   : {len(sch["row_fields"])}')
        print(f'  floors       : {sorted(sch["floors"])}')
        print(f'  floor source : {sch["floor_source"]}')
    if a.report:
        rows = current()
        acc = accounting(rows)
        print(f'ledger rows        : {acc["scoring_rows_including_non_evidence"]}')
        print(f'counted as evidence: {acc["scoring_rows"]}')
        for k in ('distinct_games', 'distinct_team_games',
                  'distinct_player_games'):
            print(f'  {k:26s} {acc[k]}')
        for name, v in floor_verdicts(acc).items():
            print(f'  {name:34s} {v["state"]} '
                  f'(have {v["have_forecasts"]}/{v["floor"]["n_forecasts"]} '
                  f'forecasts)')
    if a.state:
        st = state(a.season)
        LEDGER_STATE.write_text(json.dumps(st, indent=1, default=str) + '\n')
        print(f'state written: {LEDGER_STATE}')
        print(f"  rows counted as evidence : "
              f"{st['accounting']['scoring_rows']}")
        print(f"  games ahead of the clock : "
              f"{st['live_eligibility']['n_games_ahead_of_clock']}")
        print(f"  sealed                   : "
              f"{st['live_eligibility']['n_sealed']}")
        for k, v in st['live_eligibility']['refusal_census'].items():
            print(f'    {v:4d}  {k}')
        for k in st['blockers']:
            print(f'  blocker: {k}')
    if not (a.schema or a.report or a.state):
        ap.print_help()
    return 0


if __name__ == '__main__':
    sys.exit(main())
