#!/usr/bin/env python3.12
"""ONE command for a SHOWDOWN slate: DK export in, legal portfolio out, or a named stage refusal.

WHY THIS EXISTS. `slate_to_portfolio.py` is the classic full-slate path and contains no occurrence of
"showdown" or "captain". So with a Thursday game in front of us on 2026-10-01, the honest answer to
"can we run showdown tonight" was that the components existed and nothing drove them: the only
end-to-end driver was `nfl/research/showdown_fixture/code/run_research_fixture.py`, which hardcodes
`GAME='2026_02_NYG_LA'`, a Week 2 salary path and a specific draws manifest, and declares itself
`CANDIDATE_NOT_ACCEPTED_BASELINE`. Pointing that at a new game is a coding task, not a parameter.

This is the missing runner, with the four clauses that make the classic one worth having:

    ingest DK export -> slate identity -> availability -> projections
    -> candidates -> portfolio selection -> legality validation -> DK upload CSV

Every stage PRODUCES or REFUSES with a named code, and the run ALWAYS emits one status board saying
where it got to. A stage that cannot run does not stop the board existing.

A DK SHOWDOWN ID IS A PRICED ITEM, NOT A PERSON. This is the fact that matters most here and it was
measured, not assumed, after a first version of this file keyed the universe by `ID` and refused its
own test file. In the NYG@LAR export all 53 players carry a DIFFERENT id for captain than for flex --
106 distinct ids for 53 people. Puka Nacua is 44191175 at 17100 as captain and 44191122 at 11400 as
flex.

Three things follow, and each would have been a silent defect:

  1. The upload must carry the SLOT-SPECIFIC id. Writing the flex id into the CPT column uploads a
     different lineup from the one that was optimised, and DK would accept it as something else.
  2. The universe must be keyed by PLAYER IDENTITY, here (name, club). Keying on the DK id counts
     every player twice and makes "one captain and five flex" unenforceable.
  3. A projection artifact keyed by classic dk_id CANNOT be joined to a showdown export. The id
     spaces are disjoint -- showdown ids are 44191xxx against 44246xxx for the Week 3 classic
     draftgroup -- so the join goes through (name, club), never through dk_id.

THE DK EXPORT IS THE UNIVERSE. `slate_to_portfolio.s2_verify_identity` checks the slate against
`PRD.EXPECTED_UNIVERSE`, a pinned count for one week. A showdown export lists exactly the players in
one game with DK's own salaries and roster positions, so the file defines the universe.

IT ALSO CARRIES WHAT THE REPOSITORY LACKS. The pool's `Game Info` column reads
`NYG@LAR 09/21/2026 08:15PM ET`, so the matchup AND the kickoff come from the file. The audit written
this morning said the repository has no kickoff-time artifact for Week 4 and so could not say which
game was tonight's. That is true of the repository and false of the DK export.

WHAT IT WILL NOT DO. `AvgPointsPerGame` sits in the same rows this reads and is a THIRD-PARTY
PROJECTION -- the same class of value as FantasyCruncher. It is never read as a model input, never
blended, and never used to fill a missing projection. If our own projection does not cover a player,
the stage REFUSES and names them. A governed refusal is preferable to fabricated output, and a
portfolio built on DK's averages would have someone else's opinion inside it.

READ FROM THE SCHEMA, NOT A GUESSED COLUMN INDEX. The pool is a side-by-side block whose header row
sits at an offset that varies with the number of instruction lines, so the header is LOCATED by
finding the nine named columns rather than assumed. This repository has already lost a day to an
export that wrote 7,926 rows with every meaningful column blank because field names were guessed.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.showdown import universe as U  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'showdown-to-portfolio-1'

#: DK Showdown roster shape, taken from nfl/dfs/showdown/universe.py rather than restated, so the
#: site's rules have one definition in this repository.
SALARY_CAP = U.SALARY_CAP          # 50000
N_FLEX = U.N_FLEX                  # 5
CPT_MULTIPLIER = U.CPT_MULTIPLIER  # 1.5
ROSTER_SIZE = N_FLEX + 1

POOL_COLUMNS = ('Position', 'Name + ID', 'Name', 'ID', 'Roster Position', 'Salary',
                'Game Info', 'TeamAbbrev', 'AvgPointsPerGame')
ENTRY_COLUMNS = ('Entry ID', 'Contest Name', 'Contest ID', 'Entry Fee')

#: 'CPT' plus five 'FLEX' is what makes an export a SHOWDOWN export. A classic file carries
#: QB/RB/WR/TE/FLEX/DST, and feeding one here must refuse rather than quietly build six-player
#: lineups for a nine-slot contest.
SHOWDOWN_SLOTS = ('CPT',) + ('FLEX',) * N_FLEX

#: Never an input. Named so the exclusion is explicit rather than incidental.
THIRD_PARTY_COLUMNS = ('AvgPointsPerGame',)

#: DECLARED, DETERMINISTIC team aliases from DK's vocabulary to the football corpus's. Measured, not
#: guessed: the corpus 2026 season uses 32 codes and the only one DK spells differently is the Rams
#: (DK 'LAR', corpus 'LA'). This is a lookup, NOT a name-similarity match -- a fuzzy join between two
#: team vocabularies is how a projection ends up attached to the wrong club.
TEAM_ALIAS = {'LAR': 'LA'}

#: PORTFOLIO POLICY, not estimated quantities. These are diversification choices and are labelled as
#: choices: nothing in this repository has measured an optimal showdown exposure cap, and a number
#: presented as if it had been measured would be a silent constant. They are deliberately stricter
#: than the classic path's (0.60 player, 6-of-9 overlap) because a showdown slate is one game and six
#: seats, so the same nominal cap concentrates far more risk.
#: NEAR-OPTIMAL CANDIDATE GENERATION, policy not estimate. The exact per-world optimum is always
#: included; additional lineups are admitted only within a declared objective-loss band, measured
#: against that same world's optimum. 0.10 means "scores at least 90% of what the best possible lineup
#: scored in that world". Nothing here has measured the right band -- it is a declared tolerance for
#: how much expected objective we will trade for a portfolio that can actually be filled, and it is
#: reported with every candidate so the trade is visible rather than assumed.
NEAR_OPTIMAL_LOSS_BAND = 0.10

#: How many captain-exclusion rounds to run. Each round re-solves EXACTLY, with the captains already
#: used made infeasible as captains, so each round contributes genuine constrained optima rather than
#: perturbations. More rounds cost one full solve each.
NEAR_OPTIMAL_ROUNDS = 8

#: FLEX-CORE EXCLUSION ROUNDS, and these are what actually fixed the shortfall. Captain exclusion
#: diversifies only the captain seat; the five flex seats keep converging on the same core, so the
#: pool saturates and widening the loss band buys nothing. Measured on the 26-player synthetic slate,
#: caps and band held fixed:
#:
#:   n entries        2     4     6     8    12    20
#:   optima only    1/2   3/4   5/6   6/8 10/12     -
#:   + captain      1/2   3/4   6/6   6/8 10/12     -
#:   + flex drops   2/2   3/4   6/6   7/8 12/12 20/20
#:
#: Each round drops the single most-used person from the universe and re-solves EXACTLY, so every
#: lineup is still a lawful optimum of a restricted problem and its gap is still measured against the
#: unrestricted world optimum.
NEAR_OPTIMAL_DROP_ROUNDS = 10

#: solve() labels its reporting rows with a model-confidence `tag`. This runner does not compute one,
#: so it says so rather than supplying a plausible-looking value that downstream code might believe.
TAG_NOT_CLAIMED = 'NO_CONFIDENCE_TAG_FROM_THIS_RUNNER'

MAX_PLAYER_EXPOSURE = 0.50      # a person may fill at most half the entries
MAX_CAPTAIN_EXPOSURE = 0.30     # and captain at most three in ten
MAX_OVERLAP = 4                 # of 6 seats, between any two entries in the portfolio

#: The stages that must PASS before an upload file may be written. Selection may run for research with
#: availability unresolved; PUBLISHING with unknown inactives is a different act, and this is the list
#: that stops it.
REQUIRED_FOR_PUBLICATION = ('ingest_export', 'slate_identity', 'availability', 'projections',
                            'candidates_and_selection')

OUT_BOARD = _REPO / 'nfl/dfs/salaries/SHOWDOWN_STATUS_BOARD.json'
OUT_MD = _REPO / 'nfl/dfs/salaries/SHOWDOWN_STATUS_BOARD.md'
OUT_CSV = _REPO / 'nfl/dfs/salaries/DK_SHOWDOWN_UPLOAD_GENERATED.csv'

#: Only a default. A projection built for a different week simply will not contain this game's
#: players, which is the refusal we want rather than a silent partial fill.
DEFAULT_PROJ = _REPO / 'nfl/dfs/salaries/DK_WEEK3_PROJ_V1.json'

_GAME_INFO = re.compile(r'^([A-Z]{2,4})@([A-Z]{2,4})\s+(\d{2}/\d{2}/\d{4})\s+(\d{1,2}:\d{2}[AP]M)\s+ET$')


def _rel(p: pathlib.Path) -> str:
    """Repo-relative if it is inside the repo, absolute otherwise, and NEVER raising.

    `pathlib.relative_to` raises on a path outside the base, so reporting a path this way crashed the
    stage when a caller legitimately wrote outside the tree -- a test writing to a temp directory.
    The same defect was already fixed once in nfl/production/lineage.py; a reporting convenience must
    not be able to fail the operation it is describing.
    """
    try:
        return str(p.relative_to(_REPO))
    except ValueError:
        return str(p)


def player_key(name: str, team: str) -> str:
    """Identity of a PERSON on this slate. Deliberately not the DK id, which identifies a priced item."""
    return f'{name.strip()}|{team.strip()}'


def corpus_team(dk_team: str) -> str:
    return TEAM_ALIAS.get(dk_team.strip(), dk_team.strip())


def _stage(name, outcome, **extra):
    return {'stage': name, 'state': outcome.state.value, 'code': outcome.code,
            'detail': outcome.detail, **extra}


def s1_ingest(export: pathlib.Path) -> Outcome:
    """Read the DK showdown export: the entries block and the player-pool block."""
    if not export.exists():
        return Outcome.fail('SHOWDOWN_EXPORT_ABSENT', f'{export} not found')
    rows = list(csv.reader(export.open(newline='', encoding='utf-8-sig')))
    if not rows:
        return Outcome.fail('SHOWDOWN_EXPORT_EMPTY', f'{export.name} has no rows')
    hdr = [c.strip() for c in rows[0]]

    missing = [c for c in ENTRY_COLUMNS if c not in hdr]
    if missing:
        return Outcome.fail('SHOWDOWN_ENTRY_SCHEMA', f'the entries header lacks {missing}',
                            header=hdr[:12])
    slots = [c for c in hdr if c in ('CPT', 'FLEX')]
    if tuple(slots) != SHOWDOWN_SLOTS:
        return Outcome.fail(
            'NOT_A_SHOWDOWN_EXPORT',
            f'the entry slots are {slots or "absent"}, not {list(SHOWDOWN_SLOTS)}. A classic export '
            f'fed to the showdown runner would build six-player lineups for a nine-slot contest.',
            slots=slots, header=hdr[:12])

    ei = hdr.index('Entry ID')
    entries = [{'entry_id': r[ei].strip(),
                'contest_name': r[hdr.index('Contest Name')].strip(),
                'contest_id': r[hdr.index('Contest ID')].strip(),
                'entry_fee': r[hdr.index('Entry Fee')].strip()}
               for r in rows[1:] if len(r) > ei and r[ei].strip()]

    # LOCATE the pool header: the number of instruction lines above it varies between exports, so a
    # fixed index silently reads the wrong columns.
    start = col = None
    for i, r in enumerate(rows):
        if 'Salary' in r:
            c = r.index('Salary') - POOL_COLUMNS.index('Salary')
            if c >= 0 and [x.strip() for x in r[c:c + len(POOL_COLUMNS)]] == list(POOL_COLUMNS):
                col, start = c, i + 1
                break
    if start is None:
        return Outcome.fail(
            'SHOWDOWN_POOL_BLOCK_NOT_FOUND',
            f'no row carries the nine pool columns {POOL_COLUMNS}. Without the pool there are no '
            f'salaries and no universe, and guessing the offset is how this repository previously '
            f'wrote thousands of rows with every meaningful field blank.')

    pool = []
    for r in rows[start:]:
        if len(r) < col + len(POOL_COLUMNS):
            continue
        rec = dict(zip(POOL_COLUMNS, [x.strip() for x in r[col:col + len(POOL_COLUMNS)]]))
        if not rec['ID'] or not rec['Salary']:
            continue
        try:
            rec['salary_int'] = int(rec['Salary'])
        except ValueError:
            return Outcome.fail('SHOWDOWN_SALARY_NOT_NUMERIC',
                                f"player {rec['Name']!r} has salary {rec['Salary']!r}", row=rec)
        pool.append(rec)
    if not pool:
        return Outcome.fail('SHOWDOWN_POOL_EMPTY',
                            'the pool block was located but yielded no player rows. An empty pool is '
                            'an error, not a slate with no players in it.')
    return Outcome.ok('SHOWDOWN_EXPORT_INGESTED', {'entries': entries, 'pool': pool},
                      f'{len(entries)} entries, {len(pool)} pool rows',
                      n_entries=len(entries), n_pool_rows=len(pool))


def s2_slate_identity(pool) -> Outcome:
    """Derive the game, kickoff and clubs FROM THE FILE, and check DK's own arithmetic."""
    infos = sorted({p['Game Info'] for p in pool if p['Game Info']})
    if len(infos) != 1:
        return Outcome.fail(
            'SHOWDOWN_NOT_ONE_GAME',
            f'{len(infos)} distinct Game Info values. A showdown slate is exactly one game.',
            game_info=infos[:5])
    m = _GAME_INFO.match(infos[0])
    if not m:
        return Outcome.fail('SHOWDOWN_GAME_INFO_UNPARSED',
                            f'{infos[0]!r} does not match "AWAY@HOME MM/DD/YYYY HH:MMAM ET"',
                            game_info=infos[0])
    away, home, date_s, time_s = m.groups()
    clubs = sorted({p['TeamAbbrev'] for p in pool})
    if set(clubs) != {away, home}:
        return Outcome.fail('SHOWDOWN_CLUBS_DISAGREE_WITH_GAME_INFO',
                            f'the pool carries clubs {clubs} but Game Info names {away}@{home}',
                            clubs=clubs, away=away, home=home)

    # Build the universe keyed by PERSON. Each person must have exactly one CPT item and one FLEX item.
    players = {}
    dupes = []
    for p in pool:
        rp = p['Roster Position']
        if rp not in ('CPT', 'FLEX'):
            return Outcome.fail('SHOWDOWN_UNEXPECTED_ROSTER_POSITION',
                                f'{rp!r} is neither CPT nor FLEX', row=p)
        k = player_key(p['Name'], p['TeamAbbrev'])
        rec = players.setdefault(k, {'name': p['Name'], 'dk_team': p['TeamAbbrev'],
                                     'team': corpus_team(p['TeamAbbrev']),
                                     'position': p['Position']})
        slot = rp.lower()
        if slot in rec:
            dupes.append({'player': k, 'slot': rp})
            continue
        rec[slot] = {'dk_id': p['ID'], 'salary': p['salary_int']}
    if dupes:
        return Outcome.fail(
            'SHOWDOWN_PLAYER_PRICED_TWICE_IN_ONE_SLOT',
            f'{len(dupes)} player/slot pair(s) appear more than once, so the universe cannot say '
            f'which price is the real one', offending=dupes[:8])
    incomplete = sorted(k for k, v in players.items() if 'cpt' not in v or 'flex' not in v)
    if incomplete:
        return Outcome.fail(
            'SHOWDOWN_PLAYER_MISSING_A_PRICED_SLOT',
            f'{len(incomplete)} player(s) lack a CPT or a FLEX price, so they could be placed in a '
            f'slot DK has not priced', players=incomplete[:10])

    # CHECKED, not derived. If DK ever stops pricing the captain at this multiple, computing it
    # ourselves would produce a cap-legal-looking lineup the site rejects.
    mism = [{'player': k, 'flex': v['flex']['salary'], 'cpt': v['cpt']['salary'],
             'expected_cpt': round(v['flex']['salary'] * CPT_MULTIPLIER)}
            for k, v in players.items()
            if v['cpt']['salary'] != round(v['flex']['salary'] * CPT_MULTIPLIER)]
    if mism:
        return Outcome.fail(
            'SHOWDOWN_CAPTAIN_MULTIPLIER_DISAGREES',
            f'{len(mism)} player(s) have a captain salary that is not {CPT_MULTIPLIER}x their flex '
            f'salary. CPT_MULTIPLIER is a site rule, so a disagreement means the rule changed and we '
            f'would be pricing lineups DK will not accept.', offending=mism[:5])

    # The DK fact this module turns on. Asserted so that if DK ever shares one id across both slots,
    # the slot-specific upload logic below is revisited deliberately rather than silently.
    shared = [k for k, v in players.items() if v['cpt']['dk_id'] == v['flex']['dk_id']]
    if shared:
        return Outcome.fail(
            'SHOWDOWN_SLOT_IDS_NOT_DISTINCT',
            f'{len(shared)} player(s) share one dk_id across CPT and FLEX. Every export measured so '
            f'far prices the two slots as separate items with separate ids, and the upload writes the '
            f'slot-specific id on that basis. If this has changed, the emit stage must be revisited.',
            players=shared[:8])

    kick = dt.datetime.strptime(f'{date_s} {time_s}', '%m/%d/%Y %I:%M%p')
    return Outcome.ok('SHOWDOWN_SLATE_IDENTIFIED', {
        'away': away, 'home': home, 'clubs': clubs, 'players': players,
        'kickoff_et_naive': kick.isoformat(),
        'KICKOFF_TIMEZONE': ('DK writes ET with no offset, so this is a naive ET wall-clock time and '
                             'is NOT converted to UTC. Converting needs the DST rule in force on the '
                             'date, and a silently wrong kickoff corrupts every point-in-time '
                             'evidence cut downstream.'),
    }, f'{away}@{home} at {kick.isoformat()} ET, {len(players)} players',
        away=away, home=home, n_players=len(players),
        positions=dict(collections.Counter(v['position'] for v in players.values())))


