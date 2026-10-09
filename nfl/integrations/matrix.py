"""The integration matrix: every external surface, how it may be reached, and who must act.

One row per (capability, route). `access` is one of four classes, and they are not a ranking:

  FULLY_AUTOMATED               a public, documented, programmatic route that its publisher supports; this
                                system may fetch it on a schedule with no account and no credential.
  APPROVED_PROVIDER_CONNECTION  only through a licensed or paid provider, or a connector the owner has
                                approved. Building it needs the owner's decision, and usually money.
  MANUAL_EXPORT                 the owner downloads a file from his own logged-in account and drops it in
                                `nfl/dfs/inbox/drop/`. Everything after the drop is automatic.
  PROHIBITED_OR_UNSUPPORTED     the platform's terms bar automated access, or no route exists. Not built,
                                and not to be routed around.

`action` separates read-only research from everything that acts on an account:
  READ_ONLY_RESEARCH, ACCOUNT_DATA_READ (the owner's own private data, read only), ACCOUNT_ACTION,
  CONTEST_ENTRY, WAGERING, FINANCIAL. This system implements READ_ONLY_RESEARCH and ACCOUNT_DATA_READ
  only. Every other action is the owner's, by hand, on the platform itself.

`terms_evidence` is PRIMARY when the publisher's own page or repository was read, SNIPPET_ONLY when only
search-result text was seen (vendor pages were unreachable from this executor), and UNKNOWN when nothing
was found. A SNIPPET_ONLY clause must be checked on the live page before it is relied on. None of this
is legal advice. Evidence: nfl/research/integrations/PLATFORM_TERMS_AND_APIS.{json,md}.
"""
from __future__ import annotations

ACCESS = ('FULLY_AUTOMATED', 'APPROVED_PROVIDER_CONNECTION', 'MANUAL_EXPORT', 'PROHIBITED_OR_UNSUPPORTED')
ACTIONS = ('READ_ONLY_RESEARCH', 'ACCOUNT_DATA_READ', 'ACCOUNT_ACTION', 'CONTEST_ENTRY', 'WAGERING', 'FINANCIAL')
IMPLEMENTED_ACTIONS = ('READ_ONLY_RESEARCH', 'ACCOUNT_DATA_READ')
BUILD = ('RUNNING', 'BUILT', 'PARTIAL', 'NOT_BUILT', 'NOT_TO_BE_BUILT')


def _r(id_, capability, provider, route, access, action, build, terms_evidence, cadence, note,
       owner_decision=None, manifest_source=None, inbox_kind=None):
    return {'id': id_, 'capability': capability, 'provider': provider, 'route': route, 'access': access,
            'action': action, 'build': build, 'terms_evidence': terms_evidence, 'cadence': cadence,
            'note': note, 'owner_decision': owner_decision, 'manifest_source': manifest_source,
            'inbox_kind': inbox_kind}


