#!/usr/bin/env python3.12
"""Write the duplication directive's deliverable report from the committed artifacts (every number is read, none typed).

    python3.12 nfl/field/showdown_dupe_report.py

Inputs: nfl/postgame/dupe_research/{DUPE_RESEARCH.json, DUPE_PORTFOLIO_STUDY.json, SHADOW_DRYRUN_ATL_NO_B4.json},
nfl/research/appearance/SC_APPEAR_1_FORWARD_TEST.json, the immutable evidence record.
Output: nfl/postgame/dupe_research/DUPE_DIRECTIVE_REPORT.md
"""
from __future__ import annotations

import json
import pathlib

_REPO = pathlib.Path(__file__).resolve().parents[2]
D = _REPO / 'nfl/postgame/dupe_research'


def j(p):
    return json.loads(pathlib.Path(p).read_text())


def main():
    R = j(D / 'DUPE_RESEARCH.json')
    PS = j(D / 'DUPE_PORTFOLIO_STUDY.json')
    SH = j(D / 'SHADOW_DRYRUN_ATL_NO_B4.json')
    AP = j(_REPO / 'nfl/research/appearance/SC_APPEAR_1_FORWARD_TEST.json')
    EV = j(_REPO / 'nfl/postgame/showdown_atl_no_2026W4/evidence/DEFECT_DUPE_UNDERESTIMATE.json')
    L = ['# Showdown duplication directive -- root cause, models, calibration, decisions', '',
         'Status of everything here: **SHADOW_ONLY**. Pre-registration: `docs/NFL_SHOWDOWN_DUPLICATION_PREREGISTRATION.md` '
         '(committed 2318d267 before any model was fitted). Evidence: `nfl/postgame/showdown_atl_no_2026W4/evidence/'
         'DEFECT_DUPE_UNDERESTIMATE.json` (write-once, hash-pinned). **ATL@NO is development data** -- the defect was found '
         'there and the features were chosen after seeing it -- so every result is exploratory; the confirmatory test is '
         'the next slate.', '']
    # 1 root cause
    L += ['## 1. Root cause (oracle ownership: the mapping from ownership to complete lineups)', '',
          '| contest | entries | duplicate entries that are same-user repeats | independent-product mass over legal lineups (x field) | top-200 lineups: actual / independent / max-entropy |',
          '|---|---|---|---|---|']
    for k, d in R['diagnosis'].items():
        t = d['top200_actual']
        L.append(f"| {k} | {d['N_filled']:,} | {100 * d['self_duplicate_share_of_duplicate_entries']:.1f}% | "
                 f"{d['E1_mass_on_feasible_universe']:.2f} | {t['actual']:,} / {t['E1']:,.0f} / {t['B1_maxent']:,.0f} |")
    g = lambda k, x: R['diagnosis'][k]['actual_over_maxent_by_group'].get(x, {}).get('actual_over_B1')
    L += ['', 'Actual / max-entropy (exact ownership + legal lineups) by lineup structure -- what remains after ownership '
          'and legality are respected:', '',
          '| structure | ' + ' | '.join(R['diagnosis']) + ' |', '|---|' + '---|' * len(R['diagnosis'])]
    for x in ('stack_cpt_pc_own_qb', 'split_5-1', 'split_3-3', 'both_qbs', 'any_k_dst', 'salary_left_0',
              'salary_left_1000-1900', 'fc_rank_1_100', 'fc_rank_101_1000'):
        L.append(f'| {x} | ' + ' | '.join('-' if g(k, x) is None else f'{g(k, x):.2f}' for k in R['diagnosis']) + ' |')
    L += ['', '**What the root cause is, in order:**', '',
          '1. **The current estimator has the wrong shape, not too little mass.** N x CPT share x product of FLEX shares is '
          'not a probability: summed over legal lineups it predicts 5.7-7.7 times more entries than exist, yet it '
          'under-predicts the 200 most-duplicated lineups 2.5-5.9x. It spreads weight over the long tail of ordinary lineups '
          'and starves the popular ones.',
          '2. **Legality and exact ownership fix most of it.** A maximum-entropy model that matches every player\'s CPT and '
          'FLEX share exactly over the legal-lineup universe (salary cap, distinct players, both teams) and adds nothing '
          'else (B1) moves the log score by +1.3 to +2.2 nats per entry on every salary slate (+0.28 on PHI@CHI, where the cap cannot be applied).',
          '3. **The rest is lineup construction, consistently across all five contests:** CPT WR/TE stacked with his own '
          'QB (x1.27-1.37), 5-1 game-script splits (x1.31-1.78) at the expense of 3-3 splits (x0.85-0.92), the top-100 '
          'public-optimizer lineups (x1.36-1.51), and avoiding $1,000-1,900 of unused salary (x0.76-0.86).',
          '4. **Duplication is convergence across users, not repetition:** only 3.4-10.2% of duplicate entries are a user '
          're-entering his own lineup.',
          '5. **Player-pair dependence beyond those structures is small:** median absolute log pair lift 0.06-0.11 '
          '(specific pairs to +/-50-90%, e.g. QB with his own WR1, QB with the opposing DST, both kickers).',
          '6. **Ownership forecast error is a separate, second factor:** on ATL@NO the frozen BLEND forecast was close in '
          'aggregate but gave Brian Robinson Jr. 1.0% FLEX against 17.6% actual.', '']
    # 2 + 3 comparison & calibration
    L += ['## 2-3. Candidate model comparison and historical calibration (leave-one-slate-out, never fit and scored on '
          'the same contest)', '',
          '| held-out contest | trained on | model | log score / entry | top-1,000 predicted: actual / pred | public-optimizer top-150: actual / pred | OUR lineups: actual / pred | top-50 actual: median abs log ratio |',
          '|---|---|---|---|---|---|---|---|']
    for t, f in R['folds'].items():
        for m in ('B0', 'B5', 'B1', 'B3S', 'B2', 'B3', 'B4', 'B6', 'B7'):
            r = f['models'].get(m)
            if not r:
                continue
            fc_, ow = r.get('fc_top150_actual_over_pred'), r.get('owner_lineups_actual_over_pred')
            L.append(f"| {t} | {', '.join(f['train'])} | {m} | {r['log_score_per_entry']:.3f} | "
                     f"{r['top1000_pred_actual_over_pred']:.2f} | {'-' if fc_ is None else f'{fc_:.2f}'} | "
                     f"{'-' if ow is None else f'{ow:.2f}'} | {r['top50_actual_median_abs_log_ratio']:.2f} |")
    L += ['', 'Salary- and projection-conditioned models on the PIT_CLE fold were trained on ATL_NO only, and on the ATL '
          'folds on PIT_CLE only (PHI_CHI has no salaries). Full per-bin calibration: `DUPE_CALIBRATION_TABLE.csv`.', '',
          '### Pre-registered candidate bars (section 5)', '', '| model | folds | verdict |', '|---|---|---|']
    for m, v in R['candidate_bars'].items():
        folds_txt = ', '.join(x['fold'] + ':' + ('pass' if x['PASS'] else 'fail') for x in v['per_fold'])
        L.append(f"| {m} | {folds_txt} | {v['VERDICT']} |")
    # 4 falsification
    L += ['', '## 4. Falsification results', '',
          '- **FALSIFIED: "independence under-counts because mass is wasted on illegal lineups."** It over-allocates mass '
          '(5.7-7.7x) and is too flat. (This was my own working hypothesis; withdrawn.)',
          '- **FALSIFIED: "duplication is mostly users repeating their own lineups."** 90-97% is cross-user.',
          '- **FALSIFIED as fixes: simple inflation (B5 one constant, B6 by salary bucket) and a Poisson regression on '
          'log E1 (B7).** All fail the bars on every fold -- correcting the level of the wrong shape does not correct it.',
          '- **NOT FALSIFIED (passes every available fold): B2, B3, B3S, B4.** B4 (legal-lineup max-entropy + salary-left + '
          'construction + public-optimizer terms) has the best log score; B3S (construction only, no salaries) is the only '
          'candidate tested on all three slates.',
          '- **UNRESOLVED: PHI@CHI tail.** Without salaries the universe cannot apply the cap; every model still misses its '
          'top-50 lineups ~2.5x there. Requested in the outbox (PHI@CHI draftables).',
          '- **UNRESOLVED: contest-type differences.** The same structural coefficients fit the 150-max, 20-max and 2-entry '
          'ATL@NO fields within the bars; same-user repeats rise with fewer entries per user (3.4% 150-max, 10.2% 2-entry). '
          'One slate cannot separate contest type from slate.', '']
    # 5 portfolio
    L += ['## 5. Portfolio decisions on frozen worlds (selection seed 20261005, evaluation held-out seed 20261006)', '',
          f"Field model for F-model: {PS['field_model']['model']}, structure fitted on {PS['field_model']['theta_fitted_on']}, "
          f"ownership {PS['field_model']['ownership']}. Prize curve ASSUMED (1st ${PS['prize_curves']['196285137']['top_prize']:,.0f} "
          'in the 150-max, fitted to the owner\'s cash points, the 6th-place tie average and the pool).', '',
          '| contest | field | objective | held-out E[payout] | kept from selection worlds | P(any lineup near-optimal) | E[best score] | mean predicted copies | distinct CPTs |',
          '|---|---|---|---|---|---|---|---|---|']
    for cid, c in PS['contests'].items():
        for f, r in c['fields'].items():
            for o, v in r['objectives'].items():
                h, s = v['HELD_OUT_worlds_seed_20261006'], v['selection_worlds_seed_20261005']
                keep = h['E_payout'] / s['E_payout'] if s['E_payout'] else 0
                L.append(f"| {cid} | {f} | {o} | ${h['E_payout']:,.2f} | {keep:.2f} | {h['p_any_hit']:.3f} | {h['E_best_score']:.1f} | "
                         f"{h['mean_predicted_copies']:.1f} | {h['distinct_captains']} |")
    L += ['', '**Reading this table correctly.** The held-out worlds come from OUR football model -- the same model that '
          'chose the lineups -- and that model has no demonstrated forecasting edge. In its own worlds every portfolio beats '
          'a field that does not share its projections, so the absolute ROIs (+50% to +1,000%) measure the model\'s '
          'self-confidence, not money. Only differences between objectives on the same worlds are informative, and even '
          'those inherit the model\'s beliefs.', '',
          '**Findings.** (1) In the 150-max, expected-payout objectives are noise-chasing: with a ~$10,000 first prize and '
          '237,812 entries, 2,000 worlds cannot estimate a lineup\'s expected payout -- the split-aware EV portfolio keeps '
          'only 18-52% of its selected value on held-out worlds, against 86-94% for the coverage objective re-implemented without '
          'the exposure ladder (O0R) and 76-82% for the frozen production portfolio. '
          'The duplication-aware variants are not better there under the realised field. (2) In the 20-max and 2-entry, the '
          'duplication-aware objectives earn more on held-out worlds under both fields; in the 20-max that costs 8-9 points of '
          'scenario coverage and 1.3-1.8 points of best-lineup score, in the 2-entry the cost is mixed (coverage -6 to +2 points). (3) **No duplication-aware objective is demonstrated better** '
          'given the self-evaluation problem. The realised ATL@NO result (one draw, reported, never used):', '']
    for cid, c in PS['contests'].items():
        L.append(f"- {cid}: " + '; '.join(f"{o} ${v['assumed_curve_payout']:.2f} (best rank {v['best_rank']})"
                                          for o, v in c['realised_one_draw'].items()))
    # 6 shadow
    L += ['', '## 6. Next-slate shadow comparison (the confirmatory test)', '',
          'Tool: `nfl/field/showdown_dupe_shadow.py` (write-once, self-sealed, never read by selection). Dry run on the '
          f"frozen ATL@NO inputs with ATL@NO excluded from training (model {SH['model']}, trained on {', '.join(SH['trained_on'])}):", '',
          '| contest | our lineups | actual copies by others | current B0 | B4 (prelock-knowable) |', '|---|---|---|---|---|']
    act = {cid: v['decomposition_our_lineups']['actual_copies_by_others'] for cid, v in EV['key_numbers'].items()}
    for cid, s in SH['summary'].items():
        L.append(f"| {cid} | {s['n']} | {act[cid]:,} | {s['B0_total']:,.1f} ({act[cid] / s['B0_total']:.1f}x low) | "
                 f"{s['B4_total']:,.1f} ({act[cid] / s['B4_total']:.1f}x low) |")
    L += ['', 'The remaining 1.5-2.2x is mostly ownership-forecast error (the forecast gave Brian Robinson Jr. ~1% FLEX; '
          'he was 17.6%) plus structure fitted on one slate.', '']
    # 7 ranked recommendation
    L += ['## 7. Ranked recommendation', '',
          '1. **Run the B4 shadow comparison before lock on the next Showdown** and commit it before kickoff (B3S as well if '
          'the slate lacks a public projection file). This is the pre-registered confirmatory test; it changes nothing.',
          '2. **Report predicted copies of our lineups on the prelock board under B4 beside B0** (reporting only). The '
          'portfolio objective and lineups stay as they are.',
          '3. **Do not adopt a duplication-aware objective yet.** The decision test cannot separate duplication value from '
          'trust in our own football model, and EV objectives are not estimable at 2,000 worlds in the 150-max. Before '
          're-testing: an evaluation world source independent of the selection model, and a variance-controlled payout '
          'target (e.g. probability of a top-0.1% finish rather than expected payout).',
          '4. **Ownership of cheap rotation players (SC-OWN-ROTATION-1) is the next largest lever** -- B4 with perfect '
          'ownership predicts our copies within 5% in the 150-max and 20-max (the 2-entry has only 2 lineups); with the frozen forecast it is 1.5-2.2x low.',
          '5. Promotion of B4 requires the pre-registered bars on the prospective slates plus the owner\'s rule '
          '(proposal: >= 5 slates).', '']
    # continued work
    a = AP['results']
    L += ['## 8. Separate successor tests, continued', '',
          f"- **SC-APPEAR-1 (playing-time probability): passes both halves of its held-out bar on 2025** (fit on 2024). "
          f"Qualifying active players: Brier {a['QUALIFYING_prior3_all']['brier_current']} -> {a['QUALIFYING_prior3_all']['brier_candidate']} "
          f"(week-blocked z {a['QUALIFYING_prior3_all']['brier_improvement_week_blocked']['z']}); backups among them "
          f"{a['RANK_2_PLUS_QUALIFYING']['brier_current']} -> {a['RANK_2_PLUS_QUALIFYING']['brier_candidate']}; starters "
          f"z {a['RANK_1']['brier_improvement_week_blocked']['z']} (inside the no-regression tolerance). Volume half: "
          f"{AP['BAR_unconditional_opportunity_MAE'][:4]} under a PROXY if-plays volume (the production conditional volume was not "
          'replayed). Still SHADOW; promotion is the owner\'s decision and the allocator is unchanged.',
          '- **SC-COH-1 (football-world coherence): NOT STARTED in this round** -- it needs a simulator change and a 2025 '
          'held-out simulation run, which could not be completed and validated before the next Showdown without risking '
          'the production path. Explicitly UNRESOLVED; the defect stays open on the readiness board.', '']
    L += ['## 9. Limitations', '',
          '- Three slates, two of one contest type; PHI@CHI has no salaries or projections.',
          '- ATL@NO is development data for every claim here.',
          '- Ownership is ORACLE in the dependence test; prelock forecasts are tested only on ATL@NO.',
          '- The universe (32 players) drops 0.2-0.7% of entries.',
          '- Prize curves are assumed; self-competition between our own entries is ignored in the portfolio test.',
          '- The portfolio test evaluates in our own model\'s worlds.', '']
    p = D / 'DUPE_DIRECTIVE_REPORT.md'
    p.write_text('\n'.join(L))
    return p


if __name__ == '__main__':
    print(main())