def s3_availability(slate, official_inactives=None) -> Outcome:
    """Who is out. UNKNOWN is not NOT-PLAYING, and an absent list is DEFERRED, not an empty set.

    `official_inactives` is a list of player keys ("Name|DKTEAM") or plain names.
    """
    if official_inactives is None:
        return Outcome.deferred(
            'SHOWDOWN_OFFICIAL_INACTIVES_NOT_SUPPLIED',
            'no official inactive list was supplied for this game',
            owed='the official inactives, published about 90 minutes before kickoff',
            note=('DEFERRED and NOT an empty set. UNKNOWN is not NOT PLAYING and MISSING is not '
                  'INACTIVE. Treating an absent list as "everybody plays" is the error that makes a '
                  'portfolio look complete while holding a scratched player.'))
    byname = collections.defaultdict(list)
    for k, v in slate['players'].items():
        byname[v['name']].append(k)
    resolved, unknown, ambiguous = set(), [], []
    for item in official_inactives:
        if item in slate['players']:
            resolved.add(item)
        elif item in byname:
            if len(byname[item]) > 1:
                ambiguous.append({'name': item, 'candidates': byname[item]})
            else:
                resolved.add(byname[item][0])
        else:
            unknown.append(item)
    if unknown:
        return Outcome.fail(
            'SHOWDOWN_INACTIVE_NOT_IN_SLATE',
            f'{len(unknown)} inactive entry(ies) match nobody in this slate, so the list is for a '
            f'different game or the identities do not line up. Dropping them would quietly roster a '
            f'player who is out.', unmatched=unknown[:10])
    if ambiguous:
        return Outcome.fail('SHOWDOWN_INACTIVE_AMBIGUOUS',
                            f'{len(ambiguous)} name(s) match more than one player on this slate',
                            ambiguous=ambiguous[:5])
    return Outcome.ok('SHOWDOWN_AVAILABILITY_RESOLVED', {'absent': resolved},
                      f'{len(resolved)} ruled out of {len(slate["players"])}',
                      n_absent=len(resolved))