MATRIX = [
    # ---------------------------------------------------------------- 1. official roster, injury, schedule, stats
    _r('I01', 'Schedule and kickoff times', 'nflverse', 'GitHub release schedules file',
       'FULLY_AUTOMATED', 'READ_ONLY_RESEARCH', 'RUNNING', 'PRIMARY',
       'publisher: every 5 min in season; our capture: observed every 6-7 h',
       'Captured by .github/workflows/nfl-capture.yml to branch capture-prod.', manifest_source='schedules'),
    _r('I02', 'Weekly rosters (status ACT/RES/DEV)', 'nflverse', 'GitHub release weekly roster file',
       'FULLY_AUTOMATED', 'READ_ONLY_RESEARCH', 'PARTIAL', 'PRIMARY', 'publisher: daily 07:00 UTC',
       'Captured, but the committed blob is REDUCED to season/week/team/gsis_id/position: it drops `status` '
       'and names, which the research universe needs. The universe is still built from a manual full-file '
       'slice. Gap INT-G1.', manifest_source='weekly_rosters'),
    _r('I03', 'Depth charts', 'nflverse (ESPN-sourced since 2025)', 'GitHub release depth chart file',
       'FULLY_AUTOMATED', 'READ_ONLY_RESEARCH', 'RUNNING', 'PRIMARY', 'publisher: daily 07:00 UTC',
       'nflverse changed source from NFL Data Exchange to ESPN in 2025. nflverse states the data belong to '
       'their owners and are governed by their terms: fine for personal research, not for redistribution.',
       manifest_source='depth_charts'),
    _r('I04', 'Injury report (practice participation, game designation)', 'nflverse',
       'GitHub release injuries file', 'FULLY_AUTOMATED', 'READ_ONLY_RESEARCH', 'RUNNING', 'PRIMARY',
       'publisher: daily 07:00 UTC, September-February',
       'LATENCY: the Friday afternoon designations (about 20:00 UTC) reach nflverse no earlier than the '
       'Saturday 07:00 UTC refresh.', manifest_source='injuries'),
    _r('I05', 'Official injury report page', 'NFL.com', 'scheduled fetch of nfl.com/injuries/',
       'PROHIBITED_OR_UNSUPPORTED', 'READ_ONLY_RESEARCH', 'RUNNING', 'SNIPPET_ONLY', 'every capture run',
       'CURRENTLY AUTOMATED and terms-risky: NFL.com terms (search text only) bar "systematic retrieval of '
       'data ... to create or compile a collection ... database" without written consent. Lawful '
       'alternatives: nflverse injuries (I04, slower), a licensed feed (I20-I22), or the owner relaying '
       'what he reads (sunday_paste.py).',
       owner_decision='OD-1', manifest_source='official_injury_report'),
    _r('I06', 'Official game-day inactives', 'NFL.com', 'scheduled fetch of nfl.com/inactives/',
       'PROHIBITED_OR_UNSUPPORTED', 'READ_ONLY_RESEARCH', 'RUNNING', 'SNIPPET_ONLY', 'T-90 min window',
       'Same terms as I05. Has never yielded rows in the W5 week (SOURCE_HAS_NO_ROWS_YET). nflverse carries '
       'no pregame inactives. Lawful alternatives: licensed feed, or owner relay through sunday_paste.py '
       '(tier OWNER_RELAYED, never relabelled OFFICIAL_CAPTURED).',
       owner_decision='OD-1', manifest_source='official_inactives'),
    _r('I07', 'ESPN injuries JSON', 'ESPN (undocumented API)', 'scheduled fetch of site.api.espn.com',
       'PROHIBITED_OR_UNSUPPORTED', 'READ_ONLY_RESEARCH', 'RUNNING', 'SNIPPET_ONLY', 'every capture run',
       'Undocumented API under Disney terms that bar automated retrieval and scraping. It discharges NO '
       'target in the registry (serves_kinds empty), so stopping it loses nothing the forecast uses.',
       owner_decision='OD-2', manifest_source='espn_injuries_json'),
    _r('I08', 'Transactions (signings, IR, elevations)', 'nflverse rosters (derived)',
       'difference between consecutive weekly-roster captures', 'FULLY_AUTOMATED', 'READ_ONLY_RESEARCH',
       'NOT_BUILT', 'PRIMARY', 'follows I02',
       'The registered official_transactions endpoint is BLOCKED (ENDPOINT_NOT_YET_VERIFIED). Practice-squad '
       'elevations are not in any free feed before kickoff. Needs I02 to keep `status` (INT-G1).',
       manifest_source='official_transactions'),
    _r('I09', 'Play-by-play and player game stats', 'nflverse (NFL GSIS)', 'GitHub release pbp and player-stats',
       'FULLY_AUTOMATED', 'READ_ONLY_RESEARCH', 'PARTIAL', 'PRIMARY',
       'publisher: nightly 09:00 UTC plus game windows; stat corrections Wednesday night',
       'Not on the capture schedule: the manifest\'s last pbp capture is 2026-09-17; the W5 files were '
       'fetched by hand on 2026-10-07. Gap INT-G2.', manifest_source='pbp'),
    _r('I10', 'Snap counts', 'nflverse (Pro Football Reference-sourced)', 'GitHub release snap counts',
       'FULLY_AUTOMATED', 'READ_ONLY_RESEARCH', 'PARTIAL', 'PRIMARY', 'publisher: every 6 h in season',
       'Watch-only in the capture (NOT_APPLICABLE). PFR\'s own terms restrict tools built on scraped data; '
       'reading nflverse\'s published file for personal research is the supported route.',
       manifest_source='snap_counts'),
    _r('I11', 'Route participation / charting', 'nflverse (FTN, CC-BY-SA)', 'participation file',
       'PROHIBITED_OR_UNSUPPORTED', 'READ_ONLY_RESEARCH', 'NOT_BUILT', 'PRIMARY', 'after the postseason only',
       'UNSUPPORTED IN SEASON at no cost: free participation data arrives only after the season. In-season '
       'routes need a licensed provider (FTN, PFF). Route participation stays UNKNOWN, never inferred.',
       manifest_source='pbp_participation'),
    # ---------------------------------------------------------------- 2. DK ids and salaries
    _r('D01', 'DK player ids and salaries', 'DraftKings', 'DKSalaries.csv downloaded from the contest lobby',
       'MANUAL_EXPORT', 'READ_ONLY_RESEARCH', 'BUILT', 'SNIPPET_ONLY', 'once per slate, after salaries post',
       'Drop the file in nfl/dfs/inbox/drop/; it is recognised by its header, hashed and stored. The football '
       'projection does not wait for it (research universe).', inbox_kind='DK_SALARIES'),
    _r('D02', 'DK player ids and salaries (licensed)', 'SportsDataIO', 'DFS slates API (DK, FD, Yahoo salaries)',
       'APPROVED_PROVIDER_CONNECTION', 'READ_ONLY_RESEARCH', 'NOT_BUILT', 'SNIPPET_ONLY', 'polling',
       'The only licensed source found that sells DK slate salaries. Paid; trial data are scrambled and '
       'cannot be used for analysis.', owner_decision='OD-3'),
    _r('D03', 'DK draftables / contest JSON endpoints', 'DraftKings (undocumented)', 'scripted HTTP',
       'PROHIBITED_OR_UNSUPPORTED', 'READ_ONLY_RESEARCH', 'NOT_TO_BE_BUILT', 'SNIPPET_ONLY', 'n/a',
       'DK terms bar "automated means (including ... scripts and third-party tools) to interact with the '
       'Website in any way". Not built.'),
    _r('D04', 'Owner\'s entries (entry ids, contests, fees)', 'DraftKings', 'DKEntries.csv download',
       'MANUAL_EXPORT', 'ACCOUNT_DATA_READ', 'BUILT', 'SNIPPET_ONLY', 'when the owner has entered',
       'ACCOUNT_PRIVATE. Read only. This system never edits, uploads or submits entries.',
       inbox_kind='DK_ENTRIES'),
    _r('D05', 'Lineup upload, edit, late swap', 'DraftKings', 'CSV upload or editing in the DK client',
       'PROHIBITED_OR_UNSUPPORTED', 'CONTEST_ENTRY', 'NOT_TO_BE_BUILT', 'SNIPPET_ONLY', 'n/a',
       'Owner only, by hand. Automation is prohibited by DK terms and by the owner\'s standing rule.'),
    _r('D06', 'Contest entry, deposits, withdrawals', 'DraftKings', 'account', 'PROHIBITED_OR_UNSUPPORTED',
       'FINANCIAL', 'NOT_TO_BE_BUILT', 'SNIPPET_ONLY', 'n/a', 'Never automated; out of this system\'s scope.'),
    _r('D07', 'Login, session, credentials', 'DraftKings / Fantasy Cruncher', 'any', 'PROHIBITED_OR_UNSUPPORTED',
       'ACCOUNT_ACTION', 'NOT_TO_BE_BUILT', 'SNIPPET_ONLY', 'n/a',
       'No credential is stored, requested or used. Credentials pasted into a conversation are never used.'),
    # ---------------------------------------------------------------- 3. FC benchmark
    _r('F01', 'FC projections (benchmark only)', 'Fantasy Cruncher', 'players CSV export from the FC UI',
       'MANUAL_EXPORT', 'READ_ONLY_RESEARCH', 'BUILT', 'SNIPPET_ONLY', 'whenever the owner exports',
       'Context only, NEVER a model input. FC terms: personal non-commercial use; no scraping. No API.',
       inbox_kind='FC_PLAYERS_EXPORT'),
    _r('F02', 'FC automated pull', 'Fantasy Cruncher', 'scripted login or scraping', 'PROHIBITED_OR_UNSUPPORTED',
       'ACCOUNT_ACTION', 'NOT_TO_BE_BUILT', 'SNIPPET_ONLY', 'n/a',
       'FC terms bar "any robot, spider, scraper or other automated means". Not built.'),
    # ---------------------------------------------------------------- 6. history, ownership, grading
    _r('H01', 'Contest standings and realised ownership', 'DraftKings',
       'contest standings CSV export after the contest is final', 'MANUAL_EXPORT', 'READ_ONLY_RESEARCH',
       'BUILT', 'SNIPPET_ONLY', 'after each contest finalises',
       'POSTLOCK ONLY. Contains other users\' names (stored, never published). Realised ownership is never '
       'treated as available before lock. Loader: nfl/field/contest_ownership.py.',
       inbox_kind='DK_CONTEST_STANDINGS'),
    _r('H02', 'Postgame player grading', 'nflverse', 'player stats file (I09)', 'FULLY_AUTOMATED',
       'READ_ONLY_RESEARCH', 'PARTIAL', 'PRIMARY', 'nightly; corrections Wednesday',
       'Grading code exists; scheduled capture of the stats file is gap INT-G2.'),
    # ---------------------------------------------------------------- licensed providers (all need money)
    _r('I20', 'Official real-time data', 'Genius Sports (NFL exclusive distributor)', 'B2B licence',
       'APPROVED_PROVIDER_CONNECTION', 'READ_ONLY_RESEARCH', 'NOT_BUILT', 'SNIPPET_ONLY', 'real time',
       'Exclusive distributor of official NFL data through 2029; media and betting operators only.',
       owner_decision='OD-3'),
    _r('I21', 'Injuries, depth charts, rosters (licensed)', 'Sportradar', 'NFL API v7',
       'APPROVED_PROVIDER_CONNECTION', 'READ_ONLY_RESEARCH', 'NOT_BUILT', 'SNIPPET_ONLY', 'push/poll',
       'Paid. The 30-day trial is "for internal testing and evaluation purposes only".', owner_decision='OD-3'),
    _r('I22', 'Injuries, depth charts, inactives (licensed)', 'SportsDataIO', 'NFL API',
       'APPROVED_PROVIDER_CONNECTION', 'READ_ONLY_RESEARCH', 'NOT_BUILT', 'SNIPPET_ONLY', 'polling',
       'Paid; redistribution prohibited without consent.', owner_decision='OD-3'),
    _r('I23', 'News', 'RotoWire', 'free RSS feeds', 'PROHIBITED_OR_UNSUPPORTED', 'READ_ONLY_RESEARCH',
       'NOT_BUILT', 'UNKNOWN', 'n/a',
       'Terms for automated reading of the RSS feeds were not found. Until they are, news stays a discovery '
       'signal gathered by the network-holding agent, never confirmation.'),
    # ---------------------------------------------------------------- wagering
    _r('W01', 'Sportsbook prices and bets', 'Hard Rock Bet', 'any', 'PROHIBITED_OR_UNSUPPORTED', 'WAGERING',
       'NOT_TO_BE_BUILT', 'UNKNOWN', 'n/a',
       'No sportsbook price enters an NFL prediction, and this system never places or recommends a wager.'),
]

