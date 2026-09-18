# Downstream DFS architecture — specification only

Recorded 2026-09-16 on an owner instruction. **Nothing here is built, wired,
or scheduled.** It exists so that when the DFS layer is built it is built
against a boundary that was written down before the first line of it, rather
than discovered afterwards.

The instruction that created this file also carries the reason: a DFS layer
that can reach back into the football projection is not a DFS layer, it is a
second, unlabelled way to fit the simulator to something other than football.

## The layer boundary

```
football simulator
  -> site scoring adapter
    -> correlation / script analyzer
      -> lineup candidate generator
        -> field / ownership model
          -> contest simulator
            -> portfolio optimizer
              -> site CSV exporter
```

Each arrow is one-directional. The football simulator is upstream of all of
it and takes nothing back from any of it.

## Five modules that stay independent

1. football projection
2. DFS scoring
3. lineup construction
4. ownership / field prediction
5. payout / contest simulation

Historical DFS outcomes may train and validate **layers 3-5**. They may
**never** back-fit layer 1. This is the same rule that already forbids fitting
the simulator to a sportsbook price, applied to the other direction: a
contest result is an outcome of the field's behaviour, not evidence about
football.

## The contest schema comes from the site file, not from prose

**The imported site CSV/template is the governing contest schema.** Generic
rules taken from any external write-up are not authoritative and are not to be
copied into code.

The worked instance, and the reason the rule is stated this way: the DET-BUF
FanDuel single-game template **carries an MVP 1.5x salary field**. An external
research note asserted that FanDuel MVP has no salary multiplier. The file
wins. Had the note been treated as the schema, every lineup built against that
slate would have been illegal and the error would have surfaced only at
upload.

So: read roster slots, salary cap, multiplier fields, and legality constraints
out of the file that will be uploaded, per slate, every time.

## Correlations are estimated, never imported

No external correlation coefficient is hardcoded. External findings enter as
**hypotheses and as validation references** — something a measurement can
agree or disagree with — and nothing else.

Per slate, from the joint simulator's own draws:

- player-pair fantasy correlations
- position-pair correlations
- conditional correlation by game script
- MVP-conditioned teammate and opponent outcomes
- lineup-archetype performance by simulated game environment

A research-supported stack pattern may **seed** candidate generation. Whether
it is worth anything on this slate is decided by simulation, on this slate.

## The 150-max objective is a portfolio, not 150 optimisations

Do not generate 150 independently optimised projection-max lineups. Build one
portfolio whose members jointly cover high-value simulated scenarios, subject
to:

- contest legality
- salary
- player exposures
- lineup overlap
- correlation
- game-script coverage
- duplication risk, once a field model exists
- expected contest ROI / top-tail finish probability, once payout simulation
  exists

The last two are explicitly conditional. Until a field model and a payout
simulation exist, the objective cannot reference them and must not pretend to.

## What this file is not

It is not a design for any of the eight stages, not a schedule, and not a
claim that any of it is close. The current work is the DET-BUF projection
board, and this specification is deliberately parked behind it.

V2 NOT YET EARNED.

---

## Update 2026-09-18 — the scoring adapter layer is built

The boundary above now has code on both sides of one arrow.

```
football simulator (unchanged, knows nothing of any site)
  -> statline.assemble          one stat line per player per world
    -> draftkings.score         VERIFIED against the engine's own array
    -> fanduel.score            UNVERIFIED_FROM_RECOLLECTION, gated
      -> site_rules             roster shape, cap, multiplier salary, per site
        -> showdown/*           candidates, scenarios, correlation, audit
```

**One assembly, several sites.** `statline.py` exists so that DraftKings and
FanDuel cannot disagree because of an assembly bug rather than a rules
difference. It was needed: a first attempt at DK scoring reproduced pure
runners exactly and missed receivers by up to 17.0 points, because gadget
rushing yards live in their own layer.

**The reconciliation is the licence.** `draftkings.score` reproduces
`dk_scoring/dk_points` to 7.1e-15 across every player and every world. That is
the only evidence that the assembly is complete, and it is why FanDuel is
allowed to read the same StatLine rather than building its own.

**Provenance is not equal across sites and is not averaged.** DraftKings
legality is verified against the real entries file for this slate. FanDuel is
recalled, gated, and assigned as OUT-022. A site whose rules are unverified
cannot produce a submittable lineup here.

**The arrow is still one-directional and a test enforces it**: no module under
`nfl/production`, `nfl/research/oas1`, `nfl/capture` or `nfl/ingest` imports
anything under `nfl.dfs`.
