"""Render the IND@KC Showdown markdown FROM the JSON package."""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
P = _REPO / 'nfl' / 'research' / 'sunday'


def main():
    d = json.loads((P / 'IND_KC_SHOWDOWN_PREINACTIVES_2026W2.json').read_text())
    g, pv = d['gates'], d['provenance']
    ps = d['players']
    L = [f"# IND@KC Showdown — {d['LABEL']}", '',
         f"**USABLE FOR PREINACTIVES SAFE SHOWDOWN CONSTRUCTION: "
         f"{d['USABLE_FOR_PREINACTIVES_SAFE_SHOWDOWN_CONSTRUCTION']}**", '',
         f"Run `{pv['run_id']}` · {pv['n_draws']:,} draws · information cut "
         f"`{pv['information_cut']}` · generated {d['generated_at_utc']}", '',
         f"Inactive gate: **{g['inactive_gate']}**. "
         f"{g['inactive_gate_why']}", '',
         d['READ_THIS_FIRST']['candidate_status'] + '. '
         + d['READ_THIS_FIRST']['board_is_unsealed'] + ' '
         + d['READ_THIS_FIRST']['dst'] + ' V2 NOT YET EARNED.', '',
         '## Blockers and uncertain roles — read before pricing anything', '']
    if g['role_plausibility_flags']:
        L += ['### Role assumptions the depth chart does not support', '',
              '| player | team | flag | projected carries | depth chart |',
              '|---|---|---|---|---|']
        for f in g['role_plausibility_flags']:
            L.append(f"| **{f['player']}** | {f['team']} | `{f['flag']}` | "
                     f"{f['projected_carries_mean']} | "
                     f"{f['depth_chart_position']} |")
        L += ['', 'These are MODEL ROLE ASSUMPTIONS, not usage forecasts. '
              'The engine carries no depth-chart prior, so it can hand a '
              'fullback a lead back\'s workload. Salary was deliberately not '
              'used to judge this — letting price referee a projection is '
              'the contamination this pipeline exists to prevent.', '']
    if g['players_in_owner_entry_template_without_a_projection']:
        L += ['### In your saved entry template with NO projection', '',
              '| player | team | pos | state |', '|---|---|---|---|']
        for f in g['players_in_owner_entry_template_without_a_projection']:
            L.append(f"| **{f['name']}** | {f['team']} | {f['position']} | "
                     f"`{f['state']}` |")
        L += ['', 'An optimiser starting from that template would carry this '
              'player forward with nothing behind him.', '']
    if g['identity']['unresolved']:
        L += ['### Identity unresolved (no edit-distance matching permitted)',
              '', '| DK name | team | why |', '|---|---|---|']
        seen = set()
        for u in g['identity']['unresolved']:
            if u['name'] in seen:
                continue
            seen.add(u['name'])
            L.append(f"| {u['name']} | {u['team']} | {u['why']} |")
        L.append('')
    L += ['## Coverage audit', '',
          '| club | QB | RB | WR | TE | K |', '|---|---|---|---|---|---|']
    for club, v in d['position_support_per_club'].items():
        L.append(f"| {club} | {v['QB']} | {v['RB']} | {v['WR']} | {v['TE']} "
                 f"| {v['K']} |")
    m = g['dk_universe_vs_emitted']
    L += ['', f"Skill-layer gate: **{g['skill_layer_gate']}** "
          f"{g['empty_skill_positions'] or ''}", '',
          f"DK offers {m['dk_skill_rows']} skill FLEX rows; "
          f"**{m['n_missing']}** have no emitted projection. Every one is a "
          'minimum-salary bench or special-teams name the model gave no '
          'role. Absent is absent — none was filled in.', '',
          '## Top FLEX by model mean', '',
          '| player | team | pos | mean | p75 | p90 | p95 | ceiling | P(>=20) | P(>=30) |',
          '|---|---|---|---|---|---|---|---|---|---|']
    for p in ps[:18]:
        f = p['dk_flex']
        L.append(f"| {p['player']} | {p['team']} | {p['position']} | "
                 f"**{f['mean']:.2f}** | {f['p75']:.1f} | {f['p90']:.1f} | "
                 f"{f['p95']:.1f} | {f['ceiling_max_draw']:.1f} | "
                 f"{f['p_ge_20']:.3f} | {f['p_ge_30']:.3f} |")
    cpt = sorted(ps, key=lambda p: -p['dk_cpt']['p95'])
    L += ['', '## Top CPT candidates by model ceiling (CPT p95 = 1.5x FLEX p95)',
          '', '| player | team | pos | CPT mean | CPT p90 | CPT p95 | CPT P(>=30) | corr. to own QB |',
          '|---|---|---|---|---|---|---|---|']
    for p in cpt[:15]:
        c = p['dk_cpt']
        own = [(k, v) for k, v in p['correlation_with_qb'].items()
               if v is not None]
        best = max(own, key=lambda kv: kv[1]) if own else ('—', None)
        L.append(f"| {p['player']} | {p['team']} | {p['position']} | "
                 f"{c['mean']:.2f} | {c['p90']:.1f} | **{c['p95']:.1f}** | "
                 f"{c['p_ge_30']:.3f} | {best[0]} "
                 f"{'' if best[1] is None else f'{best[1]:+.3f}'} |")
    val = [p for p in ps
           if p['downstream_metadata_not_a_model_input']
           .get('flex_value_ceiling_per_1k') is not None]
    val.sort(key=lambda p: -p['downstream_metadata_not_a_model_input'][
        'flex_value_ceiling_per_1k'])
    L += ['', '## Top FLEX by ceiling value (DOWNSTREAM METADATA — salary '
          'never touched the model)', '',
          '| player | team | pos | FLEX p95 | salary | p95 per $1k | mean per $1k |',
          '|---|---|---|---|---|---|---|']
    for p in val[:15]:
        mdd = p['downstream_metadata_not_a_model_input']
        L.append(f"| {p['player']} | {p['team']} | {p['position']} | "
                 f"{p['dk_flex']['p95']:.1f} | "
                 f"{mdd['dk_salary_flex']} | "
                 f"**{mdd['flex_value_ceiling_per_1k']:.2f}** | "
                 f"{mdd['flex_value_mean_per_1k']:.2f} |")
    L += ['', '## Correlation structure, counted from the 8,000 draws', '',
          '| player | team | mean corr. same team | mean corr. opposing |',
          '|---|---|---|---|']
    for p in ps[:14]:
        st_, op = p['same_team_correlation'], p['opposing_team_correlation']
        a = 'n/a' if st_['mean'] is None else f"{st_['mean']:+.4f}"
        b = 'n/a' if op['mean'] is None else f"{op['mean']:+.4f}"
        L.append(f"| {p['player']} | {p['team']} | {a} | {b} |")
    L += ['', 'Every correlation above is a Pearson correlation between two '
          "players' DK point draws in the same simulated games. None of it "
          'comes from a stacking heuristic.', '',
          '## What did NOT enter the football model', '',
          d['READ_THIS_FIRST']['forbidden_inputs_confirmed'], '',
          f"Third-party sheet handling: `{pv['third_party_sheet_handling']}`.",
          '',
          '## When official inactives arrive', '',
          'The same pipeline reruns against the same fixture with the '
          'inactive list applied, and emits `POSTINACTIVES_CURRENT` so the '
          'already-built candidate lineup universe can be rescored rather '
          'than rebuilt.']
    t = '\n'.join(L) + '\n'
    (P / 'IND_KC_SHOWDOWN_PREINACTIVES_2026W2.md').write_text(t)
    print(f'wrote IND_KC_SHOWDOWN_PREINACTIVES_2026W2.md {len(t)} bytes')
    return 0


if __name__ == '__main__':
    sys.exit(main())
