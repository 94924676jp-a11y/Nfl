# Pre-registration: two prelock SHADOW tests for BUF@LAR (2026-10-12), written before either was computed

- **Written:** 2026-10-12 at about 18:50 UTC. The commit time is authoritative.
- **Status:** SHADOW ONLY. Neither test changes R6, CV1_R2 or any money-facing file. A result can only be adopted
  through a full re-run of the final pipeline with the change registered, and only if the owner chooses it.

## S1. PORT-D1 guard: credible-ceiling robustness (objective defect)

**Defect.** The near-optimal coverage objective admitted a lineup that is within the band in **1 of 2,000** corrected
worlds, and in none of the incumbent's. That lineup has the lowest mean and p99 of the 150.

**Guard G1, fixed now.**

- A candidate is admissible only if it is within the near-optimal band in **at least one world of an independent
  panel**: the same arm, the same inputs, simulator seed + 1 (2,000 worlds).
- The independent panel's per-world optimum is the best candidate in the same candidate pool. This is declared.
- No salary floor and no ceiling threshold. The guard has no free constant: the band is the existing
  `NEAR_OPTIMAL_LOSS_BAND`.

**Comparison.** Run the same 150 / 20 / 20 build on the same candidates and the same primary worlds, with and without G1.

**Report.**

- Which lineups are replaced, and by what.
- Coverage on the primary panel, the independent panel and the incumbent panel.
- Captain and player concentration.
- The objective cost.

**Decision rule.** None tonight. This is shadow evidence for the owner, and for a registered change after lock.

## S2. Higbee / Parkinson both-active role scenario (projection sensitivity)

**Evidence** (computed before this registration; it is the input, not the outcome):

- 2025, 8 LA games with both tight ends on the field: Higbee target share 10.6% (28 of 263), Parkinson 8.7%
  (23 of 263).
- 2026 weeks 1-3, both on the active roster: Higbee 41 of 369 pooled with 2025, which is **11.1%**; Parkinson
  **7.6%**.
- The current projection (CV1_R2) is Higbee about 18% of LA targets, Parkinson about 7.7%.

**Scenario S2-BOTH.**

- Higbee's projected target volume and receiving-TD share are scaled to the pooled both-active share of 11.1%.
- Parkinson is unchanged, because his projection already matches the evidence.
- The freed volume goes to the **other LA pass catchers in proportion to their own projected shares**. This is the
  declared reallocation rule; nothing is moved to Parkinson by hand. Club totals are unchanged.
- Efficiency (catch rate, yards per catch) is unchanged.
- It is applied to every projection the arm builds, including the participation variants.

**Uncertainty.** The per-game shares range from 0% to 22% (n = 11 games). This scenario is one point of a wide range,
**not a corrected projection**.

**Report.**

- Higbee and teammates' projected volume and DK.
- The shadow 150 / 20 / 20 portfolio's captain, FLEX and team exposure against CV1_R2.
- The overlap between the two portfolios.