OWNER_DECISIONS = [
    {'id': 'OD-1', 'question': 'Keep, stop, or replace the scheduled fetch of the NFL.com injury and inactives '
                               'pages (I05, I06)?',
     'why': 'NFL.com terms, seen as search text only, bar systematic retrieval to compile a database without '
            'consent. The fetch runs today in .github/workflows/nfl-capture.yml.',
     'options': ['Stop it and rely on nflverse injuries plus owner relay of inactives',
                 'Keep it for personal research after checking the live terms page',
                 'Replace it with a licensed feed (see OD-3)'],
     'agent_recommendation': 'Check the live NFL.com terms page first. If the clause is confirmed, stop the '
                             'page fetch and use nflverse injuries for designations and the owner relay for '
                             'inactives. The agent does not change the workflow until the owner decides.'},
    {'id': 'OD-2', 'question': 'Stop the scheduled ESPN injuries JSON fetch (I07)?',
     'why': 'Undocumented API under terms that bar automated retrieval; it discharges no forecast target.',
     'options': ['Stop it', 'Keep it'],
     'agent_recommendation': 'Stop it: the forecast reads nothing from it.'},
    {'id': 'OD-3', 'question': 'License a provider (SportsDataIO, Sportradar) for DK salaries, inactives or '
                               'in-season charting?',
     'why': 'It is the only automated route to DK salaries and official inactives that fits the terms. '
            'It costs money, which is the owner\'s decision alone.',
     'options': ['No: stay with manual exports', 'Evaluate a paid plan'],
     'agent_recommendation': 'No change needed for Sunday; the manual drop folder removes the copy-and-paste.'},
    {'id': 'OD-4', 'question': 'May the agent dispatch the capture workflow and commit capture syncs into this '
                               'branch without asking each time?',
     'why': 'An attempt to dispatch nfl-capture.yml was refused by this session\'s permission classifier as an '
            'unrequested action in a connected app. The sync into the working tree ran; the dispatch did not.',
     'options': ['Allow (add a permission rule)', 'Owner dispatches the workflow himself', 'Leave it scheduled only'],
     'agent_recommendation': 'Leave it on its schedule; ask for a dispatch only when a deadline needs it.'},
]


