#!/usr/bin/env python3.12
"""WS-M reproduction probe. READ-ONLY: imports repository modules and reads one
sealed run. Writes nothing, changes nothing, runs no suite, opens no price.

Regenerates sections 3, 4, 5b and 5c of WS_M_CONFIDENCE_SEMANTICS.md:

  3.  presence / allocation split of each player's OWN-TEAM opportunity share
  4.  opponent-volume perturbation, own-team basis against the published basis
  5b. magnitude entanglement of every candidate scalar
  5c. two team-level allocation entropies, and the mutual information between
      the draw and the identity of the opportunity-taker

THE DENOMINATOR RULE, STATED ONCE AND USED EVERYWHERE BELOW. A player's own
opportunity metric follows `_role()`'s branching -- a back's role is his
carries, not his targets. His DENOMINATOR, however, is every team-mate
carrying a row for that layer/key, backs included. The two are different
questions and conflating them undercounts a receiving pool by the running
backs' targets: on the evidence run it moves CeeDee Lamb's own-team share from
0.2231 to 0.2580. The wide reading is used because "his share of his own
team's targets" means all of his team's targets, and because it reconciles
with the own-team shares WS06 computed independently (Lamb 0.2234, Dart
0.8914).

Every player is addressed by gsis_id through Forecast.row_index(), which reads
the artifact's own draws_ref.row. No row is taken positionally.

    python3.12 nfl/research/remediation/ws_m/ws_m_probe.py [RUN_DIR]
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4]))

from nfl.product import distributions as D   # noqa: E402

DEFAULT_RUN = ('nfl/research/live/2026_01_DAL_NYG/FORENSIC_CORRECTED_RESEARCH/'
               '4b186a21b83a49ec')


def opportunity_metric(position, layers):
    """Which metric defines THIS player's role, mirroring _role()'s branching."""
    if 'qb' in layers:
        return ('qb', 'db')
    order = ((('rushing', 'carries'), ('receiving', 'targets'))
             if position == 'RB'
             else (('receiving', 'targets'), ('rushing', 'carries')))
    for cand in order:
        if cand[0] in layers:
            return cand
    return None


def spearman(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = np.isfinite(a) & np.isfinite(b)
    a, b = a[m], b[m]
    if len(a) < 3:
        return float('nan'), len(a)
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    return float(np.corrcoef(ra, rb)[0, 1]), len(a)


def bimodality(x):
    x = np.asarray(x, float)
    n = len(x)
    if n < 4:
        return float('nan')
    s = x.std(ddof=1)
    if s <= 0:
        return float('nan')
    z = (x - x.mean()) / s
    g1 = float((z ** 3).mean())
    g2 = float((z ** 4).mean()) - 3.0
    return (g1 ** 2 + 1.0) / (g2 + 3.0 * (n - 1) ** 2 / ((n - 2) * (n - 3)))


def norm_entropy(x, edges):
    h, _ = np.histogram(x, bins=edges)
    p = h[h > 0] / h.sum()
    return 0.0 if len(p) <= 1 else float(-(p * np.log(p)).sum()
                                         / np.log(len(edges) - 1))


def shannon(w):
    w = np.asarray(w, float)
    w = w[w > 0]
    return float(-(w * np.log(w)).sum())


def pools(fc, players):
    """(team, layer, key) -> list of gsis_id with a stored row. THE WIDE
    DENOMINATOR: everyone on the team who can take this opportunity."""
    out = {}
    for p in players:
        for layer in p['layers']:
            for key in ('db', 'carries', 'targets'):
                if fc.vector(layer, key, p['gsis_id']) is not None:
                    out.setdefault((p['team'], layer, key),
                                   []).append(p['gsis_id'])
    return out


def main(run_dir):
    run = pathlib.Path(run_dir)
    fc = D.Forecast(run)
    board = json.loads((run / 'board.json').read_text())
    players = board['players']
    pool = pools(fc, players)

    print(f'run              {run}')
    print(f'game_id          {fc.game_id}')
    print(f'draws            {fc.n_draws}')
    print(f'content_digest   {fc.content_digest}')
    print(f'board players    {len(players)}')
    print('pools (wide denominator): ' + ', '.join(
        f'{t}/{l}/{k}:{len(v)}' for (t, l, k), v in sorted(pool.items())))

    # ---------------------------------------------------------------- s3
    print('\n=== 3. presence / allocation split, OWN-TEAM denominator ===')
    cols = ('gsis pos team depth metric pub_score pub_role mu_share p_absent '
            'mu_cond sd_cond vr_uncond share_defined n_cond').split()
    print('\t'.join(cols))
    rows = []
    for p in players:
        om = opportunity_metric(p['position'], p['layers'])
        if om is None:
            continue
        layer, key = om
        v = fc.vector(layer, key, p['gsis_id'])
        mates = pool[(p['team'], layer, key)]
        if p['gsis_id'] not in mates:
            raise SystemExit(f'POOL_MEMBERSHIP_ERROR: {p["gsis_id"]} absent '
                             f'from its own {p["team"]} {layer}/{key} pool')
        tot = np.sum([fc.vector(layer, key, g) for g in mates], axis=0)
        ok = tot > 0
        s = np.where(ok, v / np.where(ok, tot, 1.0), np.nan)
        sc = s[(v > 0) & ok]
        mu = float(np.nanmean(s))
        var = float(np.nanvar(s, ddof=1))
        mu_c = float(sc.mean()) if len(sc) > 3 else float('nan')
        rows.append(dict(
            gsis=p['gsis_id'], pos=p['position'], team=p['team'],
            depth=p.get('depth_chart'), metric=f'{layer}/{key}',
            pub_score=p['confidence']['score'],
            pub_role=p['confidence']['parts']['role_certainty'],
            mu_share=mu, p_absent=float((v <= 0).mean()), mu_cond=mu_c,
            sd_cond=float(sc.std(ddof=1)) if len(sc) > 3 else float('nan'),
            vr_uncond=var / (mu * (1 - mu)) if 0 < mu < 1 else float('nan'),
            sd_uncond=float(np.nanstd(s, ddof=1)),
            iqr_uncond=float(np.nanpercentile(s, 75)
                             - np.nanpercentile(s, 25)),
            ent_uncond=norm_entropy(s[ok], np.linspace(0, 1, 21)),
            bimod_uncond=bimodality(s[ok]),
            share_defined=float(ok.mean()), n_cond=len(sc)))
    for r in sorted(rows, key=lambda r: -r['pub_score']):
        print('\t'.join('%.4f' % r[c] if isinstance(r[c], float) else str(r[c])
                        for c in cols))

    # ---------------------------------------------------------------- s4
    print('\n=== 4. opponent-volume perturbation (lead QB of each team) ===')
    teams = sorted({p['team'] for p in players})
    for team in teams:
        opp = [t for t in teams if t != team][0]
        own = np.sum([fc.vector('qb', 'db', g)
                      for g in pool[(team, 'qb', 'db')]], axis=0)
        oth = np.sum([fc.vector('qb', 'db', g)
                      for g in pool[(opp, 'qb', 'db')]], axis=0)
        lead = max(pool[(team, 'qb', 'db')],
                   key=lambda g: fc.vector('qb', 'db', g).mean())
        v = fc.vector('qb', 'db', lead)
        ok = own > 0
        s = v[ok] / own[ok]
        print(f'  {team} lead QB {lead} (opponent {opp})')
        for f in (0.70, 0.85, 1.00, 1.15, 1.30):
            game = float((own + f * oth).mean())
            print(f'    {opp} x{f:.2f}: game-pool share='
                  f'{float(v.mean()) / game:.4f}  own-team share='
                  f'{float(v.mean()) / float(own.mean()):.4f}  '
                  f'p_absent={float((v <= 0).mean()):.4f}  '
                  f'sd_own={float(s.std(ddof=1)):.4f}')

    # --------------------------------------------------------------- s5b
    print('\n=== 5b. magnitude entanglement: Spearman(candidate, mean share) '
          '===')
    mu = [r['mu_share'] for r in rows]
    mu_c = [r['mu_cond'] for r in rows]
    for cand in ('sd_uncond', 'iqr_uncond', 'ent_uncond', 'vr_uncond',
                 'bimod_uncond', 'p_absent', 'pub_role', 'pub_score'):
        rho, n = spearman([r[cand] for r in rows], mu)
        print(f'  {cand:13s} vs mean own-team share   rho={rho:+.4f}  n={n}')
    rho, n = spearman([r['sd_cond'] for r in rows], mu_c)
    print(f'  sd_cond       vs conditional mean      rho={rho:+.4f}  n={n}')
    cv = [r['sd_cond'] / r['mu_cond'] if r['mu_cond'] > 0 else float('nan')
          for r in rows]
    rho, n = spearman(cv, mu_c)
    print(f'  cv_cond       vs conditional mean      rho={rho:+.4f}  n={n}')

    # --------------------------------------------------------------- s5c
    print('\n=== 5c. two team-level allocation entropies ===')
    print('  team metric              H(E[w])  E[H(w)]       MI  MI/H(E[w])  '
          'eff_marg  eff_within')
    for (team, layer, key), mates in sorted(pool.items()):
        if len(mates) < 2:
            continue
        M = np.array([fc.vector(layer, key, g) for g in mates])
        tot = M.sum(0)
        ok = tot > 0
        W = M[:, ok] / tot[ok]
        h_marg = shannon(W.mean(1))
        with np.errstate(divide='ignore', invalid='ignore'):
            lw = np.where(W > 0, W * np.log(W), 0.0)
        h_within = float((-lw.sum(0)).mean())
        mi = h_marg - h_within
        label = f'{team} {layer}/{key}'
        print(f'  {label:24s} {h_marg:.4f}  {h_within:.4f}  {mi:.4f}      '
              f'{mi / h_marg if h_marg > 0 else float("nan"):.4f}    '
              f'{np.exp(h_marg):.3f}     {np.exp(h_within):.3f}   '
              f'(n={len(mates)}, defined={ok.mean():.4f})')

    print('\nCODE CHANGED: NO. This probe wrote nothing.')


if __name__ == '__main__':
    root = pathlib.Path(__file__).resolve().parents[4]
    main(sys.argv[1] if len(sys.argv) > 1 else root / DEFAULT_RUN)