def s4_projections(slate, absent, proj_path: pathlib.Path = None) -> Outcome:
    """Our own dk_points per player, joined on (name, club), or a refusal naming who is missing.

    JOINED ON IDENTITY, NOT dk_id. The showdown draftgroup has its own id space, disjoint from the
    classic one, so a dk_id join would match nothing and -- worse -- could match something wrong.
    """
    proj_path = DEFAULT_PROJ if proj_path is None else proj_path
    if not proj_path.exists():
        return Outcome.blocked('SHOWDOWN_PROJECTION_ARTIFACT_ABSENT', f'{proj_path} not found',
                               cause=Cause.DATA, path=str(proj_path))
    art = json.loads(proj_path.read_text())
    rows = art.get('rows')
    if not isinstance(rows, dict) or not rows:
        return Outcome.fail('SHOWDOWN_PROJECTION_ARTIFACT_SHAPE',
                            f'{proj_path.name} carries no non-empty "rows" map')
    index = collections.defaultdict(list)
    for r in rows.values():
        if r.get('name') and r.get('team'):
            index[player_key(r['name'], r['team'])].append(r)

    want = [k for k in slate['players'] if k not in absent]
    got, missing, ambiguous, declared_out = {}, [], [], []
    for k in want:
        v = slate['players'][k]
        hits = index.get(player_key(v['name'], v['team']), [])
        if len(hits) > 1:
            ambiguous.append({'player': k, 'n': len(hits)})
            continue
        # A ROW THAT DECLINES TO PROJECT ON AVAILABILITY GROUNDS IS AN ANSWER, NOT A GAP.
        # MISSING is not the same thing as DECLARED NOT PLAYING, and conflating them made the runner
        # refuse a complete slate: the model had addressed all 51 players and said of two of them
        # "reported out, so no projection", which is precisely what it should say. A coverage gap is a
        # player the model is SILENT about.
        if hits and str(hits[0].get('projection_state') or '').startswith('NOT_PLAYING'):
            declared_out.append({'player': k, 'name': v['name'], 'club': v['team'],
                                 'position': v['position'],
                                 'projection_state': hits[0].get('projection_state')})
            continue
        if not hits or not isinstance(hits[0].get('dk_points'), (int, float)):
            missing.append({'player': k, 'name': v['name'], 'club': v['team'],
                            'position': v['position'],
                            'projection_state': (hits[0].get('projection_state') if hits
                                                 else 'NO_ROW_IN_THE_PROJECTION')})
            continue
        got[k] = {'dk_points': float(hits[0]['dk_points']),
                  'gsis_id': hits[0].get('gsis_id'),
                  'projection_state': hits[0].get('projection_state')}
    if ambiguous:
        return Outcome.fail('SHOWDOWN_PROJECTION_AMBIGUOUS',
                            f'{len(ambiguous)} player(s) match more than one projection row',
                            ambiguous=ambiguous[:5])
    if missing:
        return Outcome.blocked(
            'SHOWDOWN_PROJECTION_DOES_NOT_COVER_THIS_GAME',
            f'{len(missing)} of {len(want)} rosterable players have no dk_points in '
            f'{proj_path.name}. A projection built for another week does not contain this game, and '
            f'filling the gap from {THIRD_PARTY_COLUMNS[0]} would put a third party\'s opinion '
            f'inside our portfolio.',
            cause=Cause.DATA, n_missing=len(missing), n_wanted=len(want), missing=missing[:12],
            artifact=proj_path.name,
            WOULD_RESOLVE_IT='a proprietary projection covering this game, joinable on (name, club)')
    return Outcome.ok('SHOWDOWN_PROJECTIONS_READ',
                      {'projected': got, 'declared_not_playing': [d['player'] for d in declared_out]},
                      f'{len(got)} players projected, {len(declared_out)} declared not playing',
                      n=len(got), n_declared_not_playing=len(declared_out),
                      declared_not_playing=declared_out, artifact=proj_path.name,
                      MISSING_IS_NOT_DECLARED_OUT=(
                          'a player the model declined to project because he is reported out has been '
                          'ANSWERED. Only silence is a coverage gap.'),
                      THIRD_PARTY_COLUMNS_NOT_READ=list(THIRD_PARTY_COLUMNS))


