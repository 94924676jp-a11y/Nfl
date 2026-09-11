# Two live games, and what they are actually allowed to teach

Scope: `2026_01_NE_SEA` and `2026_01_SF_LA`, plus the twelve sealed but
QB-only boards of the 2026-09-13 slate. No parameter was tuned and no
candidate was promoted in producing this.

## The asymmetry that has to be stated first

These are not two case studies of the same kind.

**NE@SEA was never forecast.** There is no board for it in the product index
or under `nfl/research/live/`, and its `practice_a`, `final_status_b` and
`inactives` obligations all closed MISSED. Its actuals are now in hand from
authoritative nflverse play-by-play — SEA 13, NE 10, NE 67 plays and 31
rushes against SEA's 47 and 21 — and there is nothing to score them against.
So NE@SEA can support data and operational findings only. It cannot support a
single statement about prediction quality.

**SF@LA is therefore the only genuine prospective case study, and n = 1.**

That asymmetry is itself the most expensive lesson of the two games: the
system silently produced no prediction for the first live game of the season,
and nothing raised an alarm at the time. A forecaster that can skip a game has
no denominator.

## What SF@LA actually showed

Scoring used exact CRPS and mid-PIT from the 1,000 stored draws, not the nine
stored percentiles.

The largest single miss was **team volume, and it points at game state**. LA
ran 57 plays against a forecast mean of 65.65 — PIT 0.18, CRPS 5.04 — while
losing 27–7. SF's 64 against 64.50 was almost exact. Carries were forecast
well on both sides (30 against 28.35, 29 against 26.59). Stafford's −66.6
passing yards is mostly downstream of his team running 8.7 fewer plays than
forecast, not of a passing-model error.

NE@SEA rhymes with it without confirming it: 67 plays to 47, a twenty-play
asymmetry in a three-point game. Two games showing the same shape is a
hypothesis, not a finding.

**Model and market missed in the same direction on six of eight markets.**
That is the detail that makes game state the leading candidate rather than
player share: two independently-constructed views of the same game were both
wrong the same way about the environment.

**The official inactive information was worth about 1%.** Total CRPS over ten
metrics moved 98.96 → 97.97. It helped receivers (Nacua 64.74 → 71.00 against
74 actual) and hurt the lead back (McCaffrey 11.98 → 13.64 against 10 actual,
CRPS 1.48 → 2.14). Redistribution worked causally in one direction and
backwards in the other, on one game.

**Nothing escaped an 80% interval.** Coverage was 10/16 at 50%, 16/16 at 80%
and 16/16 at 90%. That hints at intervals being too wide, and sixteen
correlated metrics from one game cannot support the claim. This project's own
floor is 300 graded units; we have sixteen.

**One efficiency finding worth watching.** Purdy threw 34 times against a
26.71 forecast and finished with 205 yards against 210.50. The yards look
excellent and are the product of two offsetting errors — volume badly under,
efficiency over by roughly 1.7 yards per attempt. Offsetting errors that look
like accuracy are the easiest thing in this whole exercise to misread.

## What the slate showed that the two games could not

Twelve of twelve Sunday boards sealed successfully and modelled **only
quarterbacks** — six to nine players each, no rushing, no receiving, no
touchdown allocation. The cause is a single upstream fact: those clubs filed
injury rows with `report_status` unset, `team_readiness` returns
`INJURY_REPORT_INCOMPLETE`, and the appearance layer correctly defers. One
deferred upstream removes five of the nine declared layers at once.

The runner reported this as "12 games complete / 0 blocked". That was true
about orchestration and false about football, and the two are now reported as
independent states with a nine-layer matrix computed from whether each layer
produced a real stored distribution.

## The eight questions, answered honestly

1. **Game-state-conditioned team volume** — the strongest signal available,
   and the one most at risk of being over-fitted to two games. P1, requires
   ≥20 prospective games, pre-registered, decided out of sample.
2. **Appearance / role certainty** — the gate on five of nine layers, and the
   place the inactive redistribution behaved inconsistently by position. P1.
3. **Canonical player eligibility** — the QB path ignored the official
   inactive list while the non-QB path honoured it. Repaired; the remaining
   work is auditing the other allocators for the same missing argument. P0.
4. **Incomplete-layer visibility** — shipped this session. P2, done.
5. **Pregame capture resilience** — the `content_markers` defect hid behind
   an egress block and was found by the one executor that could fetch, inside
   the one window that mattered. P2.
6. **Automatic authoritative postgame ingestion** — does not exist, and it
   **blocks every predictive item below it**. Without automatic scoring there
   is no route to any sample floor. P0.
7. **Receiving-conversion calibration** — the volume/efficiency decomposition
   above. P1, and gated behind 300 graded metrics.
8. **Remaining unmodeled markets** — RB/WR/TE rushing yards stay unavailable
   until the rushing conversion control is resolved; carries × YPC remains
   forbidden. These are declared absences, and the board marks them
   `NOT_MODELED` rather than guessing. P3.

## The rule this document exists to enforce

Two games can tell us the plumbing is wrong. Two games cannot tell us the
football is wrong. Every P0 item here is correctness or infrastructure and
needs no predictive evidence at all; every P1 item is a modeling hypothesis
that must survive multi-game, pre-registered, out-of-sample evidence before
anything is promoted.

The ordering is not a preference. Q4 — automatic postgame ingestion —
**blocks** Q5, Q6 and Q7, because a system that scores by hand will never
accumulate the evidence those items require.
