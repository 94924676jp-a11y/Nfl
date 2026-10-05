# NFL DFS YouTube Research: Showdown, Duplication, Portfolio, Ownership, Field Sims, Contest Size, Late Swap

Compiled Monday, October 5, 2026 (tonight's DraftKings Showdown: Falcons at Saints, MNF).

## How this was built

- 66 YouTube videos were found across the eight topics. Full transcripts were pulled for 63 (the transcript text that appears in YouTube's "Show transcript" panel, with timestamps).
- Excerpts were extracted from each transcript, then every excerpt was checked word-for-word against the saved transcript before it was included. 527 of 539 candidate excerpts passed; the 12 that did not match were dropped. 480 are listed below after removing off-topic (MLB/NBA/MMA) items.
- Every excerpt links to the exact second in the video, so you can click and hear it.
- The captions are YouTube auto-captions, so player names are sometimes misspelled (e.g., "DK meaf" = DK Metcalf, "Herz" = Hurts, "Geomine" = geomean). The excerpts are verbatim from the captions, errors included.

## Caveats before you use the numbers

- Several of the "historical Showdown data" numbers come from vendors selling a product (FTA Sports' 163-slate study, DFS Army's "Showdown Codex" of about 350 contests, 925 Sports). Treat them as directional claims, not peer-reviewed results. 925 Sports' kicker and DST figures (40% and 31%) match FTA's (40.5% and 31%), so they probably come from the same dataset and are not independent confirmation.
- DFS Army's 2020 video uses FanDuel numbers (MVP slot, $60K cap). Its "QB 42% / RB 38% / pass catcher 18%" MVP split and "about 20% of winners spend $55K or less" do not apply directly to DraftKings.
- "Nut," "optimal," and "winning lineup" mean slightly different things across sources: the best possible lineup after the fact, the first-place lineup, or a top-1% lineup.
- No public video found here offers a validated, out-of-sample duplication model. The best quantified claim is ETR's single-variable R² comparison (product ownership 0.55 vs. total ownership 0.26).
- Tonight's Stokastic Falcons–Saints Showdown video (published today) and Breaking Boards' Lions–Panthers live show had no transcript available yet, so they are listed but not quoted.

## Key findings at a glance

### Showdown winning lineup construction (DraftKings unless noted)

| Metric | Finding | Source |
|---|---|---|
| Optimal CPT by position | WR 33.1%, RB 28%, QB 20.9% across 163 slates | [FTA Sports 1:34](https://www.youtube.com/watch?v=1X6cgvJxsqQ&t=94s) |
| Most-popular CPT | QB is usually the most-rostered captain but is the right captain only about 20% of the time | [FTA Sports 2:07](https://www.youtube.com/watch?v=1X6cgvJxsqQ&t=127s) |
| CPT by game type | WR is the most common CPT in grinders, average games, and shootouts; RB rarely CPT in 49+ totals | [DFS Army 4:15](https://www.youtube.com/watch?v=65HDqKemR88&t=255s) |
| Field vs optimal QB CPT | Field 28–35% QB captain vs optimal rate near 20% | [DFS Army 2:45](https://www.youtube.com/watch?v=-ZBpaHty068&t=165s) |
| Underdog QB CPT | QBs who are 3.5+ point underdogs: nut captain 3 times in 205 games, field plays them about 6.5–7% | [DFS Army 7:42](https://www.youtube.com/watch?v=65HDqKemR88&t=462s) |
| Favored-team CPT | Favorites produce the nut captain 62–75% of the time | [DFS Army 3:55](https://www.youtube.com/watch?v=-ZBpaHty068&t=235s) |
| 50 Milly Maker winners (2021) | QB CPT 24%, RB 32%, core pass catcher about 36%; only 7 of 50 were 1–5; 8 were onslaughts (5–1) | [Adam Newman 5:40](https://www.youtube.com/watch?v=HfQcvFwIECA&t=340s), [6:58](https://www.youtube.com/watch?v=HfQcvFwIECA&t=418s) |
| Players from favorite (of 6) | 1: 2.5%, 2: 21.5%, 3: 34.4%, 4: 31.3%, 5: 10.4% | [FTA Sports 6:13](https://www.youtube.com/watch?v=1X6cgvJxsqQ&t=373s) |
| 5–1 / onslaught leverage | 5–1 stacks are positively leveraged in top-1% lineups; onslaughts are very low-owned | [ETR 12:44](https://www.youtube.com/watch?v=i98ljRFANdA&t=764s), [13:57](https://www.youtube.com/watch?v=i98ljRFANdA&t=837s) |
| QB count | Every one of 50 Milly winners had at least 1 QB; 26% had both | [Adam Newman 8:23](https://www.youtube.com/watch?v=HfQcvFwIECA&t=503s) |
| Field QB usage | About 80% of all field lineups contain at least one QB | [One Week Season 19:16](https://www.youtube.com/watch?v=OTvIy-Jk96U&t=1156s) |
| WR CPT + own QB | 85.2% of top-1% lineups pair a WR captain with his QB vs 77.4% of the field | [ETR 25:59](https://www.youtube.com/watch?v=i98ljRFANdA&t=1559s) |
| Kicker / DST | Kicker in 40.5% of nut lineups, DST in 31%, K or DST at CPT 8.6% | [FTA Sports 7:13](https://www.youtube.com/watch?v=1X6cgvJxsqQ&t=433s) |
| DST by total | DST in 47% of winners at totals of 42 or less, 38% in average games, 21% at 49+ (negative leverage vs ownership) | [DFS Army 5:59](https://www.youtube.com/watch?v=65HDqKemR88&t=359s) |
| Kicker by total | At least one kicker in 41–46% of winners across game types; rarely two | [DFS Army 5:37](https://www.youtube.com/watch?v=65HDqKemR88&t=337s) |
| No K/DST | 44% of 50 Milly winners had zero kickers and zero DSTs | [Adam Newman 10:41](https://www.youtube.com/watch?v=HfQcvFwIECA&t=641s) |
| Salary left | $0 left won only 7.4%; up to $900 left 31.3%; $1,000–1,900 left 22.7% | [FTA Sports 8:23](https://www.youtube.com/watch?v=1X6cgvJxsqQ&t=503s) |
| Ties vs salary | Spending $49.1K–$50K means about 7-way ties on average; capping at $49.4K reduces that to about 5 | [DFS Army 20:21](https://www.youtube.com/watch?v=65HDqKemR88&t=1221s) |
| Ties vs total ownership | Under 140% total ownership: about 10% of wins, about 2 ties on average; most wins sit at 155–190% | [DFS Army 19:10](https://www.youtube.com/watch?v=65HDqKemR88&t=1150s) |
| Hitting the nuts | DK winner hits the nut lineup about 66% of the time, near 80% in 100K+ fields | [DFS Army 2:02](https://www.youtube.com/watch?v=65HDqKemR88&t=122s) |
| Optimal CPT ownership | About 28% of optimal captains were under 5% owned; 16% were over 20% | [925 Sports 6:04](https://www.youtube.com/watch?v=kVhN3OfbEBs&t=364s) |

### Duplication modeling

- ETR's dupe estimate: product of captain and flex projected ownerships, times a correlation coefficient (they float about 0.85 for a stacked QB–WR, 0.15 unstacked), times a salary-left multiplier, times field size. Product ownership has an R² of 0.55 with dupe count vs 0.26 for total ownership ([ETR 43:54](https://www.youtube.com/watch?v=i98ljRFANdA&t=2634s), [45:41](https://www.youtube.com/watch?v=i98ljRFANdA&t=2741s)).
- SaberSim: expected dupes is roughly ownership product × contest size; geomean = product^(1/n). It overestimates dupes for very low-salary builds (e.g., $33K), and they suggest a 20–25 dupe guardrail instead of forcing 5 or fewer ([SaberSim 3:09](https://www.youtube.com/watch?v=eVWhJ0Cy2FY&t=189s), [19:12](https://www.youtube.com/watch?v=eVWhJ0Cy2FY&t=1152s), [21:12](https://www.youtube.com/watch?v=eVWhJ0Cy2FY&t=1272s)).
- The independence assumption breaks for correlated pairs. A CeeDee Lamb CPT player is far more likely to play Dak in FLEX than the ownership product implies ([SaberSim 32:30](https://www.youtube.com/watch?v=Fr2FxzlztT4&t=1950s)).
- Practical trim: remove roughly the top 10–20% of a pool by geomean ([SaberSim 16:04](https://www.youtube.com/watch?v=UTQzHyEzDEw&t=964s)).

### Field simulation, ownership, contest size, late swap

- Ownership is commonly built by running thousands of high-variance optimizer builds off an industry-aggregate projection and reading off player exposures. That makes it quick to regenerate after news ([SaberSim 3:49](https://www.youtube.com/watch?v=zMdDPCaxXjg&t=229s), [SaberSim 3:16](https://www.youtube.com/watch?v=MGO5rVk8I7M&t=196s)). SaberSim keeps 13 ownership sets for different stakes, field sizes, and entry limits ([SaberSim 0:52](https://www.youtube.com/watch?v=DHKY694-I_M&t=52s)).
- Chalk condenses in small fields: a captain owned 18% in a large field might be 30% in single entry ([SaberSim 59:46](https://www.youtube.com/watch?v=zMdDPCaxXjg&t=3586s)).
- Contest sims test each candidate lineup against a projected opponent field over about 100,000 game re-sims ([SaberSim 6:01](https://www.youtube.com/watch?v=Fr2FxzlztT4&t=361s)). The field was capped at 5,000 lineups even for bigger contests ([SaberSim 48:55](https://www.youtube.com/watch?v=mZzskOQAz2k&t=2935s)). Scaling duplication from a 10K sample up to a 100K-entry contest is a stated limitation ([SaberSim 13:32](https://www.youtube.com/watch?v=h9O1DRC4ABo&t=812s)).
- Contest size: in small-field DK Showdown, start with a captain at 20% captain ownership or less; in large fields, look for under 10% ([Occupy Fantasy 5:42](https://www.youtube.com/watch?v=W9FWB82PwNs&t=342s), [23:54](https://www.youtube.com/watch?v=W9FWB82PwNs&t=1434s)). Use skinny stacks in large fields and double stacks in small fields ([Mayo Media 13:34](https://www.youtube.com/watch?v=oj36e7aIMHc&t=814s)). Above 50K entries, the geomean rule is mainly a dupe limiter; below 10K, it can push you toward a unique build ([SaberSim 29:19](https://www.youtube.com/watch?v=eVWhJ0Cy2FY&t=1759s)).
- Late swap: inactives arrive about 90 minutes before lock, with a final sim one hour out ([SaberSim 48:41](https://www.youtube.com/watch?v=Re6X-sC0P7A&t=2921s)). If a key RB is ruled out, rebuild everything to get exposure to the replacement; if a WR is out, swap only the affected lineups ([SaberSim 10:08](https://www.youtube.com/watch?v=uvDTL8e6Ipo&t=608s), [11:57](https://www.youtube.com/watch?v=uvDTL8e6Ipo&t=717s)). Update late-game ownership when actual early-game ownership differs from projections ([SaberSim 27:32](https://www.youtube.com/watch?v=S2p7LVEeXy4&t=1652s)).

## Gaps that remain

- CPT-vs-FLEX ownership split: no video presents a large-sample study of CPT ownership vs FLEX ownership for the same player. Evidence is limited to field-vs-optimal captain rates by position and individual examples.
- ETR's paid Showdown material and Stokastic's dupe model internals are not in public transcripts.
- No video gave an exact method for propagating an inactive through ownership into a full 150-lineup portfolio. The closest is SaberSim's "re-sim, ownership regenerates, quick-swap same-team replacement" workflow.

## Video catalog

Topic numbers: 1 Showdown history, 2 Duplication, 3 Portfolio, 4 Ownership, 5 Field sim, 6 Contest size, 7 CPT ownership, 8 Late swap.

| Video | Channel | Date | Topics |
|---|---|---|---|
| [Field Lineups Explained](https://www.youtube.com/watch?v=DHKY694-I_M) |  |  | 3, 4, 5, 6 |
| [NFL DFS Small Field & Single-Entry GPP Strategy / Fantasy Football](https://www.youtube.com/watch?v=vF-hGtlpVi8) |  |  | no transcript |
| [How to be Profitable Playing NFL DFS Showdown Slates](https://www.youtube.com/watch?v=kVhN3OfbEBs) | 925 Sports | Sep 10, 2026 | 1, 2, 7 |
| [I Broke Down the 2025 Milly Maker Winning Lineups (Then Built a Process Around It)](https://www.youtube.com/watch?v=zQu7ablUMEk) | 925 Sports | Sep 02, 2026 | 6 |
| [NFL DFS Showdown Research - Results From 50 Winning Milli-Maker Lineups in 2021](https://www.youtube.com/watch?v=HfQcvFwIECA) | Adam Newman | Sep 07, 2022 | 1, 2, 6 |
| [HOW TO WIN ON DRAFTKINGS NFL SHOWDOWN: LINEUP BUILDING TIPS](https://www.youtube.com/watch?v=lyaKCYf1LrQ) | Alvin Zeidenfeld | Sep 03, 2019 | 1, 3, 6, 7, 8 |
| [Lions vs Panthers NFL DFS Showdown LIVE / DraftKings SNF Picks, Captains, Ownership & Lineups](https://www.youtube.com/watch?v=nEsN2QnJCFU) | Breaking Boards | Fantasy Football & DFS | Oct 04, 2026 | no transcript |
| [DFS Portfolio Diversification: Build Smarter Lineups with Efficient Frontier Strategy](https://www.youtube.com/watch?v=sJNfa7WuAL8) | Compounding Edges | Jul 21, 2025 | 3, 5 |
| [How to Crush NFL Showdowns on Fanduel and Draftkings Using the DFS Army Domination Station Optimizer](https://www.youtube.com/watch?v=ehza4xs_VSc) | DFS Army - Daily Fantasy Sports | Sep 08, 2020 | 1, 2, 3, 6, 7 |
| [2025 HOW TO PLAY NFL DRAFTKINGS SHOWDOWN](https://www.youtube.com/watch?v=-ZBpaHty068) | DFS Army - Daily Fantasy Sports | Aug 23, 2025 | 1, 2, 3, 7 |
| [I Cracked the Code on NFL Showdown Lineups (Do This to Win)](https://www.youtube.com/watch?v=65HDqKemR88) | DFS Army - Daily Fantasy Sports | Aug 03, 2026 | 1, 2, 3, 4, 5, 7 |
| [I Studied 230,000 NFL DFS Lineups; Here's What Will Win in 2026](https://www.youtube.com/watch?v=rz2HFI7diGY) | DFS Army - Daily Fantasy Sports | Jul 27, 2026 | 3, 6 |
| [DFS Army's Strategy Series MME Podcast   50 is the New 150](https://www.youtube.com/watch?v=CPsg0CX4_eU) | DFS Army - Daily Fantasy Sports | Jun 04, 2020 | 3, 6 |
| [How to Use PortfolioIQ for Portfolio Management](https://www.youtube.com/watch?v=A06udLfR1Oc) | DFS Hero | Aug 05, 2025 | 3 |
| [NFL DraftKings Showdown Contest Strategy, Captain's Slot and Tips](https://www.youtube.com/watch?v=iEGNBY_zeSc) | DraftKings | Oct 15, 2018 | 1, 6, 7 |
| [Studying the Sharps: Constructing DFS Lineups with Jordan Cooper](https://www.youtube.com/watch?v=1qKHG9mSEfI) | DraftKings | Oct 05, 2021 | 2, 3, 4, 5, 6 |
| [How to Win NFL DFS Tournaments in 2026](https://www.youtube.com/watch?v=A-PD6sZhvvY) | Establish The Run | Sep 06, 2026 | 2, 4, 5, 6 |
| [High Level Showdown Strategy + Super Bowl Stuff with Cody Main and Colin Drew](https://www.youtube.com/watch?v=i98ljRFANdA) | Establish The Run | Feb 04, 2022 | 1, 2, 3, 6, 7 |
| [DFS Tournament Strategy - How to Beat Small Field & Single Entry GPPs](https://www.youtube.com/watch?v=Z79IcL2Cruk) | Establish The Run | Sep 06, 2021 | 2, 6, 8 |
| [The DraftKings Showdown Rule That Deletes Your Winning Lineup](https://www.youtube.com/watch?v=1X6cgvJxsqQ) | FTA Sports | Aug 05, 2026 | 1, 3, 7, 8 |
| [NFL DFS Strategy - Winning Showdowns / How To Make More Money](https://www.youtube.com/watch?v=KKUUjA6MV38) | Fantasy Six Pack | Sep 06, 2022 | 1, 2, 6 |
| [I Gave the DFS Army Optimizer the SHOWDOWN CODE… Here’s What It Built!](https://www.youtube.com/watch?v=sBOEt7d3dM4) | Ibe's DFS Sports Betting | Oct 01, 2026 | 1, 3, 6, 7 |
| [How To Project Ownership % in DFS (DraftKings)](https://www.youtube.com/watch?v=BToDGUdOhkU) | Kev's Picks | Nov 22, 2015 | 4, 8 |
| [NFL DFS Strategy Masterclass: Game Theory, Stacking & How to Actually Win](https://www.youtube.com/watch?v=oj36e7aIMHc) | Mayo Media Network | Sep 04, 2026 | 2, 3, 4, 5, 6, 8 |
| [2026 NFL DraftKings Strategy: Stop Making These Costly DFS Mistakes](https://www.youtube.com/watch?v=SPjmh9bxUF4) | Mayo Media Network | Aug 28, 2026 | 1, 2, 3, 6, 7 |
| [NFL DFS Week 1 DraftKings Strategy And Picks  Run The Sims With A Milly Maker Winner](https://www.youtube.com/watch?v=MhwZlTi-eJw) | Neil Orfield | Sep 12, 2026 | 3, 5, 6 |
| [How to Build Winning NFL DFS Showdown Lineups on DraftKings & FanDuel (2024)](https://www.youtube.com/watch?v=W9FWB82PwNs) | Occupy Fantasy | Oct 07, 2024 | 1, 2, 3, 4, 6, 7 |
| [DraftKings Showdown Strategy for Seahawks vs Lions / JSN Captain + Game Theory Breakdown](https://www.youtube.com/watch?v=OTvIy-Jk96U) | One Week Season | Sep 30, 2024 | 1, 2, 6, 7 |
| [DRAFTKINGS & FANDUEL DFS STRATEGY REVIEW: PROJECTION VS OWNERSHIP EXPLOIT (1/4/23)](https://www.youtube.com/watch?v=x2vfd9rf5S8) | RotoGrinders - Daily Fantasy Sports Advice | Jan 04, 2023 | 1, 2, 3, 4, 6, 7, 8 |
| [DRAFTKINGS & FANDUEL DFS STRATEGY REVIEW: Large-Field GPP Lineup Simulations (1/18/23)](https://www.youtube.com/watch?v=pakvRcKsnXQ) | RotoGrinders - Daily Fantasy Sports Advice | Jan 18, 2023 | 2, 3, 4, 5, 6, 8 |
| [DFS Office Hours 10/5: Different build settings for different contests, impact of pool size on build](https://www.youtube.com/watch?v=7yKBIoYboE8) | SaberSim DFS - Daily Fantasy Sports Strategy | Oct 06, 2021 | 1, 2, 3, 6, 7, 8 |
| [DFS Q&A: How Do Contest Sims Work for Small vs. Large-Field Contests?](https://www.youtube.com/watch?v=h9O1DRC4ABo) | SaberSim DFS - Daily Fantasy Sports Strategy | Oct 12, 2023 | 1, 2, 3, 4, 5, 6, 7, 8 |
| [DFS Q&A: What is a self-sim?](https://www.youtube.com/watch?v=JjEqfaORNpA) | SaberSim DFS - Daily Fantasy Sports Strategy | Jul 11, 2024 | 1, 2, 3, 4, 5, 6, 8 |
| [How to Beat NFL DFS Showdowns](https://www.youtube.com/watch?v=iE36sFpjaVw) | SaberSim DFS - Daily Fantasy Sports Strategy | Sep 10, 2026 | 1, 2, 3, 5, 7 |
| [The 3 Rules for Beating NFL Showdown and Single Game GPPs](https://www.youtube.com/watch?v=7T2VrpJIN1M) | SaberSim DFS - Daily Fantasy Sports Strategy | Sep 09, 2021 | 1, 2, 3, 6, 7 |
| [DFS Q&A: Avoiding Dupes on Small NFL Slates](https://www.youtube.com/watch?v=KDQWYsMCP8w) | SaberSim DFS - Daily Fantasy Sports Strategy | Dec 21, 2025 | 2, 3, 5, 6, 8 |
| [Master The Art of NFL DFS Showdowns](https://www.youtube.com/watch?v=Fr2FxzlztT4) | SaberSim DFS - Daily Fantasy Sports Strategy | Sep 30, 2024 | 1, 2, 3, 4, 5, 6, 7, 8 |
| [DFS Q&A: How do I best utilize the dupe metric in the contest sims?](https://www.youtube.com/watch?v=ETNpMZGSNCs) | SaberSim DFS - Daily Fantasy Sports Strategy | Oct 03, 2023 | 1, 2, 3, 4, 5, 6, 7, 8 |
| [DFS Q&A: Simulations can help you avoid duplication in DFS](https://www.youtube.com/watch?v=PSqHBQYbYqE) | SaberSim DFS - Daily Fantasy Sports Strategy | Feb 03, 2022 | 2, 3, 4, 8 |
| [DFS Q&A: Walking Through the NFL Late Swap Process](https://www.youtube.com/watch?v=CgfglAjd2ys) | SaberSim DFS - Daily Fantasy Sports Strategy | Sep 26, 2025 | 3, 5, 6, 8 |
| [NFL Office Hours - Showdown Q&A](https://www.youtube.com/watch?v=Re6X-sC0P7A) | SaberSim DFS - Daily Fantasy Sports Strategy | Sep 08, 2023 | 1, 2, 3, 4, 5, 6, 7, 8 |
| [DFS Q&A: How Does the Portfolio Diversifier Work?](https://www.youtube.com/watch?v=iM5sS24JCSc) | SaberSim DFS - Daily Fantasy Sports Strategy | Mar 19, 2026 | 3, 5 |
| [DFS Q&A: How Do You Reduce Dupes in Showdown?](https://www.youtube.com/watch?v=JuOzj5ZOQHk) | SaberSim DFS - Daily Fantasy Sports Strategy | Sep 07, 2025 | 1, 2, 3, 5, 6, 8 |
| [SaberSim's Unique Approach to Projecting Ownership](https://www.youtube.com/watch?v=zMdDPCaxXjg) | SaberSim DFS - Daily Fantasy Sports Strategy | Dec 10, 2021 | 1, 2, 3, 4, 5, 6, 7, 8 |
| [DFS Q&A: How Should You Handle NFL Late Swap Between Builds?](https://www.youtube.com/watch?v=QJ4wmImXx5M) | SaberSim DFS - Daily Fantasy Sports Strategy | Sep 21, 2025 | 2, 3, 4, 5, 6, 8 |
| [DFS Q&A: Navigating NFL Late Swap](https://www.youtube.com/watch?v=8qVskFOoEGE) | SaberSim DFS - Daily Fantasy Sports Strategy | Sep 18, 2024 | 3, 4, 5, 6, 8 |
| [Why is avoiding duplication important in DFS?](https://www.youtube.com/watch?v=MCss_MdowIc) | SaberSim DFS - Daily Fantasy Sports Strategy | Aug 16, 2021 | 2, 3, 6 |
| [DFS Q&A: How SaberSim Creates Its Ownership Projections](https://www.youtube.com/watch?v=JnVogCYAHgY) | SaberSim DFS - Daily Fantasy Sports Strategy | Jun 03, 2023 | 1, 3, 4, 6, 7, 8 |
| [DFS Office Hours 7/29/21: Why avoiding duplication is important in DFS](https://www.youtube.com/watch?v=U13Q_op4i-g) | SaberSim DFS - Daily Fantasy Sports Strategy | Jul 30, 2021 | 2, 3, 6 |
| [DFS Q&A: How do I navigate NFL late swap?](https://www.youtube.com/watch?v=uvDTL8e6Ipo) | SaberSim DFS - Daily Fantasy Sports Strategy | Sep 09, 2022 | 1, 2, 3, 4, 6, 7, 8 |
| [DFS Q&A: What is the best way to reduce dupes in Showdown?](https://www.youtube.com/watch?v=eWWw-7T2YLk) | SaberSim DFS - Daily Fantasy Sports Strategy | Jan 15, 2024 | 2, 4, 5, 8 |
| [DFS Q&A: How Do Custom Projections and Ownership Affect Sims and Lineup Building?](https://www.youtube.com/watch?v=t0YPdy7wOuk) | SaberSim DFS - Daily Fantasy Sports Strategy | Aug 28, 2025 | 3, 4, 5 |
| [Learn How Maximize SaberSim's New Contest Sims](https://www.youtube.com/watch?v=mZzskOQAz2k) | SaberSim DFS - Daily Fantasy Sports Strategy | Aug 24, 2023 | 2, 3, 5, 6 |
| [If you’re not late-swapping in NFL DFS, you’re leaving money on the table](https://www.youtube.com/watch?v=S2p7LVEeXy4) | SaberSim DFS - Daily Fantasy Sports Strategy | Oct 01, 2021 | 3, 4, 6, 8 |
| [DFS Q&A: How are SaberSim's ownership projections calculated?](https://www.youtube.com/watch?v=MGO5rVk8I7M) | SaberSim DFS - Daily Fantasy Sports Strategy | Jun 15, 2022 | 3, 4, 6, 8 |
| [DFS Q&A: Product Ownership and Geometric Mean](https://www.youtube.com/watch?v=eVWhJ0Cy2FY) | SaberSim DFS - Daily Fantasy Sports Strategy | Oct 11, 2022 | 2, 3, 6 |
| [DFS Q&A: How Do You Filter NFL Lineups to Avoid Dupes While Staying +EV?](https://www.youtube.com/watch?v=wdjc-z_h8m4) | SaberSim DFS - Daily Fantasy Sports Strategy | Aug 27, 2025 | 1, 2, 3, 5 |
| [DFS Q&A: For the 20-Max and 150-Max contest do you use the same pool?](https://www.youtube.com/watch?v=PRtm5_i9qqQ) | SaberSim DFS - Daily Fantasy Sports Strategy | May 25, 2024 | 2, 3, 4, 6, 8 |
| [How to Late Swap in NFL DFS: A Real-Time Tutorial](https://www.youtube.com/watch?v=IAt9PW8j75M) | SaberSim DFS - Daily Fantasy Sports Strategy | Sep 09, 2024 | 3, 5, 8 |
| [Beat DFS Using The SaberSystem: 5 Principles for Maximum Profitability](https://www.youtube.com/watch?v=4jONT961JrM) | SaberSim DFS - Daily Fantasy Sports Strategy | Aug 29, 2024 | 3, 4, 5, 6, 8 |
| [DFS Q&A: How Do You Use Geomean to Reduce Dupes in NFL Showdown?](https://www.youtube.com/watch?v=UTQzHyEzDEw) | SaberSim DFS - Daily Fantasy Sports Strategy | Dec 12, 2025 | 2, 3, 5, 6 |
| [Lions vs Panthers - SNF Sunday Sweatdown / NFL Week 4 / DFS Picks, Plays & Process](https://www.youtube.com/watch?v=xJlvummhIfI) | Ship It Nation | Oct 05, 2026 | 1, 2, 3, 6, 7, 8 |
| [NFL DFS Sims Tournament Strategy Week 1 / NFL DFS Strategy](https://www.youtube.com/watch?v=uMa9MQhf0fU) | Stokastic DFS - Daily Fantasy Sports Advice | Sep 11, 2026 | 3, 4, 5, 6, 8 |
| [Falcons-Saints Showdown Strategy MNF Week 4 DFS Picks / NFL DFS Strategy](https://www.youtube.com/watch?v=2NTS1Dn33BU) | Stokastic DFS - Daily Fantasy Sports Advice | Oct 05, 2026 | no transcript |
| [How To Use The Stokastic NFL DFS Contest Generator Tool / NFL DFS Contest Simulations](https://www.youtube.com/watch?v=QX-prNRoIuA) | Stokastic DFS - Daily Fantasy Sports Advice | Sep 07, 2023 | 1, 2, 3, 5 |
| [How To Use The Stokastic NFL DFS Pre-Contest Sims Tool / NFL DFS Contest Simulations](https://www.youtube.com/watch?v=4PFRCiUGPec) | Stokastic DFS - Daily Fantasy Sports Advice | Sep 07, 2023 | 1, 2, 3, 4, 5, 6 |

# Transcript evidence by topic

Each line: timestamp link, verbatim caption excerpt, one-line takeaway.

## 1. Showdown historical strategy and winning lineup construction

23 videos, 73 transcript excerpts.


### NFL DFS Showdown Research - Results From 50 Winning Milli-Maker Lineups in 2021
Adam Newman · Sep 07, 2022 (0:12:30) · [Watch on YouTube](https://www.youtube.com/watch?v=HfQcvFwIECA)

- [5:40](https://www.youtube.com/watch?v=HfQcvFwIECA&t=340s) "quarterback captains to win as much as they actually did which was 12 out of 50 lights is 24 percent i played zero quarterback captains last year and this is making me rethink it uh in a million maker qb captains are winning 24 of the time in the last 50 from last year"
  - Takeaway: Quarterbacks were captain in 12 of 50 winning lineups (24%), despite the speaker having played no quarterback captains the prior year.
- [6:24](https://www.youtube.com/watch?v=HfQcvFwIECA&t=384s) "at running back running backs were 16 out of 50 lives that's 32 and then a core pass catcher that is you know a tight end like a kelsey or a darren waller or a obviously a core wide receiver those showed up and how many was that it was like 18 or 36"
  - Takeaway: Running backs were captain in 16 of 50 winners (32%), while core pass catchers were captain in about 18 of 50 (36%).
- [6:58](https://www.youtube.com/watch?v=HfQcvFwIECA&t=418s) "only seven of the 50 lineups uh winners had a one to five that means the captain was the only person on the team so i think one week that was alex collins against pittsburgh alex collins was the captain and it was five pittsburgh people running it back"
  - Takeaway: Only seven winning lineups used a 1-5 build, with the captain as the sole player from one team and five players from the opponent.
- [7:51](https://www.youtube.com/watch?v=HfQcvFwIECA&t=471s) "i'm planning to actually put rules in based on this data to say i only want to play three threes four twos"
  - Takeaway: The speaker planned to use rules favoring 3-3 and 4-2 lineup constructions.
- [7:57](https://www.youtube.com/watch?v=HfQcvFwIECA&t=477s) "the onslaughts i actually stayed away from onslaughts this is five the captain plus four people on the same team versus the one on the other team uh this is interesting that there's eight of these so i'm thinking about adding onslots to my uh to my lineup construction this year"
  - Takeaway: Eight winning lineups were onslaughts, defined here as the captain plus four teammates against one player from the other team.
- [8:23](https://www.youtube.com/watch?v=HfQcvFwIECA&t=503s) "all the cubies it was crazy every single lineup it's kind of intuitive but every single lineup had at least one quarterback and 26 percent of them had both i think that's really important"
  - Takeaway: Every winning lineup included at least one quarterback, and 26% included both quarterbacks.
- [10:41](https://www.youtube.com/watch?v=HfQcvFwIECA&t=641s) "i was really interested in kickers and specialty or in defenses uh because i don't like playing them i just don't and uh and so you'll see that like the winners had zero of those 44 of the time which i'm that's intriguing to me but it was less than half"
  - Takeaway: Winning lineups had zero kickers and defenses 44% of the time; the speaker considered a rule allowing at most one kicker or defense.
- [11:38](https://www.youtube.com/watch?v=HfQcvFwIECA&t=698s) "and so this was interesting how many million makers had zero fringe plays and the answer was over 50 percent and that is very interesting to me again they did some did real unique type stuff"
  - Takeaway: More than half of the winning Million Maker lineups had zero fringe plays.

### How to be Profitable Playing NFL DFS Showdown Slates
925 Sports · Sep 10, 2026 (0:19:55) · [Watch on YouTube](https://www.youtube.com/watch?v=kVhN3OfbEBs)

- [3:29](https://www.youtube.com/watch?v=kVhN3OfbEBs&t=209s) "So really the top two contenders for your captain spot should be running back at about 28% and then receiver. We also do notice that quarterback is in there about 21%. Sure. Tight ends, DST and kickers really not all that much."
  - Takeaway: The transcript gives running backs an approximately 28% share of captain selections and quarterbacks approximately 21%, while saying tight ends, DSTs, and kickers appear much less often.
- [7:31](https://www.youtube.com/watch?v=kVhN3OfbEBs&t=451s) "If you are playing a quarterback that is, you know, more of a pass heavy quarterback, you need to be running out two of their pass catchers. Jared Goff, guys. If you're playing Jared Goff in the captain spot, you want to play two of their pass catchers."
  - Takeaway: For a pass-heavy quarterback Captain, the transcript recommends including two of that quarterback’s pass catchers.
- [9:51](https://www.youtube.com/watch?v=kVhN3OfbEBs&t=591s) "But really guys, we we want to be chasing three to three. So you're splitting your captain up with two of his other players and then uh three opposing players."
  - Takeaway: The recommended roster split is 3-3, with the Captain’s team represented by the Captain and two other players, plus three opponents.
- [10:33](https://www.youtube.com/watch?v=kVhN3OfbEBs&t=633s) "So although it doesn't really hit all that frequently, when it does hit, that tends to be a very, very big edge because not many people are going to be doing that type of lineup."
  - Takeaway: The transcript says 5-1 builds occur infrequently but can offer a substantial edge because few entrants use them.
- [13:47](https://www.youtube.com/watch?v=kVhN3OfbEBs&t=827s) "So, what I do find interesting is in the optimal winning lineups, we did see a kicker in the lineup about 40% of the time. You know, pretty normal, but we also typically see a DST somewhere in the lineup about 31% of the time."
  - Takeaway: Optimal winning lineups included a kicker about 40% of the time and a DST about 31% of the time.
- [15:34](https://www.youtube.com/watch?v=kVhN3OfbEBs&t=934s) "And so the most common winning builds are somewhat chalky, guys. We're going to go with the four to two favorite stack there, guys, which is perfectly fine with that. We're having the receiver in the captain spot. So if we're doing that, we're going to target the quarterback there as well."
  - Takeaway: A sample common winning GPP build is a somewhat chalky 4-2 favorite stack with a receiver at Captain and that player’s quarterback.

### NFL DraftKings Showdown Contest Strategy, Captain's Slot and Tips
DraftKings · Oct 15, 2018 (0:10:57) · [Watch on YouTube](https://www.youtube.com/watch?v=iEGNBY_zeSc)

- [2:00](https://www.youtube.com/watch?v=iEGNBY_zeSc&t=120s) "So, anytime you can get both quarterbacks in the lineup in in in your lineup it it's usually a good thing. And then, you know, those are I think the two keys is, you know, don't overspend on that captain spot and and try to try to get your get your passing game stacks in order and find find your leverage there."
  - Takeaway: Raybon recommends considering both quarterbacks, avoiding overspending at captain, and arranging passing-game stacks.
- [2:57](https://www.youtube.com/watch?v=iEGNBY_zeSc&t=177s) "but I would say that you do want to do it because I mentioned opposing quarterbacks have a correlation of 0.59, which especially when we're talking about the NFL is a is a relatively strong correlation there. So, you want to do it more than the field does it and the field tends to not always necessarily do it that much or, you know, to the to the level of which they're correlated."
  - Takeaway: Opposing quarterbacks are stated to have a 0.59 correlation, and Raybon recommends rostering both more often than the field does.
- [4:32](https://www.youtube.com/watch?v=iEGNBY_zeSc&t=272s) "you mentioned it, you're correct in that they're more viable in cash games. In tournaments defenses tend to be a little bit more viable than kickers because they have the upside of scoring touchdowns and even multiple touchdowns and even though it doesn't happen too much."
  - Takeaway: Defenses are described as more viable than kickers in tournaments because they can score one or multiple touchdowns; both are more viable in cash games.
- [7:16](https://www.youtube.com/watch?v=iEGNBY_zeSc&t=436s) "I don't think you need a a guy like that in every lineup because then you're you're kind of creating lineups in one type of way and you don't always see a a guy like that in the winning lineup. So, it's a it's really a case-by-case basis based on the the upside uh in the given slate."
  - Takeaway: Raybon says not to force a low-cost dart throw into every lineup and to assess each case based on its slate-specific upside.
- [9:15](https://www.youtube.com/watch?v=iEGNBY_zeSc&t=555s) "only you only have a six-man lineup, so you need to kind of tell yourself uh you know, the story of how these six players fit together and arrive at a score that would outscore every other lineup."
  - Takeaway: He recommends building a coherent game story in which all six players fit together and can produce a winning score.

### I Cracked the Code on NFL Showdown Lineups (Do This to Win)
DFS Army - Daily Fantasy Sports · Aug 03, 2026 (0:26:59) · [Watch on YouTube](https://www.youtube.com/watch?v=65HDqKemR88)

- [2:02](https://www.youtube.com/watch?v=65HDqKemR88&t=122s) "The winner of showdowns on Draft DraftKings is a little bit FanDuel's more aggressive but on DraftKings the winner hits the nuts about 66% of the time. And as the field size gets larger, we go up to those 100,000 plus field sizes, we're hitting the nuts at almost 80%."
  - Takeaway: The transcript says winning lineups hit the perfect lineup about 66% of the time overall on DraftKings and almost 80% in fields of 100,000 or more.
- [4:15](https://www.youtube.com/watch?v=65HDqKemR88&t=255s) "So, in all three archetypes, grinders, average games, shootouts, the wide receiver is the most common captain on DraftKings. Um, you do see some changes, though, though. I I think it's really dramatic to me when I look at this that in shootout games, greater than 49 point totals. The RB is pretty rarely the captain. It drops all the way down to 18% where it's at 29% on the slower game."
  - Takeaway: Wide receivers are described as the most common captain in all three game archetypes, while running-back captain frequency falls to 18% in shootouts versus 29% in slower games.
- [5:37](https://www.youtube.com/watch?v=65HDqKemR88&t=337s) "Kickers are rostered pretty much over 40% of the time in winning lineups across the board. No matter what type of game it is uh somewhere between 41 and 46% of the time, there is at least one kicker in the flex. Rarely two, we'll get into that as well, but there's at least one."
  - Takeaway: The transcript reports at least one flex kicker in 41–46% of winning lineups across game types, with two kickers described as rare.
- [5:59](https://www.youtube.com/watch?v=65HDqKemR88&t=359s) "At a 42 or lower point projected total, 47% of the time there's at least one defense in the lineup as the totals go up in that average zone, 38%. And then when we drop uh when we go to shootouts, so 49 or more defenses drop all the way to just 21%, which is neg negative leverage versus their ownership in those contests."
  - Takeaway: Winning-lineup defense usage is stated as 47% in games projected at 42 points or lower, 38% in the average-total zone, and 21% in totals of 49 or more.
- [20:21](https://www.youtube.com/watch?v=65HDqKemR88&t=1221s) "those that spend 49 to 50 thou 49 12 to 50,000 on average, you're going to tie with seven people. If you if you cap your total salary cap at 494, you're going to reduce your average tie probably to around five. Still a lot. So the whole range between 485 and 50k, you're probably going to be in a fairly big tie group."
  - Takeaway: The speaker reports an average of seven ties for lineups spending roughly $49,000–$50,000 and around five ties when capping salary at 49,400, with the $48,500–$50,000 range described as a large tie group.

### I Gave the DFS Army Optimizer the SHOWDOWN CODE… Here’s What It Built!
Ibe's DFS Sports Betting · Oct 01, 2026 (0:11:51) · [Watch on YouTube](https://www.youtube.com/watch?v=sBOEt7d3dM4)

- [0:06](https://www.youtube.com/watch?v=sBOEt7d3dM4&t=6s) "Now, what is the Showdown Code? It's really the Showdown Codeex is this book that studied over 350 real showdown contests and they broke down like what was winning in these contests from the captains to the flex positions and all that stuff."
  - Takeaway: The Showdown Codex is described as reviewing more than 350 real contests and examining winning captain and flex-position construction.
- [0:20](https://www.youtube.com/watch?v=sBOEt7d3dM4&t=20s) "And then they came up with another book on how to stack these showdowns. and I'm taking the settings from how to stack showdowns and I'm using it in the optimizer to build my lineups for tonight's showdown between the Pittsburgh Steelers and the Cleveland Browns."
  - Takeaway: He applies settings from a showdown-stacking book in the optimizer to build his lineups.
- [0:55](https://www.youtube.com/watch?v=sBOEt7d3dM4&t=55s) "some of the rules that I have is quarterbacks. We want the quarterbacks in the captain position unless the quarterback is a three-point underdog. Is more than three points. So right now, we don't have any quarterbacks that fall in that position or in that category. So both of the quarterbacks are good to go. We don't want kickers in the captain spot. We don't want defenses in the captain's spot."
  - Takeaway: His stated captain rules favor quarterbacks unless they are more than three-point underdogs and exclude kickers and defenses.
- [1:14](https://www.youtube.com/watch?v=sBOEt7d3dM4&t=74s) "We also don't want backup running backs and we don't want backup tight ends in the captain spot. Also get rid of anybody that's projected to have less than 7.5 points. Get them out of the captain spot. And then we adjust our exposures from there."
  - Takeaway: He also excludes backup running backs, backup tight ends, and players projected for under 7.5 points from captain, then adjusts exposures.
- [7:10](https://www.youtube.com/watch?v=sBOEt7d3dM4&t=430s) "So, we got Jaylen Warren right here at the captain position along with both quarterbacks. It seemed like so far every Jaylen Warren lineup has had both quarterbacks in it. Then we got Chris Boswell, the Steelers defense, and then Raheem Sanders."
  - Takeaway: In the displayed optimizer results, a Jaylen Warren captain lineup includes both quarterbacks, a kicker, a defense, and Raheem Sanders.

### How to Crush NFL Showdowns on Fanduel and Draftkings Using the DFS Army Domination Station Optimizer
DFS Army - Daily Fantasy Sports · Sep 08, 2020 (0:51:20) · [Watch on YouTube](https://www.youtube.com/watch?v=ehza4xs_VSc)

- [8:46](https://www.youtube.com/watch?v=ehza4xs_VSc&t=526s) "the statistics show that close to 20 of the time the winning lineup actually spends 55k or less which is mind-blowing"
  - Takeaway: The speaker says winning lineups spend $55,000 or less close to 20% of the time.
- [12:09](https://www.youtube.com/watch?v=ehza4xs_VSc&t=729s) "this eliminates the possibility of two kickers in a lineup our study has shown that two kickers in the same lineup does not win tournaments"
  - Takeaway: The speaker recommends excluding lineups with two kickers, saying their study found that such lineups do not win tournaments.
- [24:14](https://www.youtube.com/watch?v=ehza4xs_VSc&t=1454s) "the incident of past catchers being the perfect optimal mvp are is just about 18 percent running back is about 38 percent and quarterbacks about 42 something in that range and with tight end coming in like three percent"
  - Takeaway: The speaker reports that optimal MVPs were past catchers about 18% of the time, running backs about 38%, quarterbacks about 42%, and tight ends about 3%.
- [46:30](https://www.youtube.com/watch?v=ehza4xs_VSc&t=2790s) "the onslaught stack is where we use four players from one team and just one from the second team note that the standard construction here you'll see will have three players usually from the favorite and two from the underdog"
  - Takeaway: The speaker describes a 4-1 onslaught stack and says the standard construction is usually three players from the favorite and two from the underdog.

### NFL DFS Strategy - Winning Showdowns | How To Make More Money
Fantasy Six Pack · Sep 06, 2022 (0:09:00) · [Watch on YouTube](https://www.youtube.com/watch?v=KKUUjA6MV38)

- [1:33](https://www.youtube.com/watch?v=KKUUjA6MV38&t=93s) "typically for me this is going to be a wide receiver it also can be a running back or a quarterback depending on you know the situation and in the right spots it can be a tight end"
  - Takeaway: The speaker generally prefers a wide receiver in the captain spot, with running back, quarterback, or tight end as situation-dependent alternatives.
- [2:06](https://www.youtube.com/watch?v=KKUUjA6MV38&t=126s) "if a wide receiver is going to have a good enough game that they're going to be the optimal play as captain then that means almost surely their quarterback is going to be you know having a good enough game that they're going to be needed in the flex as well to be optimal"
  - Takeaway: A wide receiver captain should be paired with that player's quarterback in the flex.
- [5:58](https://www.youtube.com/watch?v=KKUUjA6MV38&t=358s) "i always say you need to have at least two spots at flex that are correlated with the captain and we've talked about the cabin spot and how we would go about doing that so depending on who your captain is that should fill up at least two of those flex spots if not a third"
  - Takeaway: At least two flex players, potentially three, should correlate with the captain.
- [7:07](https://www.youtube.com/watch?v=KKUUjA6MV38&t=427s) "i would definitely limit it to only you know one defense special teams or one kicker i wouldn't play both kickers i wouldn't play both defenses theoretically you could play a defense and a kicker in the same lineup i again would almost surely avoid that"
  - Takeaway: The speaker recommends using no more than one defense/special-teams unit or one kicker, avoiding both kickers, both defenses, and usually a defense plus a kicker.

### The DraftKings Showdown Rule That Deletes Your Winning Lineup
FTA Sports · Aug 05, 2026 (0:18:10) · [Watch on YouTube](https://www.youtube.com/watch?v=1X6cgvJxsqQ)

- [1:34](https://www.youtube.com/watch?v=1X6cgvJxsqQ&t=94s) "Across all 163 slates, the optimal captain was a wide receiver 33.1% of the time and a running back was a optimal 28% of the time. Those two positions together take over 61% of the captain spots. I don't think that's as big as a surprise to you as you might think the quarterback is there. Now, the quarterback comes in at 20.9."
  - Takeaway: Across 163 slates, WRs were optimal captain 33.1% of the time, RBs 28%, and QBs 20.9%.
- [6:13](https://www.youtube.com/watch?v=1X6cgvJxsqQ&t=373s) "Players from the favorite in the nut lineup out of six. One player only 2.5% of the time. Two players 21.5% of the time. Three players 34.4% of the time. Four players 31.3 and five players 10.4."
  - Takeaway: Winning lineups most often used three or four players from the favorite, while one-player and five-player favorite builds were less common.
- [7:13](https://www.youtube.com/watch?v=1X6cgvJxsqQ&t=433s) "40 and a half percent of the time the nut lineup had a kicker in it. 31% of the time uh the nut lineup or the winning lineup had a defense in it. And then 8% 8.6% of the time a captain was either a kicker or a defense."
  - Takeaway: Kickers appeared in 40.5% of winning lineups and defenses in 31%, while a kicker or defense was captain 8.6% of the time.
- [8:23](https://www.youtube.com/watch?v=1X6cgvJxsqQ&t=503s) "salary left unspent by the nut lineup $0, that only won 7.4% of the time. $100 is kind of the key. Uh 31.3% of the time the winning lineup left up to $900 on the table. 22.7% of the time left 1,000 to 1,900."
  - Takeaway: Only 7.4% of winning lineups spent the full salary cap; 31.3% left up to $900 and 22.7% left $1,000–$1,900.

### HOW TO WIN ON DRAFTKINGS NFL SHOWDOWN: LINEUP BUILDING TIPS
Alvin Zeidenfeld · Sep 03, 2019 (0:14:55) · [Watch on YouTube](https://www.youtube.com/watch?v=lyaKCYf1LrQ)

- [6:15](https://www.youtube.com/watch?v=lyaKCYf1LrQ&t=375s) "so Shaheen is actually a viable captain on the draft Kings showdown slate even if you only project them for five or six draftkings points because he would let you afford basically all the other good skill position players that you would want whether it's Rogers Jones Adams true Biscay you know whoever"
  - Takeaway: A low-projection player can be a viable captain when the salary savings let the lineup afford other desired skill-position players.
- [7:24](https://www.youtube.com/watch?v=lyaKCYf1LrQ&t=444s) "about 71% yeah like 71% of winning lineup said he running back or a wide receiver in the captain spot and I think part of that is driven by a lot of people use the median projections for the game when building their lineups"
  - Takeaway: The speaker estimates that running backs or wide receivers occupied the captain spot in about 71% of winning lineups.
- [11:58](https://www.youtube.com/watch?v=lyaKCYf1LrQ&t=718s) "like we said a running back or a wide receiver typically ends up winning in the captain spot that doesn't mean that there weren't weeks where a kicker wasn't a the the best captain to have or a quarterback wasn't the best captain"
  - Takeaway: Running backs and wide receivers typically win at captain, but the speaker notes that kickers and quarterbacks can also be the best captain in a given week.
- [12:10](https://www.youtube.com/watch?v=lyaKCYf1LrQ&t=730s) "because quarterbacks still win at what 15 or 16 percent of the time exactly exactly or a defense or a tight end but most likely it's going to be a running back or wide receiver"
  - Takeaway: The speaker puts quarterback captain wins at about 15–16% and also names defenses and tight ends as possible winning captains.

### DraftKings Showdown Strategy for Seahawks vs Lions | JSN Captain + Game Theory Breakdown
One Week Season · Sep 30, 2024 (0:43:25) · [Watch on YouTube](https://www.youtube.com/watch?v=OTvIy-Jk96U)

- [16:29](https://www.youtube.com/watch?v=OTvIy-Jk96U&t=989s) "for low-scoring games the way I think about it is you need to prioritize plays that can succeed without touchdowns um and so and you also want to think about lower scoring plays are more likely to end up in winning lineups right don't use much ceiling per play and also because there aren't a lot of touchdowns scored it's pretty important to try and get the that are scored"
  - Takeaway: For a low-scoring Showdown build, prioritize players who can produce without touchdowns and recognize that lower-scoring plays may appear in winning lineups.
- [16:57](https://www.youtube.com/watch?v=OTvIy-Jk96U&t=1017s) "how that plays out in terms of picking players one Kickers and defenses are more likely to be optimal because kickers generally don't have the ceiling of you know other players except for those reallyare rare ones like that Washington New York game where it was like 18 field goals kicked or whatever um in week two"
  - Takeaway: The speaker says kickers and defenses are more likely to be optimal in lower-scoring games.
- [19:16](https://www.youtube.com/watch?v=OTvIy-Jk96U&t=1156s) "generally speaking in an average Showdown it's going to vary depending on who's playing right Lamar Jackson is generally going to be higher owned than gin Smith but generally speaking something like 80ish percent of all lineups entered are going to contain a quarterback at least one"
  - Takeaway: The speaker estimates that roughly 80% of Showdown lineups include at least one quarterback.
- [39:38](https://www.youtube.com/watch?v=OTvIy-Jk96U&t=2378s) "I'm going to go with Bates over Meyers because I think I want a three3 build here and also I tend to like I tend to skew my Kicker away from my captain because you want your captain to have a really big game and every field goal kicked is a you know potential touchdown that Captain could have scored that's taken away"
  - Takeaway: In this lineup example, the speaker chooses a 3-3 build and prefers the kicker to come from a team other than the Captain's team.

### How to Build Winning NFL DFS Showdown Lineups on DraftKings & FanDuel (2024)
Occupy Fantasy · Oct 07, 2024 (1:22:41) · [Watch on YouTube](https://www.youtube.com/watch?v=W9FWB82PwNs)

- [18:17](https://www.youtube.com/watch?v=W9FWB82PwNs&t=1097s) "Play exactly one quarterback in your lineup, not two, not zero. This is from historical data. Typically, in these smaller GPs, you one quarterback is the optimal approach."
  - Takeaway: The transcript says historical data favors exactly one quarterback in smaller FanDuel GPPs.
- [18:28](https://www.youtube.com/watch?v=W9FWB82PwNs&t=1108s) "If you have a lowowned player in your lineup under 20%, feel free to use all the salary. If possible, leave $500 to $1,000 if all five spots in your lineup include popular players."
  - Takeaway: For FanDuel small-field GPPs, the guidance permits using the full salary with a low-owned player and suggests leaving $500–$1,000 when all five players are popular.
- [31:53](https://www.youtube.com/watch?v=W9FWB82PwNs&t=1913s) "And you may think that two guys from one team, one in the captain, and four in the other. These are actually a pretty historically profitable build for wide receivers, captains. So not bad. You go something like this."
  - Takeaway: The speaker describes a build with one team supplying two players, including the captain, and the other supplying four as historically profitable for wide-receiver captains.
- [52:18](https://www.youtube.com/watch?v=W9FWB82PwNs&t=3138s) "We don't want two defenses in the lineup. We know that it rarely wins if ever on FanDuel. So, let's look at both defenses. Max of one defense on the lineup. We'll allow two kickers because clearly that happens."
  - Takeaway: The speaker recommends at most one defense on FanDuel and says to allow two kickers.

### High Level Showdown Strategy + Super Bowl Stuff with Cody Main and Colin Drew
Establish The Run · Feb 04, 2022 (0:55:18) · [Watch on YouTube](https://www.youtube.com/watch?v=i98ljRFANdA)

- [12:44](https://www.youtube.com/watch?v=i98ljRFANdA&t=764s) "basically if you look at the percentage of lineups that play a five one stack the top one percent lineup is like positively leveraged whether it's the underdog team or the favorite team so it seems like that still might might be the case a little bit"
  - Takeaway: In games with spreads between 3.5 and 5.5 points, five-one builds were positively leveraged in top-one-percent lineups whether the onslaught was built around the underdog or favorite.
- [13:57](https://www.youtube.com/watch?v=i98ljRFANdA&t=837s) "this field that feels really comfortable with these three three lineups and then feels really uncomfortable forcing these onslaught so they're really really low owned they don't they don't necessarily project as well either so anyone that's using an optimizer to run 150 probably isn't getting a whole lot of them either"
  - Takeaway: The speakers said the field favors three-three builds, while onslaughts are underused and may be missed by optimizer-generated 150-lineup sets.
- [21:30](https://www.youtube.com/watch?v=i98ljRFANdA&t=1290s) "it is more used by the field than than it does land in top one percent lineups but it's pretty close so i don't scoff at it as much as i used to just because i understand like the unique nature of doing it"
  - Takeaway: Kickers and defenses were described as more commonly used by the field than found in top-one-percent lineups, though the gap was said to be fairly close.
- [47:47](https://www.youtube.com/watch?v=i98ljRFANdA&t=2867s) "i think he had a no quarterback lineup it was yeah so the equivalent for this game would be the cooper cup no qb's a couple pass catchers in there running back touchdown game goes under the total"
  - Takeaway: The speakers cited a past solo-winning lineup with no quarterback and described a Cooper Kupp lineup with no quarterback as an analogous extreme-game-script construction.

### Lions vs Panthers - SNF Sunday Sweatdown | NFL Week 4 | DFS Picks, Plays & Process
Ship It Nation · Oct 05, 2026 (1:05:29) · [Watch on YouTube](https://www.youtube.com/watch?v=xJlvummhIfI)

- [26:09](https://www.youtube.com/watch?v=xJlvummhIfI&t=1569s) "Yeah, I I I I say the answer is yes. Uh, I mean, percentage- wise, 60 70%. Um, and the reason I say that is is because there's going to be tons of passing volume in this game. Should be high scoring. That's how I'm playing. I think the field sees that as well. The total's a high total."
  - Takeaway: One speaker expected 60–70% of lineups to use both quarterbacks in this high-total game.
- [26:57](https://www.youtube.com/watch?v=xJlvummhIfI&t=1617s) "I'm seeing I'm just running some stuff through stuff that I'm seeing here. I mean, I expect like roughly 30 to 40% of the field to play both quarterbacks in their lineup."
  - Takeaway: The other speaker estimated that roughly 30–40% of lineups would use both quarterbacks.
- [33:00](https://www.youtube.com/watch?v=xJlvummhIfI&t=1980s) "I just think so many people I mean so many of the teams are going to be both quarterbacks Gibbs and Amanra. Pick one of those and throw in Tmaine and whoever else fits is kind of how the slate's going to shake up. It's probably both quarterbacks, Gibbs, Leaporta, Tmaine and figure out your sixth piece is really what the kind of cash game"
  - Takeaway: The speakers anticipated common lineups with both quarterbacks, Gibbs, LaPorta, and Tmaine, leaving the sixth slot as the remaining construction decision.
- [45:24](https://www.youtube.com/watch?v=xJlvummhIfI&t=2724s) "they're finding a little bit more money to get up to a Sam Laaporta or um they're going down to cheaper with a guy like Bryson Tmaine, right? So, these kickers and defenses kind of land in no man's land, which makes me like them more. I like all four of them. I'm going to have have a decent amount."
  - Takeaway: The speaker expected kickers and defenses to be underplayed because the field would spend up to LaPorta or down to Tmaine, and planned to use all four.

### 2025 HOW TO PLAY NFL DRAFTKINGS SHOWDOWN
DFS Army - Daily Fantasy Sports · Aug 23, 2025 (0:10:32) · [Watch on YouTube](https://www.youtube.com/watch?v=-ZBpaHty068)

- [3:55](https://www.youtube.com/watch?v=-ZBpaHty068&t=235s) "Select your captain from favored teams as favored teams produce nuts captains between 62 to 75% of the time. In totals that are greater than 47 points completely avoid defense or kicker at captain. High-scoring games defenses tend not to get there."
  - Takeaway: The transcript recommends captains from favored teams and avoiding defense or kicker at captain in games with totals above 47 points.
- [4:24](https://www.youtube.com/watch?v=-ZBpaHty068&t=264s) "If you put a pocket passer quarterback like Dak Prescott as your captain, you're going to want not one but two of his pass catchers in there to offset the fact that, hey, if Dak Prescott's having a monster game and all of the all of the passes are going to CD Lamb, he's having a CD Lamb will outscore Dak, right?"
  - Takeaway: For a pocket-passer captain, the transcript recommends including at least two of that quarterback’s pass catchers.
- [8:01](https://www.youtube.com/watch?v=-ZBpaHty068&t=481s) "Similarly, if a game has a low total, very low, and especially if one team has a really low total and the other team a little bit higher, I might be looking to combine running back captain with same team defense in the flex. Defense dominates, running back dominates."
  - Takeaway: For a very low-total game, the transcript describes combining a running-back captain with that team’s defense in the flex.

### DFS Q&A: What is a self-sim?
SaberSim DFS - Daily Fantasy Sports Strategy · Jul 11, 2024 (0:56:19) · [Watch on YouTube](https://www.youtube.com/watch?v=JjEqfaORNpA)

- [33:39](https://www.youtube.com/watch?v=JjEqfaORNpA&t=2019s) "NFL showdown is a good example the the 42 salar 42,000 salary lineup that has a low projected score that is profitable in the contest flashback for example is profitable because nobody else played it but it if you assume only one person plays every single lineup out there every single lineup in existence that the selfsim kind of assumes for dupe Sports those lineups aren't going to look good"
  - Takeaway: The transcript gives a showdown example of a low-projected, 42,000-salary lineup described as profitable because nobody else played it.

### How to Beat NFL DFS Showdowns
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 10, 2026 (0:17:26) · [Watch on YouTube](https://www.youtube.com/watch?v=iE36sFpjaVw)

- [6:32](https://www.youtube.com/watch?v=iE36sFpjaVw&t=392s) "Then our sim optimizer goes through all 5,000 of those scripts. And for each one, it solves the best six-man lineup. Not a good lineup for that version of the game, the best one."
  - Takeaway: The described method finds the best six-man lineup for each of 5,000 simulated game scripts.

### The 3 Rules for Beating NFL Showdown and Single Game GPPs
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 09, 2021 (1:11:46) · [Watch on YouTube](https://www.youtube.com/watch?v=7T2VrpJIN1M)

- [55:00](https://www.youtube.com/watch?v=7T2VrpJIN1M&t=3300s) "for two running backs in the same team they're almost always negatively correlated but not as much as people would expect um and so having two running backs on the same team especially in a showdown um in in a main slate you you wouldn't want to do that just because they're gonna be so many positive correlations that you can work in your lineups"
  - Takeaway: The speakers say two same-team running backs can be viable in showdown and caution against applying a blanket lineup rule.

### DFS Q&A: How do I best utilize the dupe metric in the contest sims?
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 03, 2023 (1:39:07) · [Watch on YouTube](https://www.youtube.com/watch?v=ETNpMZGSNCs)

- [1:15:50](https://www.youtube.com/watch?v=ETNpMZGSNCs&t=4550s) "it's very low salary it plays two running backs from Seattle it plays DK meaf is the optimal Capital with no goo Smith right like these kinds of lineups are the things that you almost earn the right to play using a Sim based platform because you can toss aside the rules of thumb and the average correlations between players and just play low duplicated optimal lineups"
  - Takeaway: Jordan gives an optimal-simulation lineup example with two Seattle running backs, DK Metcalf at captain, no Geno Smith, and low salary, but does not present historical winning-lineup rates.

### NFL Office Hours - Showdown Q&A
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 08, 2023 (1:01:37) · [Watch on YouTube](https://www.youtube.com/watch?v=Re6X-sC0P7A)

- [23:14](https://www.youtube.com/watch?v=Re6X-sC0P7A&t=1394s) "you could see you can even see what the project uh what the exposures are Etc here by by player so this should go away so okay so when I Collapse the contest tab it it uh gives me some more space here so then I could go and see uh what the stacks are you know what is it how many four twos do I have how many five ones three threes"
  - Takeaway: The transcript describes checking field lineup frequencies for 4-2, 5-1, and 3-3 stacks, but provides no historical winning-lineup rates or CPT/QB/kicker/DST/salary-left comparisons.

### How To Use The Stokastic NFL DFS Contest Generator Tool | NFL DFS Contest Simulations
Stokastic DFS - Daily Fantasy Sports Advice · Sep 07, 2023 (0:06:38) · [Watch on YouTube](https://www.youtube.com/watch?v=QX-prNRoIuA)

- [3:19](https://www.youtube.com/watch?v=QX-prNRoIuA&t=199s) "but you can see of these lamps that I've built here 33 of them are unstacked 49.4 percent have a QB with one pass catcher 15.4 qb2 pass catchers and on and so forth"
  - Takeaway: The generated lineup pool is reported as 33 unstacked, 49.4% with a QB and one pass catcher, and 15.4 qb2 pass catchers; these are not identified as historical or winning Showdown lineup rates.

### SaberSim's Unique Approach to Projecting Ownership
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 10, 2021 (1:28:00) · [Watch on YouTube](https://www.youtube.com/watch?v=zMdDPCaxXjg)

- [32:40](https://www.youtube.com/watch?v=zMdDPCaxXjg&t=1960s) "there's a simulation we're using single game simulations to build all of these lineups some variances at 10 there's a simulation represented by this lineup or a set of simulations actually where this lineup is optimal"
  - Takeaway: For showdown, the builder uses single-game simulations and can select lineups that are optimal in those simulations; the transcript does not state historical captain rates, 5-1/4-2/3-3 rates, QB counts, kicker/DST usage, or how winners differ from the field.

### DFS Q&A: How do I navigate NFL late swap?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 09, 2022 (1:07:37) · [Watch on YouTube](https://www.youtube.com/watch?v=uvDTL8e6Ipo)

- [21:43](https://www.youtube.com/watch?v=uvDTL8e6Ipo&t=1303s) "sometimes you know you might find a max salary bill that has a quarterback in the captain and a defense the opposing defense elsewhere in the lineup i think that lineup even though its max salary is very unlikely to be played or features multiple running backs from the same team"
  - Takeaway: The speaker gives quarterback-at-captain with the opposing defense, and multiple same-team running backs, as lineup constructions that may be less likely to be duplicated.

### DFS Q&A: How Do You Filter NFL Lineups to Avoid Dupes While Staying +EV?
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 27, 2025 (0:19:42) · [Watch on YouTube](https://www.youtube.com/watch?v=wdjc-z_h8m4)

- [13:08](https://www.youtube.com/watch?v=wdjc-z_h8m4&t=788s) "Another way is lineup construction, right? Maybe it's a game where, you know, one team is heavily favored and you build uh lineups using like an op like optimizer mode like uh optimizing based on average projection and you see like, hey, it's a bunch of 5-1 lineups of the favorite."
  - Takeaway: For a heavily favored team, the speaker describes average-projection optimization producing many 5-1 lineups and suggests limiting how many of those lineups are included.

## 2. Duplication prediction and lineup duplication modeling

37 videos, 76 transcript excerpts.


### DFS Q&A: Product Ownership and Geometric Mean
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 11, 2022 (0:56:29) · [Watch on YouTube](https://www.youtube.com/watch?v=eVWhJ0Cy2FY)

- [3:09](https://www.youtube.com/watch?v=eVWhJ0Cy2FY&t=189s) "you're basically saying in the example of DFS you you could say something like the ownership product times the contest size will approximate the number of times you might expect that to be duplicated in the contest"
  - Takeaway: The speaker uses ownership product multiplied by contest size as an approximation of the expected number of duplicates.
- [6:47](https://www.youtube.com/watch?v=eVWhJ0Cy2FY&t=407s) "so the geometric mean is the ownership product to the one divided by the number of players in the lineup power"
  - Takeaway: The geometric mean is defined as the ownership product raised to the power of one divided by the number of lineup players.
- [7:14](https://www.youtube.com/watch?v=eVWhJ0Cy2FY&t=434s) "there are six players in a DFS in a DFS Showdown lineup power which means our geometric mean here is 20.1 Right keeping in mind here saber Sim I'm doing this calculation using the percentages 20% Sab Sims using the actual numbers here"
  - Takeaway: In the hypothetical six-player Showdown example, the stated geometric mean is 20.1 when ownership is entered as whole-number percentages.
- [18:39](https://www.youtube.com/watch?v=eVWhJ0Cy2FY&t=1119s) "so in this case we're treating player somebody using momes at their Captain uh and using Kelsey in their Flex as independent that they don't they not one does not affect the other which is definitely not true right somebody playing Mahomes in their Captain spot is much more likely to use Kelsey as a flex"
  - Takeaway: The ownership-product approximation assumes player selections are independent, although the speaker notes that Captain Mahomes and Flex Kelce are correlated.
- [19:12](https://www.youtube.com/watch?v=eVWhJ0Cy2FY&t=1152s) "if you followed this equation through you would probably find that there's some 33,000 total salary that's likely to have like 25 dupes purely based on this equation people are not likely to play salaries that low so that that lineup is probably going to be duped far less than this equation would imply"
  - Takeaway: The equation can overestimate duplicates for a $33,000-salary lineup because people are unlikely to play salaries that low.
- [21:12](https://www.youtube.com/watch?v=eVWhJ0Cy2FY&t=1272s) "I think this is best used as a way to filter out your extremely chalky heavily duped builds so coming back to our equation here instead of even saying I want five or less dupes in the mil maker I think a better way using this would be say I want 20 or less dupes in the mmaker or 25 or less dupes in the milim maker"
  - Takeaway: The speaker recommends using the rule as a guardrail against extremely duplicated builds, suggesting a 20- or 25-dupe limit rather than insisting on five or fewer.

### DFS Office Hours 7/29/21: Why avoiding duplication is important in DFS
SaberSim DFS - Daily Fantasy Sports Strategy · Jul 30, 2021 (0:27:16) · [Watch on YouTube](https://www.youtube.com/watch?v=U13Q_op4i-g)

- [7:10](https://www.youtube.com/watch?v=U13Q_op4i-g&t=430s) "what the sites do is they take the winnings of first and second and divide them by the number of people that tied in this case two and that gets paid out equally to both people"
  - Takeaway: When lineups tie, the prizes for the tied positions are combined and split equally among the tied entries.
- [8:39](https://www.youtube.com/watch?v=U13Q_op4i-g&t=519s) "if you know that you are never going to be duplicated your expected value here in this contest is 240 every time you put 10 in you can expect to win 240 coming out of that right if you are duplicated once if you're just guaranteed to be duplicated your expected value even in a contest that you are just vastly this profitable on drops pretty significantly down to 178 dollars"
  - Takeaway: In the hypothetical contest, expected value falls from $240 to $178 when the lineup is guaranteed to be duplicated once.
- [9:03](https://www.youtube.com/watch?v=U13Q_op4i-g&t=543s) "being duplicated in any contest period end of story is reducing your expected value of that lineup and it's reducing your overall roi playing that contest so it only gets worse the more you are duplicated"
  - Takeaway: Duplication reduces a lineup’s expected value and overall ROI, with the impact worsening as the number of duplicates increases.
- [9:18](https://www.youtube.com/watch?v=U13Q_op4i-g&t=558s) "duplicating yourself 150 times in a contest is a terrible idea it dramatically reduces the expected value of the lineup that you're playing right you only have one lineup and you're even investing why it's worse when you do it yourself is because you're paying extra to do that"
  - Takeaway: Entering the same lineup repeatedly lowers its expected value and requires paying additional entry fees.
- [11:22](https://www.youtube.com/watch?v=U13Q_op4i-g&t=682s) "um to the point where i think even on things like nfl showdown where you're playing contests that have like sometimes 100 000 people on a single showdown lineup this maybe even becomes the primary factor our goal in creating an unduplicated or a very minimally duplicated lineup becomes so much higher than wanting to fade ownership in terms of finding leverage"
  - Takeaway: In very large NFL Showdown contests, avoiding duplicated lineups may matter more than fading ownership for leverage.

### DFS Q&A: Avoiding Dupes on Small NFL Slates
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 21, 2025 (0:27:22) · [Watch on YouTube](https://www.youtube.com/watch?v=KDQWYsMCP8w)

- [3:19](https://www.youtube.com/watch?v=KDQWYsMCP8w&t=199s) "it's always good to look at past slates to try and get an answer to this question, right? So, like what I would do is I would go and try and find a recent twoame NFL slate and uh look at the results of that slate to answer this question."
  - Takeaway: The suggested method for assessing whether duplication matters is to find a comparable past slate and examine its results.
- [5:21](https://www.youtube.com/watch?v=KDQWYsMCP8w&t=321s) "I'm just going to look at 150 maxers and I'm going to look at SIM ROI. All right. So we sort high SIM ROI to low and then we come over here and then we look at the average dupes column and duplication you know is I don't know uh visible here"
  - Takeaway: The presenter checks average duplicate counts among 150-max entries after sorting by SIM ROI.
- [7:47](https://www.youtube.com/watch?v=KDQWYsMCP8w&t=467s) "You could come at duplication from salary. You could come at duplication from some ownership. You could come at geomine from lineup construction, right? Like there's all these different avenues uh that kind of lead to a lineup a lineup's likelihood of being played more or being played less, right?"
  - Takeaway: The presenter identifies salary, ownership, and lineup construction as different factors related to how likely a lineup is to be played.
- [9:10](https://www.youtube.com/watch?v=KDQWYsMCP8w&t=550s) "Okay, so 45 is about 10ish%, right? I think this is a safe number to uh to rule out, right? Is about like 10% of the lineups. Just hey, I just don't want to consider the highest, you know, 10% of Geomine lineups. I think these are the most likely to be duplicated"
  - Takeaway: The example filters out roughly the highest 10% of Geomine lineups as those considered most likely to be duplicated.

### DFS Q&A: How Do You Reduce Dupes in Showdown?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 07, 2025 (1:05:02) · [Watch on YouTube](https://www.youtube.com/watch?v=JuOzj5ZOQHk)

- [14:57](https://www.youtube.com/watch?v=JuOzj5ZOQHk&t=897s) "The first way I think to do this is to lower your max salary, right? Maybe instead of playing a 50k max, you play like a 495 max. Maybe you play 496, 497. You know, you kind of got to play around with it."
  - Takeaway: One suggested way to reduce showdown duplication is to experiment with a maximum salary below the $50,000 cap.
- [23:46](https://www.youtube.com/watch?v=JuOzj5ZOQHk&t=1426s) "So there's basically two ways to use the ownership filters there or two types of ownership filters. There's the sum ownership filters and the product/geomine ownership filters. Uh we break down the differences between those two and how they interact"
  - Takeaway: The speaker distinguishes sum-ownership filters from product/geometric-mean ownership filters and notes that they work differently.
- [25:22](https://www.youtube.com/watch?v=JuOzj5ZOQHk&t=1522s) "So like here, right, if I close my lineup group, okay, 200 sent 68 lineups to the trash. That's actually kind of a good number, right? Because 10% would be 50 and 20% would be 100. So I'm right in the middle."
  - Takeaway: In the demonstrated 500-lineup pool, a sum-ownership threshold of 200 removed 68 lineups, within the suggested 10–20% filtering range.
- [25:43](https://www.youtube.com/watch?v=JuOzj5ZOQHk&t=1543s) "Geomine is a little bit more accurate in projecting dupes. Now, in order to use geomine, you need to create a custom metric for it, which is covered in that tutorial that I pointed out."
  - Takeaway: The speaker says geometric-mean ownership is more accurate than sum ownership for projecting duplication and requires a custom metric.

### DFS Q&A: What is the best way to reduce dupes in Showdown?
SaberSim DFS - Daily Fantasy Sports Strategy · Jan 15, 2024 (0:15:07) · [Watch on YouTube](https://www.youtube.com/watch?v=eWWw-7T2YLk)

- [5:45](https://www.youtube.com/watch?v=eWWw-7T2YLk&t=345s) "now in the ownership build if a lineup comes up more than once we do allow it to be put into the pool more than once that's how we're accounting for dupes so then when we run the contest Sim I'm going to take this lineup I'm going to put it into a theoretical behind the scenes contest with the rest of the field lineups"
  - Takeaway: The ownership build retains repeated lineups to account for duplication, and the contest sim compares a lineup against a theoretical field.
- [6:43](https://www.youtube.com/watch?v=eWWw-7T2YLk&t=403s) "if you wanted to choose only non- dup lineups from the field lineups what I would do is I would go to filter I would add a filter and then I would say show lineups with I would open the contest Sim dupes less than one and then now what it's going to do it's going to move all the lineups that are duped into the trash"
  - Takeaway: To select lineups with no simulated duplicates, set a filter for contest-sim dupes less than one.
- [8:15](https://www.youtube.com/watch?v=eWWw-7T2YLk&t=495s) "upwards of 70,000 entries in them so that is way more than the 20,000 that we have when you do geometric mean you're using that actual contest size as a variable which which is why I think it's more accurate um as the number of field lineups grows"
  - Takeaway: Geometric mean uses actual contest size as a variable, which the speaker says makes it more accurate as the number of simulated field lineups grows.
- [8:38](https://www.youtube.com/watch?v=eWWw-7T2YLk&t=518s) "but if I had to choose between dupes or geometric mean I would recommend geometric mean and not to say that it's like a you know G to be 100% accurate but I think it's going to be directionally accurate"
  - Takeaway: The speaker prefers geometric mean over the contest-sim dupe count as a directional guide for reducing duplication.

### The 3 Rules for Beating NFL Showdown and Single Game GPPs
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 09, 2021 (1:11:46) · [Watch on YouTube](https://www.youtube.com/watch?v=7T2VrpJIN1M)

- [43:00](https://www.youtube.com/watch?v=7T2VrpJIN1M&t=2580s) "expected value of that lineup is essentially the probability of it landing in a certain spot times the payout when that event happens if you're duplicated in that lineup the payout that you get for that particular outcome immediately goes down reducing the expected value for that lineup"
  - Takeaway: Duplication reduces a lineup’s expected value because the payout for that outcome is divided among duplicate entries.
- [44:18](https://www.youtube.com/watch?v=7T2VrpJIN1M&t=2658s) "one thing that you'll see that's very unique for nfl showdowns and doesn't show up in a lot of our other default settings is that the max salary has actually already been lowered 100 less than the actual salary cap on draftkings"
  - Takeaway: The default showdown build lowers the maximum salary by $100 from DraftKings’ salary cap as a way to reduce duplication.
- [46:26](https://www.youtube.com/watch?v=7T2VrpJIN1M&t=2786s) "any lineup that has that uses a full salary is all especially in a bigger context is practically guaranteed to be duped many times and it's one thing to have a line up the twice maybe three times if it's a really good lineup you still don't want that"
  - Takeaway: The speakers warn that full-salary lineups in large contests are likely to be duplicated, potentially many times.

### Master The Art of NFL DFS Showdowns
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 30, 2024 (0:44:55) · [Watch on YouTube](https://www.youtube.com/watch?v=Fr2FxzlztT4)

- [2:05](https://www.youtube.com/watch?v=Fr2FxzlztT4&t=125s) "as our lineups are duplicated or duped our lineup starts to earn less and less money when it ends up being the highest scoring lineup you've almost certainly encountered the extreme case of this before if you've played any NFL showdown where first place for the contest pays out a fraction of what it was actually listed as to hundreds or even thousands of different lineups that all tied for first"
  - Takeaway: Ties caused by duplicated first-place lineups split the advertised top prize among the tied entries and reduce each lineup’s payout.
- [32:00](https://www.youtube.com/watch?v=Fr2FxzlztT4&t=1920s) "if you treat these six players any six players as being entered into any given lineup as all independent from each other the probability that a lineup is played in a contest is equal to its ownership product and then you can take that and multiply it by the number of entries in the contest and come up with an expected dupes calculation"
  - Takeaway: The ownership-product estimate assumes player selections are independent and estimates expected duplicates by multiplying lineup ownership product by contest entries.
- [33:05](https://www.youtube.com/watch?v=Fr2FxzlztT4&t=1985s) "with all that said a geomine cap set relatively high is a useful way of avoiding lineups that purely based on the math of the ownership projections could end up duped more than expected where you really want run into trouble with geomine is setting extremely low threshold and trying to use geoman calculations alone as a way to force your lineups to be unique"
  - Takeaway: A relatively high geometric-mean cap can help avoid unexpectedly duplicated lineups, while an extremely low cap used alone to force uniqueness can be harmful.

### DFS Q&A: Simulations can help you avoid duplication in DFS
SaberSim DFS - Daily Fantasy Sports Strategy · Feb 03, 2022 (1:17:24) · [Watch on YouTube](https://www.youtube.com/watch?v=PSqHBQYbYqE)

- [33:38](https://www.youtube.com/watch?v=PSqHBQYbYqE&t=2018s) "each time you have every single individual lineup based on where your sim variant slider is set we are going to randomly sample our full set of simulations for the game and use a random subset of sims that corresponds to that particular lineup right and we have 10 approximately 10 000 simulations for each game"
  - Takeaway: Each lineup uses a randomly sampled subset of the game simulations, making repeated lineups less likely to use the same simulation set.
- [35:46](https://www.youtube.com/watch?v=PSqHBQYbYqE&t=2146s) "and the higher your sim variance goes right the less likely you are to be duplicated right like as you get to a you know something like the and one your your chances of duplicating even yourself amongst multiple builds or other users using saver sim goes down quite a bit"
  - Takeaway: Increasing sim variance reduces the likelihood of duplication with other builds or SaberSim users.
- [36:23](https://www.youtube.com/watch?v=PSqHBQYbYqE&t=2183s) "there is no real contest type where your chance of being duplicated or your your focus of avoiding duplication from other saver sim users should outweigh your focus of just avoiding duplication in general right"
  - Takeaway: The speaker recommends focusing on duplication across the whole contest rather than specifically avoiding SaberSim users.

### 2025 HOW TO PLAY NFL DRAFTKINGS SHOWDOWN
DFS Army - Daily Fantasy Sports · Aug 23, 2025 (0:10:32) · [Watch on YouTube](https://www.youtube.com/watch?v=-ZBpaHty068)

- [5:26](https://www.youtube.com/watch?v=-ZBpaHty068&t=326s) "There's not many players to choose from. And if you go low, if you go high own with all the players in your lineup or most of the players in your lineup, especially if you take a high-owned captain, chances are the lineup you create is going to wind up in a giant tie group."
  - Takeaway: The transcript warns that lineups with many highly owned players, especially a highly owned captain, are likely to land in a large tie group.
- [5:59](https://www.youtube.com/watch?v=-ZBpaHty068&t=359s) "One of the tricks to avoiding some of the dupes. There are a few, but one of my primary tricks is simply to reduce the salary. the total salary of your lineup a little bit so that you don't fall on for example on DraftKings we don't fall on an exactly 50k spend almost every 50k spend will be used"
  - Takeaway: The transcript recommends leaving salary unused to avoid common DraftKings lineups that spend exactly $50,000.
- [6:38](https://www.youtube.com/watch?v=-ZBpaHty068&t=398s) "Each contest is different, but we have the ability, we can see what the ownership of each player is, and you can set a cap on your optimizer run to make sure that you're not putting lineups in that are overly chalky. That will hopefully avoid duplication."
  - Takeaway: The transcript recommends setting an optimizer ownership cap to limit overly chalky lineups and hopefully avoid duplication.

### Why is avoiding duplication important in DFS?
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 16, 2021 (0:08:40) · [Watch on YouTube](https://www.youtube.com/watch?v=MCss_MdowIc)

- [2:56](https://www.youtube.com/watch?v=MCss_MdowIc&t=176s) "what happens when we are duplicated once so let's say we win first but we're tied because somebody else uh has that lineup what the sites do is they take the winnings of first and second and divide them by the number of people that tied in this case two and that gets paid out equally to both people"
  - Takeaway: When two lineups tie for first, the site combines the first- and second-place prizes and splits them equally between the tied players.
- [4:31](https://www.youtube.com/watch?v=MCss_MdowIc&t=271s) "if you know that you are never going to be duplicated your expected value here in this contest is 240 every time you put 10 in you can expect to win 240 coming out of that right if you are duplicated once if you're just guaranteed to be duplicated your expected value even in a contest that you are just vastly this profitable on drops pretty significantly down to 178"
  - Takeaway: In the hypothetical contest, expected value falls from 240 to 178 when the lineup is guaranteed to be duplicated once.
- [6:24](https://www.youtube.com/watch?v=MCss_MdowIc&t=384s) "i think that's part of the value of ownership fade that's part of the the value of fading some ownership in general because you want to avoid dupes right the bigger the bigger value of fading ownership is getting leverage on the field and the impact of having the one percent guy that goes off in your lineup boosts you way to the top right that's the primary impact"
  - Takeaway: Fading ownership can help avoid duplicated lineups, while also providing leverage when a low-owned player performs well.

### DFS Tournament Strategy - How to Beat Small Field & Single Entry GPPs
Establish The Run · Sep 06, 2021 (0:37:26) · [Watch on YouTube](https://www.youtube.com/watch?v=Z79IcL2Cruk)

- [17:13](https://www.youtube.com/watch?v=Z79IcL2Cruk&t=1033s) "what is my total you know cumulative ownership i should have in this lineup or what's the the product ownership i should be willing to hit i think those can be good kind of general rules of thumb to make sure you're not you know spitting out a cash lineup but not all of those percentages are going to be created equal"
  - Takeaway: Cumulative or product ownership can be a general check against building a cash lineup, but the transcript cautions that ownership percentages are not interchangeable.
- [22:14](https://www.youtube.com/watch?v=Z79IcL2Cruk&t=1334s) "in some of these sports like showdown or you know some of the smaller field like we even saw in the thunderdome you know people rolling out the exact same lineup and that and that is the absolute last thing you want to be doing is you do not want to be duplicated"
  - Takeaway: The transcript warns that duplicate lineups are undesirable and notes that identical lineups appeared in smaller-field contests, including the Thunderdome.
- [22:34](https://www.youtube.com/watch?v=Z79IcL2Cruk&t=1354s) "now with nfl because we have nine spots it does become pretty hard to get duplicated and i know i was listening to you guys talk on your dfs series on the main establish the run podcast feed about how the math does really bear out that you don't necessarily want to be leaving a ton of salary on the table"
  - Takeaway: The speakers say NFL's nine roster spots make duplication difficult and that the math does not necessarily support leaving a lot of salary unused.

### DFS Q&A: How Do You Use Geomean to Reduce Dupes in NFL Showdown?
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 12, 2025 (0:19:45) · [Watch on YouTube](https://www.youtube.com/watch?v=UTQzHyEzDEw)

- [13:05](https://www.youtube.com/watch?v=UTQzHyEzDEw&t=785s) "I think there are a number of factors that go into a lineup being duplicated and is it is not solely uh geomine or product ownership. So that that's another reason I don't like to be super aggressive with it."
  - Takeaway: The speaker cautions that Geomean or product ownership alone does not determine duplication and advises against overly aggressive filtering.
- [15:44](https://www.youtube.com/watch?v=UTQzHyEzDEw&t=944s) "I like to say that you should try and just kind of trim the highest geomine lineups out of your pool. And so, you basically make up a number and then you start, you turn it on, you see how many lineups go in the trash, right?"
  - Takeaway: The suggested Geomean method is to set a threshold and check how many high-Geomean lineups it removes.
- [16:04](https://www.youtube.com/watch?v=UTQzHyEzDEw&t=964s) "I recommend doing like 10 to 20% of your pool which would in this case a 500 would be about 50 to 100 lineups. So 130 is like a little bit high."
  - Takeaway: For a 500-lineup pool, the speaker recommends trimming roughly 50 to 100 lineups, or 10 to 20%.

### How to Beat NFL DFS Showdowns
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 10, 2026 (0:17:26) · [Watch on YouTube](https://www.youtube.com/watch?v=iE36sFpjaVw)

- [2:51](https://www.youtube.com/watch?v=iE36sFpjaVw&t=171s) "Except first place in a showdown only gets handed out once. Every other person who landed on your lineup takes a slice of it. And the lineup that looks obviously right to you looks obviously right to a lot of other people because you're all working from the same total, the same spread, and the same week of buildup and narratives."
  - Takeaway: The speaker says duplicated lineups divide first-place winnings and that shared game expectations can lead many entrants to the same lineup.
- [9:23](https://www.youtube.com/watch?v=iE36sFpjaVw&t=563s) "If a lineup's going to get duplicated 200 times in a millie maker, it gets scored like a lineup that makes a few hundred bucks because that's what it pays. Think about what this number represents. It is how likely the lineup is to be the optimal lineup and how much of first place it keeps when it gets there."
  - Takeaway: The lineup evaluation accounts for expected duplication by reflecting the reduced payout when a lineup is shared.

### DFS Q&A: How do I best utilize the dupe metric in the contest sims?
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 03, 2023 (1:39:07) · [Watch on YouTube](https://www.youtube.com/watch?v=ETNpMZGSNCs)

- [1:03:10](https://www.youtube.com/watch?v=ETNpMZGSNCs&t=3790s) "it is precisely the number of dupes in the contests in field that is exactly what it represents and at the moment those contests in fields are capped at a maximum of 5,000 lineups so it is not a duplication calculator for the contest SIM for the contest that you are actually playing it in"
  - Takeaway: The dupe metric counts appearances in the contest-simulation field, capped at 5,000 lineups, rather than predicting the exact duplication count in the entered contest.
- [1:21:22](https://www.youtube.com/watch?v=ETNpMZGSNCs&t=4882s) "I build my pool of lineups I'm running my contest s I'm sorting by risk adjusted Roi and then using the dupe calculation in the contest Sim using salary and using geomean of ownership based filters I try to just trim off as much off the top there of lineups that I think are going to be exceptionally High DED"
  - Takeaway: Jordan's process combines risk-adjusted ROI sorting with dupe, salary, and geometric-mean ownership filters to remove lineups he expects to be exceptionally duplicated.

### NFL Office Hours - Showdown Q&A
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 08, 2023 (1:01:37) · [Watch on YouTube](https://www.youtube.com/watch?v=Re6X-sC0P7A)

- [30:54](https://www.youtube.com/watch?v=Re6X-sC0P7A&t=1854s) "basically if you you can use the geometric mean of a lineup to estimate how many times you think a lineup is going to be duplicated here and if you are on the standard plan how I would go about doing that is I would set a line of pool and then I would go to add new rule"
  - Takeaway: The geometric mean is presented as a way to estimate lineup duplication; a larger geometric mean indicates a lineup is more likely to be duplicated, and a smaller one indicates it is less likely.
- [31:51](https://www.youtube.com/watch?v=Re6X-sC0P7A&t=1911s) "I'm going to do 20 divided by 158 000 close the parentheses and I'm going to do to the power new parenthesis one divided by this second part is the number of players in your lineup so for a showdown it is going to be six"
  - Takeaway: The demonstrated geometric-mean calculation uses an estimated 20 dupes, 158,000 contest entries, and six players in a Showdown lineup.

### DraftKings Showdown Strategy for Seahawks vs Lions | JSN Captain + Game Theory Breakdown
One Week Season · Sep 30, 2024 (0:43:25) · [Watch on YouTube](https://www.youtube.com/watch?v=OTvIy-Jk96U)

- [28:53](https://www.youtube.com/watch?v=OTvIy-Jk96U&t=1733s) "so this is something that if you want to be a shown tournament player you kind of need to know you need to know how to spot duplication or likely duplication we can also see like $100 salary left you know look who we're playing all these guys are big name players like you've got to be able to figure out where the ownership is going to go where the duplication is likely to be"
  - Takeaway: To anticipate duplicated lineups, the speaker recommends considering salary left, player names, likely ownership, and common constructions.
- [29:12](https://www.youtube.com/watch?v=OTvIy-Jk96U&t=1752s) "because if you are entering a lineup That is duplicated a bunch of times that is massively minus EV and you can think about it and say look if I get first place and I split it 50 ways and I only get five grand instead of inste 200 Grand like whatever like I'm still happy with that sure"
  - Takeaway: The speaker says duplicated lineups can sharply reduce expected value by splitting first-place winnings among many entrants.

### High Level Showdown Strategy + Super Bowl Stuff with Cody Main and Colin Drew
Establish The Run · Feb 04, 2022 (0:55:18) · [Watch on YouTube](https://www.youtube.com/watch?v=i98ljRFANdA)

- [43:54](https://www.youtube.com/watch?v=i98ljRFANdA&t=2634s) "you basically have the product of the ownership of the individual players so whatever the captain projected ownership percent is and then the flex percent you know projected ownership percents for the other players multiply that together use some type of correlation coefficient"
  - Takeaway: Their duplication estimate starts with the product of projected ownerships for the captain and flex players, adjusted with a correlation coefficient.
- [45:41](https://www.youtube.com/watch?v=i98ljRFANdA&t=2741s) "there's a 0.55 r squared between product ownership and number of dupes which is really pretty strong when we're talking about just one single variable and a 0.26 r squared between total ownership and dupe"
  - Takeaway: Product ownership had an R-squared of 0.55 with lineup duplication, compared with 0.26 for total ownership.

### DFS Q&A: How Do You Filter NFL Lineups to Avoid Dupes While Staying +EV?
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 27, 2025 (0:19:42) · [Watch on YouTube](https://www.youtube.com/watch?v=wdjc-z_h8m4)

- [12:46](https://www.youtube.com/watch?v=wdjc-z_h8m4&t=766s) "I think there's effectively three ways to manage duplication in showdown. Number one is salary, right? You could lower your max salary, avoid playing lineups uh that more people are likely to play where they are max salary, leaving nothing on the table."
  - Takeaway: Lowering the maximum salary and leaving salary unused is presented as a way to reduce lineup duplication.
- [13:46](https://www.youtube.com/watch?v=wdjc-z_h8m4&t=826s) "another option would be using some type of ownership filter. Geometric mean comes to mind, right? a very good one. And if you want to learn more about like applying geometric mean, check out this tutorial."
  - Takeaway: The speaker recommends an ownership filter and specifically names geometric mean as an option for managing duplication.

### DFS Q&A: For the 20-Max and 150-Max contest do you use the same pool?
SaberSim DFS - Daily Fantasy Sports Strategy · May 25, 2024 (0:58:29) · [Watch on YouTube](https://www.youtube.com/watch?v=PRtm5_i9qqQ)

- [26:41](https://www.youtube.com/watch?v=PRtm5_i9qqQ&t=1601s) "The contest selection or contest Sim is taking into account duplication already right? We have a field of lineups um we say this is what you know we think the field is likely to play um and then we Sim each lineup in the contest Sim against that that pool see how it performs and that that expected field does have dupes in it"
  - Takeaway: Contest simulations account for duplication by simulating each lineup against an expected field that includes duplicated lineups.
- [29:44](https://www.youtube.com/watch?v=PRtm5_i9qqQ&t=1784s) "if we remove that we're at 150 and 186 if we add it back in we're at 162 and 119 so we didn't really go down too much here but what we did is we we're now playing a set of lups that's going to be even like less duped and is a little more um safe in its Roi"
  - Takeaway: Filtering out lineups projected to be duplicated reduced the available set while making the remaining lineups less duplicated and safer in projected ROI in this example.

### DFS Office Hours 10/5: Different build settings for different contests, impact of pool size on build
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 06, 2021 (1:17:26) · [Watch on YouTube](https://www.youtube.com/watch?v=7yKBIoYboE8)

- [43:16](https://www.youtube.com/watch?v=7yKBIoYboE8&t=2596s) "the product of these ownerships is going to kind of imply to you that the chance of this lineup being duplicated is way lower than it is then i line up with cole at captain"
  - Takeaway: The speaker uses the product of lineup ownerships as an indicator of relative duplication risk.

### How to Crush NFL Showdowns on Fanduel and Draftkings Using the DFS Army Domination Station Optimizer
DFS Army - Daily Fantasy Sports · Sep 08, 2020 (0:51:20) · [Watch on YouTube](https://www.youtube.com/watch?v=ehza4xs_VSc)

- [7:39](https://www.youtube.com/watch?v=ehza4xs_VSc&t=459s) "and we're dealing with a mass multi-entry tournament with 150 000 entrants we are talking about a tie of hundreds and hundreds of lineups so the optimizer wants to spend the full cap most of the time"
  - Takeaway: The speaker warns that full-cap lineups in a 150,000-entry tournament can tie with hundreds of other lineups.

### DFS Q&A: How Do Contest Sims Work for Small vs. Large-Field Contests?
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 12, 2023 (0:18:57) · [Watch on YouTube](https://www.youtube.com/watch?v=h9O1DRC4ABo)

- [12:39](https://www.youtube.com/watch?v=h9O1DRC4ABo&t=759s) "when we build your pool of lineups to start when a lineup comes up more than once we just tally that as Sim optimals we don't insert the lineup into your pool more than once for the ownership build we are actually doing that when the lineup comes up more than once we are letting the lineup stay in the pool and that is representing dupes"
  - Takeaway: The lineup pool counts repeated lineups as Sim optimals without inserting duplicates, while the ownership build retains repeated lineups to represent duplication.

### How to be Profitable Playing NFL DFS Showdown Slates
925 Sports · Sep 10, 2026 (0:19:55) · [Watch on YouTube](https://www.youtube.com/watch?v=kVhN3OfbEBs)

- [11:19](https://www.youtube.com/watch?v=kVhN3OfbEBs&t=679s) "If you try to get too chalky with your builds, guys, you are just going or too tight with your builds where you're just not really leaving that much salary on the table. You're just going to get duplicated a bunch with your lineup. So even if you do hit, it's not unique enough to really hit big."
  - Takeaway: The transcript says overly chalky builds that leave little salary unused are likely to be duplicated, limiting the payoff even when they hit.

### NFL DFS Strategy Masterclass: Game Theory, Stacking & How to Actually Win
Mayo Media Network · Sep 04, 2026 (1:09:42) · [Watch on YouTube](https://www.youtube.com/watch?v=oj36e7aIMHc)

- [35:39](https://www.youtube.com/watch?v=oj36e7aIMHc&t=2139s) "if someone's playing if 10 people out of 100, so 10% of the field is playing exactly the same three-man lineup and then building around it. And they're And nine of the 10 guys are taking the same guy and putting it with it. Although, you know, 10% doesn't sound super chalky. If you're playing in that tournament, that is super chalky."
  - Takeaway: A shared three-player core can make a lineup combination highly chalky in a particular contest even when only 10% of the field has that core.

### How To Use The Stokastic NFL DFS Contest Generator Tool | NFL DFS Contest Simulations
Stokastic DFS - Daily Fantasy Sports Advice · Sep 07, 2023 (0:06:38) · [Watch on YouTube](https://www.youtube.com/watch?v=QX-prNRoIuA)

- [4:00](https://www.youtube.com/watch?v=QX-prNRoIuA&t=240s) "that's where dupes are really important because this will be able to help you identify which lineups in large field tournaments are expected to be duped by the field and then you could try to avoid playing any sort of lineups that might be duped you know like 30 40 times or something like that for single game contests"
  - Takeaway: The tool flags single-game lineups expected to be duplicated by the field, with 30–40 duplicates given as an example to avoid.

### I Cracked the Code on NFL Showdown Lineups (Do This to Win)
DFS Army - Daily Fantasy Sports · Aug 03, 2026 (0:26:59) · [Watch on YouTube](https://www.youtube.com/watch?v=65HDqKemR88)

- [19:10](https://www.youtube.com/watch?v=65HDqKemR88&t=1150s) "The lower your total ownership of your lineup is, the fewer ties you're probably going to get into. And you can see here that we have bands under 140% total ownership. 33 wins. So about 10% of the time out of the 350 lineups that we looked at"
  - Takeaway: The transcript connects lower total lineup ownership with fewer ties and reports 33 wins in its under-140%-ownership band across 350 lineups.

### SaberSim's Unique Approach to Projecting Ownership
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 10, 2021 (1:28:00) · [Watch on YouTube](https://www.youtube.com/watch?v=zMdDPCaxXjg)

- [1:17:56](https://www.youtube.com/watch?v=zMdDPCaxXjg&t=4676s) "i think it's a good balance of not sacrificing too much raw expectation um while also lowering your chance of getting duplicated a fair bit at least it feels that way you can still build really chalky lineups at 49.5 but that's where i like to settle in"
  - Takeaway: The speaker favors a salary setting of 49.5 as a balance between raw expectation and reducing duplication, while noting that chalky lineups can still be built at that level.

### DFS Q&A: How Should You Handle NFL Late Swap Between Builds?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 21, 2025 (0:27:24) · [Watch on YouTube](https://www.youtube.com/watch?v=QJ4wmImXx5M)

- [23:29](https://www.youtube.com/watch?v=QJ4wmImXx5M&t=1409s) "You could test this on like today, uh, if you have some time, right? Run it, save it, submit it, and then see how many lineups kind of overlap there. That's that's like one way of doing it. Uh, but like there's no way to make sure you don't overlap across lineup builds."
  - Takeaway: To assess overlap between separate builds, test them and count overlapping lineups; the speaker says there is no way to guarantee no cross-build overlap.

### How to Win NFL DFS Tournaments in 2026
Establish The Run · Sep 06, 2026 (1:03:32) · [Watch on YouTube](https://www.youtube.com/watch?v=A-PD6sZhvvY)

- [49:53](https://www.youtube.com/watch?v=A-PD6sZhvvY&t=2993s) "like what we keep trying to hit home in the content that we provide our inseason subscribers is that you can play this like 45% owned running back that looks like a really strong play. It's just be aware of the combinations of players you're adding on to that very strong running back because you start to narrow your path a little bit more."
  - Takeaway: A 45%-owned running back can be played, but the combinations of players paired with him can narrow the lineup's path to winning.

### DRAFTKINGS & FANDUEL DFS STRATEGY REVIEW: PROJECTION VS OWNERSHIP EXPLOIT (1/4/23)
RotoGrinders - Daily Fantasy Sports Advice · Jan 04, 2023 (1:21:28) · [Watch on YouTube](https://www.youtube.com/watch?v=x2vfd9rf5S8)

- [14:07](https://www.youtube.com/watch?v=x2vfd9rf5S8&t=847s) "150 median points 150 ownership and we're using ownership sum which is not as not as as blunter than ownership product but they're both blunt okay so don't take this as gospel like what what oh this is 150 this is 149"
  - Takeaway: The speaker discusses ownership sum and ownership product as blunt measures rather than treating either as a precise duplication metric.

### NFL DFS Showdown Research - Results From 50 Winning Milli-Maker Lineups in 2021
Adam Newman · Sep 07, 2022 (0:12:30) · [Watch on YouTube](https://www.youtube.com/watch?v=HfQcvFwIECA)

- [7:45](https://www.youtube.com/watch?v=HfQcvFwIECA&t=465s) "these dupes are okay but it's still not like enough for me this one of them was over 100 or about 100"
  - Takeaway: The speaker observed that a winning lineup had more than 100, or about 100, duplicates.

### DFS Q&A: How do I navigate NFL late swap?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 09, 2022 (1:07:37) · [Watch on YouTube](https://www.youtube.com/watch?v=uvDTL8e6Ipo)

- [20:49](https://www.youtube.com/watch?v=uvDTL8e6Ipo&t=1249s) "there's literally hundreds of thousands of good showdown lineups you can build most people using traditional optimizers or building by hand will overweight the value of using all of their salary compared to how often that's optimal"
  - Takeaway: The speaker says using all available salary is often overvalued by traditional optimizers and recommends considering duplication when building showdown lineups.

### How to Build Winning NFL DFS Showdown Lineups on DraftKings & FanDuel (2024)
Occupy Fantasy · Oct 07, 2024 (1:22:41) · [Watch on YouTube](https://www.youtube.com/watch?v=W9FWB82PwNs)

- [50:10](https://www.youtube.com/watch?v=W9FWB82PwNs&t=3010s) "For cheat code quarterbacks like Lamar, Patrick Mahomes, this is when Mahomes was actually good at football. whether MVP percentages exceed 40%, use at most 585. These are based on duplications and historical results on FanDuel GPPS."
  - Takeaway: The transcript ties FanDuel salary limits for popular quarterback MVPs to duplication and historical results, with a stated 585 limit when MVP percentages exceed 40%.

### 2026 NFL DraftKings Strategy: Stop Making These Costly DFS Mistakes
Mayo Media Network · Aug 28, 2026 (1:05:48) · [Watch on YouTube](https://www.youtube.com/watch?v=SPjmh9bxUF4)

- [36:07](https://www.youtube.com/watch?v=SPjmh9bxUF4&t=2167s) "because there's people have you covered. If I have 150 lineups and you've got one, I've got like 10 lineups just like your one. It may not be. People are always worried about dupes. On a classic slate, we're not worried about that. What we're saying is you probably are boxed in instead of being able to get out of the box."
  - Takeaway: He argues that a one-lineup player can be covered by multiple similar entries in a 150-lineup portfolio, and frames the larger concern on classic slates as being boxed into common lineup choices rather than duplicate counts.

### Learn How Maximize SaberSim's New Contest Sims
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 24, 2023 (1:17:07) · [Watch on YouTube](https://www.youtube.com/watch?v=mZzskOQAz2k)

- [35:59](https://www.youtube.com/watch?v=mZzskOQAz2k&t=2159s) "sort by entry fee um and or I guess total entry fees like entry fee times number of entries you could sort by that and then fill from the most expensive to the cheapest like after you fill each one trash those fill the next one trash those and that would get you uh make sure that you're not duplicating any of your lineups across contests"
  - Takeaway: To avoid reusing lineups across contests, fill contests from most expensive to cheapest and remove each filled set before moving on.

### How To Use The Stokastic NFL DFS Pre-Contest Sims Tool | NFL DFS Contest Simulations
Stokastic DFS - Daily Fantasy Sports Advice · Sep 07, 2023 (0:10:35) · [Watch on YouTube](https://www.youtube.com/watch?v=4PFRCiUGPec)

- [4:49](https://www.youtube.com/watch?v=4PFRCiUGPec&t=289s) "however for something like Showdown on DraftKings or single game contests The dupes do come in and play a really large portion and it's something that definitely impacts your Roi if you have a lineup that say is duped you know 40 times as opposed to a lineup That is not duped at all that's going to impact what the payout is expected to be"
  - Takeaway: The transcript says duplication is more consequential in DraftKings Showdown and single-game contests, and a lineup duplicated 40 times can have a different expected payout from an unduplicated lineup.

### Lions vs Panthers - SNF Sunday Sweatdown | NFL Week 4 | DFS Picks, Plays & Process
Ship It Nation · Oct 05, 2026 (1:05:29) · [Watch on YouTube](https://www.youtube.com/watch?v=xJlvummhIfI)

- [47:16](https://www.youtube.com/watch?v=xJlvummhIfI&t=2836s) "Sam Leaporta drop down to Fitzgerald, leave the leave the $2,200. I mean, you just cut your dupes big time. Something something like that."
  - Takeaway: The speaker suggested leaving $2,200 in salary as a way to reduce duplicated lineups.

## 3. 150-max portfolio construction

51 videos, 97 transcript excerpts.


### How to Use PortfolioIQ for Portfolio Management
DFS Hero · Aug 05, 2025 (0:15:01) · [Watch on YouTube](https://www.youtube.com/watch?v=A06udLfR1Oc)

- [2:57](https://www.youtube.com/watch?v=A06udLfR1Oc&t=177s) "Portfolio IQ simply tries to diversify your portfolio. So your 20 or 150 or whatever lineups you need to choose from the total amount. It does so by decorrelating your lineups from each other."
  - Takeaway: PortfolioIQ is intended to diversify pools of 20, 150, or other numbers of lineups by reducing correlation among them.
- [3:44](https://www.youtube.com/watch?v=A06udLfR1Oc&t=224s) "Portfolio IQ analyzes all of your lineups and finds like that perfect combination of of of lineups that work together as a team. So, it looks at like what players appear in which lineups. Um, and it tries to shuffle those combinations to give you a good spread that considers both upside and protection."
  - Takeaway: The tool considers which players appear in which lineups and combines lineups to balance upside and protection.
- [4:22](https://www.youtube.com/watch?v=A06udLfR1Oc&t=262s) "it is by default choosing lineups of worse quality to account for the the the the the decorrelation or account for the variance that exists. um within the sport or or the contest, let's say."
  - Takeaway: Portfolio construction may select lower-quality individual lineups to reduce correlation and account for variance.
- [7:00](https://www.youtube.com/watch?v=A06udLfR1Oc&t=420s) "Clicking portfolio IQ gives you three different strategies. The first strategy is it's optimized for the contest. Second, the second is steady and the third is max win. Contest optimize essentially tries to create the perfect balance between upside and protection."
  - Takeaway: PortfolioIQ offers Contest Optimized, Steady, and Max Win strategies, with Contest Optimized balancing upside and protection.
- [7:43](https://www.youtube.com/watch?v=A06udLfR1Oc&t=463s) "steady is spread it out as much as possible, decorrelate as much as possible, I want, you know, a very wide gamut of players so I have a lot of protection."
  - Takeaway: The Steady strategy seeks a wide range of players and maximum decorrelation for protection.
- [10:13](https://www.youtube.com/watch?v=A06udLfR1Oc&t=613s) "Once it's done, you see kind of this view here that shows you what your top 20 ranked lineups were, what was the projection, what was the average ROI, and what was the risk adjusted ROI. You then see your optimized portfolio, which is the 20 that would be selected if you hit apply optimized portfolio."
  - Takeaway: The results view compares the top 20 ranked lineups' projection, average ROI, and risk-adjusted ROI with the 20 lineups selected for the optimized portfolio.
- [10:38](https://www.youtube.com/watch?v=A06udLfR1Oc&t=638s) "you sacrifice projection, you sacrifice ROI, and you sacrifice, you know, riskadjusted ROI, but you've decreased your correlation, you've decorrelated 66%. And you're now 61% diversified."
  - Takeaway: In the demonstrated optimization, projection and ROI were traded off for 66% decorrelation and 61% diversification.
- [11:23](https://www.youtube.com/watch?v=A06udLfR1Oc&t=683s) "So, for example, um Tyler O'Neal went from 70% to 40%, you can see the difference here at the bottom. So, in minus30, - 255 minus 40 for Westber. So, from 80% owned, he went down to 40% owned."
  - Takeaway: The example shows player exposures changing from 70% to 40% for Tyler O'Neal and from 80% to 40% for Westber.
- [12:40](https://www.youtube.com/watch?v=A06udLfR1Oc&t=760s) "So the whole purpose of this is again not chasing the winner per se, but more so setting up your portfolio in a way that um maximizes the performance of the to of the lineups in their totality versus one specific lineup."
  - Takeaway: The stated objective is to maximize the performance of the lineup portfolio as a whole rather than focus on one lineup.

### DFS Portfolio Diversification: Build Smarter Lineups with Efficient Frontier Strategy
Compounding Edges · Jul 21, 2025 (0:03:49) · [Watch on YouTube](https://www.youtube.com/watch?v=sJNfa7WuAL8)

- [0:30](https://www.youtube.com/watch?v=sJNfa7WuAL8&t=30s) "So we need to always use a simulating step prior to using a diversification step. It doesn't have to be used immediately prior. I'm just choosing to use it in this case immediately prior, but you can add steps before and after and around."
  - Takeaway: A recipe must include a simulating step before diversification, but the two steps do not need to be adjacent.
- [1:01](https://www.youtube.com/watch?v=sJNfa7WuAL8&t=61s) "From this, I'm going to only choose the top 150 lineups. But for now, let's talk about what the efficient frontier is."
  - Takeaway: The demonstrated portfolio-diversification workflow selects the top 150 lineups.
- [1:39](https://www.youtube.com/watch?v=sJNfa7WuAL8&t=99s) "So in finance, it's pretty obvious what's going on with your stocks there. However, in DFS, we measure risk a little bit differently. And the risk in DFS is that your lineups are basically moving the same direction. So when one finish is good, most of them finish good."
  - Takeaway: The video describes DFS risk as lineups moving in the same direction and often finishing well or poorly together.
- [2:12](https://www.youtube.com/watch?v=sJNfa7WuAL8&t=132s) "So that's what this efficient frontier does. It says, "Hey, I want the lineups out of this cloud that move in the most opposite directions.""
  - Takeaway: The efficient-frontier strategy selects lineups from the cloud that move in the most opposite directions.
- [2:53](https://www.youtube.com/watch?v=sJNfa7WuAL8&t=173s) "But you can see that there's a good amount of diversification in the lineups that are being selected from both a team perspective and a stack perspective, which is good."
  - Takeaway: The selected lineups show diversification by both team and stack.

### NFL DFS Week 1 DraftKings Strategy And Picks  Run The Sims With A Milly Maker Winner
Neil Orfield · Sep 12, 2026 (0:28:11) · [Watch on YouTube](https://www.youtube.com/watch?v=MhwZlTi-eJw)

- [1:23](https://www.youtube.com/watch?v=MhwZlTi-eJw&t=83s) "So, I use large lineup set. I'm going to do uh 5,000 lineups, which is the maximum. I'm going to use the Shady Portfolio Optimizer. This is an add-on that comes from Shady Advice. He's one of the best DFS players in the world. This is a portfolio optimization tool."
  - Takeaway: He generates a large lineup set and uses the Shady Portfolio Optimizer as a portfolio optimization tool.
- [1:38](https://www.youtube.com/watch?v=MhwZlTi-eJw&t=98s) "And I'm going to do 150 lineups. I'll use risk zero in the shady portfolio optimizer. That is the recommended setting. Uh I'll do $10 to $25 entry fee and a field size of 15,000 with a topheavy payout structure."
  - Takeaway: His portfolio setup uses 150 lineups, risk zero, a 15,000-entry field, and a top-heavy payout structure.
- [3:23](https://www.youtube.com/watch?v=MhwZlTi-eJw&t=203s) "Interestingly, we don't see any quarterbacks repeat in the first eight lineups here. The first repeat we have is Josh Allen as the ninth quarterback. So, we are getting a pretty diversified set of lineups today."
  - Takeaway: He describes the lack of repeated quarterbacks among the first eight simulated lineups as lineup diversification.
- [3:47](https://www.youtube.com/watch?v=MhwZlTi-eJw&t=227s) "Looking at my top exposures, you can see my exposure in the shady exposure column on the far right. That'll be the top 150 lineups with the shady portfolio optimizer tool. This is how often I'm getting players."
  - Takeaway: He evaluates player exposure by how often each player appears in the top 150 optimized lineups.
- [26:36](https://www.youtube.com/watch?v=MhwZlTi-eJw&t=1596s) "Normally I would continue going until I have lineups that look the way I want, exposures that look the way I want. Um, I'm not going to do that over and over, but it would be it's kind of an incremental process. So, you saw the first adjustment I made."
  - Takeaway: His portfolio-adjustment process is incremental, with repeated runs until lineups and exposures meet his preferences.

### DFS Army's Strategy Series MME Podcast   50 is the New 150
DFS Army - Daily Fantasy Sports · Jun 04, 2020 (0:18:56) · [Watch on YouTube](https://www.youtube.com/watch?v=CPsg0CX4_eU)

- [8:37](https://www.youtube.com/watch?v=CPsg0CX4_eU&t=517s) "the 50 lineups lets you do a few things first off you're not putting as much money in so psychologically you have maybe an advantage or to yourself of maybe going heavy on a certain guy instead of having you know say this say a tournament's ten dollars and it's fifteen hundred dollars fifteen hundred dollars is a bunch of money i don't care how big your bankroll is but five hundred dollars is a little bit easier to swallow"
  - Takeaway: The speaker says entering 50 rather than 150 lineups reduces the amount invested and makes heavier exposure to a particular player psychologically easier.
- [9:11](https://www.youtube.com/watch?v=CPsg0CX4_eU&t=551s) "i'm going to go 80 to 100 on these two guys because i really think they're in great spots and even though the payout structure is really bad since i'm going so heavy on these on these individuals or players that i'm investing my money on i'm either having to have a really really good night or really really bad night"
  - Takeaway: The speaker describes putting 80–100 lineups on each of two players as a concentrated approach that can produce especially good or bad results.
- [11:18](https://www.youtube.com/watch?v=CPsg0CX4_eU&t=678s) "in these 150 max contests with how top heavy they are is around that 30 to 60 um lineups i kind of like 50 i like being a little on the head on on the top end of that because i kind of want more but 30 makes perfect sense you know if you want to go up a little more in 60"
  - Takeaway: The speaker identifies 30–60 entries, with a preference for about 50, as the lineup-count range he sees as a sweet spot in top-heavy 150-max contests.
- [17:30](https://www.youtube.com/watch?v=CPsg0CX4_eU&t=1050s) "you know maybe not as aggressively as some guys at the 80 to 100 mark on a few guys maybe they're at that 70 mark i think that's the lowest i would go on your core say four guys in a in a contest but also you know when you're wrong wrong when you go that heavy as well it hurts a lot more when you've got 150 lives invested than say 50."
  - Takeaway: When playing 150 lineups, the speaker describes a core of four players with exposure as high as 70–100 lineups, while noting that heavy exposure hurts more when those picks are wrong.

### DFS Q&A: How Does the Portfolio Diversifier Work?
SaberSim DFS - Daily Fantasy Sports Strategy · Mar 19, 2026 (0:25:25) · [Watch on YouTube](https://www.youtube.com/watch?v=iM5sS24JCSc)

- [15:08](https://www.youtube.com/watch?v=iM5sS24JCSc&t=908s) "So, I think it's okay to set some of these uh filters and and rules to kind of protect yourself when you know you're looking at 150 lineups or more. You know, it does get hard to be granular with every micro decision in your lineups."
  - Takeaway: The speaker suggests safeguards such as filters and rules when managing 150 or more lineups because handling every micro-decision can be difficult.
- [22:04](https://www.youtube.com/watch?v=iM5sS24JCSc&t=1324s) "This is the uh this is the difference between sorting uniques one versus sorting portfolio is that portfolio is making more decisions based on how the lineups play together rather than just giving you highest saber score to lowest saber score."
  - Takeaway: Portfolio sorting considers how lineups complement one another instead of simply ranking them by raw Saber Score.
- [24:05](https://www.youtube.com/watch?v=iM5sS24JCSc&t=1445s) "The portfolio diversifier says, "Hey, you know, we now have to meet this 50% exposure request while still picking and selecting the best lineups that fit together." And then it thinks it re chooses the lineups. And now I have the 50 the 50% gaffer is now being met."
  - Takeaway: After a 50% exposure cap is requested, the portfolio diversifier reselects lineups while still trying to choose lineups that fit together.

### DRAFTKINGS & FANDUEL DFS STRATEGY REVIEW: PROJECTION VS OWNERSHIP EXPLOIT (1/4/23)
RotoGrinders - Daily Fantasy Sports Advice · Jan 04, 2023 (1:21:28) · [Watch on YouTube](https://www.youtube.com/watch?v=x2vfd9rf5S8)

- [1:08:52](https://www.youtube.com/watch?v=x2vfd9rf5S8&t=4132s) "then from there you're like okay now what is my diversification based on my bankroll and my allocation like how much risk do I want to take on on this late in comparison to other slates then at the end of the day it's a financial need"
  - Takeaway: The speaker frames diversification and risk allocation in relation to bankroll and other slates.
- [1:11:39](https://www.youtube.com/watch?v=x2vfd9rf5S8&t=4299s) "you could create 300 lineups at a time in lineup HQ and import like 10 sets of them like I have 3 000 lineups and then go I want to trim based on this I want to trim based on that"
  - Takeaway: The speaker describes building and trimming a large lineup set using multiple criteria as a portfolio workflow.
- [1:12:04](https://www.youtube.com/watch?v=x2vfd9rf5S8&t=4324s) "depending on how many lines it may take one two three four done three thousand lineups turn into like 57 lineups and it's just like only the lineups that have a higher projection versus the ownership like there you go and then it'll even show you like the exposures of those 57 lineups like who's in who's in those lineups the most"
  - Takeaway: The portfolio trimmer can reduce 3,000 lineups to 57 based on projection versus ownership and show player exposures.

### DFS Q&A: How Do You Filter NFL Lineups to Avoid Dupes While Staying +EV?
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 27, 2025 (0:19:42) · [Watch on YouTube](https://www.youtube.com/watch?v=wdjc-z_h8m4)

- [10:00](https://www.youtube.com/watch?v=wdjc-z_h8m4&t=600s) "I think it makes more and more sense to turn this off. If if you're playing like 50 entries or less, then okay, yeah, you know, uh leave it on. But when you get into hundreds and hundreds of lineups, I think it's okay to turn off."
  - Takeaway: For the avoid-duplicates-across-lineup-groups setting, the speaker suggests leaving it on at 50 entries or fewer and considers turning it off for hundreds of lineups.
- [10:21](https://www.youtube.com/watch?v=wdjc-z_h8m4&t=621s) "what I did here was I did different groups. I grouped like all of my winter take alls together and then I grouped all of the satellites together and then I even grouped like all of the dime times together. Um all of the boosters, right?"
  - Takeaway: The speaker groups similar contest types together, including satellites, rather than grouping every contest individually.
- [10:35](https://www.youtube.com/watch?v=wdjc-z_h8m4&t=635s) "I think that you can I don't I don't think you need an individual group for all of your contests and I think that you can uh group them and then allow duplicates and then that shouldn't hinder anything between your groups, right? Like I don't think anything is occurring at any contest's expense"
  - Takeaway: The speaker says similar contests can be grouped together with duplicates allowed across lineup groups without harming the other contests.

### DFS Q&A: For the 20-Max and 150-Max contest do you use the same pool?
SaberSim DFS - Daily Fantasy Sports Strategy · May 25, 2024 (0:58:29) · [Watch on YouTube](https://www.youtube.com/watch?v=PRtm5_i9qqQ)

- [21:25](https://www.youtube.com/watch?v=PRtm5_i9qqQ&t=1285s) "that is also Al a good argument for why spreading out your entries into as spreading out your lineups into as many entries as possible and following the profit plan is such a good idea right you give yourself more exposure to your entire pool each slate you play and give yourself more opportunities of of just getting any given lineup into your entries file"
  - Takeaway: Spreading lineups across as many entries as possible increases exposure to the lineup pool and the chance of entering any particular lineup.
- [35:28](https://www.youtube.com/watch?v=PRtm5_i9qqQ&t=2128s) "for me personally like I I I would generally be building my entire portfolio in one pool and then running the contest Sims for my different contests and filling those into there"
  - Takeaway: His general approach is to build one portfolio pool, run contest simulations for the different contests, and fill lineups from those results.
- [44:12](https://www.youtube.com/watch?v=PRtm5_i9qqQ&t=2652s) "back to the team Stacks this looks a little bit more like what I'm expecting most of the time I like to see a soft curve here of my team stack exposures I like to be really Diversified really spread out across my pool uh if there's a team that is really popping in my stack exposure I like there to be a pretty compelling reason for it"
  - Takeaway: For a 150-lineup portfolio, he prefers diversified, broadly spread team-stack exposures and wants a compelling reason for any unusually high exposure.

### Beat DFS Using The SaberSystem: 5 Principles for Maximum Profitability
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 29, 2024 (0:16:28) · [Watch on YouTube](https://www.youtube.com/watch?v=4jONT961JrM)

- [3:20](https://www.youtube.com/watch?v=4jONT961JrM&t=200s) "the overall action that you play in DFS is essentially an Investment Portfolio and there are two real levers that we can pull to affect that portfolio in a way that reduces our variance and puts real money in our pockets sooner"
  - Takeaway: The transcript frames all DFS entries across contests, slates, sports, and days as an investment portfolio whose variance can be managed.
- [6:31](https://www.youtube.com/watch?v=4jONT961JrM&t=391s) "be focusing on intentionally playing lineups that are different from one another by putting all of these different unique lineups in play our goal is to give ourselves as many unique shots on goal as possible but playing 150 lineups that are all very similar to each other does not have that impact"
  - Takeaway: Portfolio lineups should be intentionally diversified; 150 similar lineups do not provide as many distinct chances.
- [6:42](https://www.youtube.com/watch?v=4jONT961JrM&t=402s) "avoid heavily restricting your player pool overexposing yourself to core or top plays and diversify using tools like Min uniques to make your lineups different from each other"
  - Takeaway: The transcript advises against overly restrictive player pools and excessive exposure to core plays, and recommends Min uniques to diversify lineups.

### DFS Q&A: How Do You Use Geomean to Reduce Dupes in NFL Showdown?
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 12, 2025 (0:19:45) · [Watch on YouTube](https://www.youtube.com/watch?v=UTQzHyEzDEw)

- [4:06](https://www.youtube.com/watch?v=UTQzHyEzDEw&t=246s) "The idea is that DFS is a very high variance game already. Uh, it is more high variance than sports betting, then no limit Texas holdem, then pot limit Omaha. And there's already enough variance that you don't need to add more by putting the same lineup in all of your contests because effectively all your result all your results are correlated."
  - Takeaway: The speaker recommends avoiding the added variance and correlated results that come from entering the same lineup in multiple contests.
- [4:30](https://www.youtube.com/watch?v=UTQzHyEzDEw&t=270s) "when you put 600 unique lineups into 600 entries, you are effectively spreading out your risk by doing so, right? Uh more lineups, more opportunities to be correct, and that should help to smooth out some of your results on a night-to-ight basis."
  - Takeaway: Using a unique lineup for each entry is described as spreading risk and smoothing results.
- [9:21](https://www.youtube.com/watch?v=UTQzHyEzDEw&t=561s) "The toggle on will give you a true unique lineup for each entry. The toggle off allows lineups to be reused, but it is not forcing it whatsoever because remember each ROI for each contest sim is effectively a separate sorting metric."
  - Takeaway: The cross-group duplicate toggle controls whether lineups must be unique or may be reused across contest groups.

### How to Crush NFL Showdowns on Fanduel and Draftkings Using the DFS Army Domination Station Optimizer
DFS Army - Daily Fantasy Sports · Sep 08, 2020 (0:51:20) · [Watch on YouTube](https://www.youtube.com/watch?v=ehza4xs_VSc)

- [10:04](https://www.youtube.com/watch?v=ehza4xs_VSc&t=604s) "if you put in one unique your distribution of lineups is going to be a lot tighter so if you're on the right core that's going to work out really well most of the time if you use two uniques you're going to get a little bit more spread exposures across all the different players in your pool"
  - Takeaway: The speaker says one unique produces a tighter lineup distribution, while two uniques spread exposure across more players.
- [36:26](https://www.youtube.com/watch?v=ehza4xs_VSc&t=2186s) "in the mvp spot we control our exposures using min exposure that's forced minimum exposure that forces the tool to put the player into uh the the mvp spot we can control exactly the exposures using the forced minimum in the flex we are controlling our exposures and controlling for exposures primarily using max exposure limits"
  - Takeaway: The speaker uses minimum exposure to force MVP selections and primarily maximum exposure limits to control FLEX exposure.

### NFL DFS Sims Tournament Strategy Week 1 | NFL DFS Strategy
Stokastic DFS - Daily Fantasy Sports Advice · Sep 11, 2026 (1:11:45) · [Watch on YouTube](https://www.youtube.com/watch?v=uMa9MQhf0fU)

- [20:56](https://www.youtube.com/watch?v=uMa9MQhf0fU&t=1256s) "And the Sims right now, they like Ashton Genty. getting we're getting 30% of it. We're almost 2x the field on Ashton Genty. We're over the field on Devon Chan."
  - Takeaway: He describes portfolio exposures in relation to projected field ownership, including being nearly twice the field on Ashton Genty.
- [51:31](https://www.youtube.com/watch?v=uMa9MQhf0fU&t=3091s) "It doesn't mean that I don't want to get to any of Tucker, but I would rather just spread out exposures there. Instead of having 26 lineups that have both Tucker and Mayor, I would rather have like 13 and 13 of mayor and Naylor and Mayor and Tucker."
  - Takeaway: He favors diversifying lineup exposures across Tucker-and-Mayer and Naylor-and-Mayer combinations rather than using the same pair in all 26 lineups.

### DFS Q&A: How Do Contest Sims Work for Small vs. Large-Field Contests?
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 12, 2023 (0:18:57) · [Watch on YouTube](https://www.youtube.com/watch?v=h9O1DRC4ABo)

- [6:17](https://www.youtube.com/watch?v=h9O1DRC4ABo&t=377s) "by itself are just too risky for my risk tolerance I'm I'm coming in here and I am adding value to my own process by managing my own risk right and different people have different risk tolerances so the amount of adjustments that you make is going to depend on the type of player you are"
  - Takeaway: Andrew recommends managing lineup risk according to personal risk tolerance rather than accepting the tool’s exposures without review.
- [7:07](https://www.youtube.com/watch?v=h9O1DRC4ABo&t=427s) "that's why we build you a big pool you know you build you need 20 lineups we'll build you 500 we'll build you we'll build you 5,000 we're trying to give you optionality to make those Game Theory decisions to make those risk adjustment decisions after the lineups are built"
  - Takeaway: He describes building a large lineup pool to provide options for post-build game-theory and risk adjustments.

### DFS Q&A: What is a self-sim?
SaberSim DFS - Daily Fantasy Sports Strategy · Jul 11, 2024 (0:56:19) · [Watch on YouTube](https://www.youtube.com/watch?v=JjEqfaORNpA)

- [8:16](https://www.youtube.com/watch?v=JjEqfaORNpA&t=496s) "what I would tend to do is is set this filter I like actually using the selfsim as my fin sorting method and I'll explain why in a second and then diversifying with Min uniques is generally my final step so I will find my Max Min uniques point which is five and then go one less than the Max and go to four now this is very similar to a lineup portfolio that I would probably play on this slate"
  - Takeaway: The described portfolio process sorts using the self-sim, then diversifies with minimum uniques set one below the maximum, using five as the maximum and four as the selected setting.
- [13:43](https://www.youtube.com/watch?v=JjEqfaORNpA&t=823s) "when we go to the real Sim or the self Sim sorry they kind of fall down and instead we're going to say and we're going to get 18% we're about going to match how often they show up in our pool we're going to focus on really the three teams that have the highest run totals as the biggest portion of our portfolio right we're like we're basically getting exposure to the best projected teams and we're playing a pretty balanced way that way"
  - Takeaway: In this example, the speaker describes getting about 18% exposure to a team and building a balanced portfolio around the three teams with the highest run totals.

### The 3 Rules for Beating NFL Showdown and Single Game GPPs
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 09, 2021 (1:11:46) · [Watch on YouTube](https://www.youtube.com/watch?v=7T2VrpJIN1M)

- [25:54](https://www.youtube.com/watch?v=7T2VrpJIN1M&t=1554s) "you don't want to just um fall into the trap of putting all of your your lineups behind something that's not going to happen 100 of the time and so this is really why it is so important to put in so many lineups into your contest you don't want to just be putting in five lineups in your shirt on slate"
  - Takeaway: They advise entering multiple lineups to cover different possible game outcomes rather than concentrating the portfolio on one script.
- [36:34](https://www.youtube.com/watch?v=7T2VrpJIN1M&t=2194s) "i think honestly if people are following our advice here you probably should be building at least 150 lineups like i think i probably put in uh probably around that like on the miss on the show on slate like you're gonna be putting in a lot of lineups and like yeah you do want to do some manual oversight of them"
  - Takeaway: They recommend building at least 150 lineups when following their approach, with some manual review.

### DFS Q&A: Walking Through the NFL Late Swap Process
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 26, 2025 (0:24:26) · [Watch on YouTube](https://www.youtube.com/watch?v=CgfglAjd2ys)

- [13:51](https://www.youtube.com/watch?v=CgfglAjd2ys&t=831s) "have 10% hertz. Uh, you know, let's let's crank this up, right? Let's do like 150 lineups. We're going to rediversify. All right. So, we're still getting 10% hertz, right? 15 lineups. Okay. But now what I can do is I can click the magnifying glass on him. the exposures are going to update,"
  - Takeaway: The demonstration maintains 10% minimum exposure to Hertz in a 150-lineup set and uses the player filter to inspect exposures.
- [16:19](https://www.youtube.com/watch?v=CgfglAjd2ys&t=979s) "So we went from like 94% Herz and Brown down to 73%. Right? So we've we've lost three lineups with that duo. And then you can effectively just keep doing this until you find the number you want."
  - Takeaway: The demonstrated way to adjust a player-pair combination is to remove lineups with the duo and repeat the process until its exposure reaches the desired level.

### HOW TO WIN ON DRAFTKINGS NFL SHOWDOWN: LINEUP BUILDING TIPS
Alvin Zeidenfeld · Sep 03, 2019 (0:14:55) · [Watch on YouTube](https://www.youtube.com/watch?v=lyaKCYf1LrQ)

- [10:00](https://www.youtube.com/watch?v=lyaKCYf1LrQ&t=600s) "I start with the captains so I want to make sure I create groups for anybody that I'm possibly gonna use as a captain so that's where the majority of the groups come from I would say and and then kind of beyond that I'll make groups to try to restrict situations where I think guys might be competing for playing time"
  - Takeaway: The speaker builds optimizer groups around possible captains, then adds groups to restrict combinations of players who may compete for playing time.
- [11:20](https://www.youtube.com/watch?v=lyaKCYf1LrQ&t=680s) "they still win and you can start exposures though you can you can make them lower instead of having like 30% of your captain lineups be a quarterback you said under like five or ten and it's just it's a matter of risk to like are you okay completely blanking the slate if Aaron Rodgers throws three touchdowns like I might be okay with that"
  - Takeaway: Captain exposure can be reduced—for example, from 30% quarterback captains to under 5% or 10%—depending on the player's tolerance for risk.

### How To Use The Stokastic NFL DFS Contest Generator Tool | NFL DFS Contest Simulations
Stokastic DFS - Daily Fantasy Sports Advice · Sep 07, 2023 (0:06:38) · [Watch on YouTube](https://www.youtube.com/watch?v=QX-prNRoIuA)

- [2:01](https://www.youtube.com/watch?v=QX-prNRoIuA&t=121s) "the pool exposure which is of those 10 000 lineups how much of this player did you get exposure to of those ten thousand and this is the difference the difference between the exposure you have and the ownership now let's say you want to get more or less of a player"
  - Takeaway: Pool exposure measures how often a player appears across the 10,000 generated lineups and is compared with that player's projected ownership.
- [2:54](https://www.youtube.com/watch?v=QX-prNRoIuA&t=174s) "the stacks so this is going to show of the pool you built how many of them are exposures to different sort of Stack types so if you set in the stack exposures you are going to have to do whatever number you want like talking before and then hit apply"
  - Takeaway: The tool displays the lineup pool's exposure to different stack types and lets users set stack exposure targets.

### DFS Q&A: How Should You Handle NFL Late Swap Between Builds?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 21, 2025 (0:27:24) · [Watch on YouTube](https://www.youtube.com/watch?v=QJ4wmImXx5M)

- [12:47](https://www.youtube.com/watch?v=QJ4wmImXx5M&t=767s) "Let's say we're building, you know, 150 lineups for a Sunday. Let's say we want to use portfolio diversifier, which is what we recommend."
  - Takeaway: The speaker recommends using the portfolio diversifier when building a 150-lineup set.
- [21:41](https://www.youtube.com/watch?v=QJ4wmImXx5M&t=1301s) "So everything I I always look at before I submit my lineups. I always come in here and sort by this leverage column. Right. I want to see what players I have positive leverage on. You know these are players I'm going to be taking a stand for. Right? I have more exposure to them in my set of lineups than the field does."
  - Takeaway: Before submitting, the speaker reviews leverage and identifies players with greater lineup exposure than the field.

### Studying the Sharps: Constructing DFS Lineups with Jordan Cooper
DraftKings · Oct 05, 2021 (1:24:55) · [Watch on YouTube](https://www.youtube.com/watch?v=1qKHG9mSEfI)

- [12:12](https://www.youtube.com/watch?v=1qKHG9mSEfI&t=732s) "that doesn't mean you have to have all these exposures to all these different players and you play 20 lives or 150 lineups and you have like a bit of everything so that you make sure you're diversified your method for diversification is you just do the best thing each day and you diversify across the year where you play each each asset quote-unquote is a different day of the season"
  - Takeaway: Cooper describes diversifying across the season rather than spreading exposures across players in a 20- or 150-lineup portfolio.
- [21:22](https://www.youtube.com/watch?v=1qKHG9mSEfI&t=1282s) "so in your dalvin cook lineups it maybe make more sense to play a bengal on the other side you play t you play burrow and higgins so you're capitalizing your whole lineup on a certain outcome but in other lineups to diversify you're taking the negative you're not taking the fact that the vikings are not going to win you're just saying that the production is going to go in a different way if dalvin cook fails who benefits from that"
  - Takeaway: The example builds different lineups around alternate production outcomes, including pairing Dalvin Cook lineups with Bengals and diversifying with lineups that benefit if Cook fails.

### I Gave the DFS Army Optimizer the SHOWDOWN CODE… Here’s What It Built!
Ibe's DFS Sports Betting · Oct 01, 2026 (0:11:51) · [Watch on YouTube](https://www.youtube.com/watch?v=sBOEt7d3dM4)

- [1:49](https://www.youtube.com/watch?v=sBOEt7d3dM4&t=109s) "I have everything set up already. I'm just ready to run my lineups. I'm going to be running 165 lineups. Let me go ahead and click that. And so, right now, it's going to be running 165 lineups. I'm going to be picking 150 of them."
  - Takeaway: He generates 165 lineups and says he will choose 150 from them.
- [4:17](https://www.youtube.com/watch?v=sBOEt7d3dM4&t=257s) "And this one does not have Aaron Rogers in it. The only Steelers player it has is Jaylen Warren along with Danzel Boston, Harold Fannon Jr., KC Conception and Jerry Judy. This would be one of them lineups you play if you think that Cleveland's going to win the game pretty much."
  - Takeaway: He interprets one lineup as a Cleveland-win game script, with Jaylen Warren as its only Steelers player.

### DFS Office Hours 7/29/21: Why avoiding duplication is important in DFS
SaberSim DFS - Daily Fantasy Sports Strategy · Jul 30, 2021 (0:27:16) · [Watch on YouTube](https://www.youtube.com/watch?v=U13Q_op4i-g)

- [15:32](https://www.youtube.com/watch?v=U13Q_op4i-g&t=932s) "to build this all as 150 lineups do a single lineup build at 150 i typically use settings that match what the 150 max looks like and then i build everything in one 150 build i do all of my work in that build and then i fill using the ranked fill method"
  - Takeaway: He combines his contests into one 150-lineup build using settings for the 150-max contest, then fills entries using the ranked-fill method.
- [17:13](https://www.youtube.com/watch?v=U13Q_op4i-g&t=1033s) "the only slider i typically am likely to touch here is smart diversity i typically turn it up i use it a little bit higher so almost as kind of a counter balance to that"
  - Takeaway: He typically increases the smart-diversity setting as a counterbalance to his other build choices.

### Learn How Maximize SaberSim's New Contest Sims
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 24, 2023 (1:17:07) · [Watch on YouTube](https://www.youtube.com/watch?v=mZzskOQAz2k)

- [25:50](https://www.youtube.com/watch?v=mZzskOQAz2k&t=1550s) "have insane variants around that but you're always going to have a lot of variance no matter what you put in um and that's where mme really uh is helpful is by giving more shots on goal and finding uncorrelated lineups or less correlated lineups uh using them in uniques so that you can still put in"
  - Takeaway: The speakers recommend using MME and uniques to get more shots on goal and reduce lineup correlation.
- [36:19](https://www.youtube.com/watch?v=mZzskOQAz2k&t=2179s) "the more different the contests are in terms of size and stakes and payout structures the less the lineups that are good in one contest are likely to resemble the lineups that are good in another contest so you can kind of group line up contests that are similar into one contest Sim setting bucket and then simulate those lineups against that contest"
  - Takeaway: Group similar contests by size, stakes, and payout structure because their best lineups are more likely to resemble one another.

### How To Use The Stokastic NFL DFS Pre-Contest Sims Tool | NFL DFS Contest Simulations
Stokastic DFS - Daily Fantasy Sports Advice · Sep 07, 2023 (0:10:35) · [Watch on YouTube](https://www.youtube.com/watch?v=4PFRCiUGPec)

- [6:57](https://www.youtube.com/watch?v=4PFRCiUGPec&t=417s) "and you could also do stack boost change so let's say you just want more exposure to the Tampa Bay Buccaneers offense as a whole you could go in here and manually change their entire stack boost up as much as you want or decrease it as much as you want so that will change the amount of stacks you're getting of that team"
  - Takeaway: The tool lets users increase or decrease a team's stack boost to change their exposure to that team's stacks.
- [9:03](https://www.youtube.com/watch?v=4PFRCiUGPec&t=543s) "in this build we have the most of Chris Godwin he was in 27.3 percent of lineups you can see his projected fantasy points here as well as a simulated Roi the ownership projection on him as well as the leverage so the Leverage is going to be the difference between the projected ownership and then the amount of him you have in your lineup"
  - Takeaway: The exposure view shows player exposure, projected ownership, and leverage, which the transcript defines as the difference between projected ownership and the amount of the player in your lineups.

### DRAFTKINGS & FANDUEL DFS STRATEGY REVIEW: Large-Field GPP Lineup Simulations (1/18/23)
RotoGrinders - Daily Fantasy Sports Advice · Jan 18, 2023 (1:00:36) · [Watch on YouTube](https://www.youtube.com/watch?v=pakvRcKsnXQ)

- [42:54](https://www.youtube.com/watch?v=pakvRcKsnXQ&t=2574s) "I'll go 150 to 160 give me 300. then I'll go 140 to 150 give me 300. 130 to 140 give me 300 like you could do that and slices and he could also choose to place"
  - Takeaway: The process can create multiple lineup slices by ownership range, with 300 lineups in each slice, and select entries from those slices.
- [46:32](https://www.youtube.com/watch?v=pakvRcKsnXQ&t=2792s) "it's all about building a portfolio of with risk management once you get down to candidate lineups like I said you got 3 000 down to 88 and you're only playing 20. if you wanted out of the 88 right to just randomly choose 20. that would be fine your expected value of your portfolio of 20 lineups ain't gonna be much different"
  - Takeaway: After narrowing 3,000 lineups to 88 candidates, randomly choosing 20 is described as having expected value not much different; portfolio selection is framed as risk management.

### DFS Office Hours 10/5: Different build settings for different contests, impact of pool size on build
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 06, 2021 (1:17:26) · [Watch on YouTube](https://www.youtube.com/watch?v=7yKBIoYboE8)

- [1:06:42](https://www.youtube.com/watch?v=7yKBIoYboE8&t=4002s) "if you have 200 plus unique lineups you have so much actual individual control over your exposures to dial things in and get as precise as you want then it makes sense to take that approach but if you only have 10 lineups six lineups 20 lineups is really on that edge"
  - Takeaway: The speaker says larger lineup pools allow more precise exposure control, while pools of 10, 6, or around 20 lineups offer less room for nuanced exposure adjustments.

### How to Beat NFL DFS Showdowns
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 10, 2026 (0:17:26) · [Watch on YouTube](https://www.youtube.com/watch?v=iE36sFpjaVw)

- [9:55](https://www.youtube.com/watch?v=iE36sFpjaVw&t=595s) "It is not 20 copies of the same game script. It spreads your lineup across the different ways that the game could go. So, if you're wrong about how the night unfolds, you're not wrong 20 times. You've got a piece of the shootout, a piece of the blowout, and a piece of the grind."
  - Takeaway: The portfolio approach diversifies lineups across different game-script outcomes rather than repeating one script.

### DFS Q&A: Avoiding Dupes on Small NFL Slates
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 21, 2025 (0:27:22) · [Watch on YouTube](https://www.youtube.com/watch?v=KDQWYsMCP8w)

- [2:03](https://www.youtube.com/watch?v=KDQWYsMCP8w&t=123s) "you never want to waste lineups in your pool is like the first thing I would say. So, let's say that uh you know, you don't want to play lineups that have two tight ends, right? Like that is something that that people might say and that I've heard."
  - Takeaway: The presenter advises avoiding wasted pool entries by preventing unwanted lineup types up front.

### The DraftKings Showdown Rule That Deletes Your Winning Lineup
FTA Sports · Aug 05, 2026 (0:18:10) · [Watch on YouTube](https://www.youtube.com/watch?v=1X6cgvJxsqQ)

- [16:04](https://www.youtube.com/watch?v=1X6cgvJxsqQ&t=964s) "So, if you make 150 lineups, maybe 140 of them, you have 2/3 you have three or four split, four three three or four two, maybe 10 of those lineups you go five one just to see if it's maybe one of those op chances the week that goes off."
  - Takeaway: For a 150-lineup set, the speaker suggests mostly using three-four or four-three team splits and reserving some lineups for a five-one split.

### Master The Art of NFL DFS Showdowns
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 30, 2024 (0:44:55) · [Watch on YouTube](https://www.youtube.com/watch?v=Fr2FxzlztT4)

- [23:55](https://www.youtube.com/watch?v=Fr2FxzlztT4&t=1435s) "you've likely still added some additional value to your lineup portfolio by making yourself a bit different from other players your 5,000 lineup pool will now have lineups that feature that player more and that are different from what other people may have gotten entirely"
  - Takeaway: Projection adjustments can change player exposure across a 5,000-lineup pool and make the portfolio differ from other players’ lineups.

### DFS Q&A: How do I best utilize the dupe metric in the contest sims?
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 03, 2023 (1:39:07) · [Watch on YouTube](https://www.youtube.com/watch?v=ETNpMZGSNCs)

- [1:17:04](https://www.youtube.com/watch?v=ETNpMZGSNCs&t=4624s) "the second contest Sim would be running that subset of optimal of good lineups against each other and on that one you're saying what is the best portfolio of these lineups to play right because if all if let's say 70% of your top lineups are Bill Stacks well when you Sim those lineups against each other on the second time the bills Stacks in that subset have become chalky"
  - Takeaway: A second contest simulation can evaluate a subset of good lineups against one another, exposing overrepresented lineup clusters such as Bills stacks.

### DFS Q&A: Simulations can help you avoid duplication in DFS
SaberSim DFS - Daily Fantasy Sports Strategy · Feb 03, 2022 (1:17:24) · [Watch on YouTube](https://www.youtube.com/watch?v=PSqHBQYbYqE)

- [54:24](https://www.youtube.com/watch?v=PSqHBQYbYqE&t=3264s) "you can pick and choose each individual lineup you can edit exposures if you want to to the set of five lineups overall it's far easier you know i would say in general especially if they're the same kind of as you've said identical if they're identical contests it just makes more sense to build everything in the um in one build manage it from there"
  - Takeaway: For identical contests, the speaker recommends building the desired lineups together so they can be reviewed and their exposures managed as a set.

### DFS Q&A: How Do You Reduce Dupes in Showdown?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 07, 2025 (1:05:02) · [Watch on YouTube](https://www.youtube.com/watch?v=JuOzj5ZOQHk)

- [49:39](https://www.youtube.com/watch?v=JuOzj5ZOQHk&t=2979s) "the portfolio diversifier does not only care about the lineup's ROI and what it cares more about is how the lineups complement each other. Okay. Uh so for instance, right, let's say I go to this dime where I had like three lineups, right? And we'll let this load."
  - Takeaway: Portfolio sorting prioritizes how lineups complement one another, rather than selecting solely by each lineup's ROI.

### 2025 HOW TO PLAY NFL DRAFTKINGS SHOWDOWN
DFS Army - Daily Fantasy Sports · Aug 23, 2025 (0:10:32) · [Watch on YouTube](https://www.youtube.com/watch?v=-ZBpaHty068)

- [9:06](https://www.youtube.com/watch?v=-ZBpaHty068&t=546s) "he ended up having a dud and the lineups that I built a few I built about 20% of my lineups where I faded to him and those were the ones that wound up making me all the money for that slate."
  - Takeaway: The speaker says about 20% of his lineups faded Christian McCaffrey, and those lineups made him money on that slate.

### I Cracked the Code on NFL Showdown Lineups (Do This to Win)
DFS Army - Daily Fantasy Sports · Aug 03, 2026 (0:26:59) · [Watch on YouTube](https://www.youtube.com/watch?v=65HDqKemR88)

- [10:10](https://www.youtube.com/watch?v=65HDqKemR88&t=610s) "these inform how I run showdown optimizations when I'm building 150 uh lineups trying to win a large field contest. So, when a wide receiver is captain, their own quarterback, massive leverage to playing them. We already know that. That's not that shocking, right?"
  - Takeaway: The speaker says he uses correlation findings while optimizing 150 lineups, including pairing a wide-receiver captain with that player's quarterback; exposure targets, diversification, and game-script portfolio clusters are not specified here.

### SaberSim's Unique Approach to Projecting Ownership
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 10, 2021 (1:28:00) · [Watch on YouTube](https://www.youtube.com/watch?v=zMdDPCaxXjg)

- [1:05:42](https://www.youtube.com/watch?v=zMdDPCaxXjg&t=3942s) "you play 20 in fade gibson and you have zero of 20 that have gibson and i may be one-third the field on gibson and i may play uh i may be one-third the field on gibson but still have almost 20 lineups with him in it right and while percentages are great at the end of the day in some ways you have to consider the actual raw lineups you are playing"
  - Takeaway: When setting portfolio exposures, consider both exposure percentages and the actual number of lineups containing a player.

### DFS Q&A: Navigating NFL Late Swap
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 18, 2024 (0:30:32) · [Watch on YouTube](https://www.youtube.com/watch?v=8qVskFOoEGE)

- [29:17](https://www.youtube.com/watch?v=8qVskFOoEGE&t=1757s) "on Showdown maybe you want to build out line ups for different ways that the game could play out maybe you want to do like a run heavy game script maybe you want to do a pass heavy game script maybe you want to do you know five lineups with like the captain quarterback paired with a wide receiver maybe you want to do five lineups Captain quarterback with no number one wide receiver it's a way of doing different builds"
  - Takeaway: The Favorites feature can help create and combine groups of lineups built around different game scripts and quarterback-captain constructions.

### Why is avoiding duplication important in DFS?
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 16, 2021 (0:08:40) · [Watch on YouTube](https://www.youtube.com/watch?v=MCss_MdowIc)

- [5:10](https://www.youtube.com/watch?v=MCss_MdowIc&t=310s) "duplicating yourself 150 times in a contest is a terrible idea it dramatically reduces the expected value of the lineup that you're playing"
  - Takeaway: Entering the same lineup 150 times is described as reducing that lineup's expected value.

### DFS Q&A: How SaberSim Creates Its Ownership Projections
SaberSim DFS - Daily Fantasy Sports Strategy · Jun 03, 2023 (0:24:23) · [Watch on YouTube](https://www.youtube.com/watch?v=JnVogCYAHgY)

- [10:50](https://www.youtube.com/watch?v=JnVogCYAHgY&t=650s) "I built 2500 lineups I only had four lineups with uh Haywood Highsmith as the captain and one of those was actually the lineup That shipped"
  - Takeaway: The speaker reports having four Highsmith-Captain lineups in a 2,500-lineup portfolio, including the winning lineup.

### I Studied 230,000 NFL DFS Lineups; Here's What Will Win in 2026
DFS Army - Daily Fantasy Sports · Jul 27, 2026 (0:25:36) · [Watch on YouTube](https://www.youtube.com/watch?v=rz2HFI7diGY)

- [16:33](https://www.youtube.com/watch?v=rz2HFI7diGY&t=993s) "Generally, we saw two deliberate clusters. Your stack game will carry anywhere from two to four players on your lineup and probably on average three, right? Um and then a secondary game also carries a stack. We found that having a secondary stack not connected to your initial stack um showed up in almost 70%"
  - Takeaway: The transcript says top-finishing lineups commonly used a primary cluster of two to four players and a separate secondary stack, which appeared in almost 70% of top-finishing lineups.

### DFS Q&A: How do I navigate NFL late swap?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 09, 2022 (1:07:37) · [Watch on YouTube](https://www.youtube.com/watch?v=uvDTL8e6Ipo)

- [7:27](https://www.youtube.com/watch?v=uvDTL8e6Ipo&t=447s) "when you build your lineups before lock on saber sim you're building a big pool of lineups and selecting the best lineups out of that so anytime you late swap on a given slate with with sabre sim you are going to slightly increase the variance of your lineups just a bit"
  - Takeaway: The build process creates a pool of lineups and selects the best; late swapping slightly increases lineup variance.

### How to Build Winning NFL DFS Showdown Lineups on DraftKings & FanDuel (2024)
Occupy Fantasy · Oct 07, 2024 (1:22:41) · [Watch on YouTube](https://www.youtube.com/watch?v=W9FWB82PwNs)

- [53:33](https://www.youtube.com/watch?v=W9FWB82PwNs&t=3213s) "If you like a few of the less popular captain MVP choices, like tonight, you like Shahed, like a lava, like carb, try to double the amount that the field has in your own personal lineups."
  - Takeaway: For a portfolio of lineups, the speaker suggests targeting roughly twice the field's exposure to favored less-popular MVP choices.

### DFS Q&A: How Do Custom Projections and Ownership Affect Sims and Lineup Building?
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 28, 2025 (0:25:36) · [Watch on YouTube](https://www.youtube.com/watch?v=t0YPdy7wOuk)

- [2:36](https://www.youtube.com/watch?v=t0YPdy7wOuk&t=156s) "however many contests are within a group the ROI results get averaged out so if I have two contests for example right super simple example I I have two lineups/ two single entry contests and the same lineup grades out as 100% ROI in one contest and then 200% ROI in the other contest."
  - Takeaway: When contests are grouped, the diversifier averages a lineup’s ROI across the contests in that group.

### High Level Showdown Strategy + Super Bowl Stuff with Cody Main and Colin Drew
Establish The Run · Feb 04, 2022 (0:55:18) · [Watch on YouTube](https://www.youtube.com/watch?v=i98ljRFANdA)

- [10:00](https://www.youtube.com/watch?v=i98ljRFANdA&t=600s) "then kind of spreading out exposure along uh spectrum of how i think a game might come out so like if i get a game script that i'm built building for then i've got a shot at a solo winner so large field multi-entry tournaments whatever you know whatever dollar range that fits your bankroll"
  - Takeaway: Cody described spreading exposure across possible game scripts so a lineup matching a script has a chance to win outright in large-field multi-entry contests.

### 2026 NFL DraftKings Strategy: Stop Making These Costly DFS Mistakes
Mayo Media Network · Aug 28, 2026 (1:05:48) · [Watch on YouTube](https://www.youtube.com/watch?v=SPjmh9bxUF4)

- [5:20](https://www.youtube.com/watch?v=SPjmh9bxUF4&t=320s) "if you're someone who throws in three lineups a week or five lineups a week going from five to 150 and trying to figure out how all of that works and trying to get the proper balance and try to attack it from different angles and build sets of lineups that are completely different but maybe create the same theme the entire time."
  - Takeaway: When moving from a few entries to 150, he recommends balancing lineups, attacking from different angles, and building distinct lineups that can still share an overall theme.

### If you’re not late-swapping in NFL DFS, you’re leaving money on the table
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 01, 2021 (1:02:30) · [Watch on YouTube](https://www.youtube.com/watch?v=S2p7LVEeXy4)

- [17:31](https://www.youtube.com/watch?v=S2p7LVEeXy4&t=1051s) "so you can set player exposures if you want to make certain adjustments again maybe there's a particular player let's use the example again from last week so dalvin cook is ruled out and madison is coming in to take his spot the builder is going to pick up that madison is a great play and is probably going to late swap a lot of madison into your lineups but say for example that you know at the very least you want 30 madison in your lineups it's very easy to just go in here and say that when you late swap give me at least 30 of the player"
  - Takeaway: The late-swap builder allows a user to set a minimum player exposure, such as at least 30% Alexander Madison.

### DFS Q&A: How are SaberSim's ownership projections calculated?
SaberSim DFS - Daily Fantasy Sports Strategy · Jun 15, 2022 (0:58:03) · [Watch on YouTube](https://www.youtube.com/watch?v=MGO5rVk8I7M)

- [23:15](https://www.youtube.com/watch?v=MGO5rVk8I7M&t=1395s) "the way i would actually go about approaching this would be i would run my research build right um i would build my lineups i would build my 1500 lineup pool at 0 0 10 right similar to what i do on other other slates something like this and get a feeling for where i thought players were going to be over or under owned"
  - Takeaway: For a multi-entry process, Jordan describes building a 1,500-lineup research pool at 0-0-10 to assess which players may be over- or under-owned.

### Field Lineups Explained
 ·  · [Watch on YouTube](https://www.youtube.com/watch?v=DHKY694-I_M)

- [4:37](https://www.youtube.com/watch?v=DHKY694-I_M&t=277s) "you can see how your lineups did as a whole here as a portfolio in the contest with the actual lineups that were played here not just the hypothetical con hypothetical lineups that we believed would be in your contest"
  - Takeaway: The post-contest tool evaluates a user's lineups together as a portfolio against the actual lineups played.

### DFS Q&A: Product Ownership and Geometric Mean
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 11, 2022 (0:56:29) · [Watch on YouTube](https://www.youtube.com/watch?v=eVWhJ0Cy2FY)

- [47:21](https://www.youtube.com/watch?v=eVWhJ0Cy2FY&t=2841s) "you should just make all the changes you want based on the strategy that you're going into the Slate with because you want to like capture everything you're trying to capture all at once without forgetting anything"
  - Takeaway: When making exposure edits, the speaker recommends applying all changes that fit the intended slate strategy rather than making only a subset.

### How to Late Swap in NFL DFS: A Real-Time Tutorial
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 09, 2024 (0:08:18) · [Watch on YouTube](https://www.youtube.com/watch?v=IAt9PW8j75M)

- [6:06](https://www.youtube.com/watch?v=IAt9PW8j75M&t=366s) "this would be an opportunity where I could go through and review any of my exposures maybe make a couple of additional adjustments if I wanted to get higher or lower on anyone review my stack types here for example"
  - Takeaway: The speaker reviews player exposures and stack types after generating late swaps and may adjust exposure levels.

### Lions vs Panthers - SNF Sunday Sweatdown | NFL Week 4 | DFS Picks, Plays & Process
Ship It Nation · Oct 05, 2026 (1:05:29) · [Watch on YouTube](https://www.youtube.com/watch?v=xJlvummhIfI)

- [19:14](https://www.youtube.com/watch?v=xJlvummhIfI&t=1154s) "I'll probably match the field to be honest. I'll probably play around 30% Gibbs captain. Um, just maybe I mean as it shakes out, I I expect him to kind of come in higher than that. I ran a dry run ham here and got 81% Jir Gibbs in the captain position which then leads uh the flex position to be a bunch of Darren Waller, Bryson Tmaine um the kickers"
  - Takeaway: The speaker discussed a roughly 30% Gibbs-captain target versus an 81% Gibbs-captain dry-run result, with the latter yielding cheaper flex plays.

## 4. Ownership projection methodology

18 videos, 31 transcript excerpts.


### How To Project Ownership % in DFS (DraftKings)
Kev's Picks · Nov 22, 2015 (0:04:33) · [Watch on YouTube](https://www.youtube.com/watch?v=BToDGUdOhkU)

- [0:32](https://www.youtube.com/watch?v=BToDGUdOhkU&t=32s) "number one is previous ownership percentages for that player number two did that player's price increase or decrease number three the matchup for the week for that player four is recent performance and five is FanDuel Thursday contest"
  - Takeaway: The transcript lists prior ownership, price movement, matchup, recent performance, and FanDuel Thursday ownership as inputs to an ownership projection.
- [1:09](https://www.youtube.com/watch?v=BToDGUdOhkU&t=69s) "for this example let's say Tom Brady has been 25 20 and 23% owned the last 3 weeks we're guessing that he should be right around that range this week so at this point I'm projecting 23% ownership so right in between basically the last 3 weeks percentages"
  - Takeaway: The example uses a player's ownership over the previous three weeks to estimate a 23% projection.
- [1:22](https://www.youtube.com/watch?v=BToDGUdOhkU&t=82s) "next thing you want to do is check his price so this week he's priced at $8,700 the last few weeks he averaged a $8,200 so we went up and price $500 but you also have to compare that price in comparison to other quarterbacks as well"
  - Takeaway: The method compares the player's current salary with his recent average and with the salaries of other players at the position.
- [1:36](https://www.youtube.com/watch?v=BToDGUdOhkU&t=96s) "so if all quarterbacks Rose then it's not a big deal but if the other quarterbacks went down and Brady went up $500 that's a pretty big deal and that's going to come into play with the ownership percentages as well so at this point he rose so I'm decreasing my projection down to 19% for Brady"
  - Takeaway: A salary increase relative to other quarterbacks lowers the example ownership projection to 19%.
- [1:53](https://www.youtube.com/watch?v=BToDGUdOhkU&t=113s) "so let's say that the Patriots are facing the number four ranked passing defense and they're playing on the road this is going to give me another decrease to my projection because of a bad matchup so I'll send him down to 12% projection"
  - Takeaway: A difficult matchup and playing on the road lead to a further reduction in the example projection, to 12%.
- [2:11](https://www.youtube.com/watch?v=BToDGUdOhkU&t=131s) "let's say that Brady just played the Monday nighter and he threw six touchdowns and 500 yards just had a crazy game lots of people watch these Prime Time games everyone's going to remember that awesome performance everyone who missed out on them last week a lot of those people are going to want to roster him this week so for that reason we're going to increase his projection so back up to 20%"
  - Takeaway: A highly visible recent performance can increase projected ownership, with the example moving back up to 20%.
- [3:11](https://www.youtube.com/watch?v=BToDGUdOhkU&t=191s) "let's say that Friday morning you check and see Brady was 29% owned on the FanDuel Thursday contest then you want to compare the pricing between FanDuel and DraftKings if the players are pretty similar on both sites you can get a good projection if one player is really cheap on FanDuel and really expensive on DraftKings you can't really use this"
  - Takeaway: FanDuel Thursday ownership can inform a DraftKings projection when player pricing is similar across the two sites.
- [3:35](https://www.youtube.com/watch?v=BToDGUdOhkU&t=215s) "we'll say that it's pretty similar but slightly cheaper at FanDuel so we're going to give Brady a slight bump in projection since he was 29% own on FanDuel we're going to bump him up to 23 on DraftKings"
  - Takeaway: In the example, 29% FanDuel ownership and slightly cheaper FanDuel pricing produce a slight increase to a 23% DraftKings projection.

### DFS Q&A: What is a self-sim?
SaberSim DFS - Daily Fantasy Sports Strategy · Jul 11, 2024 (0:56:19) · [Watch on YouTube](https://www.youtube.com/watch?v=JjEqfaORNpA)

- [3:43](https://www.youtube.com/watch?v=JjEqfaORNpA&t=223s) "when we run the contest Sim in every single iteration of that contest Sim you're simming it against the same field you are simming it here against a field where Nick Peta is exactly 26.3 three% owned now that is probably pretty true we put a lot of work into our ownership models into our field lineups we put a lot of work into identifying what makes these different contests different from each other so I feel pretty good about that ownership projection but there's some variance there"
  - Takeaway: The speaker says a contest sim uses the same field in every iteration, with contest-specific ownership models and field lineups, while acknowledging ownership variance.
- [9:16](https://www.youtube.com/watch?v=JjEqfaORNpA&t=556s) "the field lineups that we create for all of those different contest fields are using an industry aggregate projection so we're basically trying to predict what is the real field you're playing against going to do"
  - Takeaway: The field lineups for different contest types use an industry aggregate projection to estimate what the opposing field will do.

### DFS Q&A: Simulations can help you avoid duplication in DFS
SaberSim DFS - Daily Fantasy Sports Strategy · Feb 03, 2022 (1:17:24) · [Watch on YouTube](https://www.youtube.com/watch?v=PSqHBQYbYqE)

- [11:49](https://www.youtube.com/watch?v=PSqHBQYbYqE&t=709s) "the second reason i don't like these ownership heuristics is because they don't take into account contest context right well how do we deal with that problem we adjust our ownership fade slider based on the context contest you tell us you're playing right we turn down the impact of ownership when you're playing a 5000 person single entry we turn up the ownership factor when you're playing a 50 000 person uh 150 max"
  - Takeaway: The speaker says ownership fade is adjusted according to contest context, with less impact for a 5,000-person single-entry contest and more for a 50,000-person 150-max contest.
- [56:35](https://www.youtube.com/watch?v=PSqHBQYbYqE&t=3395s) "our ownership model is a computer-based model so it's going to kind of study based on our projections and our salaries what is the optimal way that that saver sim would play the slate"
  - Takeaway: The speaker says SaberSim's ownership model uses projections and salaries to estimate how the slate would be played.

### SaberSim's Unique Approach to Projecting Ownership
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 10, 2021 (1:28:00) · [Watch on YouTube](https://www.youtube.com/watch?v=zMdDPCaxXjg)

- [3:38](https://www.youtube.com/watch?v=zMdDPCaxXjg&t=218s) "it allows us to project ownership for every single slate every single game out there and it allows us to regenerate ownership basically more or less instantly when news breaks"
  - Takeaway: The speaker says the ownership projections cover every slate and game and can be regenerated almost immediately after news breaks.
- [3:49](https://www.youtube.com/watch?v=zMdDPCaxXjg&t=229s) "the ownership model is doing is it is taking an aggregate projection and it is building thousands of lineups at a high variance setting basically mimicking the slate and then the exposure to certain players in those sets of lineups becomes the ownership projection"
  - Takeaway: SaberSim derives ownership from player exposure in thousands of high-variance lineups built from aggregate projections.

### DFS Q&A: Navigating NFL Late Swap
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 18, 2024 (0:30:32) · [Watch on YouTube](https://www.youtube.com/watch?v=8qVskFOoEGE)

- [27:03](https://www.youtube.com/watch?v=8qVskFOoEGE&t=1623s) "also from the live Fields we're not even using projected ownership anymore we know that he was played at 19.6 n% of lineups so the way I like to think about the live ownership is you know ownership is a puzzle as the games unlock as ownership becomes available we are getting pieces of the puzzle"
  - Takeaway: As games unlock, live ownership uses observed ownership for players already in the field rather than their projected ownership.
- [27:44](https://www.youtube.com/watch?v=8qVskFOoEGE&t=1664s) "ownership becomes more and more accurate the more and more people that we start to see their actual projections for so the the the last set of ownership projections are going to be more accurate in my opinion right because we have so many pieces of the puzzle at that point"
  - Takeaway: The speaker says ownership projections become more accurate as more actual player ownership becomes available.

### DFS Q&A: How SaberSim Creates Its Ownership Projections
SaberSim DFS - Daily Fantasy Sports Strategy · Jun 03, 2023 (0:24:23) · [Watch on YouTube](https://www.youtube.com/watch?v=JnVogCYAHgY)

- [3:30](https://www.youtube.com/watch?v=JnVogCYAHgY&t=210s) "we run Builds on very very high Sim diversity and see how all the players do over that set of builds that we run and then that those exposures that come out of those builds are what end up being our ownership projections here"
  - Takeaway: SaberSim says ownership projections are derived from player exposures across builds run with very high Sim diversity.
- [5:22](https://www.youtube.com/watch?v=JnVogCYAHgY&t=322s) "when news comes out you know we don't have to go manually rerun ownership or anything like that the Builder can take in those inputs and then redistribute ownership accordingly here"
  - Takeaway: The Builder can incorporate news inputs and redistribute ownership without manually rerunning ownership.

### Field Lineups Explained
 ·  · [Watch on YouTube](https://www.youtube.com/watch?v=DHKY694-I_M)

- [0:52](https://www.youtube.com/watch?v=DHKY694-I_M&t=52s) "what we do is we run what we call an ownership build here which we build like cups with certain inputs and rules and the exposures from those builds become the ownership projections"
  - Takeaway: Ownership projections are based on exposures from ownership builds created with specified inputs and rules.
- [0:52](https://www.youtube.com/watch?v=DHKY694-I_M&t=52s) "we ended up creating 13 different sets of ownership to represent the different stakes and size and entry limits for the contest that you play"
  - Takeaway: The site provides 13 ownership sets intended to reflect differences in contest stakes, size, and entry limits.

### DFS Q&A: How Do Contest Sims Work for Small vs. Large-Field Contests?
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 12, 2023 (0:18:57) · [Watch on YouTube](https://www.youtube.com/watch?v=h9O1DRC4ABo)

- [4:40](https://www.youtube.com/watch?v=h9O1DRC4ABo&t=280s) "so then you are coming in here and increasing his ownership right I think I think ownership adjustments are a point of Game Theory right and then from there you could take into narrative maybe there is this narrative that the Chiefs wide receivers just just aren't good"
  - Takeaway: Andrew describes manually increasing a player’s ownership when expecting it to be higher and also considering relevant narratives.

### Studying the Sharps: Constructing DFS Lineups with Jordan Cooper
DraftKings · Oct 05, 2021 (1:24:55) · [Watch on YouTube](https://www.youtube.com/watch?v=1qKHG9mSEfI)

- [28:17](https://www.youtube.com/watch?v=1qKHG9mSEfI&t=1697s) "the methodology i have now is aggregate the ownership projections aggregate some other projection source um plug in the salaries of course and then figure out in each category how much how many standard deviations above or below the mean for that position the player is"
  - Takeaway: Meiselman describes combining ownership projections, another projection source, salary, and position-specific standard deviations to rate players.

### DRAFTKINGS & FANDUEL DFS STRATEGY REVIEW: PROJECTION VS OWNERSHIP EXPLOIT (1/4/23)
RotoGrinders - Daily Fantasy Sports Advice · Jan 04, 2023 (1:21:28) · [Watch on YouTube](https://www.youtube.com/watch?v=x2vfd9rf5S8)

- [44:35](https://www.youtube.com/watch?v=x2vfd9rf5S8&t=2675s) "it's all based around the ownership being accurate right and so based on the projection being accurate someone someone's projected for 36 minutes when they're all or really they should be projected for 24 minutes"
  - Takeaway: The projection-versus-ownership approach depends on accurate ownership and player projections, including projected minutes.

### DFS Q&A: How do I navigate NFL late swap?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 09, 2022 (1:07:37) · [Watch on YouTube](https://www.youtube.com/watch?v=uvDTL8e6Ipo)

- [16:10](https://www.youtube.com/watch?v=uvDTL8e6Ipo&t=970s) "i do think uh juan dale robinson on the giants is likelier to be quite a bit chalkier than this um he is the stone minimum it seems like he's locked into the wide receiver role for the giants uh and it seems like a play that people are going to get to quite a bit i would at least expect him to get up to maybe closer to like 10 ownership"
  - Takeaway: The speaker expected Wan'Dale Robinson's ownership to rise toward 10%, citing his minimum salary, expected role, and likelihood of attracting lineups.

### DFS Q&A: What is the best way to reduce dupes in Showdown?
SaberSim DFS - Daily Fantasy Sports Strategy · Jan 15, 2024 (0:15:07) · [Watch on YouTube](https://www.youtube.com/watch?v=eWWw-7T2YLk)

- [12:49](https://www.youtube.com/watch?v=eWWw-7T2YLk&t=769s) "the way that the the second game went didn't help me but I would still continue to late swap because the Builder is just going to optimize your lineups the best best that it can based on what's actually happened and those live sims are running during the game guys and then those live sims you know run at the conclusion of the game and then before the next game starts taking into account inactives and and updating projections"
  - Takeaway: The builder uses what has happened so far, while live sims run during games and projections are updated for inactives before the next game.

### How to Build Winning NFL DFS Showdown Lineups on DraftKings & FanDuel (2024)
Occupy Fantasy · Oct 07, 2024 (1:22:41) · [Watch on YouTube](https://www.youtube.com/watch?v=W9FWB82PwNs)

- [38:32](https://www.youtube.com/watch?v=W9FWB82PwNs&t=2312s) "So for these showdown slates, our lineup builder architect, Jack and I, we carefully craft this. We look at industry projections. We figure out which players are the most likely to be used. We run lineup builds with those and we it spits out projected exposure for every player."
  - Takeaway: The speaker says showdown ownership projections start with industry projections and lineup builds that produce projected player exposure.

### If you’re not late-swapping in NFL DFS, you’re leaving money on the table
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 01, 2021 (1:02:30) · [Watch on YouTube](https://www.youtube.com/watch?v=S2p7LVEeXy4)

- [27:32](https://www.youtube.com/watch?v=S2p7LVEeXy4&t=1652s) "and let's say that in actuality uh tyreek hill comes in at 25 ownership um and obviously associated with that we're probably going to have increased patrick mahomes ownership people are clearly more interested in the chief stacks than we thought but this is now going to affect the way the ownership is going to spread out at this position for other players right that ownership has to come from somewhere now it's not always super easy to just immediately dissect where that ownership is going to come from"
  - Takeaway: The speakers describe updating late-game ownership expectations when actual early-game ownership differs from projections, since ownership shifts affect other players.

### DFS Q&A: How are SaberSim's ownership projections calculated?
SaberSim DFS - Daily Fantasy Sports Strategy · Jun 15, 2022 (0:58:03) · [Watch on YouTube](https://www.youtube.com/watch?v=MGO5rVk8I7M)

- [2:10](https://www.youtube.com/watch?v=MGO5rVk8I7M&t=130s) "at the moment the way that we think about our ownership projections is we are projecting ownership for a large field gpp um essentially you know something resembling the flagship contest uh on any given slate uh maybe the mini max would also work as kind of a decent approximation just a large field lots of lineups kind of thing um and you when you have smaller fields uh you are going to have some ownership condensing"
  - Takeaway: SaberSim's ownership projections target large-field GPPs; ownership of the best-projected chalk plays tends to condense in smaller fields.

### DRAFTKINGS & FANDUEL DFS STRATEGY REVIEW: Large-Field GPP Lineup Simulations (1/18/23)
RotoGrinders - Daily Fantasy Sports Advice · Jan 18, 2023 (1:00:36) · [Watch on YouTube](https://www.youtube.com/watch?v=pakvRcKsnXQ)

- [6:26](https://www.youtube.com/watch?v=pakvRcKsnXQ&t=386s) "which will change multiple times so obviously we're using these numbers as an example right ownership will change you know by seven o'clock eight hours from now like it's a 7 30 slate eight and a half hours from now some of the minutes may change our projections team will come in and start uh making some manual adjustments"
  - Takeaway: Projections and ownership can change during the day as minutes change, and the projections team may make manual adjustments.

### DFS Q&A: For the 20-Max and 150-Max contest do you use the same pool?
SaberSim DFS - Daily Fantasy Sports Strategy · May 25, 2024 (0:58:29) · [Watch on YouTube](https://www.youtube.com/watch?v=PRtm5_i9qqQ)

- [15:51](https://www.youtube.com/watch?v=PRtm5_i9qqQ&t=951s) "Obi toppen is a really good example here on this slate projected ownership 31.6 came in at 46% all lineups with Obi toppen are now going to be they're going to come in with a lower Roi than expected"
  - Takeaway: He compares projected and actual ownership in post-contest review; a player whose actual ownership exceeded projection could lower the ROI of lineups containing him.

### Beat DFS Using The SaberSystem: 5 Principles for Maximum Profitability
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 29, 2024 (0:16:28) · [Watch on YouTube](https://www.youtube.com/watch?v=4jONT961JrM)

- [10:42](https://www.youtube.com/watch?v=4jONT961JrM&t=642s) "starting lineups weather and injuries can dramatically affect the way teams are projected the upside of individual players projected ownership and the correlations between players in the same game so building lineups with the most upto-date information is crucial to building strong lineups"
  - Takeaway: Starting lineups, weather, and injuries can affect team projections, player upside, projected ownership, and same-game correlations.

## 5. Field simulation and opponent lineup simulation

29 videos, 46 transcript excerpts.


### DFS Q&A: How Do Custom Projections and Ownership Affect Sims and Lineup Building?
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 28, 2025 (0:25:36) · [Watch on YouTube](https://www.youtube.com/watch?v=t0YPdy7wOuk)

- [5:54](https://www.youtube.com/watch?v=t0YPdy7wOuk&t=354s) "We're going and doing a slate simulation. We're taking one instance of each game on the slate, playing it out, assigning the scores to the players, and then assigning the scores to the lineup, and then deciding the standings, the payouts, all that. Right?"
  - Takeaway: The contest sim plays out a slate instance, scores players and lineups, and determines standings and payouts.
- [6:08](https://www.youtube.com/watch?v=t0YPdy7wOuk&t=368s) "So if you say Bailey scores 28 and we say 26, well maybe a lineup that was in sixth place based on the Saberson baseline projections actually gets moved up to fourth place because of your adjustment. And then now that lineup's ROI is higher."
  - Takeaway: A custom projection adjustment can change simulated lineup placement and ROI.
- [6:58](https://www.youtube.com/watch?v=t0YPdy7wOuk&t=418s) "changing this, if I, you know, move some players up, down, this doesn't change the field lineups. The field lineups are static. they they don't change by themselves. Okay, so adjusting this does not adjust the field lineups."
  - Takeaway: Changing ownership in the build does not automatically change the simulated field lineups.
- [8:31](https://www.youtube.com/watch?v=t0YPdy7wOuk&t=511s) "So, what you're going to have to do is do it a little bit like the old way old way I'm air quoting of using the max exposure to ownership option. Uh, I like to open this up a little bit, make it like 25%. Then it's going to apply a minimax exposure to every player on the slate."
  - Takeaway: The suggested workaround is to use the max-exposure-to-ownership option, with the speaker opening it to 25% to apply min/max exposures across players.
- [16:00](https://www.youtube.com/watch?v=t0YPdy7wOuk&t=960s) "In this build, I would run my actual lineups. And then now when the contest sim runs, it's going to sim my lineups in build one against the lineups in the build I've named custom field. So that is how you do that."
  - Takeaway: The contest sim can compare actual lineups against field lineups generated in a separate build named custom field.

### DFS Q&A: Walking Through the NFL Late Swap Process
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 26, 2025 (0:24:26) · [Watch on YouTube](https://www.youtube.com/watch?v=CgfglAjd2ys)

- [10:38](https://www.youtube.com/watch?v=CgfglAjd2ys&t=638s) "if you're playing a 20man winner or take all, I would go in, I would set entries to 20, percent to first to 100. Cash percent here is going to be 5% because um one out of 20 is 5% here. So only first place is getting paid."
  - Takeaway: For a 20-entry winner-take-all contest, the speaker sets entries to 20, first-place percentage to 100, and cash percentage to 5%.
- [21:39](https://www.youtube.com/watch?v=CgfglAjd2ys&t=1299s) "when you took three contests, put them in one group, it used to use the average. It does not do that anymore. Okay? When you put more than one lineup, more than one contest into a single group, the It intelligently fills the lineups into the contests even though they are still in the same group. So, it is not averaging anymore."
  - Takeaway: For multiple contests in one lineup group, the builder assigns lineups across contests intelligently rather than using average ROI.
- [23:00](https://www.youtube.com/watch?v=CgfglAjd2ys&t=1380s) "portfolio is a contest sim. However, it is a simplified contest sim. So, Portfolio Plus, which is what is on Ultimate, uses exact contest data for every contest that you're playing. Portfolio uses one simplified contest sim for all of your contests."
  - Takeaway: Portfolio uses one simplified contest simulation across contests, while Portfolio Plus uses exact contest data for each contest.

### Learn How Maximize SaberSim's New Contest Sims
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 24, 2023 (1:17:07) · [Watch on YouTube](https://www.youtube.com/watch?v=mZzskOQAz2k)

- [8:17](https://www.youtube.com/watch?v=mZzskOQAz2k&t=497s) "each lineup in your lineup pool is pit against the lineups in the field that you specified using the payout structure defined in your settings here and that process takes place X number of times where X is number of Sims so it's a it's a true simulation of how we expect the contest to actually play out"
  - Takeaway: Contest Sims evaluate each user lineup against the specified field and payout structure over repeated simulations.
- [20:28](https://www.youtube.com/watch?v=mZzskOQAz2k&t=1228s) "points to each player and then like populate it for each of your letters in each of the field lines so essentially we're saying like Okay and this simulation of the Slate which is just a collection of of Sims of each game you know these are all the fantasy points scored by all of the lineups in all of your field lineups and then we rank them"
  - Takeaway: Each slate simulation combines game simulations, scores the field lineups, and ranks them.
- [48:55](https://www.youtube.com/watch?v=mZzskOQAz2k&t=2935s) "yeah I mean so that's one one of the big things that I want to improve upon is like first just like build more field lineup so that we can do that more accurately because right now so we we build 5000 field lines so um when you enter a contest size really like we're simulating against just the 5000 um so that's the maximum right now"
  - Takeaway: At the time of the discussion, field simulations used a maximum of 5,000 field lineups, even for larger contests.

### Field Lineups Explained
 ·  · [Watch on YouTube](https://www.youtube.com/watch?v=DHKY694-I_M)

- [0:04](https://www.youtube.com/watch?v=DHKY694-I_M&t=4s) "projected field lineups are our best prediction of what the lineups you are competing against in your contest are going to look like these include things such as exposure such as stack types such as secondary stack correlations"
  - Takeaway: The projected field lineups represent the expected opponents’ lineups, including their exposures, stack types, and secondary-stack correlations.
- [2:25](https://www.youtube.com/watch?v=DHKY694-I_M&t=145s) "these are our buckets of ownership here and you can click on any one of these and it will actually bring up the lineups in that set of field lineups"
  - Takeaway: Users can open an ownership bucket to view the field lineups assigned to that set.
- [3:13](https://www.youtube.com/watch?v=DHKY694-I_M&t=193s) "because your lineups are battling against these field lineups each and every time we run the contest thing we are playing that simulation out a 100,000 times so if you if you are not accurately represent representing the field if we are not doing that for you here then you're going to get these false signals about which lineups are good"
  - Takeaway: The contest simulation runs 100,000 iterations, and the speaker says inaccurate field representation can give false signals about lineup quality.

### NFL DFS Sims Tournament Strategy Week 1 | NFL DFS Strategy
Stokastic DFS - Daily Fantasy Sports Advice · Sep 11, 2026 (1:11:45) · [Watch on YouTube](https://www.youtube.com/watch?v=uMa9MQhf0fU)

- [1:00:03](https://www.youtube.com/watch?v=uMa9MQhf0fU&t=3603s) "This is why the sims are great because you can really just get super granular with this stuff. Jacobe Brassette. Yeah, we have 3% QB plus two. So 3% double stacks. We have one lineup with a skinny stack and that's it."
  - Takeaway: The Sims are used to inspect detailed stack exposures, including quarterback-plus-two, double-stack, and skinny-stack lineup rates.
- [1:05:49](https://www.youtube.com/watch?v=uMa9MQhf0fU&t=3949s) "You can still get unique, you can still get weird, you can still go double tight end. It doesn't mean that those lineups are going to be chalky. They're simming better than any other lineups right now. Maybe things change. Maybe more injuries pop up between now and Sunday."
  - Takeaway: He uses Sims results to assess unusual lineup constructions and notes that results may change if more injuries emerge.

### DFS Q&A: How Do Contest Sims Work for Small vs. Large-Field Contests?
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 12, 2023 (0:18:57) · [Watch on YouTube](https://www.youtube.com/watch?v=h9O1DRC4ABo)

- [10:19](https://www.youtube.com/watch?v=h9O1DRC4ABo&t=619s) "so we we actually have 10,000 field items for NFL showdown so if your contest size is below that number we going to randomly sample the 10,000 each time we run the contest stim I see where your concern is coming from I think it's coming from a place uh that is uh you know founded"
  - Takeaway: For a contest smaller than 10,000 entries, SaberSim randomly samples from its 10,000 NFL Showdown field items each time it runs the contest simulation.
- [13:32](https://www.youtube.com/watch?v=h9O1DRC4ABo&t=812s) "the hardest thing to scale from from the 10,000 lineup contest that we're running to a 100,000 lineup contest uh you don't know for instance if this lineup is going to go from two dupes to 20 dupes two dupes to five dupes I don't think it scales particularly well for dupes"
  - Takeaway: Andrew identifies estimating how duplication scales from a 10,000-lineup simulation to a 100,000-entry contest as a key limitation.

### How to Beat NFL DFS Showdowns
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 10, 2026 (0:17:26) · [Watch on YouTube](https://www.youtube.com/watch?v=iE36sFpjaVw)

- [9:02](https://www.youtube.com/watch?v=iE36sFpjaVw&t=542s) "So, we take every one of these 5,000 lineups and drop it into a simulated version of the actual contest you're entering filled with lineups we think your opponents are going to play. Then, we run the game out again 100,000 times. And what you get is an ROI for every single lineup."
  - Takeaway: The described contest simulation places candidate lineups against projected opponent lineups and re-runs the game 100,000 times to estimate each lineup's ROI.
- [14:39](https://www.youtube.com/watch?v=iE36sFpjaVw&t=879s) "We know exactly what your opponents played. the real lineups, the real duplication, all of it. So, we take the lineups that you played and reimulate the entire slate against the real field. What comes back is what your lineups are actually worth, not what you won or lost, what they were actually worth."
  - Takeaway: The next-day flashback re-simulates the slate against actual opponent lineups and duplication.

### DFS Q&A: How Does the Portfolio Diversifier Work?
SaberSim DFS - Daily Fantasy Sports Strategy · Mar 19, 2026 (0:25:25) · [Watch on YouTube](https://www.youtube.com/watch?v=iM5sS24JCSc)

- [18:58](https://www.youtube.com/watch?v=iM5sS24JCSc&t=1138s) "Okay, saber score and the ROIs are both using a contest sim. The run contest sim option on ultimate uses the exact contests that you're playing. The saber score option is an ROI. So when I see the average saber score of 112.73, this is 112.73% ROI."
  - Takeaway: Saber Score and ROI use contest simulation, while the Ultimate run-contest-sim option uses the exact contests being played.
- [21:00](https://www.youtube.com/watch?v=iM5sS24JCSc&t=1260s) "Hey, how are your lineups performing when we put them up against lineups that we think the rest of the users in your contest are going to play? That is how the portfolio diversifier decides which lineups to actually give you and it prioritizes whatever your metric is."
  - Takeaway: The portfolio diversifier evaluates lineups against lineups it expects other users in the contest to play.

### DFS Q&A: Navigating NFL Late Swap
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 18, 2024 (0:30:32) · [Watch on YouTube](https://www.youtube.com/watch?v=8qVskFOoEGE)

- [13:39](https://www.youtube.com/watch?v=8qVskFOoEGE&t=819s) "the idea of self simming is to account for ownership variants where you're basically saying okay what if we run a Sim and the Yankees are actually 6% owned and not 2% owned and then what saber Sim is telling you is like ah if the Yankees are actually going to be 6% owned they're actually not as good of a play anymore"
  - Takeaway: Self-simming tests how a lineup pool grades when its actual team ownership differs from the ownership represented by field lineups.
- [14:19](https://www.youtube.com/watch?v=8qVskFOoEGE&t=859s) "you could think that your positive are y pre-s slate but if the Yankees come in you know a couple percent points higher stack ownership wise that could have a drastic effect on the viability of those lineups so that is what the self Sim is is doing because when you run a build we don't have parameters on how often a team can come up it's how often they're coming up in the Sim"
  - Takeaway: The speaker describes self-sim results as a way to identify lineups whose apparent ROI may be fragile to higher-than-expected stack ownership.

### DFS Q&A: What is the best way to reduce dupes in Showdown?
SaberSim DFS - Daily Fantasy Sports Strategy · Jan 15, 2024 (0:15:07) · [Watch on YouTube](https://www.youtube.com/watch?v=eWWw-7T2YLk)

- [4:05](https://www.youtube.com/watch?v=eWWw-7T2YLk&t=245s) "remember that the metrics that you're going to get from using your contest Sim Roi risk adjusted Roi win rate cash rate Roi standard deviation and dupes"
  - Takeaway: The contest sim provides ROI, risk-adjusted ROI, win rate, cash rate, ROI standard deviation, and dupe count.
- [6:28](https://www.youtube.com/watch?v=eWWw-7T2YLk&t=388s) "so then in that case you are using the contest Sim against the own lineups that you've created so in that case every lineup would be duped uh one time here because one there's no duplicates and then two you are simming against yourself basically"
  - Takeaway: When a build is simmed against itself, each lineup registers as duplicated once because the lineup is included in its own comparison.

### How to Late Swap in NFL DFS: A Real-Time Tutorial
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 09, 2024 (0:08:18) · [Watch on YouTube](https://www.youtube.com/watch?v=IAt9PW8j75M)

- [1:21](https://www.youtube.com/watch?v=IAt9PW8j75M&t=81s) "when you late swap with Sabers Sim and run a late swap contest you account for the live information of how the players in your lineups games are going for those that are already in progress and the real lineups that your opponents are playing and our contest Sims are going to account for that information automatically here"
  - Takeaway: Late-swap contest simulations account for live performance in ongoing games and the actual lineups opponents are playing.
- [4:41](https://www.youtube.com/watch?v=IAt9PW8j75M&t=281s) "for those on the saber Sim ultimate plan we want to next run a contest Sim which is going to take into account again how players are actually performing in your contests as well as what your opponents are doing in their lineups to identify the most profitable swaps we can swap to"
  - Takeaway: The Ultimate plan's contest simulation uses player performance and opponents' lineups to identify profitable swaps.

### DFS Q&A: What is a self-sim?
SaberSim DFS - Daily Fantasy Sports Strategy · Jul 11, 2024 (0:56:19) · [Watch on YouTube](https://www.youtube.com/watch?v=JjEqfaORNpA)

- [2:09](https://www.youtube.com/watch?v=JjEqfaORNpA&t=129s) "the self Sim refers to running a contest Sim on your own lineups so when you run a contest Sim what you're doing is you are taking each of your lineups in your 5,000 lineup pool and you are playing it into a simulated version of the contest that you're planning on playing that night using the payout structure the size of the contest and then an expected field so you have a set of field lineups and you're saying this is what I think my opponents are going to do"
  - Takeaway: A self-sim runs each lineup in the 5,000-lineup pool against a simulated contest using its payout structure, contest size, and an expected field.

### DFS Q&A: Avoiding Dupes on Small NFL Slates
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 21, 2025 (0:27:22) · [Watch on YouTube](https://www.youtube.com/watch?v=KDQWYsMCP8w)

- [15:39](https://www.youtube.com/watch?v=KDQWYsMCP8w&t=939s) "Portfolio uses saber score. Portfolio plus uses ROI of the exact contest that you're in. Uh saber score is an ROI. So basically what we do is we run one simplified contest sim just like a basic payout structure basic number of entrance and then the saber score values are an ROI."
  - Takeaway: Portfolio uses Saber Score, while Portfolio Plus uses the ROI of the specific contest; Saber Score comes from a simplified contest simulation.

### Master The Art of NFL DFS Showdowns
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 30, 2024 (0:44:55) · [Watch on YouTube](https://www.youtube.com/watch?v=Fr2FxzlztT4)

- [6:01](https://www.youtube.com/watch?v=Fr2FxzlztT4&t=361s) "the lineups we think your opponents will play in each one of your contests we test out each lineup out of your 5,000 as if it was entered into that field and then re simulate the game 100,000 times this way we can calculate the ROI of each lineup you've built"
  - Takeaway: Contest simulations test each candidate lineup against an expected opponent field, resimulate the game 100,000 times, and calculate lineup ROI.

### DFS Q&A: How do I best utilize the dupe metric in the contest sims?
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 03, 2023 (1:39:07) · [Watch on YouTube](https://www.youtube.com/watch?v=ETNpMZGSNCs)

- [9:15](https://www.youtube.com/watch?v=ETNpMZGSNCs&t=555s) "the way that the contest Sim works is it takes each lineup in your pool and it puts it into a contest made up of your field lineups with the payout structure defined by your settings and then it simulates that contest 100,000 times for that given lineup and then it goes to the second lineup in your pool and does that again"
  - Takeaway: The contest sim tests each lineup separately against field lineups under the configured payout structure, running 100,000 simulations for each lineup.

### NFL Office Hours - Showdown Q&A
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 08, 2023 (1:01:37) · [Watch on YouTube](https://www.youtube.com/watch?v=Re6X-sC0P7A)

- [22:16](https://www.youtube.com/watch?v=Re6X-sC0P7A&t=1336s) "well now when I go to my contest Sim settings build one is going to be an option so instead of looking at the saber Sim ownership lineups it will look at the lineups in build one and it will run the contest Sim against the lineups in that build"
  - Takeaway: A custom build can be selected as the field lineups against which the Contest Sim runs, rather than using the SaberSim ownership lineups.

### DFS Q&A: How Do You Reduce Dupes in Showdown?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 07, 2025 (1:05:02) · [Watch on YouTube](https://www.youtube.com/watch?v=JuOzj5ZOQHk)

- [59:58](https://www.youtube.com/watch?v=JuOzj5ZOQHk&t=3598s) "greater than or equal to 10. Sort by SIM ROI. So like a good SIM ROI in this contest would be basically anything that's positive. This just tells me that this is a a very tough contest and you know it's a high dollar entry contest."
  - Takeaway: The speaker evaluates simulated ROI in the context of the specific contest, describing any positive result as good in the demonstrated tough, high-dollar contest.

### NFL DFS Strategy Masterclass: Game Theory, Stacking & How to Actually Win
Mayo Media Network · Sep 04, 2026 (1:09:42) · [Watch on YouTube](https://www.youtube.com/watch?v=oj36e7aIMHc)

- [5:36](https://www.youtube.com/watch?v=oj36e7aIMHc&t=336s) "as DFS gotten more competitive, the Sims have helped me kind of marry the two strategies. Know when I'm going too far in terms of point all these leverage plays. Like I don't want three uncorrelated high ceiling plays at wide receiver all at 5%. I just don't need that to win some of the contests that I'm playing."
  - Takeaway: Contest simulations help balance chalk and leverage and identify when a lineup has too many uncorrelated high-ceiling plays.

### NFL DFS Week 1 DraftKings Strategy And Picks  Run The Sims With A Milly Maker Winner
Neil Orfield · Sep 12, 2026 (0:28:11) · [Watch on YouTube](https://www.youtube.com/watch?v=MhwZlTi-eJw)

- [22:32](https://www.youtube.com/watch?v=MhwZlTi-eJw&t=1352s) "Of course, you can run different sets of sims if you're playing both like the $5 and the $100, for example, uh, Millie Maker on DraftKings. You you would want to use different entry fee um some some different settings."
  - Takeaway: He recommends running separate simulations with different settings for contests with different entry fees.

### How To Use The Stokastic NFL DFS Contest Generator Tool | NFL DFS Contest Simulations
Stokastic DFS - Daily Fantasy Sports Advice · Sep 07, 2023 (0:06:38) · [Watch on YouTube](https://www.youtube.com/watch?v=QX-prNRoIuA)

- [5:46](https://www.youtube.com/watch?v=QX-prNRoIuA&t=346s) "you could click on the post contest simulator and then right from there there's already going to be a file in there with all the lineups that you've built and you can simulate out this late"
  - Takeaway: The post-contest simulator can use a file containing the generated lineups to simulate the slate.

### SaberSim's Unique Approach to Projecting Ownership
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 10, 2021 (1:28:00) · [Watch on YouTube](https://www.youtube.com/watch?v=zMdDPCaxXjg)

- [4:03](https://www.youtube.com/watch?v=zMdDPCaxXjg&t=243s) "it is essentially it is building real lineups that the field might build and then saying how often a certain player shows up is how often that player is going to be owned in the contest"
  - Takeaway: The ownership process builds lineups intended to resemble those the field might build and uses player appearance frequency to estimate ownership.

### DFS Q&A: How Should You Handle NFL Late Swap Between Builds?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 21, 2025 (0:27:24) · [Watch on YouTube](https://www.youtube.com/watch?v=QJ4wmImXx5M)

- [7:55](https://www.youtube.com/watch?v=QJ4wmImXx5M&t=475s) "Where we do have live data from Ultimate, focus on capturing as much of the live data as possible. Uh, because it's just basically more accuracy in the standings in the contest sim, right? If we know exactly how many points a player scores or has scored to a very long point in the game, well then now we can better figure out what what the standings are, what your chances are moving up, down, best swaps, etc."
  - Takeaway: The speaker says live player scoring data improves contest-sim standings, movement chances, and identification of better swaps.

### How to Win NFL DFS Tournaments in 2026
Establish The Run · Sep 06, 2026 (1:03:32) · [Watch on YouTube](https://www.youtube.com/watch?v=A-PD6sZhvvY)

- [59:33](https://www.youtube.com/watch?v=A-PD6sZhvvY&t=3573s) "Yeah. And you know, really important for anyone using Sims to be sure you select the contest that you're playing for when you run your Sims. In other words, like it is going to pick up on what types of lineups actually can win here versus needing the pure nuts as Sam said."
  - Takeaway: The speakers recommend selecting the target contest when running Sims because the lineup types that can win vary by contest.

### Studying the Sharps: Constructing DFS Lineups with Jordan Cooper
DraftKings · Oct 05, 2021 (1:24:55) · [Watch on YouTube](https://www.youtube.com/watch?v=1qKHG9mSEfI)

- [14:54](https://www.youtube.com/watch?v=1qKHG9mSEfI&t=894s) "there were 117 000 lineups in this contest and you know what they are because you just saw the the ownership of them you you're doing this the day after and then you run and you go okay based on my accurate projections here are the lineups that over a hundred thousand trials over five hundred thousand trials over two million trials shows the highest return"
  - Takeaway: Cooper describes using known contest lineups and projections to run repeated trials and identify lineups with the highest return.

### How To Use The Stokastic NFL DFS Pre-Contest Sims Tool | NFL DFS Contest Simulations
Stokastic DFS - Daily Fantasy Sports Advice · Sep 07, 2023 (0:10:35) · [Watch on YouTube](https://www.youtube.com/watch?v=4PFRCiUGPec)

- [3:20](https://www.youtube.com/watch?v=4PFRCiUGPec&t=200s) "The win percentage this is the percentage of time that that lineup is expected to come in first place based on the 40 000 simulations all these all these lineups ran against each other this is the percentage of time that that lineup ended up winning"
  - Takeaway: The tool runs 40,000 simulations with the lineups against each other and reports a lineup's first-place win percentage.

### DRAFTKINGS & FANDUEL DFS STRATEGY REVIEW: Large-Field GPP Lineup Simulations (1/18/23)
RotoGrinders - Daily Fantasy Sports Advice · Jan 18, 2023 (1:00:36) · [Watch on YouTube](https://www.youtube.com/watch?v=pakvRcKsnXQ)

- [35:04](https://www.youtube.com/watch?v=pakvRcKsnXQ&t=2104s) "and once those lineups are in we just click over to the lineup simulation screen and there you go and you can press the button it runs a thousand Sims Monte Carlo Sims of each player based on the floor and the ceiling the median shows you the standard deviation of the lineup and the win percentage"
  - Takeaway: The lineup simulator runs 1,000 Monte Carlo simulations using player floors and ceilings and reports lineup median, standard deviation, and win percentage.

### DFS Q&A: How Do You Filter NFL Lineups to Avoid Dupes While Staying +EV?
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 27, 2025 (0:19:42) · [Watch on YouTube](https://www.youtube.com/watch?v=wdjc-z_h8m4)

- [6:35](https://www.youtube.com/watch?v=wdjc-z_h8m4&t=395s) "The the contest sim is going to do a better job than saber score is of grading lineups. It's taking into account uh the ownership in the field lineups. It's taking into account the payout structures. It's taking into account uh upside by how many how often your lineup gets to the top of the contest, which helps it have a positive ROI."
  - Takeaway: The speaker says contest simulation evaluates lineups using field-lineup ownership, payout structures, and how often a lineup reaches the top of the contest.

### Beat DFS Using The SaberSystem: 5 Principles for Maximum Profitability
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 29, 2024 (0:16:28) · [Watch on YouTube](https://www.youtube.com/watch?v=4jONT961JrM)

- [13:51](https://www.youtube.com/watch?v=4jONT961JrM&t=831s) "we simulate every contest on DraftKings 100,000 times using the real lineups played and the payout structure essentially replaying every contest 100,000 times calculating the expected Roi of every lineup and every player that played it"
  - Takeaway: Contest Flashback simulates each DraftKings contest 100,000 times using the actual lineups and payout structure to calculate expected ROI.

### DFS Q&A: How Do You Use Geomean to Reduce Dupes in NFL Showdown?
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 12, 2025 (0:19:45) · [Watch on YouTube](https://www.youtube.com/watch?v=UTQzHyEzDEw)

- [9:31](https://www.youtube.com/watch?v=UTQzHyEzDEw&t=571s) "remember each ROI for each contest sim is effectively a separate sorting metric. Hey, uh you know, ROI one is is different than ROI 2, different than ROI 3. It just so happens some lineups perform well in multiple contests, right?"
  - Takeaway: Contest simulations use separate ROI sorting metrics, though some lineups may rank well in multiple contests.

## 6. Large-field vs small-field strategy

47 videos, 83 transcript excerpts.


### How to Win NFL DFS Tournaments in 2026
Establish The Run · Sep 06, 2026 (1:03:32) · [Watch on YouTube](https://www.youtube.com/watch?v=A-PD6sZhvvY)

- [57:59](https://www.youtube.com/watch?v=A-PD6sZhvvY&t=3479s) "Yeah, I think the big difference between small field and large field is that in large field you have to get closer to the pure nuts, closest to the pure optimal that you can. Uh it's rare that anybody's going to hit the actual pure optimal, but you know, you have to get closer to that."
  - Takeaway: For large fields, the speaker recommends getting closer to the slate's pure optimal ceiling.
- [58:38](https://www.youtube.com/watch?v=A-PD6sZhvvY&t=3518s) "we've shown that double stacks are more uh viable and part of that is not just because of the game environment but it's also because if you don't hit that perfect game environment and you stack you know Almond Raw and Jameson Williams with Goth one one of them could hit 30 points and the other one could hit 15. And in small field, that's like really powerful that you still have that floor from the other one."
  - Takeaway: In small fields, double stacks can retain useful floor when one player hits 30 points and the other scores 15, even if the game does not produce a perfect ceiling environment.
- [1:00:18](https://www.youtube.com/watch?v=A-PD6sZhvvY&t=3618s) "the larger the field that you're playing, the more of an upside you need to hit, the path to creating more upside is ultimately through more balance in finding more players that can really outperform their salary. It's really hard to find a couple cheap players that really, really crush."
  - Takeaway: The larger the field, the more upside is needed; the speaker says balance and multiple players outperforming salary can create that upside.
- [1:01:03](https://www.youtube.com/watch?v=A-PD6sZhvvY&t=3663s) "Like has a real chance at getting 20 if you're playing the really really large field stuff. And I think that's where the data on the DST stuff really showed is that too much especially like really cheap chalk defenses that's just making the salary work. That stuff is okay, more okay in small field, really bad in large field."
  - Takeaway: For very large fields, the speaker favors roster spots with a real chance to score 20 and describes cheap chalk defenses used mainly to make salary work as much worse than in small fields.

### DFS Office Hours 10/5: Different build settings for different contests, impact of pool size on build
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 06, 2021 (1:17:26) · [Watch on YouTube](https://www.youtube.com/watch?v=7yKBIoYboE8)

- [11:44](https://www.youtube.com/watch?v=7yKBIoYboE8&t=704s) "if we over fade ownership slightly i think it is better than us under fading ownership slightly if our lineups are a little bit more contrarian for gpps right i think it's better than being a little too chalky same with sim variants"
  - Takeaway: When uncertain about GPP settings, the speaker favors slightly more ownership fade and contrarian lineups over being too chalky.
- [1:00:06](https://www.youtube.com/watch?v=7yKBIoYboE8&t=3606s) "we have a different factor of correlation and ownership and upside in the form of some variance than if we were playing a 150 max large field gpp these sliders are going to control basically the the parameters of how the lineups themselves are built and create different size stacks and different overall total ownership"
  - Takeaway: The speaker says lineup-building settings for a smaller-field contest differ from those for a large-field 150-max GPP, affecting correlation, ownership, variance, and stack size.
- [1:04:35](https://www.youtube.com/watch?v=7yKBIoYboE8&t=3875s) "when you have fewer lineups overall i think it's easier to just hand pick your individual lineups by looking at them visually and picking your favorite ones but also the fewer lineups you have the less nuance you can express in your exposures"
  - Takeaway: For a small set of entries, the speaker recommends visually selecting preferred lineups because exposure adjustments have less granularity.

### I Broke Down the 2025 Milly Maker Winning Lineups (Then Built a Process Around It)
925 Sports · Sep 02, 2026 (0:17:35) · [Watch on YouTube](https://www.youtube.com/watch?v=zQu7ablUMEk)

- [2:03](https://www.youtube.com/watch?v=zQu7ablUMEk&t=123s) "one thing I've noticed guys about these higher entry contests is that there's a lot of people that are just putting out terrible lineups as well to the point where it's actually kind of easier to finish in the top 20% for these contests than it is like single entry doubles because people are trying to get a little bit too unique"
  - Takeaway: The speaker says higher-entry contests can have weaker lineups than single-entry doubles, partly because entrants try too hard to be unique.
- [12:15](https://www.youtube.com/watch?v=zQu7ablUMEk&t=735s) "You do need to play the chalk to be successful in terms of winning GPPs, but you also need to get unique with your roster construction as well. Play chalk mixed in with some players that are not overly too chalky."
  - Takeaway: The recommended GPP approach is to combine chalk with less-chalky players rather than fading chalk or using only chalk.
- [12:25](https://www.youtube.com/watch?v=zQu7ablUMEk&t=745s) "about the average ownership of a GPP winning lineup fell between about 120 to 135. Again, depends on the week overall for the ownership, but typically around let's just say 127 on average. So chalkier lineups did tend to win, but you do need to get unique as well."
  - Takeaway: Winning lineups averaged about 120–135% total ownership, roughly 127% on average, while still needing some uniqueness.

### NFL DFS Week 1 DraftKings Strategy And Picks  Run The Sims With A Milly Maker Winner
Neil Orfield · Sep 12, 2026 (0:28:11) · [Watch on YouTube](https://www.youtube.com/watch?v=MhwZlTi-eJw)

- [1:53](https://www.youtube.com/watch?v=MhwZlTi-eJw&t=113s) "Uh I'll do $10 to $25 entry fee and a field size of 15,000 with a topheavy payout structure. I usually play large field GP. So I'm customizing for the types of contests that I play."
  - Takeaway: For his large-field contests, he configures the simulation for a 15,000-entry field and a top-heavy payout structure.
- [1:53](https://www.youtube.com/watch?v=MhwZlTi-eJw&t=113s) "if you're playing smaller field GPs, if you're playing a contest that has 3,000 entries in it, you're going to want to use the 3,000 field size. Uh so make sure you're adjusting for the types of contest that you're playing."
  - Takeaway: He advises matching the simulated field size to the contest, giving 3,000 entries as an example.
- [27:34](https://www.youtube.com/watch?v=MhwZlTi-eJw&t=1654s) "But if you are playing a contest with only 11 or only a thousand um entrance in it, you want to make sure that you're playing that type of field when you run the Sims. You don't want to do a 15,000 person field because you don't need to get as unique in a field of 1,000 as you do in a field of 15,000."
  - Takeaway: He says smaller fields require less lineup uniqueness than 15,000-entry fields and recommends simulating the actual contest field size.

### DFS Office Hours 7/29/21: Why avoiding duplication is important in DFS
SaberSim DFS - Daily Fantasy Sports Strategy · Jul 30, 2021 (0:27:16) · [Watch on YouTube](https://www.youtube.com/watch?v=U13Q_op4i-g)

- [20:18](https://www.youtube.com/watch?v=U13Q_op4i-g&t=1218s) "i'm pretty aggressive with my stands i generally take on a slate um i am often plays that i think are going to be over owned i'm more likely personally to just completely fade than i am to be under the field"
  - Takeaway: He says he often completely fades plays he expects to be overowned rather than merely playing them below the field’s ownership.
- [23:03](https://www.youtube.com/watch?v=U13Q_op4i-g&t=1383s) "we've talked about a lot here that stacking makes more sense on bigger slates and also smaller contests like in general larger stacks and more more commonly stacking makes sense on bigger slates smaller contests contests that people are unlikely to find the optimal the mathematical optimal themselves"
  - Takeaway: He says stacking and larger stacks generally make more sense on bigger slates and in smaller contests where opponents are less likely to find the mathematical optimum.
- [23:51](https://www.youtube.com/watch?v=U13Q_op4i-g&t=1431s) "the contests are so small that sometimes all you have to do is kind of just pick the right team pick the one team that scores the most runs and stacking is still viable because you're only competing against a thousand other people in the contest or something like that"
  - Takeaway: In small contests with roughly a thousand opponents, picking the highest-scoring team and stacking it can be enough to compete.

### DFS Army's Strategy Series MME Podcast   50 is the New 150
DFS Army - Daily Fantasy Sports · Jun 04, 2020 (0:18:56) · [Watch on YouTube](https://www.youtube.com/watch?v=CPsg0CX4_eU)

- [7:34](https://www.youtube.com/watch?v=CPsg0CX4_eU&t=454s) "if you're playing a 20 entry max right that you want to take stands on people you want to go almost all in on a few guys to really get over market on those guys right when you play usually 150 lineups people will tell you well you don't need to take quite as much stands"
  - Takeaway: The transcript contrasts 20-entry-max strategy, which calls for concentrated player stands, with the advice often given for 150 lineups to take fewer stands.
- [7:56](https://www.youtube.com/watch?v=CPsg0CX4_eU&t=476s) "well there i think is your fundamental flaw even if you're gonna go 150 i still think you need to play it more like you're playing at 20 max if you're gonna go that route but to me it's still not even worth it"
  - Takeaway: The speaker says that even a 150-lineup entry should use a strategy more like 20-max, while still arguing that 150 entries are not worthwhile in these contests.
- [14:51](https://www.youtube.com/watch?v=CPsg0CX4_eU&t=891s) "this is when you play 50. throw 50 in there don't throw 150 in there make your roi will be happy i think your game your bankroll will appreciate it"
  - Takeaway: For the high-dollar 150-max contest discussed, the speaker recommends entering 50 lineups instead of maxing out at 150.

### 2026 NFL DraftKings Strategy: Stop Making These Costly DFS Mistakes
Mayo Media Network · Aug 28, 2026 (1:05:48) · [Watch on YouTube](https://www.youtube.com/watch?v=SPjmh9bxUF4)

- [9:33](https://www.youtube.com/watch?v=SPjmh9bxUF4&t=573s) "single entry contest is one where everybody can only put in one. It's usually a capped field, smaller field versus your lotteryies, better payout structures, etc. They're great to play in. And it doesn't mean your single lineup strategy can't be used in single entry, but it's saying there's a big difference, Pat, between playing the $50 single entry and playing the $55 with 20K to first where everybody can have 50 teams"
  - Takeaway: He distinguishes capped, smaller-field single-entry contests from a contest where opponents may enter 50 lineups, even if you enter only one.
- [39:58](https://www.youtube.com/watch?v=SPjmh9bxUF4&t=2398s) "the 254 max or the 153 max is those tournaments aren't huge. I'm not playing against 147,000 people where I need to have the perfect lineup. I've made mistakes in those lineups and come second. I've won one of them before. I've come in third a bunch of times, seventh with like two duds in my lineup."
  - Takeaway: He says smaller 4-max and 3-max tournaments do not require a perfect lineup against a massive field and describes placing highly despite having lineup mistakes.
- [40:58](https://www.youtube.com/watch?v=SPjmh9bxUF4&t=2458s) "Instead of a 2504 max, you could play a $20. Oh, but the first prize sucks. What is it? Oh, it's 1,500 bucks. All right. How many times have you won $1,500 on DraftKings? Well, never yet. I'm still trying. All right, then you should be you should be ecstatic about the potential of that prize and you might actually have a shot at winning that prize."
  - Takeaway: He encourages weighing a more attainable $1,500 top prize in a $20 contest against chasing a much larger prize in a 250-max contest.

### DFS Tournament Strategy - How to Beat Small Field & Single Entry GPPs
Establish The Run · Sep 06, 2021 (0:37:26) · [Watch on YouTube](https://www.youtube.com/watch?v=Z79IcL2Cruk)

- [7:47](https://www.youtube.com/watch?v=Z79IcL2Cruk&t=467s) "i feel like wiggins is a good example of someone who plays very close to the optimal in these small fields but will make just the slightest tweaks uh to his lineup to get differentiated and in that style i think it does really lend itself to the super small field stuff under you know 200 or 300 because you're basically rolling out a cash lineup with just a few subtle tweaks to make sure you're not duplicated"
  - Takeaway: For super-small fields under 200 or 300 entries, the speakers describe using a near-optimal, cash-like lineup with slight adjustments to reduce duplication.
- [9:14](https://www.youtube.com/watch?v=Z79IcL2Cruk&t=554s) "when in reality it's almost the opposite where and you're in a small field tournament you don't need to perfect don't need to be perfect you just want to get less things right and the way to get less things right is to correlate your lineup you don't need to hit you know the 95th percentile outcome on every player across the board whereas when you are in these really large field tournaments you kind of do need that 95th percentile outcome"
  - Takeaway: Small-field lineups can win without every player reaching an extreme outcome, while large-field tournaments require more 95th-percentile outcomes.
- [15:55](https://www.youtube.com/watch?v=Z79IcL2Cruk&t=955s) "the mistakes the field make a lot of the time even though we suggest kind of a barbell approach which is you know mixing some chalk and low low owned guys the the field goes too far in each direction sometimes where they're overly chalky or they're overly contrarian and you do kind of find a have to find that sweet spot in the middle where you have a good mix"
  - Takeaway: The speakers recommend balancing chalk and low-owned players rather than being excessively chalky or excessively contrarian.

### DFS Q&A: How Do You Use Geomean to Reduce Dupes in NFL Showdown?
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 12, 2025 (0:19:45) · [Watch on YouTube](https://www.youtube.com/watch?v=UTQzHyEzDEw)

- [1:25](https://www.youtube.com/watch?v=UTQzHyEzDEw&t=85s) "anytime you kind of want different build parameters, whether that's minimax salary, whether that is rules, whether that is uh curating your player pool to be kind of smaller, right? Uh you're always going to want to do that in separate builds."
  - Takeaway: The speaker recommends separate builds when using different parameters, rules, or player pools.
- [6:18](https://www.youtube.com/watch?v=UTQzHyEzDEw&t=378s) "Every lineup in your pool is going to get a different ROI for every contest, right? It's going to have four ROIs. In this example, some of them might be high, some of them might be low, right?"
  - Takeaway: A lineup’s ROI can differ across contests, so its suitability may vary by contest.
- [7:21](https://www.youtube.com/watch?v=UTQzHyEzDEw&t=441s) "are optimized for that exact contest. Right? I'm not playing I'm not optimizing for only one of these and then putting that 150 into the others where they might not be the best lineups for those contests. Instead, I'm letting Saber say, "Hey, this is the best 150 for this contest, the best 150 for that one, the best 150 for that one, and then the last one.""
  - Takeaway: The speaker favors selecting lineups optimized separately for each contest rather than reusing one contest’s 150 lineups everywhere.

### NFL DFS Sims Tournament Strategy Week 1 | NFL DFS Strategy
Stokastic DFS - Daily Fantasy Sports Advice · Sep 11, 2026 (1:11:45) · [Watch on YouTube](https://www.youtube.com/watch?v=uMa9MQhf0fU)

- [52:01](https://www.youtube.com/watch?v=uMa9MQhf0fU&t=3121s) "It depends on what tournament you're playing. But also, dude, if you're playing, let's say, the um the power sweep is my favorite. I love the power sweep and the spy, the the 150 three max and then the $100 single entry."
  - Takeaway: He names the Power Sweep, Spy, 150, three-max, and $100 single-entry contests while discussing tournament-dependent lineup choices.
- [1:03:36](https://www.youtube.com/watch?v=uMa9MQhf0fU&t=3816s) "Now granted, this is for a large field tournament, so you aren't necessarily getting these same lineups if you're playing, you know, some smaller single entry stuff, but it does give us a pretty good idea of what we're able to get to."
  - Takeaway: He cautions that lineups shown for a large-field tournament may differ from those suited to smaller single-entry contests.

### The 3 Rules for Beating NFL Showdown and Single Game GPPs
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 09, 2021 (1:11:46) · [Watch on YouTube](https://www.youtube.com/watch?v=7T2VrpJIN1M)

- [5:07](https://www.youtube.com/watch?v=7T2VrpJIN1M&t=307s) "and what that really is trying to ballpark for you is if everyone that entered this max it out how many people would it take to fill up the contest the higher that number is the easier the contest is going to be because it just means that you're playing against weaker players on average"
  - Takeaway: They use effective entrants—contest entries divided by the entry limit—as a measure of contest difficulty, favoring higher values.
- [6:21](https://www.youtube.com/watch?v=7T2VrpJIN1M&t=381s) "so start with that foundation of 20 max then from there go to single entries and three max and so on and i just don't even mess around with cash"
  - Takeaway: Their contest-selection sequence starts with 20-max contests, then moves to single-entry and three-max contests.

### NFL Office Hours - Showdown Q&A
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 08, 2023 (1:01:37) · [Watch on YouTube](https://www.youtube.com/watch?v=Re6X-sC0P7A)

- [15:19](https://www.youtube.com/watch?v=Re6X-sC0P7A&t=919s) "I think the only time that it's going to be less than 10 is if you're playing super small field like I think less than 100 it might come down so basically what we're saying is that at a single entry less than 100 you probably don't even need the optimal to win you just need a a good solid lineup"
  - Takeaway: Showdown Sim diversity is described as generally 10, with a possible reduction for very small fields under 100 entries; in that small single-entry setting, a solid lineup may be sufficient.
- [55:49](https://www.youtube.com/watch?v=Re6X-sC0P7A&t=3349s) "honestly um I would say that risk-adjusted Roi is the safer option here Roi is a little riskier a little higher leverage here so this is going to really come down to a uh risk tolerance question right are you okay playing these Ultra leverage lineups or do you want to play something a little bit safer"
  - Takeaway: For a 20-max build, the transcript frames ROI versus risk-adjusted ROI as a risk-tolerance choice: ROI is riskier and higher leverage, while risk-adjusted ROI is safer.

### NFL DFS Strategy Masterclass: Game Theory, Stacking & How to Actually Win
Mayo Media Network · Sep 04, 2026 (1:09:42) · [Watch on YouTube](https://www.youtube.com/watch?v=oj36e7aIMHc)

- [13:34](https://www.youtube.com/watch?v=oj36e7aIMHc&t=814s) "And it's kind of actually flipped where in these really large field tournaments, if you're going to win the Million Maker, for example, sort of have to hit the nuts and have, you know, three different wide receivers at the 90th percentile. So, you might want to do, you know, a single skinny stack with, you know, Burrow to Chase and hope you get the alpha wide receiver game"
  - Takeaway: For large-field tournaments, the advice is to use a skinny stack that can capture an extreme ceiling outcome rather than spreading production across a heavier stack.
- [14:00](https://www.youtube.com/watch?v=oj36e7aIMHc&t=840s) "Small field tournament, opposite, right? Like we only need to be X amount of lineups. We don't need the nuts. We don't need to be perfect if we have the double of Burrow to Chase and Higgins, we don't necessarily need Chase to go for 40. He can get his 25, be kind of so-so, decent, you know, plus at his at his price, but not crazy so."
  - Takeaway: Small-field lineups can use a double stack and win without requiring a maximum ceiling game from every player.

### SaberSim's Unique Approach to Projecting Ownership
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 10, 2021 (1:28:00) · [Watch on YouTube](https://www.youtube.com/watch?v=zMdDPCaxXjg)

- [58:46](https://www.youtube.com/watch?v=zMdDPCaxXjg&t=3526s) "it's a blanket ownership projection for a large field gbp so imagine the mini max or the the flagship contest that night on draftkings or fanduel the flagship 150 max so yeah ownership will condense more at smaller fields"
  - Takeaway: The projections are for large-field GPPs, while ownership is expected to condense more in smaller fields.
- [59:46](https://www.youtube.com/watch?v=zMdDPCaxXjg&t=3586s) "let's say justin jefferson and naji harris are the chalkiest captains right um after the madison one goes away if they're 18 in large field right it might be 30 in a single entry so if you're making a determination that the optimal the optimal ownership of jefferson is like 25 right"
  - Takeaway: The speaker illustrates that a captain owned at 18% in a large field might be owned at 30% in single entry, so contest-specific ownership can differ.

### DFS Q&A: How Should You Handle NFL Late Swap Between Builds?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 21, 2025 (0:27:24) · [Watch on YouTube](https://www.youtube.com/watch?v=QJ4wmImXx5M)

- [17:01](https://www.youtube.com/watch?v=QJ4wmImXx5M&t=1021s) "But, I'd say breaking up into different builds. Like maybe you have a 150 and then multiple 20 maxes. Okay. Run the 150 by itself. Maybe run one build with all your 20 maxes. Remember, you can rename these so to, you know, better track them."
  - Takeaway: The speaker suggests separating a 150-max contest set from multiple 20-max contests into different builds.
- [20:32](https://www.youtube.com/watch?v=QJ4wmImXx5M&t=1232s) "Yeah, absolutely. Right. So, you know, if a even if a player's 1% owned, 2% owned, right? If you have 6%, 10%, 15%, right? Uh that is that is a lot of leverage on the field."
  - Takeaway: Having 6%, 10%, or 15% exposure to a player projected for 1% or 2% ownership is described as substantial leverage over the field.

### DraftKings Showdown Strategy for Seahawks vs Lions | JSN Captain + Game Theory Breakdown
One Week Season · Sep 30, 2024 (0:43:25) · [Watch on YouTube](https://www.youtube.com/watch?v=OTvIy-Jk96U)

- [14:04](https://www.youtube.com/watch?v=OTvIy-Jk96U&t=844s) "I'm going to pull up a line or a a contest here we typically go kind of smaller field single entry so I'm just going to jump into the hard count it's actually only 411 entries do is that fine or you want to go something a little I don't know if there's something little bigger that's fine hard counts good"
  - Takeaway: The hosts use a contest with 411 entries as an example of their typical smaller-field, single-entry approach.
- [28:40](https://www.youtube.com/watch?v=OTvIy-Jk96U&t=1720s) "what that also tells you is in the big tournament with you know in a large tournament there going to be tons of this lineup entered and in a small tournament there's almost still certainly to be duplication"
  - Takeaway: The speaker warns that an optimizer-generated lineup may be duplicated in both large and small tournaments.

### Studying the Sharps: Constructing DFS Lineups with Jordan Cooper
DraftKings · Oct 05, 2021 (1:24:55) · [Watch on YouTube](https://www.youtube.com/watch?v=1qKHG9mSEfI)

- [1:20:25](https://www.youtube.com/watch?v=1qKHG9mSEfI&t=4825s) "amount of options so much of the field is not concern not not prioritizing uh dupe factor so what ends up happening is that in that thousand lineup contest there may be 950 lineups that have at least one duplicate of it which means all 950 lineups are now set giving the eevee of their lineups to the 50 that remain unique so i'd rather play one of those 50 uniques no matter what"
  - Takeaway: In a 1,000-lineup contest example, Cooper says 950 lineups could have a duplicate and favors one of the 50 unique lineups.
- [1:21:21](https://www.youtube.com/watch?v=1qKHG9mSEfI&t=4881s) "we're gonna see a showdown to open uh the nfl season 473 000 entries on draftkings you download the csv afterwards and you're going to find that 92 of the lineups have been duplicated and some of those lineups have been duplicated hundreds some thousands of times"
  - Takeaway: Cooper cites an upcoming 473,000-entry DraftKings showdown and says 92 of the lineups had been duplicated, with some duplicated hundreds or thousands of times.

### DFS Q&A: Navigating NFL Late Swap
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 18, 2024 (0:30:32) · [Watch on YouTube](https://www.youtube.com/watch?v=8qVskFOoEGE)

- [9:37](https://www.youtube.com/watch?v=8qVskFOoEGE&t=577s) "our contest selection recommendation are to play 25 to 50% of your bankroll allocation into single entries and three Maxes play the other 50 to 100% I'm sorry 50 to 75% in 20 Maxes and 150 Maxes now based on our back testing this helps to smooth out variants and leads to users needing a smaller bankroll to weather the swings of DFS"
  - Takeaway: The recommended bankroll allocation is 25–50% for single-entry and three-max contests and 50–75% for 20-max and 150-max contests, which the speaker says helps smooth variance.
- [11:12](https://www.youtube.com/watch?v=8qVskFOoEGE&t=672s) "all you're doing is saying hey I'm only going to put my 10 best lineups into the contest and I'm not going to put my 11 through 20th best lineups into the contest that is okay to do so don't think that you have to max out the contest if you decide to play it you can enter less than the maximum that is totally cool"
  - Takeaway: Players do not have to max out a contest and may submit only their preferred lineups.

### Why is avoiding duplication important in DFS?
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 16, 2021 (0:08:40) · [Watch on YouTube](https://www.youtube.com/watch?v=MCss_MdowIc)

- [0:58](https://www.youtube.com/watch?v=MCss_MdowIc&t=58s) "contest with their single entry lineup you guys you never want to do that so even if you're going to be a single entry player you're just going to play one lineup every night you should be entering it into all the single entry contests first and if you need to get more action you only want to enter it one time into the multi-entry contest"
  - Takeaway: A single-entry player should enter their lineup in single-entry contests first and, if seeking more action, enter it only once in a multi-entry contest.
- [7:10](https://www.youtube.com/watch?v=MCss_MdowIc&t=430s) "you're playing contests that have like sometimes 100 000 people on a single showdown lineup this maybe even becomes the primary factor our goal in creating an unduplicated or a very minimally duplicated lineup becomes so much higher than wanting to fade ownership in terms of finding leverage"
  - Takeaway: For NFL showdown contests with sometimes 100,000 entrants, the speaker says creating an unduplicated or minimally duplicated lineup may become more important than fading ownership for leverage.

### DFS Q&A: How SaberSim Creates Its Ownership Projections
SaberSim DFS - Daily Fantasy Sports Strategy · Jun 03, 2023 (0:24:23) · [Watch on YouTube](https://www.youtube.com/watch?v=JnVogCYAHgY)

- [7:03](https://www.youtube.com/watch?v=JnVogCYAHgY&t=423s) "a lineup in that is a lineup That is optimized for a bigger contest where you're going to need a higher score to win is much more likely to win a smaller contest rather than a lineup That is optimized for a smaller contest trying to win a bigger contest"
  - Takeaway: The speaker favors using lineups optimized for larger contests in smaller contests rather than the reverse.
- [8:07](https://www.youtube.com/watch?v=JnVogCYAHgY&t=487s) "these contests where you have more entries where the entry limit is higher uh if you are building for that you know the one of those items can probably take down the single entry as opposed to building you know single entry lineups and then putting them into a 20 Max"
  - Takeaway: The speaker recommends building to the higher entry limit when choosing between contest settings such as single-entry and 20-max.

### DFS Q&A: How do I navigate NFL late swap?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 09, 2022 (1:07:37) · [Watch on YouTube](https://www.youtube.com/watch?v=uvDTL8e6Ipo)

- [45:30](https://www.youtube.com/watch?v=uvDTL8e6Ipo&t=2730s) "one there's only five players instead of six and two you don't have to pay more to roster a player at mvp so the the number of viable lineups is so much smaller and it's just so hard to win with a unique lineup so i'm skipping it"
  - Takeaway: The speaker says FanDuel NFL single-game contests have fewer viable lineups because they use five players and do not charge extra salary for the MVP, making unique lineups harder.
- [45:47](https://www.youtube.com/watch?v=uvDTL8e6Ipo&t=2747s) "i would say i think if i were playing it i would probably lean a little bit more on playing smaller fields and maybe focusing more on the elevator contests and playing way less of my bankroll like if i was going to play i'd probably play like half a percent of my bankroll fanduel"
  - Takeaway: For FanDuel NFL single-game play, the speaker would favor smaller fields and lower bankroll exposure.

### How to Build Winning NFL DFS Showdown Lineups on DraftKings & FanDuel (2024)
Occupy Fantasy · Oct 07, 2024 (1:22:41) · [Watch on YouTube](https://www.youtube.com/watch?v=W9FWB82PwNs)

- [5:42](https://www.youtube.com/watch?v=W9FWB82PwNs&t=342s) "In general for DraftKings, start your captain. Start your lineup with a captain who isn't projected for more than 20% captain ownership. All right. Let's go to occupy model. Let's sort by draft kings captain ownership."
  - Takeaway: For DraftKings small-field GPPs, the guidance starts with a captain projected at no more than 20% captain ownership.
- [23:54](https://www.youtube.com/watch?v=W9FWB82PwNs&t=1434s) "Yeah, generally and in large field you're looking for that generally less than 10% not necessarily less than 20% owned player."
  - Takeaway: For large-field contests, the speaker says to look generally for a player below 10% ownership, rather than merely below 20%.

### Learn How Maximize SaberSim's New Contest Sims
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 24, 2023 (1:17:07) · [Watch on YouTube](https://www.youtube.com/watch?v=mZzskOQAz2k)

- [12:53](https://www.youtube.com/watch?v=mZzskOQAz2k&t=773s) "so you'll see in top heavier contests the contest Sims are going to incentivize you more to playing more contrarian builds your Roi strictly your Roi there is also going to be a lot higher your highest Roi of your build is going to be higher for these top after your contests"
  - Takeaway: The speakers say top-heavy contests favor more contrarian builds and can produce higher lineup ROI.
- [23:00](https://www.youtube.com/watch?v=mZzskOQAz2k&t=1380s) "but the percent of first is so much higher in the flagship that you get way more when you win with this lineup and so even though the the cash rate for the lineup was way higher in the solo shot which is expected it's a softer field it's easier to Cache um the win rate um was about the same but the ROI is way higher in the flagship"
  - Takeaway: In the example, the flagship had much higher ROI than the solo shot despite a lower cash rate, because first place paid more and win rates were similar.

### If you’re not late-swapping in NFL DFS, you’re leaving money on the table
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 01, 2021 (1:02:30) · [Watch on YouTube](https://www.youtube.com/watch?v=S2p7LVEeXy4)

- [15:57](https://www.youtube.com/watch?v=S2p7LVEeXy4&t=957s) "a common question that comes up here is if you've got a bunch of different contest types here uh for single entry three max 20 max pick a slider setting that is kind of in between uh the different options a median somewhat value so maybe for this in particular again this is a showdown the sliders look a little bit different but i might pick like a 20 max 10 to 50 000 entrance which is fairly in between everything here"
  - Takeaway: For mixed contest types, the suggested slider setting is an intermediate value, with a 20-max contest offered as an example.
- [43:00](https://www.youtube.com/watch?v=S2p7LVEeXy4&t=2580s) "with cache you're probably going to keep a similar lineup no matter how your cache line is doing but with the gpp like if it's doing really really badly or really really well you're gonna go uh less chalky if it's doing badly and and more chalky if it's doing really well"
  - Takeaway: The speakers recommend maintaining a similar cash lineup but shifting GPP lineups toward less chalk when doing poorly and more chalk when doing well.

### DFS Q&A: How are SaberSim's ownership projections calculated?
SaberSim DFS - Daily Fantasy Sports Strategy · Jun 15, 2022 (0:58:03) · [Watch on YouTube](https://www.youtube.com/watch?v=MGO5rVk8I7M)

- [19:36](https://www.youtube.com/watch?v=MGO5rVk8I7M&t=1176s) "yeah so a lot of times for single entry the way i like to use sabersim or how i kind of recommend people using it uh is allowing sabersim to you know if you're used to building single entry i think a lot of times that's kind of more of a hand building type approach right people that are playing one lineup of slate used to building it generally by hand"
  - Takeaway: For single-entry contests, Jordan recommends using SaberSim to create a pool and then hand-picking the final lineup rather than relying only on a hand-built lineup.
- [42:18](https://www.youtube.com/watch?v=MGO5rVk8I7M&t=2538s) "that's a harder question to answer mostly because it misses contest nuance right in a single entry contest uh or maybe a contest where you're trying to beat a hundred or a thousand other people right it might be perfectly fine playing a guy like cease at his projection uh and ownership right even if he was 60 percent owned in a single entry contest"
  - Takeaway: Whether chalk is worth playing depends on contest size; Jordan says a highly owned player may still be fine in single-entry contests.

### DFS Q&A: Product Ownership and Geometric Mean
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 11, 2022 (0:56:29) · [Watch on YouTube](https://www.youtube.com/watch?v=eVWhJ0Cy2FY)

- [29:19](https://www.youtube.com/watch?v=eVWhJ0Cy2FY&t=1759s) "if you're playing really large field stuff like if you're if your contests have I would say greater than 50,000 total lineups right like the same way we think about the sliders here right like if you're playing the largest field contest greater than 50,000 I would use this more as the way I described where I'm trying instead to just limit lineups"
  - Takeaway: For contests with more than 50,000 lineups, the speaker recommends using the ownership rule mainly to limit heavily duplicated lineups.
- [29:56](https://www.youtube.com/watch?v=eVWhJ0Cy2FY&t=1796s) "if you're playing the smaller 20 Max kinds of contest anything I would say under that 50,000 total lineups or under especially like 10,000 total lineups then I think this actually becomes an interesting or somewhat useful tool to actually try to get a unique build"
  - Takeaway: For smaller contests—especially those under 10,000 lineups—the speaker says the rule may be useful for trying to produce a unique build.

### How to Crush NFL Showdowns on Fanduel and Draftkings Using the DFS Army Domination Station Optimizer
DFS Army - Daily Fantasy Sports · Sep 08, 2020 (0:51:20) · [Watch on YouTube](https://www.youtube.com/watch?v=ehza4xs_VSc)

- [3:09](https://www.youtube.com/watch?v=ehza4xs_VSc&t=189s) "i want to be clear this is not something i would use in cash games for cash games and maybe a single entry you just make the lineup you can use the projections as a guide"
  - Takeaway: The speaker distinguishes this mass-multi-entry approach from cash games and possibly single-entry contests, where they recommend making the lineup directly and using projections as a guide.

### DFS Q&A: How Do Contest Sims Work for Small vs. Large-Field Contests?
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 12, 2023 (0:18:57) · [Watch on YouTube](https://www.youtube.com/watch?v=h9O1DRC4ABo)

- [8:54](https://www.youtube.com/watch?v=h9O1DRC4ABo&t=534s) "and the big update here is the field lineups right right so the field lineups for Showdown are only going to be one set of field lineups but for like NFL classic for MLB classic here you're going to see field lineups for 13 sets of ownership here right and those are taken into account low stakes medium Stakes high stakes uh 150 versus 20 Max versus single entry"
  - Takeaway: SaberSim uses one field-lineup set for Showdown and 13 ownership sets for NFL and MLB classic, accounting for stake levels and 150-max, 20-max, and single-entry contests.

### DFS Q&A: What is a self-sim?
SaberSim DFS - Daily Fantasy Sports Strategy · Jul 11, 2024 (0:56:19) · [Watch on YouTube](https://www.youtube.com/watch?v=JjEqfaORNpA)

- [2:27](https://www.youtube.com/watch?v=JjEqfaORNpA&t=147s) "On saber Sim we create a dozen different fields for different contest types we say in the flagship we think people are going to play like this in the low stake single entry we think people are going to play like this in win or take alls we think people are going to play like this"
  - Takeaway: The speaker says SaberSim creates different expected fields for contest types including flagship, low-stakes single-entry, and win-or-take-all contests.

### DFS Q&A: Avoiding Dupes on Small NFL Slates
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 21, 2025 (0:27:22) · [Watch on YouTube](https://www.youtube.com/watch?v=KDQWYsMCP8w)

- [23:30](https://www.youtube.com/watch?v=KDQWYsMCP8w&t=1410s) "because there is one contest you primarily care about and others that you don't, then I would only sim the one contest that you care about. If you actually care about the other contests in your set, but you still only want to play, say 20, say you're playing a 20 max, a three max, and a single entry, right?"
  - Takeaway: The presenter recommends simulating only the priority contest if the other contests do not matter to the player.

### Master The Art of NFL DFS Showdowns
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 30, 2024 (0:44:55) · [Watch on YouTube](https://www.youtube.com/watch?v=Fr2FxzlztT4)

- [24:47](https://www.youtube.com/watch?v=Fr2FxzlztT4&t=1487s) "these next tips in particular are going to be best suited for large field gpps they can will be useful for smaller tournaments but you will want to adjust the way you're applying these rules accordingly and as a very broad rule of thumb the strategies that I'm about to talk about here I mostly employ for contests that are over 50,000 total entrance"
  - Takeaway: The lineup-construction tips are aimed mainly at large-field GPPs, particularly contests with over 50,000 entries, and should be adjusted for smaller tournaments.

### NFL DraftKings Showdown Contest Strategy, Captain's Slot and Tips
DraftKings · Oct 15, 2018 (0:10:57) · [Watch on YouTube](https://www.youtube.com/watch?v=iEGNBY_zeSc)

- [9:03](https://www.youtube.com/watch?v=iEGNBY_zeSc&t=543s) "uh they aren't playing 150 lineups in a on every slate or whatnot. So, um you you do want to have a way to kind of narrow it down uh to what you to what you feel is a is is a sound play."
  - Takeaway: For players not entering 150 lineups on every slate, Raybon recommends narrowing choices to plays they consider sound.

### DFS Q&A: How do I best utilize the dupe metric in the contest sims?
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 03, 2023 (1:39:07) · [Watch on YouTube](https://www.youtube.com/watch?v=ETNpMZGSNCs)

- [50:56](https://www.youtube.com/watch?v=ETNpMZGSNCs&t=3056s) "there is a little bit more of a discrepancy between different contest types I have found that splitting off your single and three single entry and three max contests into one kind of bucket and splitting off your 20 Max and 150 Max contest into a different bucket is generally a pretty good way to go where 20 Max and 150 Maxes generally pretty close settings"
  - Takeaway: For classic slates, Jordan recommends grouping single-entry and three-max contests separately from 20-max and 150-max contests because their settings are generally closer within those groups.

### DFS Q&A: Walking Through the NFL Late Swap Process
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 26, 2025 (0:24:26) · [Watch on YouTube](https://www.youtube.com/watch?v=CgfglAjd2ys)

- [20:12](https://www.youtube.com/watch?v=CgfglAjd2ys&t=1212s) "Saber score is when you come into saber score you actually see what the saber scores are with this eye icon right it is a combination of three variables projection percentile and a negative weight on ownership"
  - Takeaway: SaberScore combines projection, percentile, and a negative ownership weight.

### DFS Q&A: How Do You Reduce Dupes in Showdown?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 07, 2025 (1:05:02) · [Watch on YouTube](https://www.youtube.com/watch?v=JuOzj5ZOQHk)

- [9:51](https://www.youtube.com/watch?v=JuOzj5ZOQHk&t=591s) "Sometimes people like different rules or different uh player pools or, you know, different minax salaries filters. just like there's a number of different reasons, different minimax exposures. Uh it it just depends how much you want to customize your lineups on like a per contest basis here"
  - Takeaway: The speaker says separate builds can be customized per contest using different rules, player pools, salary filters, and minimum/maximum exposures.

### HOW TO WIN ON DRAFTKINGS NFL SHOWDOWN: LINEUP BUILDING TIPS
Alvin Zeidenfeld · Sep 03, 2019 (0:14:55) · [Watch on YouTube](https://www.youtube.com/watch?v=lyaKCYf1LrQ)

- [2:36](https://www.youtube.com/watch?v=lyaKCYf1LrQ&t=156s) "as you get to 150 line ups you are still focused on those things but you're taking more of a diverse approach so if I was only gonna build three or 20 line ups I would probably hone in I'm just a handful of captains"
  - Takeaway: The speaker describes taking a more diverse approach across 150 lineups, while focusing on a handful of captains for three- or 20-lineup builds.

### I Gave the DFS Army Optimizer the SHOWDOWN CODE… Here’s What It Built!
Ibe's DFS Sports Betting · Oct 01, 2026 (0:11:51) · [Watch on YouTube](https://www.youtube.com/watch?v=sBOEt7d3dM4)

- [2:16](https://www.youtube.com/watch?v=sBOEt7d3dM4&t=136s) "and who else are throwing in our lineups to kind of get different because it's on showdowns. A lot of people want to be building a lot of the same looking lineups. So you got to try to get different if you really want to try to separate yourself."
  - Takeaway: He recommends differentiating showdown lineups because many people build similar-looking lineups; no distinct strategy by contest size is stated.

### DRAFTKINGS & FANDUEL DFS STRATEGY REVIEW: PROJECTION VS OWNERSHIP EXPLOIT (1/4/23)
RotoGrinders - Daily Fantasy Sports Advice · Jan 04, 2023 (1:21:28) · [Watch on YouTube](https://www.youtube.com/watch?v=x2vfd9rf5S8)

- [46:18](https://www.youtube.com/watch?v=x2vfd9rf5S8&t=2778s) "smaller field contests are typically you're playing lineups that are you're focusing a little bit more projection than ownership right although there's more available leverage for you and in large field a lot of times you know you're not you're not throwing in your cash lineup but you're also probably not throwing in you know some garbage lineup with all one percent players you're trying to find where that balance is"
  - Takeaway: The speaker says smaller-field play generally emphasizes projection more, while large-field play seeks a balance rather than using either a cash lineup or an extremely low-owned lineup.

### I Studied 230,000 NFL DFS Lineups; Here's What Will Win in 2026
DFS Army - Daily Fantasy Sports · Jul 27, 2026 (0:25:36) · [Watch on YouTube](https://www.youtube.com/watch?v=rz2HFI7diGY)

- [18:25](https://www.youtube.com/watch?v=rz2HFI7diGY&t=1105s) "ownership scaling with field size. That's just pure logic, right? The high the larger the field, the lower the ownership you need to have in your lineup to get unique. And the smaller the field, the less uniqueness you you need in your lineup. So those you guys looking for single entry advice. All right. What about a 100 man or 200 man contest? Do not worry about total ownership in those. It it does not affect those types of um contests."
  - Takeaway: The speaker recommends more lineup uniqueness as field size grows and says total ownership does not affect 100- or 200-entry contests.

### NFL DFS Showdown Research - Results From 50 Winning Milli-Maker Lineups in 2021
Adam Newman · Sep 07, 2022 (0:12:30) · [Watch on YouTube](https://www.youtube.com/watch?v=HfQcvFwIECA)

- [3:58](https://www.youtube.com/watch?v=HfQcvFwIECA&t=238s) "so just things to consider when you're playing that large of a field and you want to try to take you want to chop the pot with as few people as possible uh so you there's a high risk of reward with those types of things"
  - Takeaway: For a large field, the speaker emphasized trying to split the pot with as few people as possible and described that approach as high risk.

### High Level Showdown Strategy + Super Bowl Stuff with Cody Main and Colin Drew
Establish The Run · Feb 04, 2022 (0:55:18) · [Watch on YouTube](https://www.youtube.com/watch?v=i98ljRFANdA)

- [40:15](https://www.youtube.com/watch?v=i98ljRFANdA&t=2415s) "maybe it's leaving salary on the table but still building a really good correlated lineup maybe it's doing like what dribby mentioned and just flipping uh captains we're we're in the dome a wide receiver captain's going to get outsized projections in terms of ownership and borough would be really low on"
  - Takeaway: For smaller-field single-entry or three-max play, the speaker recommended using one or two uniqueness levers rather than going far off the board.

### How To Use The Stokastic NFL DFS Pre-Contest Sims Tool | NFL DFS Contest Simulations
Stokastic DFS - Daily Fantasy Sports Advice · Sep 07, 2023 (0:10:35) · [Watch on YouTube](https://www.youtube.com/watch?v=4PFRCiUGPec)

- [3:49](https://www.youtube.com/watch?v=4PFRCiUGPec&t=229s) "so how you should select this is whatever closest mirrors the contest that you're playing in in the payout structure so you're playing something that's really flat that only pays out say five or ten percent of the prize pool the first place you want to pick one of those options if you're playing more of a large field tournament with a more top heavy payout it could be 20 25 30"
  - Takeaway: The tool's simulated ROI payout setting should mirror the contest's payout structure: flatter contests pay a smaller share to first, while more top-heavy large-field tournaments may use 20, 25, or 30.

### Field Lineups Explained
 ·  · [Watch on YouTube](https://www.youtube.com/watch?v=DHKY694-I_M)

- [1:37](https://www.youtube.com/watch?v=DHKY694-I_M&t=97s) "Evan Ingram goes from 29% owned at the low stake single entry to 47% owned at the high stake single entry"
  - Takeaway: In the example given, Evan Engram’s projected ownership is higher in the high-stakes single-entry contest than in the low-stakes single-entry contest.

### DRAFTKINGS & FANDUEL DFS STRATEGY REVIEW: Large-Field GPP Lineup Simulations (1/18/23)
RotoGrinders - Daily Fantasy Sports Advice · Jan 18, 2023 (1:00:36) · [Watch on YouTube](https://www.youtube.com/watch?v=pakvRcKsnXQ)

- [13:46](https://www.youtube.com/watch?v=pakvRcKsnXQ&t=826s) "and especially when we come to large field gpps the larger the contest that means the more we're willing to drop right so if you just played like the top like hit this lineup right here 184 like this may be fine in like a hundred man 300 man type of content maybe maybe that's fine it's still not that much leverage"
  - Takeaway: The speaker says larger contests justify dropping more projection for ownership leverage, while a lineup with 184 ownership may be acceptable in a 100- or 300-entry contest.

### DFS Q&A: For the 20-Max and 150-Max contest do you use the same pool?
SaberSim DFS - Daily Fantasy Sports Strategy · May 25, 2024 (0:58:29) · [Watch on YouTube](https://www.youtube.com/watch?v=PRtm5_i9qqQ)

- [34:39](https://www.youtube.com/watch?v=PRtm5_i9qqQ&t=2079s) "if you're if you're on sabersim standard or sabersim Pro then I think it makes a little bit more sense to run different builds because your greatest tool to affect like the differences in strategy between those contests become your slider settings right so in this case you know your single entry you're playing your your slider settings are best at like nine and six but if you're your large field 150 Max tournaments it's 10 and eight"
  - Takeaway: For Standard or Pro users, he recommends separate builds for contest types and using different slider settings for single-entry and large-field 150-max contests.

### Beat DFS Using The SaberSystem: 5 Principles for Maximum Profitability
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 29, 2024 (0:16:28) · [Watch on YouTube](https://www.youtube.com/watch?v=4jONT961JrM)

- [6:12](https://www.youtube.com/watch?v=4jONT961JrM&t=372s) "fill contests from lowest to highest entry fee this will again help you play against the easiest competition first but also spread your money out into as many lineups and contests as possible the goal here should be playing roughly an even mix of single entry in three Max and 20 Max and 150 Max contests"
  - Takeaway: The recommended contest mix is roughly even among single-entry, 3-max, 20-max, and 150-max contests, filling from lowest to highest entry fee.

### Lions vs Panthers - SNF Sunday Sweatdown | NFL Week 4 | DFS Picks, Plays & Process
Ship It Nation · Oct 05, 2026 (1:05:29) · [Watch on YouTube](https://www.youtube.com/watch?v=xJlvummhIfI)

- [48:08](https://www.youtube.com/watch?v=xJlvummhIfI&t=2888s) "But what we can do is we can predict how the field's going to build and build against it. And I think just doing that more middling type of build where you're not as stars and scrubs heavy, you're not playing the traumains of the world when everybody's playing them to to afford Gibbs and and a Monra and both quarterbacks."
  - Takeaway: The speaker advocated anticipating popular stars-and-scrubs builds and countering them with more middling constructions.

## 7. Showdown ownership: CPT vs FLEX and captain leverage

21 videos, 26 transcript excerpts.


### The 3 Rules for Beating NFL Showdown and Single Game GPPs
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 09, 2021 (1:11:46) · [Watch on YouTube](https://www.youtube.com/watch?v=7T2VrpJIN1M)

- [48:20](https://www.youtube.com/watch?v=7T2VrpJIN1M&t=2900s) "possible is almost always going to use a quarterback at uh captain because you get the one and a half multiplier on the largest overall uh point but i think the other reason for this as well is that the quarterback is correlated to a lot of positions so that's a very popular play"
  - Takeaway: They say traditional optimizers commonly select a quarterback at captain because of the multiplier, projection, and correlation with other positions.
- [50:42](https://www.youtube.com/watch?v=7T2VrpJIN1M&t=3042s) "somebody like brady i actually maybe even would go down as low as 10 percent uh which is going to um drop me down to about half of what we expect a field to be at and then you can kind of use this leverage score this negative leverage score in this uh case to make a determination of how leveraged against the field you want to be on brady captain lineups here"
  - Takeaway: They suggest reducing Brady’s captain exposure, potentially to 10%, and using leverage relative to expected field exposure to assess the stance.

### How to be Profitable Playing NFL DFS Showdown Slates
925 Sports · Sep 10, 2026 (0:19:55) · [Watch on YouTube](https://www.youtube.com/watch?v=kVhN3OfbEBs)

- [5:54](https://www.youtube.com/watch?v=kVhN3OfbEBs&t=354s) "Typically speaking, it's a player that's around 10% on average. That can be the difference. So, between a player at 1% really going off that like people didn't expect or very chalky player hitting."
  - Takeaway: The transcript describes an average Captain ownership around 10% and notes that both a 1%-owned Captain hitting and a very chalky Captain hitting can make the difference.
- [6:04](https://www.youtube.com/watch?v=kVhN3OfbEBs&t=364s) "And then about when you use the 1.5x multiplier about 24 fantasy points for their projected outcome. And in regards to that ownership we can see it is a little bit spread out guys like about 28% of the optimal captain choices were under 5% 16% were over 20%."
  - Takeaway: The cited optimal Captain ownership distribution had about 28% of choices under 5% ownership and 16% over 20%; the transcript also mentions an approximately 24-point projected-outcome bar with the 1.5x multiplier.

### NFL DraftKings Showdown Contest Strategy, Captain's Slot and Tips
DraftKings · Oct 15, 2018 (0:10:57) · [Watch on YouTube](https://www.youtube.com/watch?v=iEGNBY_zeSc)

- [1:04](https://www.youtube.com/watch?v=iEGNBY_zeSc&t=64s) "Actually, what you want to do is you want to find the guy who is in that middle to lower tier, who's who's ceiling he who can kind of match the ceiling of some of those upside guys."
  - Takeaway: Consider a middle- or lower-tier player at captain when that player's ceiling can match the ceiling of higher-tier options.
- [9:42](https://www.youtube.com/watch?v=iEGNBY_zeSc&t=582s) "if you're saying, "Hey, uh you know, this quarterback at the most expensive price is going to be worth it in the captain spot where I'm paying an extra 1.5 you know, for him." Uh that means he's probably going to have to get some rushing touchdowns"
  - Takeaway: An expensive quarterback at captain may need rushing touchdowns to justify the 1.5× captain cost when his receivers could offer comparable value.

### 2025 HOW TO PLAY NFL DRAFTKINGS SHOWDOWN
DFS Army - Daily Fantasy Sports · Aug 23, 2025 (0:10:32) · [Watch on YouTube](https://www.youtube.com/watch?v=-ZBpaHty068)

- [2:45](https://www.youtube.com/watch?v=-ZBpaHty068&t=165s) "So again the field owns quarterbacks at a 28 to 35% level whereas the optimal captain rate is down closer to 20%. So there is leverage by simply either not using quarterbacks at captain or using less than what you normally would or what the field is doing."
  - Takeaway: The transcript says quarterbacks are captained by the field at 28–35%, compared with an optimal captain rate closer to 20%.
- [3:28](https://www.youtube.com/watch?v=-ZBpaHty068&t=208s) "Even on FanDuel that favors wide receivers, the field ownership for running backs the captain spot is tends to be in the 22 to 26% range. Whereas running back optimal rates are well over 30, closer to 35%. Similar for wide receivers, the field is about 10% too low on captain wide receiver than they should be."
  - Takeaway: The transcript says the field underuses running backs and wide receivers at captain relative to their stated optimal rates.

### High Level Showdown Strategy + Super Bowl Stuff with Cody Main and Colin Drew
Establish The Run · Feb 04, 2022 (0:55:18) · [Watch on YouTube](https://www.youtube.com/watch?v=i98ljRFANdA)

- [19:56](https://www.youtube.com/watch?v=i98ljRFANdA&t=1196s) "too much of the field is is playing their captain quarterback teams with zero or one pass catchers and like when you think about how that's gonna work like if you have matt stafford as your captain and just pair him with cooper cup like it's so much more likely"
  - Takeaway: The speaker said quarterback-captain lineups should generally include two or more pass catchers from that quarterback's team.
- [25:59](https://www.youtube.com/watch?v=i98ljRFANdA&t=1559s) "we've seen 85.2 percent of top 1 percent lineups uh pair their captain wide receiver with the quarterback compared to just 77.4 percent of the field so the field is doing like what you're talking about with cup more often than it's winning now"
  - Takeaway: Top-one-percent lineups paired a wide receiver captain with his quarterback 85.2% of the time, versus 77.4% for the field.

### DFS Office Hours 10/5: Different build settings for different contests, impact of pool size on build
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 06, 2021 (1:17:26) · [Watch on YouTube](https://www.youtube.com/watch?v=7yKBIoYboE8)

- [42:05](https://www.youtube.com/watch?v=7yKBIoYboE8&t=2525s) "if this number was 20 and the field was going to roster him at 25 30 35 i would probably be more inclined to fade him because i think there's kind of negative leverage there"
  - Takeaway: The speaker would consider fading a player projected to be optimal captain 20% of the time if the field is expected to roster him at 25–35%.

### How to Crush NFL Showdowns on Fanduel and Draftkings Using the DFS Army Domination Station Optimizer
DFS Army - Daily Fantasy Sports · Sep 08, 2020 (0:51:20) · [Watch on YouTube](https://www.youtube.com/watch?v=ehza4xs_VSc)

- [22:44](https://www.youtube.com/watch?v=ehza4xs_VSc&t=1364s) "the next is you tab over and click on the mvp tab remember the flex tab controls the flex position the mvp tab little info box toggle the mvp box to set mvp exposures so we'll take a look this is the mvp and from here we can actually control our exposures"
  - Takeaway: The speaker says the FLEX tab controls FLEX exposure and the MVP tab is used to set MVP exposure.

### DFS Q&A: How Do Contest Sims Work for Small vs. Large-Field Contests?
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 12, 2023 (0:18:57) · [Watch on YouTube](https://www.youtube.com/watch?v=h9O1DRC4ABo)

- [16:24](https://www.youtube.com/watch?v=h9O1DRC4ABo&t=984s) "I want to say you know going back to my earlier example with Travis Kelce hey I think he's going to be more owned in the captain that's going to have an effect on his ownership his adjusted ownership and that will be taken into account in the single game saber scores since we're waiting average adjusted ownership of the lineup"
  - Takeaway: An adjustment expecting Travis Kelce to be more popular at captain affects his adjusted ownership and is incorporated into single-game SaberScores.

### How to Beat NFL DFS Showdowns
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 10, 2026 (0:17:26) · [Watch on YouTube](https://www.youtube.com/watch?v=iE36sFpjaVw)

- [11:22](https://www.youtube.com/watch?v=iE36sFpjaVw&t=682s) "So, I'm going to hedge against him at the captain spot. I'm going to set his max exposure to 10% getting lower than the field on him. And then to double down on that particular take, I'm gonna bump up my exposure for Devonte Adams up to 20%."
  - Takeaway: The speaker demonstrates adjusting captain exposure by capping Puka at 10% and raising Devonte Adams exposure to 20%.

### The DraftKings Showdown Rule That Deletes Your Winning Lineup
FTA Sports · Aug 05, 2026 (0:18:10) · [Watch on YouTube](https://www.youtube.com/watch?v=1X6cgvJxsqQ)

- [2:07](https://www.youtube.com/watch?v=1X6cgvJxsqQ&t=127s) "Now, think about how often you do see a quarterback in the captain showdown field. It's all the time. He's usually the most popular captain pick in almost every single contest you will ever enter. So, the most rostered captain in the format is the right captain only about 20% of the time"
  - Takeaway: The transcript contrasts the frequently rostered quarterback captain with the finding that the most-rostered captain was optimal only about 20% of the time.

### DFS Q&A: How do I best utilize the dupe metric in the contest sims?
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 03, 2023 (1:39:07) · [Watch on YouTube](https://www.youtube.com/watch?v=ETNpMZGSNCs)

- [1:13:38](https://www.youtube.com/watch?v=ETNpMZGSNCs&t=4418s) "if we take um DK mchf we have 108 lineups in our pool that have DK metf and we say no Gino Smith In Flex so there are 14 lineups in our pool with DK meaf as the captain and no goino Smith in the flex out of 108 DK metf Captain lineups and this is only with 500 lineups"
  - Takeaway: In a 500-lineup pool, 14 of 108 DK Metcalf captain lineups did not include Geno Smith in the flex.

### NFL Office Hours - Showdown Q&A
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 08, 2023 (1:01:37) · [Watch on YouTube](https://www.youtube.com/watch?v=Re6X-sC0P7A)

- [54:01](https://www.youtube.com/watch?v=Re6X-sC0P7A&t=3241s) "just because the captain is popular does not mean you cannot play them in a profitable way so maybe you know you see that Patrick Mahomes is the most popular that doesn't mean you need to go in full fade Patrick Mahomes right you just need to like hey my Patrick Mahomes sign ups maybe I want to look at those right maybe I want to key in on these you know three Patrick Mahone sign ups that I'm playing and make sure that they look the way I want them to look"
  - Takeaway: A popular captain need not be fully faded; the suggested approach is to inspect the construction of the lineups using that captain. No CPT-versus-FLEX ownership rates are provided.

### HOW TO WIN ON DRAFTKINGS NFL SHOWDOWN: LINEUP BUILDING TIPS
Alvin Zeidenfeld · Sep 03, 2019 (0:14:55) · [Watch on YouTube](https://www.youtube.com/watch?v=lyaKCYf1LrQ)

- [8:58](https://www.youtube.com/watch?v=lyaKCYf1LrQ&t=538s) "because the quarterbacks are popular when they when they do smash you still end up splitting that with a lot more people whereas if you're able to get the random Treadwell week or whatever that's when you can actually win as unique lineup that's when you can win a hundred grand plus is when you have kind of that uniqueness either at the captive spot or with the guys that you're pairing up the quarterback with"
  - Takeaway: Popular quarterback outcomes can lead to more prize splits, while a unique captain or quarterback pairing can help distinguish a lineup.

### I Cracked the Code on NFL Showdown Lineups (Do This to Win)
DFS Army - Daily Fantasy Sports · Aug 03, 2026 (0:26:59) · [Watch on YouTube](https://www.youtube.com/watch?v=65HDqKemR88)

- [7:42](https://www.youtube.com/watch?v=65HDqKemR88&t=462s) "Underdog quarterbacks that are greater than three and a half point the three and a half point or greater underdogs out of a 205 game sample size were only the nut captain three times for.22%. [music] Only three time out of 200. So at a 1% they they win at about a 1.5% rate but the field plays them at about 6 1/2 to 7% as a captain."
  - Takeaway: In a 205-game sample, quarterbacks favored by at least 3.5 points less often as underdogs were winning captains three times, about a 1.5% win rate versus 6.5–7% field captain ownership.

### SaberSim's Unique Approach to Projecting Ownership
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 10, 2021 (1:28:00) · [Watch on YouTube](https://www.youtube.com/watch?v=zMdDPCaxXjg)

- [59:46](https://www.youtube.com/watch?v=zMdDPCaxXjg&t=3586s) "let's say justin jefferson and naji harris are the chalkiest captains right um after the madison one goes away if they're 18 in large field right it might be 30 in a single entry so if you're making a determination that the optimal the optimal ownership of jefferson is like 25 right"
  - Takeaway: The example discusses captain ownership specifically, noting that popular captains may be more concentrated in single-entry than large-field contests.

### DraftKings Showdown Strategy for Seahawks vs Lions | JSN Captain + Game Theory Breakdown
One Week Season · Sep 30, 2024 (0:43:25) · [Watch on YouTube](https://www.youtube.com/watch?v=OTvIy-Jk96U)

- [23:44](https://www.youtube.com/watch?v=OTvIy-Jk96U&t=1424s) "he could get you to 20 fantasy points which becomes 30 with the captain bonus and he could get there without scoring a touchdown it's a very viable path so he's not a guy I think you need to pair with like DK metf"
  - Takeaway: The speaker describes a Captain path based on PPR production and the Captain bonus that does not require a touchdown or a paired teammate.

### I Gave the DFS Army Optimizer the SHOWDOWN CODE… Here’s What It Built!
Ibe's DFS Sports Betting · Oct 01, 2026 (0:11:51) · [Watch on YouTube](https://www.youtube.com/watch?v=sBOEt7d3dM4)

- [9:39](https://www.youtube.com/watch?v=sBOEt7d3dM4&t=579s) "I'm just going to look at my optimizer to see who they had in my captain position the most out of 150 of these lineups. Actually, 165. So look like they're leaning more towards Jaylen Warren at the captain position with Deshun Watson next. I can always adjust these."
  - Takeaway: In this optimizer run, Jaylen Warren appears most often at captain, followed by Deshun Watson, and the captain exposures can be adjusted.

### DFS Q&A: How do I navigate NFL late swap?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 09, 2022 (1:07:37) · [Watch on YouTube](https://www.youtube.com/watch?v=uvDTL8e6Ipo)

- [34:06](https://www.youtube.com/watch?v=uvDTL8e6Ipo&t=2046s) "if you lock josh allen at your captain spot and then run the build you are taking random sims and then the builder is going to force josh allen as your captain regardless of the outcome of that sim which is why i recommend for showdown nfl showdown in particular doing as much as possible as you can after the build"
  - Takeaway: Locking a player at captain forces that player into the captain spot regardless of the randomly selected simulation, so the speaker recommends making as many lineup adjustments as possible after building.

### How to Build Winning NFL DFS Showdown Lineups on DraftKings & FanDuel (2024)
Occupy Fantasy · Oct 07, 2024 (1:22:41) · [Watch on YouTube](https://www.youtube.com/watch?v=W9FWB82PwNs)

- [8:51](https://www.youtube.com/watch?v=W9FWB82PwNs&t=531s) "So basically what these these two sections talk about is to find out which guys we want to play at captain in our small field GPs especially. It's where do where's the occupied model? Where do your personal rankings rank these guys and how does that compare to projected ownership?"
  - Takeaway: The captain-selection method compares the model and personal player rankings with projected ownership, especially for small-field GPPs.

### 2026 NFL DraftKings Strategy: Stop Making These Costly DFS Mistakes
Mayo Media Network · Aug 28, 2026 (1:05:48) · [Watch on YouTube](https://www.youtube.com/watch?v=SPjmh9bxUF4)

- [36:50](https://www.youtube.com/watch?v=SPjmh9bxUF4&t=2210s) "the people that are like well you tell me to get different let me put I'm using the last year stuff let me put Jan Dodson in the captain then I'll just do that and then I get every and it's like that's just as bad because now you obviously I know your rest of your lineup is Herz Barkley whoever the top two guys are on the other side and whatever lands on your last one again it's See how there's two extremes, Pat?"
  - Takeaway: He warns that using a low-owned captain while filling the rest of a Showdown lineup with the obvious top players is another extreme, rather than a balanced way to differentiate.

### Lions vs Panthers - SNF Sunday Sweatdown | NFL Week 4 | DFS Picks, Plays & Process
Ship It Nation · Oct 05, 2026 (1:05:29) · [Watch on YouTube](https://www.youtube.com/watch?v=xJlvummhIfI)

- [19:53](https://www.youtube.com/watch?v=xJlvummhIfI&t=1193s) "I actually like Bryce Young as my second favorite captain for the reasons I alluded to earlier. He's going to be right around 5% owned in the captain spot. There's a bunch of unknowns. He could spread it out to a bunch of different guys, right? Not having Jaylen Coker, who was second on the team in routes run"
  - Takeaway: The speaker expected Bryce Young to be around 5% owned at captain and favored him there partly because Carolina's receiving options were uncertain.

## 8. Late swap, late news, and inactives

26 videos, 48 transcript excerpts.


### If you’re not late-swapping in NFL DFS, you’re leaving money on the table
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 01, 2021 (1:02:30) · [Watch on YouTube](https://www.youtube.com/watch?v=S2p7LVEeXy4)

- [2:35](https://www.youtube.com/watch?v=S2p7LVEeXy4&t=155s) "the most obvious reason to do a light swap is to remove an injured player from your lineup so sometimes players have a surprise in injury they're declared inactive uh having a guaranteed zero in your lineup is minus eb so you definitely want to swap them out"
  - Takeaway: Remove players declared inactive because leaving them in the lineup guarantees a zero.
- [2:52](https://www.youtube.com/watch?v=S2p7LVEeXy4&t=172s) "the most important thing to pay attention to is running back injuries because running back injuries can be extremely impactful and may completely change what your optimal lineup should be so like probably more than a lot of other sports if some scrub running back or some not that talented running back gets a lot of playing time in a good offense they're probably going to have a really low salary and probably going to be one of the top values of the slave"
  - Takeaway: Running back injuries can create low-salary replacement value and change optimal lineup construction.
- [9:52](https://www.youtube.com/watch?v=S2p7LVEeXy4&t=592s) "we simulate every single game on the slate play-by-play thousands of times writing accurate game scripts while keeping track of the score the time on the clock and every other detail that affects the game in our simulations and we don't stop this process when the slate just locks we simulate every individual game with the most up-to-date information right up until kickoff of that game"
  - Takeaway: The tool updates play-by-play game simulations with current information through each game's kickoff.
- [22:38](https://www.youtube.com/watch?v=S2p7LVEeXy4&t=1358s) "so in this specific case let's say this was true that aaron jones was a true game time decision we didn't know he was going to play air aj dillon is a very good backup the green bay offense is extremely good so aj dylan is probably if he does play he's going to be projected at something like 16 17 dk fantasy points maybe even higher right so what i would do probably is if i thought there was a decent chance he was out i would probably raise aj dillon to something close to what i think his"
  - Takeaway: For a genuine Aaron Jones game-time decision, the suggested approach is to raise A.J. Dillon's projection toward his expected value if Jones is out.
- [50:39](https://www.youtube.com/watch?v=S2p7LVEeXy4&t=3039s) "the latest player in the lineup is always placed in the flex plot spot and if uh it's equal it is the more expensive player that he's used in the flex position um so the lineup should be made right"
  - Takeaway: The builder places the latest-starting player in the FLEX position, using the more expensive player there when start times are equal.

### DFS Q&A: Avoiding Dupes on Small NFL Slates
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 21, 2025 (0:27:22) · [Watch on YouTube](https://www.youtube.com/watch?v=KDQWYsMCP8w)

- [21:16](https://www.youtube.com/watch?v=KDQWYsMCP8w&t=1276s) "On ultimate, yes, you should swap. And the reason for that is because you're going to get to take into account the actual scores that all of the players scored in the first game. So that's that's really valuable information, right? We're not using projections. We're actually using how they scored"
  - Takeaway: On Ultimate, late swapping uses actual first-game player scores rather than projections.
- [21:42](https://www.youtube.com/watch?v=KDQWYsMCP8w&t=1302s) "on starter what you want to be mindful of is you want to be mindful of any projection adjustments. Okay? So like for instance I would go into the discord and then I would look to see if any sims have run and if sims have run then yes I would want to late swap."
  - Takeaway: On Starter, the presenter recommends checking Discord for new simulations and late swapping when projections have been adjusted.
- [22:50](https://www.youtube.com/watch?v=KDQWYsMCP8w&t=1370s) "We're like, hey, we we projected this perfect. We got inactives, right? There were no changes. So, if you see no changes, there is no need to late swap. If you do see changes, then yes, I would late swap."
  - Takeaway: The presenter says to late swap when news changes projections, but not when inactives produce no changes.

### DFS Q&A: Walking Through the NFL Late Swap Process
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 26, 2025 (0:24:26) · [Watch on YouTube](https://www.youtube.com/watch?v=CgfglAjd2ys)

- [3:44](https://www.youtube.com/watch?v=CgfglAjd2ys&t=224s) "When you do that, if you already have one lineup in all of your cash contests, it's going to make sure that when you swap that remains the same. You only swap one lineup and it goes into all of those same entries for those contests."
  - Takeaway: Turning on group duplicates for cash contests keeps the shared lineup together during late swap.
- [5:31](https://www.youtube.com/watch?v=CgfglAjd2ys&t=331s) "DraftKings is effectively the final say in this situation. So when you swapped in Sabersim, Sabersim thought all of the Jennings were out, but when you uploaded it, because only 50 of 190 uploaded, that means that 140 lineups, DraftKings had a different lineup than Sabers Sim thought you had."
  - Takeaway: DraftKings’ entries can differ from SaberSim’s lineup state; here, only 50 of 190 lineups updated, leaving 140 mismatched.
- [6:03](https://www.youtube.com/watch?v=CgfglAjd2ys&t=363s) "you run a late swap, you upload it, and you get an error, come back to Sabersim, click this upload icon again, reimpport your entry file. What you're doing is you're telling Sabersim, hey, uh, or what what you're doing here is Sabersim is asking DraftKings, hey, tell me what you think the lineups look like, and I will just start over fresh."
  - Takeaway: After an upload error, reimport the entry file so SaberSim retrieves the current DraftKings lineups, then restart the swap.

### DFS Q&A: Navigating NFL Late Swap
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 18, 2024 (0:30:32) · [Watch on YouTube](https://www.youtube.com/watch?v=8qVskFOoEGE)

- [19:30](https://www.youtube.com/watch?v=8qVskFOoEGE&t=1170s) "so this will default to 10 swaps per lineup I think it's fine if you know if this was like a Thursday to Monday slate and I was doing this on Friday following the Thursday game I'd probably Max that out to to the most possible but when there is one game left on the Slate there's only going to be so many swap options per lineup so I think leaving it at 10 is fine"
  - Takeaway: The late-swap default is 10 swaps per lineup; the speaker suggests maximizing swaps after an earlier game on a Thursday-to-Monday slate, but says 10 is fine when only one game remains.
- [19:52](https://www.youtube.com/watch?v=8qVskFOoEGE&t=1192s) "so now let's say that you know I'm ready I really don't want to change anything else I'm happy with it I would just click build swaps so let's let this Swap all right so I would first run the late Swap and then I would run the contest Sim"
  - Takeaway: The demonstrated late-swap workflow is to build swaps first and then run the contest sim.
- [25:28](https://www.youtube.com/watch?v=8qVskFOoEGE&t=1528s) "no you don't have to do this we do this automatically for you so if you go to the contest tab you go to field lineups click this gear icon use live Fields use live sims are going to be toggled on automatically where we are automatically using the live Sim data now what is the live s data right so as the games play out"
  - Takeaway: The speaker says live fields and live sims are automatically enabled for late swap, so users do not need to change the sim settings manually.

### DFS Q&A: How do I navigate NFL late swap?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 09, 2022 (1:07:37) · [Watch on YouTube](https://www.youtube.com/watch?v=uvDTL8e6Ipo)

- [8:39](https://www.youtube.com/watch?v=uvDTL8e6Ipo&t=519s) "there's only one late swap window really and it's after the early games have locked but before the afternoon games have started and after typically after the afternoon games inactive report has come out"
  - Takeaway: The described NFL late-swap window is after early games lock and before afternoon games start, typically after the afternoon inactives report.
- [10:08](https://www.youtube.com/watch?v=uvDTL8e6Ipo&t=608s) "when something like this happens i'm typically late swapping everything right i'm going in and i'm running a late swap build and i'm rebuilding all of my lineups right so actually wait whoops sorry so i'm late swapping 20 lineups and i'm doing it like this because now i'm gonna want to get to a ton of breeda"
  - Takeaway: When a key running back is ruled out and creates a strong replacement-value opportunity, the speaker rebuilds all lineups to get more exposure to the replacement.
- [11:57](https://www.youtube.com/watch?v=uvDTL8e6Ipo&t=717s) "if we have a situation instead where it's like a starting wide receiver that gets ruled out or something like that instead what i typically want to do is late swap but only late swap out lineups containing out players and that will just rebuild"
  - Takeaway: For a starting wide receiver being ruled out, the speaker late-swaps only lineups containing the unavailable player.

### How to Late Swap in NFL DFS: A Real-Time Tutorial
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 09, 2024 (0:08:18) · [Watch on YouTube](https://www.youtube.com/watch?v=IAt9PW8j75M)

- [0:23](https://www.youtube.com/watch?v=IAt9PW8j75M&t=23s) "the first is we need to get players that aren't playing in the afternoon games out of our lineups when the inactives reports come out 90 minutes before the afternoon game starts sometimes there will be surprise scratches or potentially players that were questionable heading into the Slate that get ruled out opening up Big Value opportunities for other players on the team"
  - Takeaway: Late swap removes players ruled out by inactives, including surprise scratches, and can make room for newly valuable players.
- [0:49](https://www.youtube.com/watch?v=IAt9PW8j75M&t=49s) "some final tuning simulations that run in our final simulations as well as our models team is working throughout the day to update snaps Target shares things like that so we want to capture any of those final updates we have in those last simulations for the afternoon games"
  - Takeaway: The late-swap process can incorporate final simulation and model updates, including updates to snaps and target shares.
- [2:07](https://www.youtube.com/watch?v=IAt9PW8j75M&t=127s) "if at any point this turns red it means you have players that are out in your entries file that you need to remove as soon as possible if this ever turns red you should always come up here click this and quick swap any out players out and swap them to the best available player redownload that entries file and re-upload it to the site that you're playing on"
  - Takeaway: When the quick-swap indicator shows out players, remove them promptly, replace them with the best available players, and upload the revised entries file.

### NFL DFS Sims Tournament Strategy Week 1 | NFL DFS Strategy
Stokastic DFS - Daily Fantasy Sports Advice · Sep 11, 2026 (1:11:45) · [Watch on YouTube](https://www.youtube.com/watch?v=uMa9MQhf0fU)

- [14:31](https://www.youtube.com/watch?v=uMa9MQhf0fU&t=871s) "And Katon Mitchell coming into this one, by the way, is still limited. If Katon Mitchell doesn't play, I think Amarian Hampton just looks that much better. Honestly, pro. He probably looks a whole lot better."
  - Takeaway: He says Mitchell's limited status matters to Hampton's outlook and that Hampton would look substantially better if Mitchell is inactive.
- [56:06](https://www.youtube.com/watch?v=uMa9MQhf0fU&t=3366s) "And the Brock Bowowers news opens up a lot of value for us where the running back position, I think there are so many good mid to highriced running backs this week that I'm a little bit uncomfortable um going out there and I don't want to say burning, but but using a a a a running back spot on Marshon Lloyd."
  - Takeaway: He says Bowers news opened up value and affected his willingness to use a running-back roster spot on Marshon Lloyd.

### The DraftKings Showdown Rule That Deletes Your Winning Lineup
FTA Sports · Aug 05, 2026 (0:18:10) · [Watch on YouTube](https://www.youtube.com/watch?v=1X6cgvJxsqQ)

- [11:08](https://www.youtube.com/watch?v=1X6cgvJxsqQ&t=668s) "So, only 1.2% of net lineups contained a player our projections never generated a number four at all. The genuinely inactive, the practice squad people, the guys on the salary file who are not playing, cutting those is a real filter and cost you almost nothing."
  - Takeaway: The transcript distinguishes players with no projection, including inactive or non-playing players, as a filter that affected 1.2% of winning lineups.
- [17:24](https://www.youtube.com/watch?v=1X6cgvJxsqQ&t=1044s) "So, maybe rerun your lineups about an hour before kickoff on Thursday Night Football, Sunday Morning Football, Sunday Night Football, or even Monday Night Football, and go from there."
  - Takeaway: The speaker recommends rerunning lineups about an hour before kickoff for Thursday, Sunday morning, Sunday night, and Monday games.

### SaberSim's Unique Approach to Projecting Ownership
SaberSim DFS - Daily Fantasy Sports Strategy · Dec 10, 2021 (1:28:00) · [Watch on YouTube](https://www.youtube.com/watch?v=zMdDPCaxXjg)

- [15:07](https://www.youtube.com/watch?v=zMdDPCaxXjg&t=907s) "we remove all of your exposures that are set and we attempt to rebuild your lineups right we're basically saying we can't meet these exposures anymore too many players are locked into the lineups there's not enough positional flexibility or salary flexibility"
  - Takeaway: Late-swap rebuilds can fail when locked players leave too little positional or salary flexibility to satisfy the existing exposure settings.
- [50:22](https://www.youtube.com/watch?v=zMdDPCaxXjg&t=3022s) "and if there is an update here since the last time i made an adjustment something that has changed for a player playing in the game that night right i swap provided that the projections on sabersim have also changed but if the projections have changed if the sims have run"
  - Takeaway: The speaker late-swaps when there has been relevant player news and SaberSim's projections have changed following a simulation update.

### DFS Q&A: How Should You Handle NFL Late Swap Between Builds?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 21, 2025 (0:27:24) · [Watch on YouTube](https://www.youtube.com/watch?v=QJ4wmImXx5M)

- [2:37](https://www.youtube.com/watch?v=QJ4wmImXx5M&t=157s) "So after slate lock, it is always better to use the late swap build. uh the regular build will change all of the players whose games have started which obviously you don't want or obviously isn't compatible with uh DK won't accept that."
  - Takeaway: After slate lock, use a late swap build because a regular build can change players whose games have already started.
- [4:52](https://www.youtube.com/watch?v=QJ4wmImXx5M&t=292s) "If you're on ultimate, I would still build the swap. I would probably submit something just so you have something new in. But what I would do, right, is I would come back to my swap build before the next set of games started. And then I would rerun the contest sim, let my lineups be chosen, resave and resubmit."
  - Takeaway: For Ultimate, rerun the contest sim in the existing swap build before the next games start, then resave and resubmit to account for live developments.

### DFS Q&A: How SaberSim Creates Its Ownership Projections
SaberSim DFS - Daily Fantasy Sports Strategy · Jun 03, 2023 (0:24:23) · [Watch on YouTube](https://www.youtube.com/watch?v=JnVogCYAHgY)

- [19:17](https://www.youtube.com/watch?v=JnVogCYAHgY&t=1157s) "when I'm doing a quick swap I am doing a best from same team so the reason for that is I want to maintain the stacks and maintain the correlations in my lineups I don't really want a four stack to go down to a three stack"
  - Takeaway: For a quick swap, the speaker uses the best available player from the same team to preserve lineup stacks and correlations.
- [20:00](https://www.youtube.com/watch?v=JnVogCYAHgY&t=1200s) "even in that situation I would not rebuild my entire 150 lineup set what I would instead do is if you have a lineup file which I do not at the moment in late swap here what you can do is in your contest there is going to be an option down here that says late swap lineups without players only"
  - Takeaway: Rather than rebuilding a 150-lineup set after an inactive, the speaker recommends using the late-swap option to rebuild only lineups containing unavailable players.

### DFS Q&A: How are SaberSim's ownership projections calculated?
SaberSim DFS - Daily Fantasy Sports Strategy · Jun 15, 2022 (0:58:03) · [Watch on YouTube](https://www.youtube.com/watch?v=MGO5rVk8I7M)

- [48:40](https://www.youtube.com/watch?v=MGO5rVk8I7M&t=2920s) "because i uploaded an entries file filled it with lineups and then downloaded it right sabersim now knows what i'm playing and what this means is that based on my entries file that i have uploaded we have a player that's out so we click this it's saying you have jackie bradley jr in one of your lineups and he's not in the lineup"
  - Takeaway: After an entries file is uploaded, SaberSim can identify a player who is out in one of the entered lineups.
- [49:04](https://www.youtube.com/watch?v=MGO5rVk8I7M&t=2944s) "we can click this and say let's swap him out and put the best available player from the same team right we want to he might be in a red sox stack and i want to maintain that so there we go we swap him in with ref snyder and we can download again upload to dk"
  - Takeaway: The quick-swap workflow replaces an out player with the best available player from the same team to preserve the stack, then allows the updated entries file to be uploaded.

### Beat DFS Using The SaberSystem: 5 Principles for Maximum Profitability
SaberSim DFS - Daily Fantasy Sports Strategy · Aug 29, 2024 (0:16:28) · [Watch on YouTube](https://www.youtube.com/watch?v=4jONT961JrM)

- [10:58](https://www.youtube.com/watch?v=4jONT961JrM&t=658s) "not only do we need to make sure we're building lineups before lock with the most upto-date information as possible and also making sure that our process is time efficient enough to react to breaking news when it comes out but we also need to make sure we're late swapping during the Slate to account for news when it comes out after lock"
  - Takeaway: The transcript recommends building with current information, reacting efficiently to breaking news, and late swapping for news after lock.
- [13:08](https://www.youtube.com/watch?v=4jONT961JrM&t=788s) "plus these simulations update in just a few minutes anytime news breaks that shakes up the slate and we keep you posted when you need to take action our desktop and mobile push notifications will give you a heads up when you have a player that is out in your entries file or when a player's projection drops by a large enough threshold"
  - Takeaway: The simulations update within minutes of slate-changing news, and push notifications flag players who are out or whose projections drop past a threshold.

### DFS Tournament Strategy - How to Beat Small Field & Single Entry GPPs
Establish The Run · Sep 06, 2021 (0:37:26) · [Watch on YouTube](https://www.youtube.com/watch?v=Z79IcL2Cruk)

- [27:40](https://www.youtube.com/watch?v=Z79IcL2Cruk&t=1660s) "one other thing i'll talk about like late swap i think is pretty important and even more important the smaller the field size gets because you have it's easier to tell what your opponents are doing you have a little bit more information"
  - Takeaway: Late swap is described as especially important in smaller fields, where it is easier to see what opponents are doing and more information is available.
- [28:52](https://www.youtube.com/watch?v=Z79IcL2Cruk&t=1732s) "take a couple contrarian plays early and what ended up happening was like three chalk running backs fell like it was crazy and i think i had like antonio gibson or something did really well and at that point it was super clear that i had this leverage on the field and i could play this really expensive uh really chalky but high upside game stack"
  - Takeaway: After contrarian early plays performed well and chalk running backs fell, the speaker used late-slate flexibility to play an expensive, chalky, high-upside game stack.

### How To Project Ownership % in DFS (DraftKings)
Kev's Picks · Nov 22, 2015 (0:04:33) · [Watch on YouTube](https://www.youtube.com/watch?v=BToDGUdOhkU)

- [2:39](https://www.youtube.com/watch?v=BToDGUdOhkU&t=159s) "so when the Thursday contest start at FanDuel you'll be able to view the ownerships and we use FanDuel because of lineup lock at DraftKings you can change your lineups right up until the game while at FanDuel the lineups lock at the first game of the contest"
  - Takeaway: The transcript says DraftKings lineups can be changed until the game, while FanDuel lineups lock at the contest's first game.

### DFS Q&A: How Do Contest Sims Work for Small vs. Large-Field Contests?
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 12, 2023 (0:18:57) · [Watch on YouTube](https://www.youtube.com/watch?v=h9O1DRC4ABo)

- [15:41](https://www.youtube.com/watch?v=h9O1DRC4ABo&t=941s) "so we will never override your custom projection so say that you know Travis Kelce is projected for 10 points and you bump him up to 15 let's say a new sim runs and it bumps him up to 20 we're going to keep his projection at 15 for you in the my projection column"
  - Takeaway: A new simulation does not overwrite a user's custom projection: in Andrew’s example, the custom projection remains 15 even if the new simulation raises the projection to 20.

### DFS Q&A: How do I best utilize the dupe metric in the contest sims?
SaberSim DFS - Daily Fantasy Sports Strategy · Oct 03, 2023 (1:39:07) · [Watch on YouTube](https://www.youtube.com/watch?v=ETNpMZGSNCs)

- [16:50](https://www.youtube.com/watch?v=ETNpMZGSNCs&t=1010s) "when you late swap now it rebuilds a pool of lineups just like it does before lock so each lineup in your original set gets swapped you know x times 100 times 250 times something like that basically pool size divided by number of lineups time and then we sort those lineups based on saber score or you can run a contest them on those"
  - Takeaway: Late swap rebuilds multiple candidate swaps for each original lineup, with the number of attempts based on pool size divided by the number of lineups, then sorts the results by Saber Score or contest simulation.

### DFS Q&A: Simulations can help you avoid duplication in DFS
SaberSim DFS - Daily Fantasy Sports Strategy · Feb 03, 2022 (1:17:24) · [Watch on YouTube](https://www.youtube.com/watch?v=PSqHBQYbYqE)

- [4:33](https://www.youtube.com/watch?v=PSqHBQYbYqE&t=273s) "so that means you can't set exposures after the late swap because there's no pool of lineups to sort through to match the exposures so if you want to add additional exposures here you need to do it in the entry editor here"
  - Takeaway: Late-swap exposures must be set in the entry editor because the late-swap build has no lineup pool to sort through.

### NFL Office Hours - Showdown Q&A
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 08, 2023 (1:01:37) · [Watch on YouTube](https://www.youtube.com/watch?v=Re6X-sC0P7A)

- [48:41](https://www.youtube.com/watch?v=Re6X-sC0P7A&t=2921s) "we are also you know once inactives come out we are taking in that information and then we are running a final Sim one hour to lock so uh inactors come out 90 minutes before lock final Sim one hour before lock will take into account any players inactive or active"
  - Takeaway: The stated schedule is for inactives to arrive about 90 minutes before lock and a final simulation to run one hour before lock, taking active/inactive information into account.

### DFS Q&A: How Do You Reduce Dupes in Showdown?
SaberSim DFS - Daily Fantasy Sports Strategy · Sep 07, 2025 (1:05:02) · [Watch on YouTube](https://www.youtube.com/watch?v=JuOzj5ZOQHk)

- [29:55](https://www.youtube.com/watch?v=JuOzj5ZOQHk&t=1795s) "So, I would recommend doing a full late swap and sim um before the afternoon slates. If you don't have any players that are out, then I think it's fine to go straight to the late swap. If you do have some players that are out, I would recommend quick swapping first and then doing a late swap."
  - Takeaway: Before afternoon slates, the recommendation is to quick-swap first if players are out, then run a full late swap and sim; otherwise, proceed directly to late swap.

### HOW TO WIN ON DRAFTKINGS NFL SHOWDOWN: LINEUP BUILDING TIPS
Alvin Zeidenfeld · Sep 03, 2019 (0:14:55) · [Watch on YouTube](https://www.youtube.com/watch?v=lyaKCYf1LrQ)

- [4:56](https://www.youtube.com/watch?v=lyaKCYf1LrQ&t=296s) "late news it's definitely your friend and showdown most people are gonna be entering these lineups and they're not going to go back and adjust things when inactives are ruled out so the best-case scenario for us would be this opening week that trey Burton practice is limited is a game-time decision and then is ruled out an hour before lock because they're gonna be 50,000 lineups that aren't gonna make an adjustment"
  - Takeaway: The speaker says late inactive news can create an advantage because many entrants will not return to adjust their lineups before lock.

### NFL DFS Strategy Masterclass: Game Theory, Stacking & How to Actually Win
Mayo Media Network · Sep 04, 2026 (1:09:42) · [Watch on YouTube](https://www.youtube.com/watch?v=oj36e7aIMHc)

- [3:32](https://www.youtube.com/watch?v=oj36e7aIMHc&t=212s) "there might be a little bit of edge in thinking about late swap more intelligently, especially if you're in like these massive double ups where people are running trains, and based on your early start, you can kind of figure if you're going to chop with a bunch of different people, and if it's worth getting off this maybe obvious lineup that a lot of people are playing."
  - Takeaway: Late swap can be used in large double-ups to respond to an early result and avoid a likely chop with many opponents.

### DFS Q&A: What is the best way to reduce dupes in Showdown?
SaberSim DFS - Daily Fantasy Sports Strategy · Jan 15, 2024 (0:15:07) · [Watch on YouTube](https://www.youtube.com/watch?v=eWWw-7T2YLk)

- [9:36](https://www.youtube.com/watch?v=eWWw-7T2YLk&t=576s) "if you're using multiple contest Sims I do recommend deleting the lineups after you fill them that way they don't get duplicated now when you go to late swap late swap is not looking at the lineups in this build it's looking at the lineups in your contest file"
  - Takeaway: Deleting entered lineups from a build avoids duplicating them, and late swap reads lineups from the contest file rather than the build.

### DRAFTKINGS & FANDUEL DFS STRATEGY REVIEW: Large-Field GPP Lineup Simulations (1/18/23)
RotoGrinders - Daily Fantasy Sports Advice · Jan 18, 2023 (1:00:36) · [Watch on YouTube](https://www.youtube.com/watch?v=pakvRcKsnXQ)

- [40:38](https://www.youtube.com/watch?v=pakvRcKsnXQ&t=2438s) "if this was 6 30 eastern half an hour before the slave and these were the updated projections and everything everything was massaged everything was you know a minute here a minute there starting lineup came out oh this guy isn't starting we got to change some of these projections then the ownership changes"
  - Takeaway: If starting-lineup news shows a player is not starting, projections should be changed, which also changes ownership.

### DFS Q&A: For the 20-Max and 150-Max contest do you use the same pool?
SaberSim DFS - Daily Fantasy Sports Strategy · May 25, 2024 (0:58:29) · [Watch on YouTube](https://www.youtube.com/watch?v=PRtm5_i9qqQ)

- [4:30](https://www.youtube.com/watch?v=PRtm5_i9qqQ&t=270s) "what what I would recommend doing here is to lock in the players that are actually in the lineup so and then eliminate the rest of the players in the pool so let's say you were in a situation where you had it you missed this first lock and then it's it's like 530 or 525 or something like that the next games are coming up and you've got 150 identical of the same lineups what you can do is go in and identify the players from these early games that you actually have in your lineups here"
  - Takeaway: After missing an early lock with identical lineups, lock the players already in those lineups and eliminate the other players from the started games before rebuilding.

### Lions vs Panthers - SNF Sunday Sweatdown | NFL Week 4 | DFS Picks, Plays & Process
Ship It Nation · Oct 05, 2026 (1:05:29) · [Watch on YouTube](https://www.youtube.com/watch?v=xJlvummhIfI)

- [58:08](https://www.youtube.com/watch?v=xJlvummhIfI&t=3488s) "Oh, Jaylen Coker's inactive. We knew that. All right. Yeah. So, let me get the inactives and then we can I think if you want to give a play of the day, we can then jump out of here. Um, Tataroya McMillan. Yeah, he's on IR. We knew that. Um so inactives Lions, nothing."
  - Takeaway: The speakers confirmed Coker was inactive, noted McMillan was on IR, and reported no Lions inactives at that point.