def _lineup_score(cap_key, flex_keys, draws, world: int) -> float:
    """Score one lineup in one world, exactly as optimal_worlds scores it.

    Taken from the solver's own transition, `dp[...] + v * U.CPT_MULTIPLIER` for the captain and `v`
    for a flex seat, so a gap computed here is comparable with the optimum the solver reported. A
    scoring rule restated by hand and allowed to drift would make every gap meaningless.
    """
    return (CPT_MULTIPLIER * float(draws[cap_key][world])
            + sum(float(draws[k][world]) for k in flex_keys))


def near_optimal_candidates(slate, absent, draws, *, loss_band: float = None,
                            rounds: int = None, drop_rounds: int = None) -> Outcome:
    """A broader LAWFUL candidate pool: exact per-world optima, plus constrained optima near them.

    WHY. Selecting only from per-world optima gives a narrow pool, because optima share a high-value
    core. Once the exposure cap retires that core there is often no further candidate that also
    respects the overlap cap, and the selector lands short. The wrong fix is to loosen the caps to fill
    the file. The right fix is more lawful candidates.

    HOW, and why it reuses the audited solver rather than writing a second one. Each round calls
    `optimal_worlds.solve` again with the captains already used made INFEASIBLE AS CAPTAINS -- their
    captain salary is raised above the cap, so no captain state can be entered for them, while they
    remain fully available as flex. Every lineup returned is therefore an EXACT optimum of a
    constrained problem, carrying the solver's own guarantees: one captain and five flex, under the
    cap, both clubs represented, no duplicate person. Nothing is perturbed, nothing is repaired, and
    there is no second dynamic program to drift out of agreement with the first.

    EVERY CANDIDATE RECORDS ITS OBJECTIVE GAP from the world optimum it is being compared against, and
    the exact optima are always included with a gap of zero.

    NO CORRELATION OR OWNERSHIP IS INVENTED. The only inputs are the draws supplied by the caller.
    Candidates are ranked by how often they are world-optimal and by objective gap -- never by
    projected ownership, leverage or duplication, none of which this function has or pretends to have.
    """
    import numpy as np
    from nfl.dfs.showdown import optimal_worlds as OW

    band = NEAR_OPTIMAL_LOSS_BAND if loss_band is None else float(loss_band)
    n_rounds = NEAR_OPTIMAL_ROUNDS if rounds is None else int(rounds)
    if not 0.0 <= band < 1.0:
        return Outcome.fail('SHOWDOWN_LOSS_BAND_OUT_OF_RANGE',
                            f'loss band {band} must be in [0, 1)', band=band)

    want = sorted(k for k in slate['players'] if k not in absent)
    pre = _draws_precheck(slate, absent, draws, want)
    if pre is not None:
        return pre
    n_worlds = len(draws[want[0]])

    def _players(forbid_captain=(), drop=()):
        out = []
        for k in want:
            if k in drop:
                # DROPPED FROM THE UNIVERSE ENTIRELY, not merely as captain. This is what diversifies
                # the five flex seats, and the solve over the reduced universe is still exact, so the
                # lineup is still lawful.
                continue
            v = slate['players'][k]
            cpt = v['cpt']['salary']
            if k in forbid_captain:
                # INFEASIBLE AS CAPTAIN, STILL AVAILABLE AS FLEX. The DP indexes captain states by
                # cpt_salary // unit against a budget of cap // unit, so a captain salary above the
                # cap cannot enter any captain state. This is the whole mechanism -- no flag is added
                # to the solver and its logic is untouched.
                cpt = SALARY_CAP + 1000
            out.append({'name': k, 'team': v['dk_team'], 'pos': v['position'],
                        'tag': TAG_NOT_CLAIMED, 'salary': v['flex']['salary'],
                        'cpt_salary': cpt, 'draws': np.asarray(draws[k], dtype=float)})
        return out

    n_drop = NEAR_OPTIMAL_DROP_ROUNDS if drop_rounds is None else int(drop_rounds)
    base = OW.solve(_players(), cap=SALARY_CAP, n_flex=N_FLEX, require_team_coverage=True)
    if base.state.value != 'PASS':
        return base
    names = base.value['names']
    # The world optimum each candidate is measured against.
    world_best = {}
    for w, ln in enumerate(base.value['lineups']):
        if ln is None:
            continue
        cpt_i, flex_i = ln
        world_best[w] = _lineup_score(names[cpt_i], [names[i] for i in flex_i], draws, w)
    if not world_best:
        return Outcome.fail(
            'SHOWDOWN_NO_FEASIBLE_LINEUP',
            'the exact solve produced no feasible lineup in any world, so there is no optimum to '
            'measure a near-optimal band against.')

    cands = {}

    def _absorb(outcome, round_no):
        nm = outcome.value['names']
        for w, ln in enumerate(outcome.value['lineups']):
            if ln is None or w not in world_best:
                continue
            cpt_i, flex_i = ln
            cap_key = nm[cpt_i]
            flex_keys = tuple(sorted(nm[i] for i in flex_i))
            sc = _lineup_score(cap_key, flex_keys, draws, w)
            best = world_best[w]
            gap = 0.0 if best <= 0 else max(0.0, (best - sc) / best)
            if round_no > 0 and gap > band:
                continue
            key = (cap_key, flex_keys)
            rec = cands.setdefault(key, {'captain': cap_key, 'flex': list(flex_keys),
                                         'n_worlds_optimal': 0, 'gaps': [], 'rounds': set()})
            if round_no == 0:
                rec['n_worlds_optimal'] += 1
            rec['gaps'].append(gap)
            rec['rounds'].add(round_no)

    _absorb(base, 0)
    used_captains = {c['captain'] for c in cands.values()}
    rounds_run = [{'round': 0, 'forbidden_captains': 0, 'n_candidates_after': len(cands)}]
    for r in range(1, max(1, n_rounds)):
        if len(used_captains) >= len(want) - N_FLEX:
            break
        o = OW.solve(_players(forbid_captain=used_captains), cap=SALARY_CAP, n_flex=N_FLEX,
                     require_team_coverage=True)
        if o.state.value != 'PASS':
            # A round that cannot solve is not an error: the captain pool is exhausted. Recorded.
            rounds_run.append({'round': r, 'forbidden_captains': len(used_captains),
                               'stopped': o.code})
            break
        before = len(cands)
        _absorb(o, r)
        rounds_run.append({'round': r, 'forbidden_captains': len(used_captains),
                           'n_new': len(cands) - before, 'n_candidates_after': len(cands)})
        new_caps = {c['captain'] for c in cands.values()} - used_captains
        if not new_caps:
            break
        used_captains |= new_caps

    # FLEX-CORE EXCLUSION. Drop the most-used person and re-solve, repeatedly. Captain exclusion
    # saturates the pool because the flex seats keep reconverging; this is the round type that moved
    # the fill numbers.
    dropped = set()
    for r in range(max(0, n_drop)):
        counts = collections.Counter()
        for rec in cands.values():
            for k in [rec['captain']] + rec['flex']:
                counts[k] += 1
        nxt = next((k for k, _ in counts.most_common() if k not in dropped), None)
        if nxt is None or len(want) - len(dropped) - 1 < ROSTER_SIZE:
            break
        dropped.add(nxt)
        o = OW.solve(_players(drop=dropped), cap=SALARY_CAP, n_flex=N_FLEX,
                     require_team_coverage=True)
        if o.state.value != 'PASS':
            rounds_run.append({'drop_round': r, 'n_dropped': len(dropped), 'stopped': o.code})
            break
        before = len(cands)
        _absorb(o, 1000 + r)
        rounds_run.append({'drop_round': r, 'n_dropped': len(dropped),
                           'n_new': len(cands) - before, 'n_candidates_after': len(cands)})

    rows = []
    for rec in cands.values():
        lawful = validate_lineup({'captain': rec['captain'], 'flex': rec['flex']}, slate, absent)
        if lawful.state.value != 'PASS':
            # Should be unreachable: every candidate came from the constrained DP. Kept as a tripwire
            # rather than an assertion, so an unlawful candidate is reported instead of crashing.
            continue
        rows.append({'captain': rec['captain'], 'flex': rec['flex'],
                     'n_worlds_optimal': rec['n_worlds_optimal'],
                     'best_gap': round(min(rec['gaps']), 6),
                     'mean_gap': round(sum(rec['gaps']) / len(rec['gaps']), 6),
                     'first_round': min(rec['rounds']),
                     'salary': lawful.value['salary']})
    rows.sort(key=lambda r: (-r['n_worlds_optimal'], r['best_gap'],
                            r['captain'], tuple(r['flex'])))
    n_exact = sum(1 for r in rows if r['n_worlds_optimal'] > 0)
    return Outcome.ok('SHOWDOWN_CANDIDATES_GENERATED', rows,
                      f'{len(rows)} lawful candidates, {n_exact} world-optimal',
                      n_candidates=len(rows), n_world_optimal=n_exact,
                      n_worlds=n_worlds, loss_band=band, rounds=rounds_run,
                      n_dropped_for_diversity=len(dropped),
                      max_gap=round(max((r['best_gap'] for r in rows), default=0.0), 6),
                      EXACT_OPTIMA_ALWAYS_INCLUDED=True,
                      RANKED_BY='world-optimality count then objective gap',
                      NOT_RANKED_BY='ownership, leverage or duplication -- none of which exist here')


