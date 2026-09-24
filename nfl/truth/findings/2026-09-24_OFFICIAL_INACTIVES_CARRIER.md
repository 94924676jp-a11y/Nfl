# Where official game-day inactives actually come from

**Date:** 2026-09-24
**Supersedes:** the first version of this finding, which was wrong in its
central claim. See "Correction" below — the error is left visible on purpose.
**All measurements offline**, against preserved capture bytes. No network.

## Correction

The earlier version of this finding concluded:

> no source inside this repository can supply official game-day inactives

**That is false, and I produced it by the exact defect this project tracks.**
I searched the preserved article HTML for the marker `Inactives:` (with a
colon), got zero hits, and read a failed probe as an established absence. The
article does not use that string. The inactive lists were in the bytes the
whole time, in clean server-rendered HTML. A probe that finds nothing is
evidence about the probe until it has been shown to be evidence about the
document.

What survives from the first version is narrower and still true: the
`/inactives/` **landing page** carries nothing, and ESPN cannot carry
inactives. What does not survive is the generalisation from those two to
"nothing can".

## The carrier exists and is already in the capture history

`https://www.nfl.com/news/inactive-reports-sunday-week-1-2026-nfl-season`
(captured `2026-09-13T16:00:17Z`, 889,811 bytes) is **server-rendered and
content-bearing**. Structure, verbatim from the preserved bytes:

```html
<h3>PANTHERS</h3><ul>
  <li>TE Ja'Tavion Sanders</li>
  <li>WR John Metchie</li>
  <li>QB Haynes King (emergency third QB)</li>
  …
</ul>
<h3>BEARS</h3><ul><li>QB Miller Moss</li>…</ul>
```

Per game, per team, position-prefixed, with the emergency-third-QB
parenthetical annotated inline. This is the official list, not a designation
feed.

Three URL shapes are proven to have worked:

| Shape | Example captured | Bytes |
|---|---|---|
| Weekly Sunday article | `/news/inactive-reports-sunday-week-1-2026-nfl-season` | 889,811 |
| Single-game article | `/news/australia-game-inactives-san-francisco-49ers-at-los-angeles-rams` | — |
| Operator plain-text relay | `operator-relay://official_inactives_delivery_2026-09-17T2351Z` | 583 |

The relay was a Week 2 **Thursday night** delivery (DET @ BUF), which is the
same slot as tonight's game. So a Week 3 Thursday-night equivalent is the
thing to ask for.

## What is genuinely dead

**The `/inactives/` landing page.** Of 367 preserved
`official_inactives` blobs, **363** are an explicit empty-state page whose
visible text reads *"Please check back soon for NFL Inactive Reports for this
Season."* Every one of those was recorded as a capture **PASS** — 402 PASS
rows in the manifest. The fetch succeeded; the page said it had nothing. That
gap between "the request worked" and "we obtained the thing" is the whole
defect.

**ESPN.** Measured on `espn_injuries_json.7291a7378c17df0e.json.gz` (captured
`2026-09-24T12:07:44Z`): 800 rows across 32 teams, status vocabulary closed at
`Active` 585, `Questionable` 161, `Injured Reserve` 25, `Out` 22, `Doubtful`
7, with matching `INJURY_STATUS_*` types. **Zero values bear an inactive
concept.** `Out` is an injury designation issued during the practice week by
the club; the inactive list is filed 90 minutes before kickoff. Converting one
into the other is forbidden by standing constraint, and the 585 `Active` rows
are the mirror trap — injury-report status, not confirmation a player will
dress. ESPN keeps its existing rank as a designation source. It cannot close
`PREDICTION_TIME_ELIGIBILITY_UNAVAILABLE`.

## What was built from this

`nfl/truth/official_inactives_parser.py` (`official-inactives-parser/1.0.0`),
tested by `nfl/tests/test_official_inactives_parser.py` — 26 checks, 0
failures, 0 blocked. It:

- raises `EmptyStatePage` **by name** on the landing-page shell rather than
  returning `{}`, which is the defect above encoded as a refusal;
- parses both the article HTML and the plain-text relay to one structure;
- refuses `for_game` unless **both** teams appear, because a half-attributed
  result lets one team's silence read as "nobody inactive";
- refuses an agent-authored intelligence report — parsing another agent's
  prose summary as though it were the source document is its own error class;
- returns `LISTED_OFFICIAL_INACTIVE` only, and states in the payload that an
  unlisted player is **unlisted**, not active.

Run against the whole preserved population it classifies all 367 blobs:
363 empty-state, 3 parsed, 1 refused. Nothing silently returns an empty list.

## Consequence for tonight

The parser is ready and proven against real bytes of the same shape. What is
missing is only the document for **this** game. The outbox request therefore
names a specific URL family rather than asking for "something", and the
acceptance test is unchanged: the preserved raw bytes must themselves identify
the inactive players for ATL and GB without inference.

`NO_VERIFIED_OFFICIAL_INACTIVES_ARTIFACT` remains a real and preferred answer
over a plausible one. The pre-inactive forecast stands on its own either way.
