"""Assemble WEEK5_WORLD_CORRECTNESS_AUDIT.json from the measured pieces. Read-only on the repo."""
import json, pathlib
H = pathlib.Path(__file__).resolve().parent
raw = json.loads((H / 'WEEK5_WORLD_CORRECTNESS_AUDIT.raw.json').read_text())
chk = json.loads((H / 'checker_raw.json').read_text())
cv = json.loads((H / 'club_volume_td.json').read_text())

defects = [
 {'defect': 'D-01 star lower tail too thin (W5-G5)',
  'measured_week5': 'all 40 of the top 40 projected skill players sit below the lower 95% bound of the historical P(DK<5) for their bin; proj>=20 mean sim P(<5) 0.62% vs 4.92% (20+|ALL) and 6.57% (20+|WR); proj 15-20 mean 2.34% vs 10.26%',
  'players_most_affected': ['Chris Olave|NO (0.75% vs 6.57%, -5.82pp, 8.8x)', 'Nico Collins|HOU (1.10%, -5.47pp, 6.0x)',
                            'Caleb Williams|CHI (0.35% vs 4.92%, 14x)', 'Tyler Shough|NO (0.25%, 19.7x)', 'Joe Burrow|CIN (0.65%, 7.6x)',
                            'Drake Maye|NE (0.45% vs 10.41%, 23x)', 'Jayden Daniels|WAS (0.80%, 13x)', 'Ashton Jeanty|LV (1.40% vs 9.05%)'],
  'optimizer_bias': 'TOWARD high-mean stars and stacks built on them: bust risk is understated 3-23x, so floors, cash-style objectives and any variance penalty overstate their safety; lineup-level downside variance understated',
  'safe_to_repair_before_sunday': False,
  'reason': 'the repair (P2 volatility) reshapes every player distribution and has no prospective validation; promoting it now changes production without evidence (rule 2/3). The mean is unaffected, so the effect is on distribution-consuming decisions only.'},
 {'defect': 'D-05 published-world accounting (W5-G6)',
  'measured_week5': 'club-worlds of 32,000: receiving yards != QB passing yards 30,641; receiving yards without a reception 17,192 (23,623 player-cells, mean 8.9 yds, max 231.7); receiving TD without a reception 4,151 (4,433 cells); rushing TD > carries 1,367; club points < 6 x offensive TDs 1,155; passing TD != receiving TD 51; receptions > targets 0; targets > attempts 0. Opposing-DST floor (DST >= 2 x INTs - 4) broken in 977; corr(opposing DST, INTs thrown) -0.02..+0.05. Record-breaking cells: 93 pass-yard cells > 554, 42 rec-yard cells > 336.',
  'players_most_affected': ['CHI receivers (Odunze, Burden, Loveland, Swift): +28.4 club rec yds over QB per world', 'MIA receivers (Malik Washington, Caleb Douglas): -25.6', 'GB (+14.5), MIN (+13.1), NYJ (-12.6)',
                            'rec TD without catch: Eli Raridon|NE 167 worlds, Elic Ayomanor|TEN 105, Cody White|LV 103, Skyy Moore|GB 102',
                            'rush TD > carries: Joe Burrow|CIN 138, Travis Homer|PIT 114, Cam Ward|TEN 70'],
  'optimizer_bias': 'stack valuation distorted: CHI/GB/MIN pass-catchers carry yards their QB did not throw (TOWARD those receivers and QB+receiver stacks); MIA/NYJ/LV/NE receivers carry fewer (AWAY). QB-vs-opposing-DST turnover anti-correlation is absent, so pairing a QB with the DST facing him is not penalised. Fringe TEs/WRs gain spurious TD ceiling worlds (TOWARD punts in GPP).',
  'safe_to_repair_before_sunday': False,
  'reason': 'the only built repair (event-consistent worlds, W5-G17) failed integration: over-dispersed receivers, 1.8-3.7% ties, double-counted defensive TD points, reshuffled 169 of 190 lineups. Switching the anchor to NONE/multiplicative is itself a production change that reintroduces the W4 mean gaps (-5.95..+3.33).'},
 {'defect': 'DST non-integer scores (incumbent anchor step)',
  'measured_week5': 'pooled 96.35% of DST worlds non-integer (94.65-98.2% per unit); anchor factors 0.563 (NYJ) to 1.338 (MIN); worlds below the DK floor of -4: PIT 4.0%, MIN 2.65%, LV 1.65%, CHI 1.35%; max 42.8 (MIN). Mean equals projection by construction.',
  'players_most_affected': ['MIN DST (x1.338)', 'PIT DST (x1.336)', 'LV DST (x1.070)', 'NYJ DST (x0.563, raw sim 8.81 vs proj 4.96)', 'MIA DST (x0.591)', 'TEN DST (x0.662)', 'GB DST (x0.690)'],
  'optimizer_bias': 'mean-based optimisers unaffected; distribution-based ones see spread scaled with the factor: TOWARD MIN/PIT/LV DST (inflated ceilings, 40+ point worlds) and AWAY from NYJ/MIA/TEN/GB DST (compressed ceilings). DST is not linked to the world\'s interceptions, so DST-vs-QB correlation is understated.',
  'safe_to_repair_before_sunday': False,
  'reason': 'being investigated by another agent; rounding moves the mean, an additive shift changes the PA-bucket semantics, and re-simulating from events is the failed W5-G17 path. No candidate has been validated.'},
 {'defect': 'W5-G16 appearance probability from a club-slot table',
  'measured_week5': '157 non-QB skill players carry p_plays < 1 straight from the slot table (WR2 0.8605, WR3 0.5865, RB2 0.6349, TE2 0.579, WR5 0.077); only 64 skill players have p=1. Worlds carry almost no zero-participation: share of zero-opportunity worlds minus (1 - p_plays) averages -0.135 (min -0.497); Monangai 0.05% zero worlds vs 36.5% implied.',
  'players_most_affected': ['Tee Higgins|CIN 16.77 vs 18.53 if plays (-1.76)', 'Luther Burden III|CHI -1.74', 'Matthew Golden|GB -1.58', 'Devaughn Vele|NO -1.51', 'Stefon Diggs|WAS -1.26',
                            'Kyle Monangai|CHI -3.31', 'Rachaad White|WAS -3.41', 'Rico Dowdle|PIT -2.75', 'Mack Hollins|NE -4.30', 'Kalif Raymond|CHI -3.59', 'Jaylin Noel|HOU 0.48 vs 5.83 (p 0.077, played 4/4)'],
  'optimizer_bias': 'AWAY from active depth-2/3 players (WR2, WR3, RB2, TE2 and every-week backups) in every world, since the discount is spread over all worlds as reduced volume rather than as zero worlds; TOWARD depth-rank-1 teammates by comparison. Once a player is confirmed active, his world distribution is neither the conditional one nor a valid mixture.',
  'safe_to_repair_before_sunday': False,
  'reason': 'candidate AP-1 is preregistered for prospective test 2026 W6-W11; promoting it before Sunday spends that test and is a production change without confirmatory evidence.'},
 {'defect': 'W5-G18 QB identity does not move team volume',
  'measured_week5': 'worlds start Caleb Williams (p 1.0, 21.92) and Jayden Daniels (p 1.0, 19.83). Backups: Bagent p 0.138, 0.07 DK, zero opportunity in 88.3% of worlds and mean 0.51 when he has any (vs 7.22 if plays) -- no world is a Bagent-starts game. Same for Mariota (0.10; 0.65 given opportunity vs 6.16). Decision board: a QB switch moves no CHI/WAS receiver by 0.5 DK.',
  'players_most_affected': ["CHI: D'Andre Swift 16.85, Rome Odunze 14.59, Luther Burden III 13.30, Colston Loveland 11.74, Kyle Monangai 7.61, Kalif Raymond 7.25", 'WAS: Terry McLaurin 13.77, Stefon Diggs 11.74, Jacory Croskey-Merritt 9.13, Rachaad White 7.37, Chig Okonkwo 6.66'],
  'optimizer_bias': 'if Bagent (or Mariota/Kaliakmanis) starts, CHI (WAS) pass-catchers keep starter-QB volume and their worlds stay correlated with a QB who is not playing: TOWARD those receivers and TOWARD stacks with the backup that the worlds cannot represent (backup-receiver correlation near zero because the backup has no volume in ~88% of worlds).',
  'safe_to_repair_before_sunday': False,
  'reason': 'QBCTX failed its bar and QBCTX-DB1 is preregistered; the legitimate pre-Sunday lever is the official designation entering STATE and the existing scenario re-run, which moves only the QB.'},
]