def _draws_precheck(slate, absent, draws, want):
    """Shared draws validation. Returns an Outcome to propagate, or None if the draws are usable."""
    if len(want) < ROSTER_SIZE:
        return Outcome.fail(
            'SHOWDOWN_TOO_FEW_ROSTERABLE',
            f'{len(want)} rosterable player(s) cannot fill {ROSTER_SIZE} seats', n=len(want))
    missing = [k for k in want if k not in (draws or {})]
    if missing:
        return Outcome.blocked(
            'SHOWDOWN_DRAWS_ABSENT',
            f'{len(missing)} of {len(want)} rosterable players have no simulated draws. p_optimal is '
            f'a property of the joint distribution under a cap and cannot be computed from a '
            f'projected mean; manufacturing draws from one would invent the quantity being measured.',
            cause=Cause.DATA, n_missing=len(missing), missing=missing[:12],
            WOULD_RESOLVE_IT='a sealed simulation producing per-player DK-point draws for this game')
    lens = {len(draws[k]) for k in want}
    if len(lens) != 1:
        return Outcome.fail(
            'SHOWDOWN_DRAWS_RAGGED',
            f'draw sequences have {len(lens)} different lengths {sorted(lens)[:4]}. Worlds must be '
            f'shared across players or a "world" means a different thing per column, and the joint '
            f'structure the optimiser measures is destroyed.', lengths=sorted(lens)[:6])
    return None


