"""Q9B step 1: is the hurdle STRUCTURAL, or is it a mis-estimated share?

    python3.12 -m nfl.research.q9b.identify

THE QUESTION Q9 DID NOT ANSWER. Q9 improved zero-mass calibration and marginal
CRPS. That is consistent with a structural hurdle AND with a plain allocator
whose share estimates are simply wrong. Improving is not evidence of the
mechanism you had in mind, and this module measures which it is before any
competitor is built.

THE DECOMPOSITION. Under a multinomial allocator with team budget N and shares
pi over the appearing players, the implied zero probability for player i is
exactly

    P(Y_i = 0 | appears, N, pi) = (1 - pi_i)^N

averaged over the budget's own predictive distribution. So the observed zero
rate can be split three ways:

    MULTINOMIAL SAMPLING ZERO   (1 - pi*_i)^N under a CORRECT share
    MIS-ESTIMATED SHARE          the gap between the production share's implied
                                 zero mass and that correct-share value
    STRUCTURAL EXCESS            what the observation still has left over

pi* IS A PARAMETER ORACLE, NOT A REALISATION ORACLE. It is the player's own
realised share averaged over his APPEARING GAMES IN THE EVALUATION SEASON,
renormalised within each team-week -- not that game's share. Using the game's
own share would hand a zero-target player a share of exactly zero, predict his
zero with certainty, and prove nothing except that the outcome knows itself.
That is the conditioning-on-the-outcome trap Q8 caught in a different place.

WHAT EACH VERDICT WOULD MEAN.

  structural excess near zero      the hurdle is NOT identified. A better
                                   share model should recover Q9's gain and the
                                   plain family is the right one.
  structural excess large          there is zero mass a correctly-shared
                                   multinomial cannot produce, and a hurdle is
                                   a real mechanism rather than a
                                   reparameterisation.

THE DISPERSION AUDIT rides along because it gates the same decision: a
Dirichlet-multinomial arm enters the comparison only if cross-player variance
genuinely exceeds the multinomial's N*pi*(1-pi), and not because a literature
scan recommends it.
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.research.q6 import frame as Q6F                          # noqa: E402
from nfl.research.q6 import forward_chain as Q6C                  # noqa: E402
from nfl.research.q7 import panel as Q7P                          # noqa: E402
from nfl.research.q8 import audit as AUD                          # noqa: E402
from nfl.research.q9 import hurdle as Q9                          # noqa: E402

SPEC_VERSION = 'q9b-identifiability-1'
HERE = _REPO / 'nfl' / 'research' / 'q9b'
EVAL_SEASONS = Q9.EVAL_SEASONS
SEED = 20260922
N_BUDGET_DRAWS = 400


def _prep():
    rows, _ = Q6F.load_frame()
    rows = Q6F.attach_role_class(rows)
    rows, _ = Q6F.attach_opportunity(rows)
    rows = AUD._own_history(rows)
    q7 = Q7P.load_recv()
    rows, _ = AUD.attach_receiving(rows, q7)
    rows = Q9.attach_hurdle_history(rows)
    return rows, q7


def _season_mean_shares(test):
    """pi*: each player's realised share averaged over his APPEARING games.

    A PARAMETER oracle. It is an evaluation-season aggregate, never that
    team-week's own answer, so it says "if the share estimate were right" and
    not "if the outcome were known".
    """
    by = collections.defaultdict(list)
    for r in test:
        if r['appeared'] and r.get('share_targets') is not None:
            by[r['pid']].append(r['share_targets'])
    return {k: float(np.mean(v)) for k, v in by.items()}


def _implied_zero(pi, budget_draws):
    """E_N[(1 - pi)^N], the exact multinomial zero mass under share pi."""
    pi = np.clip(np.asarray(pi, float), 0.0, 1.0)
    B = np.asarray(budget_draws, float).reshape(-1, 1)
    return np.power(1.0 - pi.reshape(1, -1), B).mean(axis=0)


def run(eval_seasons=EVAL_SEASONS, seed=SEED, progress=True):
    rows, q7 = _prep()
    denom = AUD.load_denom()
    p_r8 = AUD.load_p_r8()
    out, disp_rows, fit_log = [], [], []

    for Y in eval_seasons:
        train = [r for r in rows if r['s'] < Y]
        test = [r for r in rows if r['s'] == Y]
        if not train or not test:
            continue
        cm_fit = AUD._class_means(train)
        k_fit, _ = Q6C._share_k(train, 'targets')
        bud_point, bud_resid, _ = AUD.budget_model(denom, Y)
        star = _season_mean_shares(test)
        rng = np.random.default_rng([seed, Y])

        groups = collections.defaultdict(list)
        for r in test:
            groups[(r['s'], r['w'], r['t'])].append(r)

        for gkey, g in sorted(groups.items()):
            den = int(g[0]['den_targets'])
            if den <= 0:
                continue
            app = [r for r in g if r['appeared']]
            if len(app) < 2:
                continue
            own = np.array([r['own_share'] if r['own_share'] is not None
                            else AUD._class_of(cm_fit, r) for r in app], float)
            n_own = np.array([r['own_n'] for r in app], float)
            cls = np.array([AUD._class_of(cm_fit, r) for r in app], float)
            w = np.where(n_own > 0, n_own / (n_own + k_fit), 0.0)
            base = np.maximum(w * own + (1 - w) * cls, 0.0)
            if base.sum() <= 0:
                continue
            pi_hat = base / base.sum()
            s = np.array([star.get(r['pid'], 0.0) for r in app], float)
            if s.sum() <= 0:
                continue
            pi_star = s / s.sum()
            budget = np.maximum(np.rint(
                bud_point.get(gkey, den)
                + bud_resid[rng.integers(0, len(bud_resid), N_BUDGET_DRAWS)]),
                0).astype(int)
            z_hat = _implied_zero(pi_hat, budget)
            z_star = _implied_zero(pi_star, budget)
            for j, r in enumerate(app):
                out.append({
                    'season': Y, 'team_game': f"{Y}-{r['w']}-{r['t']}",
                    'pid': r['pid'], 'pos': r['pos'],
                    'role_class': r['role_class'],
                    'prior_depth': r['prior_depth_bucket'],
                    'appearance_certainty': Q9._certainty(
                        p_r8.get((r['s'], r['w'], r['t'], r['pid']), 0.0)),
                    'n_appearing': len(app),
                    'team_budget': den,
                    'pi_hat': float(pi_hat[j]), 'pi_star': float(pi_star[j]),
                    'implied_zero_pi_hat': float(z_hat[j]),
                    'implied_zero_pi_star': float(z_star[j]),
                    'observed_zero': int(r['targets'] == 0),
                    'targets': int(r['targets']),
                })
                # DISPERSION: the realised count against the multinomial's own
                # variance at the correct share. Accumulated per player-game
                # and pooled per player below.
                disp_rows.append({
                    'pid': r['pid'], 'season': Y,
                    'n': float(den), 'pi': float(pi_star[j]),
                    'y': float(r['targets'])})
        fit_log.append({'eval_season': Y, 'n_rows': len(out),
                        'n_players_with_a_season_mean_share': len(star)})
        if progress:
            print(f'  {Y}: {len(out)} cumulative rows', flush=True)
    return {'rows': out, 'dispersion': disp_rows, 'fit_log': fit_log}


# ------------------------------------------------------------- reporting
def _decompose(rs):
    obs = float(np.mean([r['observed_zero'] for r in rs]))
    zh = float(np.mean([r['implied_zero_pi_hat'] for r in rs]))
    zs = float(np.mean([r['implied_zero_pi_star'] for r in rs]))
    return {
        'n': len(rs),
        'observed_zero_rate': round(obs, 6),
        'implied_zero_production_share': round(zh, 6),
        'implied_zero_correct_share': round(zs, 6),
        'multinomial_sampling_zero': round(zs, 6),
        'mis_estimated_share_component': round(zh - zs, 6),
        'structural_excess': round(obs - zs, 6),
        'structural_excess_share_of_total_zero': (
            round((obs - zs) / obs, 5) if obs > 0 else None),
        'production_shortfall_vs_observed': round(zh - obs, 6),
        'reads': ('structural excess near zero means a correctly-shared '
                  'multinomial already produces the observed zero mass and the '
                  'hurdle is not identified; a large positive excess means '
                  'there is zero mass no multinomial with a correct share can '
                  'produce'),
    }


def _sweep(rows, keyf, minimum=200):
    g = collections.defaultdict(list)
    for r in rows:
        g[keyf(r)].append(r)
    return {k: _decompose(v) for k, v in sorted(g.items())
            if len(v) >= minimum}


def _dispersion(disp_rows, minimum=8):
    """Observed variance against the multinomial's own N*pi*(1-pi).

    THE GATE FOR A DIRICHLET-MULTINOMIAL ARM. It enters the comparison only if
    the ratio is meaningfully above 1 -- never because a literature scan
    recommends it. The comparison is made at the CORRECT share, so a ratio
    above 1 cannot be an artefact of a bad share estimate.
    """
    by = collections.defaultdict(list)
    for r in disp_rows:
        by[r['pid']].append(r)
    ratios, n_used = [], 0
    for pid, rs in by.items():
        if len(rs) < minimum:
            continue
        y = np.array([r['y'] for r in rs], float)
        exp_var = float(np.mean([r['n'] * r['pi'] * (1 - r['pi'])
                                 for r in rs]))
        mu = np.array([r['n'] * r['pi'] for r in rs], float)
        obs_var = float(np.mean((y - mu) ** 2))
        if exp_var > 1e-9:
            ratios.append(obs_var / exp_var)
            n_used += 1
    if not ratios:
        return {'n_players': 0, 'verdict': 'NOT_ESTIMABLE'}
    a = np.array(ratios, float)
    med = float(np.median(a))
    # Pre-declared threshold, fixed before the number was read: a ratio below
    # 1.25 is not "meaningful overdispersion" for a mechanism whose whole
    # justification is extra variance.
    thresh = 1.25
    verdict = ('OVERDISPERSED_DM_JUSTIFIED' if med >= thresh
               else 'NOT_MEANINGFULLY_OVERDISPERSED_DM_REFUSED')
    return {
        'n_players': n_used,
        'min_games_per_player': minimum,
        'variance_ratio_median': round(med, 5),
        'variance_ratio_mean': round(float(a.mean()), 5),
        'variance_ratio_p25': round(float(np.percentile(a, 25)), 5),
        'variance_ratio_p75': round(float(np.percentile(a, 75)), 5),
        'share_above_1': round(float((a > 1.0).mean()), 5),
        'predeclared_threshold': thresh,
        'verdict': verdict,
        'reads': ('the ratio of realised variance to the multinomial variance '
                  'at the CORRECT share. Above 1 is overdispersion a '
                  'multinomial cannot produce; the threshold was fixed before '
                  'the number was read.'),
    }


def summarise(res):
    rows = res['rows']
    out = {
        'artifact': 'NFL_Q9B_IDENTIFIABILITY_AUDIT',
        'spec_version': SPEC_VERSION,
        'promoted': False, 'is_research_only': True,
        'market_inputs_used': [], 'live_2026_rows_used': 0,
        'n_rows': len(rows),
        'eval_seasons': sorted({r['season'] for r in rows}),
        'population': 'appearing players in team-weeks with a positive budget',
        'oracle_kind': (
            'pi* is a PARAMETER oracle -- the player\'s realised share '
            'averaged over his appearing games in the evaluation season, '
            'renormalised within the team-week. It is never that game\'s own '
            'share, which would predict a zero-target player\'s zero with '
            'certainty and prove nothing.'),
        'overall': _decompose(rows),
        'by_position': _sweep(rows, lambda r: r['pos']),
        'by_role_class': _sweep(rows, lambda r: r['role_class']),
        'by_prior_depth': _sweep(rows, lambda r: r['prior_depth']),
        'by_appearance_certainty': _sweep(
            rows, lambda r: r['appearance_certainty']),
        'by_team_budget_band': _sweep(rows, lambda r: _budget_band(
            r['team_budget'])),
        'dispersion_audit': _dispersion(res['dispersion']),
        'fit_log': res['fit_log'],
    }
    out['verdict'] = _verdict(out)
    return out


def _budget_band(n):
    return ('<25' if n < 25 else '25-32' if n < 33 else
            '33-39' if n < 40 else '40+')


def _verdict(out):
    o = out['overall']
    ex = o['structural_excess']
    tot = o['observed_zero_rate']
    frac = ex / tot if tot else 0.0
    # Pre-declared before the number was read: a structural excess under 2
    # percentage points of the zero rate, or under 5% of it, is not a
    # mechanism -- it is a share problem wearing a mechanism's name.
    identified = bool(ex >= 0.02 and frac >= 0.05)
    return {
        'structural_excess': ex,
        'structural_excess_fraction_of_zero_mass': round(frac, 5),
        'mis_estimated_share_component': o['mis_estimated_share_component'],
        'multinomial_sampling_zero': o['multinomial_sampling_zero'],
        'hurdle_identified_as_structural': identified,
        'predeclared_rule': ('a structural excess of at least 2 percentage '
                             'points AND at least 5% of the observed zero '
                             'mass, both fixed before the numbers were read'),
        'means': ('IDENTIFIED: there is zero mass a correctly-shared '
                  'multinomial cannot produce, so a hurdle is a mechanism. '
                  'NOT IDENTIFIED: a better share model should recover Q9\'s '
                  'gain and the plain family is the right one.'
                  if identified else
                  'NOT IDENTIFIED: the observed zero mass is within reach of a '
                  'multinomial with a correct share, so Q9\'s gain is '
                  'evidence about the SHARE ESTIMATE and not about a '
                  'structural hurdle. A plain allocator with better shares '
                  'should recover it, and MNL_PLUS is the test of that.'),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--seasons', default=','.join(str(s) for s in EVAL_SEASONS))
    a = ap.parse_args(argv)
    res = run(tuple(int(x) for x in a.seasons.split(',')))
    s = summarise(res)
    (HERE / 'Q9B_IDENTIFIABILITY.json').write_text(
        json.dumps(s, indent=1, default=str) + '\n')
    o = s['overall']
    print(f"\nrows                          : {s['n_rows']}")
    print(f"observed zero rate            : {o['observed_zero_rate']:.5f}")
    print(f"  multinomial sampling zero   : {o['multinomial_sampling_zero']:.5f}"
          f"   (at the CORRECT share)")
    print(f"  mis-estimated share         : "
          f"{o['mis_estimated_share_component']:+.5f}")
    print(f"  STRUCTURAL EXCESS           : {o['structural_excess']:+.5f}"
          f"   ({100 * (s['verdict']['structural_excess_fraction_of_zero_mass'] or 0):.2f}% of zero mass)")
    print(f"production implied zero       : "
          f"{o['implied_zero_production_share']:.5f}")
    print(f"\nhurdle identified as structural: "
          f"{s['verdict']['hurdle_identified_as_structural']}")
    d = s['dispersion_audit']
    print(f"dispersion ratio median        : "
          f"{d.get('variance_ratio_median')}  -> {d.get('verdict')}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