final = {
 'ARTIFACT': 'WEEK5_WORLD_CORRECTNESS_AUDIT', 'spec': 'read-only audit, 2026-10-09',
 'inputs': raw['inputs'], 'n_worlds': raw['n_worlds'],
 'input_hashes': {'PROJ.json': '16cf8340d88c848fe46235261643914dd49303f7382a3f0978bec39832497723 (matches DRAWS.projection_sha256)',
                  'STATE.json': '837f33c69d11d84dbdac8846c146f03fa5542124f3d3f104c428bc7e1c93159b (matches DRAWS.state_sha256)',
                  'DRAWS.json': '4c3228175ab9f97f94c2075dca9195db3f349b0f8972df8672433eb778a8e328',
                  'WORLDS.npz': '221c7c9eb3c290fe659f458ec4f61f1c51a2d0622d06add942cd7ab6f62ec268'},
 'scope_note': 'measures the published arrays the optimizer would score. Changes nothing. Labelled RESEARCH (FOOTBALL_ONLY arm, not validated).',
 'section1_projection_vs_world_means': {k: v for k, v in raw['section1'].items() if k != 'participation_rows_p_plays_lt_1'},
 'section1_club_volume_and_td': {'by_club': cv, 'READING': 'sum of dk_points_if_plays per club exceeds the unconditional club sum by 28-59%: conditional numbers are per-player conditionals and must not be summed or consumed jointly. The residual DK gaps after the efficiency anchor track club TD disagreement (sim vs projection offensive TDs): NO +0.24, PIT +0.22, NE +0.17, WAS +0.16 / CLE -0.28, MIN -0.23, MIA -0.20.'},
 'section1_participation_rows': raw['section1']['participation_rows_p_plays_lt_1'],
 'section2_accounting_by_club': raw['section2_accounting_by_club'],
 'section2_totals_club_worlds': raw['section2_totals_club_worlds'],
 'section2_player_level_world_counts_from_checker': {k: {kk: chk['checks'][k].get(kk) for kk in ('violations', 'of', 'player_world_cells')}
                                                     for k in ('REC_LE_TARGETS', 'YDS_WITHOUT_CATCH', 'REC_TD_WITHOUT_CATCH', 'INT_LE_ATTEMPTS', 'DK_FROM_PUBLISHED')},
 'section2_checker_defect': 'nfl/tools/world_accounting_check.py POINTS_GE_6_PER_TD reads pts[0, :, col] (game index 0) for every club: correct on a Showdown file, wrong on Classic. Its counts for GB (81) and CHI (63) agree with this audit; every other club is compared with CHI@GB points (e.g. MIA 325 checker vs 59 here). Not repaired (read-only).',
 'section2_game_tie_share_rounded_points': raw['section2_game_tie_share'],
 'section2_record_breaking_cells': {'pass_yards_gt_554': 93, 'rec_yards_gt_336': 42, 'rush_yards_gt_296': 4, 'receptions_gt_21': 1,
                                     'note': 'NFL single-game records (Van Brocklin 554, Anderson 336, Peterson 296, Marshall 21); max pass 867.3, rec 495.7'},
 'section3_dst': raw['section3_dst'], 'section3_kicker': raw['section3_kicker'],
 'section3_impossible_values': raw['section3_impossible_values'],
 'section4_distributions_top40': raw['section4_distributions_top40'], 'section4_summary': raw['section4_summary'],
 'section4_comparator_caveat': 'empirical bins are on REALISED season ppg; a projected-20 player is less selected than a realised-20 one, so the true dud rate for projected stars is if anything higher than 6.6%: the shortfall is a lower bound. The worlds contain no in-game injury / early-exit process (starters have ~0 zero-opportunity worlds), one identifiable source of the missing tail.',
 'section5_defects': defects,
 'section5_other_findings': [
   'fumbles lost are not modelled anywhere (proj_v1.py:419 records it); every RB/QB/WR mean is slightly high',
   'club points are a continuous draw: 95.6-99.65% non-integer per club; 0.1-1.35% of club-worlds round to 1 point (not a reachable NFL score); 2.65-4.1% of games tie on rounded points (historical with OT about 0.29%)',
   'no kicker exists in the universe (DK Classic has no K slot); field goals exist only implicitly in the continuous club points',
   'role ceilings: no player is banded above his askable_ceiling and no club-position has two ALPHA rows (n_capped 114, n_demoted_duplicate_alpha 0)',
   "scoring_centre.home_spread is home-minus-away margin (CHI@GB -6.35 = 20.63 - 26.97) while STATE environment.home_spread is a market spread (-1.5 = GB favoured): same name, opposite conventions",
 ],
 'section5_inputs': raw['section5_inputs'],
 'players': raw['players'],
}
(H / 'WEEK5_WORLD_CORRECTNESS_AUDIT.json').write_text(json.dumps(final, indent=1, default=float))
print('ok', len(json.dumps(final)))