def s5_candidates_and_selection(slate, absent, draws, n_entries: int) -> Outcome:
    """Generate a lawful candidate pool, then fill the portfolio from it under the declared caps.

    The pool is `near_optimal_candidates`: the exact per-world optima plus constrained optima within
    the declared objective-loss band. The CAPS ARE NOT RELAXED to fill the file -- if the broader pool
    still cannot satisfy them, that is reported with the partial portfolio and the shortfall stands.
    """
    gen = near_optimal_candidates(slate, absent, draws)
    if gen.state.value != 'PASS':
        return gen
    ranked = gen.value
    if not ranked:
        return Outcome.fail(
            'SHOWDOWN_NO_FEASIBLE_LINEUP',
            'the candidate generator produced no lawful lineup. An empty candidate set is an error, '
            'not a portfolio of nothing.')

    chosen, exposure, cpt_exposure = [], collections.Counter(), collections.Counter()
    cap_player = max(1, int(MAX_PLAYER_EXPOSURE * n_entries))
    cap_cpt = max(1, int(MAX_CAPTAIN_EXPOSURE * n_entries))
    for cand in ranked:
        if len(chosen) >= n_entries:
            break
        seats = [cand['captain']] + cand['flex']
        if any(exposure[k] + 1 > cap_player for k in seats):
            continue
        if cpt_exposure[cand['captain']] + 1 > cap_cpt:
            continue
        if any(len(set(seats) & set([c['captain']] + c['flex'])) > MAX_OVERLAP for c in chosen):
            continue
        v = validate_lineup(cand, slate, absent)
        if v.state.value != 'PASS':
            continue
        chosen.append(cand)
        for k in seats:
            exposure[k] += 1
        cpt_exposure[cand['captain']] += 1

    caps = {'player': MAX_PLAYER_EXPOSURE, 'captain': MAX_CAPTAIN_EXPOSURE,
            'overlap': MAX_OVERLAP}
    pool = {'n_candidates': gen.evidence.get('n_candidates'),
            'n_world_optimal': gen.evidence.get('n_world_optimal'),
            'loss_band': gen.evidence.get('loss_band')}
    if len(chosen) < n_entries:
        return Outcome.deferred(
            'SHOWDOWN_PORTFOLIO_SHORT_OF_ENTRIES',
            f'{len(chosen)} lineups satisfy the declared caps out of a pool of {len(ranked)}, against '
            f'{n_entries} entries. The caps are a policy choice and loosening them to fill the file is '
            f'exactly the move this project forbids, so the shortfall is reported rather than '
            f'absorbed.',
            owed='either fewer entries, a wider loss band as an explicit decision, or more rounds',
            n_chosen=len(chosen), n_entries=n_entries, partial=chosen, caps=caps, pool=pool)
    return Outcome.ok('SHOWDOWN_PORTFOLIO_SELECTED', chosen,
                      f'{len(chosen)} entries from a pool of {len(ranked)}',
                      n_chosen=len(chosen), n_candidates=len(ranked), caps=caps, pool=pool,
                      max_gap_used=round(max(c['best_gap'] for c in chosen), 6),
                      site_legality_enforced=True)


