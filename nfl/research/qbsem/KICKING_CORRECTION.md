## Kicking — a correction, and the numbers

**I reported that kicking was ABSENT from this board and that no kicker
was in the room. That was wrong.** The `kicking` layer carries **two rows**,
one per club, with full FGA / FGM / XPA / XPM / DK distributions. What is
true is narrower and is a defect in its own right:

> **Every board computes a kicking layer and no board publishes a kicker
> among its players.** `board["players"]` holds 29 rows and omits both
> kickers, so `n_players` undercounts by the size of the kicking room and
> `BOARD.md` renders no kicking section. The draws are sealed; only the
> publication surface drops them.

Measured across the whole sealed corpus: 112 boards, **6 kicking rows, 0 of
them published**. It is systematic and longstanding, not a GSVU regression.
The tripwire now audits the kicking layer straight off the manifest and
states this as NOT_EXECUTED rather than working around it.

Repairing the publication surface changes every future board and belongs
in its own change with its own identity. It is **not** done in this pass,
in which nothing is promoted and nothing is sealed.

### The kicking numbers, from the sealed draws — GSVU, 8,000 draws

| Kicker | Tm | Metric | Mean | P10 | P50 | P90 | P(=0) |
|---|---|---|--:|--:|--:|--:|--:|
| `00-0036162` | BUF | FG attempts | **1.8786** | 0.0 | 2.0 | 4.0 | 0.1291 |
| `00-0036162` | BUF | FG made | **1.5930** | 0.0 | 1.0 | 3.0 | 0.1790 |
| `00-0036162` | BUF | XP attempts | **2.4761** | 0.0 | 2.0 | 5.0 | 0.1013 |
| `00-0036162` | BUF | XP made | **2.3579** | 0.0 | 2.0 | 5.0 | 0.1098 |
| `00-0036162` | BUF | DK points | **8.1312** | 3.0 | 8.0 | 14.0 | 0.0168 |
| `00-0039172` | DET | FG attempts | **1.9585** | 0.0 | 2.0 | 4.0 | 0.1240 |
| `00-0039172` | DET | FG made | **1.6724** | 0.0 | 2.0 | 3.0 | 0.1724 |
| `00-0039172` | DET | XP attempts | **2.2464** | 0.0 | 2.0 | 4.0 | 0.1194 |
| `00-0039172` | DET | XP made | **2.1375** | 0.0 | 2.0 | 4.0 | 0.1316 |
| `00-0039172` | DET | DK points | **8.1864** | 3.0 | 8.0 | 14.0 | 0.0175 |

Distance bands, attempts and makes:

| Kicker | Tm | Band | Att mean | Made mean |
|---|---|---|--:|--:|
| `00-0036162` | BUF | FG<20 | 0.0044 | 0.0041 |
| `00-0036162` | BUF | FG20s | 0.4070 | 0.3955 |
| `00-0036162` | BUF | FG30s | 0.5226 | 0.4884 |
| `00-0036162` | BUF | FG40s | 0.5337 | 0.4156 |
| `00-0036162` | BUF | FG50+ | 0.4109 | 0.2894 |
| `00-0039172` | DET | FG<20 | 0.0047 | 0.0045 |
| `00-0039172` | DET | FG20s | 0.4290 | 0.4214 |
| `00-0039172` | DET | FG30s | 0.5370 | 0.5045 |
| `00-0039172` | DET | FG40s | 0.5563 | 0.4522 |
| `00-0039172` | DET | FG50+ | 0.4315 | 0.2898 |

`kicking/offensive_td` is on the row too and is **not** a kicker metric:
it is the TEAM`s offensive touchdowns in that draw, recorded as the input
the kicker model was conditioned on. `xpa` tracks it at about 0.86
attempts per touchdown — means 0.856, 1.768, 2.677, 3.623 at td = 1..4 —
with the remainder two-point tries.
