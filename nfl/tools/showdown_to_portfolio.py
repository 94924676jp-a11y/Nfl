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
    got, missing, ambiguous = {}, [], []
    for k in want:
        v = slate['players'][k]
        hits = index.get(player_key(v['name'], v['team']), [])
        if len(hits) > 1:
            ambiguous.append({'player': k, 'n': len(hits)})
            continue
        if not hits or not isinstance(hits[0].get('dk_points'), (int, float)):
            missing.append({'player': k, 'name': v['name'], 'club': v['team'],
                            'position': v['position']})
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
    return Outcome.ok('SHOWDOWN_PROJECTIONS_READ', got, f'{len(got)} players projected',
                      n=len(got), artifact=proj_path.name,
                      THIRD_PARTY_COLUMNS_NOT_READ=list(THIRD_PARTY_COLUMNS))


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


def run(export, *, official_inactives=None, proj_path=None) -> Outcome:
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

    # Candidate generation and portfolio selection are NOT wired yet, and this says so rather than
    # emitting a lineup from an unwired optimiser. nfl/dfs/showdown/optimal_worlds.solve already
    # carries the both-teams constraint in its DP state and is the thing to connect; validate_lineup
    # above is already the legality gate for whatever it returns.
    o5 = Outcome.deferred(
        'SHOWDOWN_SELECTION_NOT_WIRED',
        'projections cover this slate, but candidate generation and portfolio selection are not yet '
        'connected to optimal_worlds.solve',
        owed='wire optimal_worlds.solve and a portfolio selector with exposure and overlap caps',
        note=('DEFERRED with the stages above it PASSING, so the board shows exactly how far the '
              'product got. Emitting a lineup from an unwired optimiser would be worse.'))
    stages.append(_stage('candidates_and_selection', o5))
    return Outcome.deferred('SHOWDOWN_RUN_INCOMPLETE', o5.detail,
                            owed='wire selection',
                            board=finish('DEGRADED_NO_SELECTION', o5.detail,
                                         refused_at='candidates_and_selection'))


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
    a = ap.parse_args()
    inact = json.loads(pathlib.Path(a.inactives).read_text()) if a.inactives else None
    o = run(a.export, official_inactives=inact,
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