def validate_lineup(lineup, slate, absent=()) -> Outcome:
    """Is this six-player lineup one DK would accept? Each clause separately, with a named code.

    `lineup` is {'captain': player_key, 'flex': [player_key x5]}.
    """
    cap, flex = lineup.get('captain'), list(lineup.get('flex') or [])
    if cap is None or len(flex) != N_FLEX:
        return Outcome.fail('LINEUP_WRONG_SHAPE',
                            f'expected one captain and {N_FLEX} flex, got {cap!r} and {len(flex)}')
    keys = [cap] + flex
    if len(set(keys)) != ROSTER_SIZE:
        dup = [k for k, v in collections.Counter(keys).items() if v > 1]
        return Outcome.fail('LINEUP_DUPLICATE_PLAYER',
                            'a player appears more than once, including as captain and flex',
                            players=dup)
    unknown = [k for k in keys if k not in slate['players']]
    if unknown:
        return Outcome.fail('LINEUP_PLAYER_NOT_IN_SLATE', 'a player is not in this slate',
                            players=unknown)
    scratched = [k for k in keys if k in (absent or ())]
    if scratched:
        return Outcome.fail('LINEUP_CONTAINS_AN_ABSENT_PLAYER', 'a player ruled out is rostered',
                            players=scratched)
    salary = (slate['players'][cap]['cpt']['salary']
              + sum(slate['players'][k]['flex']['salary'] for k in flex))
    if salary > SALARY_CAP:
        return Outcome.fail('LINEUP_OVER_THE_CAP', f'{salary} against a cap of {SALARY_CAP}',
                            salary=salary)
    teams = {slate['players'][k]['dk_team'] for k in keys}
    if len(teams) < 2:
        return Outcome.fail(
            'LINEUP_SINGLE_TEAM',
            'DK Showdown requires at least one player from each club. This is a SITE RULE: a lineup '
            'breaking it cannot be entered, however well it scores.', teams=sorted(teams))
    return Outcome.ok('LINEUP_LEGAL',
                      {'salary': salary, 'teams': sorted(teams),
                       'cpt_dk_id': slate['players'][cap]['cpt']['dk_id'],
                       'flex_dk_ids': [slate['players'][k]['flex']['dk_id'] for k in flex]},
                      f'{salary} of {SALARY_CAP}, {len(teams)} clubs', salary=salary)


def s_emit_csv(chosen, entries, slate, out: pathlib.Path = None) -> Outcome:
    """Write the DK upload file, CPT + 5 FLEX, using the SLOT-SPECIFIC dk_id for each seat."""
    out = OUT_CSV if out is None else out
    if not chosen:
        return Outcome.fail('SHOWDOWN_NOTHING_TO_EMIT',
                            'no lineup was selected, so there is no upload file. An empty CSV that '
                            'looks like a deliverable is worse than none.')
    if len(chosen) < len(entries):
        return Outcome.fail(
            'SHOWDOWN_FEWER_LINEUPS_THAN_ENTRIES',
            f'{len(chosen)} lineups for {len(entries)} entries. Writing it anyway would leave entries '
            f'silently blank.', n_lineups=len(chosen), n_entries=len(entries))
    for i, ln in enumerate(chosen):
        v = validate_lineup(ln, slate)
        if v.state.value != 'PASS':
            return Outcome.fail('SHOWDOWN_ILLEGAL_LINEUP_AT_EMIT',
                                f'lineup {i} is not enterable: {v.code}. The legality gate runs again '
                                f'here so an illegal lineup cannot reach a file.',
                                index=i, code=v.code, detail=v.detail)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(list(ENTRY_COLUMNS) + list(SHOWDOWN_SLOTS))
        for e, ln in zip(entries, chosen):
            p = slate['players']
            w.writerow([e['entry_id'], e['contest_name'], e['contest_id'], e['entry_fee'],
                        p[ln['captain']]['cpt']['dk_id'],
                        *[p[k]['flex']['dk_id'] for k in ln['flex']]])
    return Outcome.ok('SHOWDOWN_CSV_WRITTEN', {'path': _rel(out)},
                      f'{len(chosen)} rows', n_rows=len(chosen),
                      SLOT_SPECIFIC_IDS=('the CPT column carries the captain item id and each FLEX '
                                         'column the flex item id, which are different numbers for '
                                         'the same person'),
                      NOT_SUBMITTED=('written to disk; nothing uploads it. Entering a contest is the '
                                     'owner\'s action, never this runner\'s.'))


