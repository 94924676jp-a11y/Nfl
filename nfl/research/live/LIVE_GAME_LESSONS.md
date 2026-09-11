# Two live games, and what they are actually allowed to teach

Scope: `2026_01_NE_SEA` and `2026_01_SF_LA`, plus the twelve sealed but
QB-only boards of the 2026-09-13 slate. No parameter was tuned and no
candidate was promoted in producing this.

## Correction, and the defect behind it

An earlier version of this document asserted that **NE@SEA was never
forecast**. That was false, and the error is more instructive than anything
else in the review.

`nfl/research/shadow/g1_ne_sea/` holds a `V1_CANDIDATE` forecast sealed
before the outcome was opened (`bba6f0b`) and scored against the realised
game (`604eaac`). Both commits are in history; both artifacts were in the
working tree the whole time. A second seal, `g1_ne_sea_runB`, was also
present and also unseen.

The cause was **discovery, with a namespace-migration component, and nothing
else**. Nothing had been deleted, moved out of git, or left on another
branch. `research.daily_board.discover` hard-codes one root
(`nfl/research/live/`) and one label grammar
(`{pre,post}_inactives_V1_CANDIDATE[_R<n>]`). The shadow artifact matched
neither — different root, no cutoff/candidate label, files at the top of the
directory, `SEALED_FORECAST.json` beside `forecast_artifact.json` instead of
a `board.json`. So the evaluator found nothing, and I reported *absence of a
match* as *absence of a forecast*.

That is a worse class of failure than a missing forecast. It did not corrupt
a number; it corrupted a conclusion, and it would have recurred silently at
every future layout change. `nfl/research/sealed_index.py` now discovers by
**content** across every namespace this project has used, the namespace list
is append-only by intent, and a regression test requires a historically
sealed forecast to stay discoverable when namespaces change.

**Both games are genuine prospective case studies. n = 2.**

## What NE@SEA was, and what it was not

Sealed at a **T−31h information set** (newest observation 2026-09-08T17:06Z
against a 2026-09-10T00:20Z kickoff) — not T−90m. No official inactives
existed at seal time. Components `A1, A3G, C0, R2, SC1`; **C3 not reached**.
No player-level receiving or rushing forecast was produced, and many rows
are scored `NO_FORECAST_MISSING_PREGAME_INPUT`.

Those are real limitations and they are preserved rather than papered over.
What existed was scored.

## The finding that matters most

**The Seattle quarterback room was forecast almost exactly. The split
inside it was maximally wrong.**

| | actual | forecast | |
|---|---:|---:|---|
| SEA room passing yards | 200 | 197.46 | **+2.54** |
| SEA room attempts | 24 | 27.44 | −3.44 |
| SEA room dropbacks | 27 | 30.97 | −3.97 |
| Sam Darnold attempts | 2 | 24.48 | PIT **0.066** |
| Drew Lock attempts | 22 | 2.10 | PIT **0.981** |

Darnold was injured early and Lock replaced him. **No pregame information set
could have known that.** The room aggregate was the forecastable estimand and
it was forecast well; the allocation between two quarterbacks carried a risk
that is simply not resolvable before kickoff.

This matters beyond one game. If per-QB markets are scored without reporting
the room aggregate beside them, irreducible in-game replacement variance gets
charged to the model as allocation error, and we would "fix" an allocation
that was not broken.

Drake Maye, by contrast, was forecast well and is the cleanest single-player
result either game produced: 33 attempts against 24.80 (CRPS 4.56, inside
80%), **178 passing yards against 194.21 (CRPS 22.20, PIT 0.413, inside
80%)**, 42 dropbacks against 30.07.

## Team volume, now on two games

NE@SEA (from the sealed forecast): NE 42 dropbacks against 33.69 and 31
carries; SEA 27 dropbacks against 30.97 and 22 carries. SF@LA: LA ran 57
plays against 65.65 (PIT 0.18, CRPS 5.04) while losing 27–7; SF 64 against
64.50.

Both games show volume diverging from forecast on the side whose game script
went against it, and in SF@LA the model and the market missed the **same
direction on six of eight markets** — two independently-constructed views
both wrong about the environment. That is the strongest predictive signal
available, and it is still two games.

## A second shape now visible on both games

The team that threw **more** than forecast gained **fewer** yards per attempt
than forecast. NE: 42 dropbacks (+8.31) but 178 yards (−34.46). SF@LA: Purdy
34 attempts against 26.71 but 205 yards against 210.50. Offsetting errors
make yardage look accurate while both components are wrong.

Two observations is a hypothesis. It is now written down so it can be tested
rather than rediscovered.

## What is genuinely comparable between the two games

Only **team volume and quarterback quantities**. SF@LA carries receiving and
rushing layers that NE@SEA never produced, the information sets differ by
about thirty hours, and the opponents differ — so any difference between the
two confounds architecture, cutoff and opponent. The comparison is made only
where the estimands are the same, and not elsewhere.

## The slate, for context

Twelve of twelve Sunday boards sealed and modelled **only quarterbacks**,
because those clubs filed injury rows with `report_status` unset and the
appearance layer correctly deferred. One deferred upstream removes five of
nine declared layers. The runner called that "12 complete / 0 blocked"; it now
reports execution and completeness as independent states.

## The rule this document exists to enforce

Two games can tell us the plumbing is wrong. Two games cannot tell us the
football is wrong. Every P0 item is correctness or infrastructure and needs no
predictive evidence; every P1 is a hypothesis that must survive multi-game,
pre-registered, out-of-sample evidence before anything is promoted.

And one rule earned the hard way this session: **do not report the absence of
a match as the absence of a thing.** Search every namespace, by content,
before asserting that something was never done.