def by_access():
    out = {a: [] for a in ACCESS}
    for r in MATRIX:
        out[r['access']].append(r)
    return out


def check():
    """Structural invariants. Returns a list of violations (empty means sound)."""
    bad = []
    ids = [r['id'] for r in MATRIX]
    if len(ids) != len(set(ids)):
        bad.append('duplicate ids')
    for r in MATRIX:
        if r['access'] not in ACCESS:
            bad.append(f"{r['id']}: access {r['access']}")
        if r['action'] not in ACTIONS:
            bad.append(f"{r['id']}: action {r['action']}")
        if r['build'] not in BUILD:
            bad.append(f"{r['id']}: build {r['build']}")
        if r['action'] not in IMPLEMENTED_ACTIONS and r['build'] != 'NOT_TO_BE_BUILT':
            bad.append(f"{r['id']}: {r['action']} must be NOT_TO_BE_BUILT")
        if r['access'] == 'PROHIBITED_OR_UNSUPPORTED' and r['build'] == 'RUNNING' and not r['owner_decision']:
            bad.append(f"{r['id']}: a prohibited route that runs must name an owner decision")
        if r['access'] == 'MANUAL_EXPORT' and r['build'] != 'NOT_TO_BE_BUILT' and not r['inbox_kind']:
            bad.append(f"{r['id']}: a manual export needs an inbox kind")
    od = {d['id'] for d in OWNER_DECISIONS}
    for r in MATRIX:
        if r['owner_decision'] and r['owner_decision'] not in od:
            bad.append(f"{r['id']}: unknown owner decision {r['owner_decision']}")
    return bad


def to_markdown():
    """The matrix as Markdown tables, one per access class. Generated, so the document cannot drift."""
    out = []
    for a, rs in by_access().items():
        out.append(f'### {a.replace("_", " ").title()} ({len(rs)})\n')
        out.append('| Id | Capability | Provider and route | Action | Built | Terms evidence | Notes |')
        out.append('|---|---|---|---|---|---|---|')
        for r in rs:
            dec = f" **Owner decision {r['owner_decision']}.**" if r['owner_decision'] else ''
            out.append(f"| {r['id']} | {r['capability']} | {r['provider']}: {r['route']} | {r['action']} | "
                       f"{r['build']} | {r['terms_evidence']} | {r['note']}{dec} |")
        out.append('')
    return '\n'.join(out)