def run(export, *, official_inactives=None, proj_path=None, draws=None, n_entries=None,
        out_csv=None) -> Outcome:
    """Drive the stages. The board is emitted whatever happens."""
    export = pathlib.Path(export)
    stages = []
    board = {'ARTIFACT': 'SHOWDOWN_STATUS_BOARD', 'spec_version': SPEC_VERSION,
             'export': str(export), 'run_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
             'stages': stages,
             'BOARD_SEMANTICS': ('this board always exists. A stage that could not run appears here '
                                 'as the reason the product is degraded, rather than as silence.')}

    def finish(code, detail, **extra):
        board['RESULT'] = code
        board['RESULT_DETAIL'] = detail
        board.update(extra)
        OUT_BOARD.parent.mkdir(parents=True, exist_ok=True)
        OUT_BOARD.write_text(json.dumps(board, indent=2, default=str))
        OUT_MD.write_text(_render(board))
        return board

    o1 = s1_ingest(export)
    stages.append(_stage('ingest_export', o1, **(o1.evidence or {})))
    if o1.state.value != 'PASS':
        return Outcome.fail('SHOWDOWN_RUN_REFUSED', f'ingest: {o1.code}',
                            board=finish('REFUSED', o1.detail, refused_at='ingest_export'))
    entries, pool = o1.value['entries'], o1.value['pool']

    o2 = s2_slate_identity(pool)
    stages.append(_stage('slate_identity', o2, **(o2.evidence or {})))
    if o2.state.value != 'PASS':
        return Outcome.fail('SHOWDOWN_RUN_REFUSED', f'identity: {o2.code}',
                            board=finish('REFUSED', o2.detail, refused_at='slate_identity'))
    slate = o2.value
    board['game'] = {'away': slate['away'], 'home': slate['home'],
                     'kickoff_et_naive': slate['kickoff_et_naive'],
                     'n_players': len(slate['players']), 'n_entries': len(entries)}

    o3 = s3_availability(slate, official_inactives)
    stages.append(_stage('availability', o3, **(o3.evidence or {})))
    if o3.state.value == 'FAIL':
        return Outcome.fail('SHOWDOWN_RUN_REFUSED', f'availability: {o3.code}',
                            board=finish('REFUSED', o3.detail, refused_at='availability'))
    absent = set(o3.value['absent']) if o3.state.value == 'PASS' else set()
    board['availability_is_complete'] = (o3.state.value == 'PASS')

    o4 = s4_projections(slate, absent, proj_path)
    stages.append(_stage('projections', o4, **(o4.evidence or {})))
    if o4.state.value != 'PASS':
        return Outcome.blocked(
            'SHOWDOWN_RUN_BLOCKED', f'projections: {o4.code}', cause=Cause.DATA,
            board=finish('BLOCKED_NO_PROJECTIONS', o4.detail, refused_at='projections'))

    # Players the projection declared out are excluded from selection as well as from coverage.
    absent = set(absent) | set((o4.value or {}).get('declared_not_playing') or ())
    n = len(entries) if n_entries is None else int(n_entries)
    o5 = s5_candidates_and_selection(slate, absent, draws, n)
    stages.append(_stage('candidates_and_selection', o5, **(o5.evidence or {})))
    if o5.state.value != 'PASS':
        return Outcome.blocked(
            'SHOWDOWN_RUN_BLOCKED', f'selection: {o5.code}', cause=Cause.DATA,
            board=finish('BLOCKED_NO_PORTFOLIO', o5.detail, refused_at='candidates_and_selection'))
    chosen = o5.value

    # THE PUBLICATION GATE. Selection may run for research with availability unresolved; writing an
    # upload file is a different act. A portfolio built without the official inactives can hold a
    # player who is out, and the board records which stage withheld publication rather than writing a
    # file that looks finished.
    by_stage = {st['stage']: st['state'] for st in stages}
    withheld = [nm for nm in REQUIRED_FOR_PUBLICATION if by_stage.get(nm) != 'PASS']
    if withheld:
        return Outcome.deferred(
            'SHOWDOWN_PUBLICATION_WITHHELD',
            f'a portfolio of {len(chosen)} lineups was selected, but {withheld} did not PASS so no '
            f'upload file is written. An upload built on an unresolved stage looks finished and is '
            f'not.',
            owed=f'resolve {withheld}',
            board=finish('SELECTED_NOT_PUBLISHED',
                         f'selected {len(chosen)}; publication withheld on {withheld}',
                         refused_at='publication_gate', withheld=withheld,
                         n_selected=len(chosen)))

    o6 = s_emit_csv(chosen, entries[:len(chosen)], slate, out=out_csv)
    stages.append(_stage('emit_csv', o6, **(o6.evidence or {})))
    if o6.state.value != 'PASS':
        return Outcome.fail('SHOWDOWN_RUN_REFUSED', f'emit: {o6.code}',
                            board=finish('REFUSED', o6.detail, refused_at='emit_csv'))
    return Outcome.ok('SHOWDOWN_PORTFOLIO_DELIVERED',
                      {'n_entries': len(chosen), 'upload': o6.value['path']},
                      f'{len(chosen)} entries written',
                      board=finish('DELIVERED', f'{len(chosen)} entries written',
                                   n_selected=len(chosen), upload=o6.value['path']))


def _render(b) -> str:
    L = [f"# Showdown status board — {b.get('RESULT', 'UNKNOWN')}", '',
         f"export `{b.get('export')}`", f"run {b.get('run_at_utc')}", '']
    g = b.get('game')
    if g:
        L += [f"**{g['away']}@{g['home']}** at {g['kickoff_et_naive']} ET — "
              f"{g['n_players']} players, {g['n_entries']} entries", '']
    L += ['| stage | state | code |', '|---|---|---|']
    for s in b.get('stages') or []:
        L.append(f"| {s['stage']} | {s['state']} | {s['code']} |")
    L += ['', f"**{b.get('RESULT')}** — {b.get('RESULT_DETAIL')}", '',
          'Nothing here is a recommendation to wager, and nothing uploads a lineup.']
    return '\n'.join(L) + '\n'


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description='DK showdown export in, legal portfolio out.')
    ap.add_argument('export', help='path to the DK showdown entries CSV')
    ap.add_argument('--projections', default=None,
                    help='projection artifact with a rows map (default: the Week 3 V1 artifact)')
    ap.add_argument('--inactives', default=None,
                    help='JSON file holding a list of official inactive names or "Name|TEAM" keys')
    ap.add_argument('--draws', default=None,
                    help='draws artifact from showdown_draws.py')
    ap.add_argument('--entries', type=int, default=None,
                    help='how many entries to fill (default: every entry in the export)')
    a = ap.parse_args()
    inact = json.loads(pathlib.Path(a.inactives).read_text()) if a.inactives else None
    draws = None
    if a.draws:
        d = json.loads(pathlib.Path(a.draws).read_text())
        draws = d.get('draws', d)
    o = run(a.export, official_inactives=inact, draws=draws, n_entries=a.entries,
            proj_path=pathlib.Path(a.projections) if a.projections else None)
    print(o.state.value, o.code)
    print(o.detail or '')
    b = (o.evidence or {}).get('board') or {}
    g = b.get('game')
    if g:
        print(f"  game  {g['away']}@{g['home']} at {g['kickoff_et_naive']} ET  "
              f"{g['n_players']} players, {g['n_entries']} entries")
    for s in b.get('stages') or []:
        print(f"  {s['stage']:28s} {s['state']:10s} {s['code']}")
    print(f"  board -> {_rel(OUT_BOARD)}")
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
