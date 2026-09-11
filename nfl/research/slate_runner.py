"""One governed entrypoint for a whole NFL slate.

    python3.12 -m nfl.research.slate_runner --date 2026-09-13 --candidate R8

It ORCHESTRATES existing mechanisms and invents no prediction: discovery comes
from the captured schedule vintage, sealing from make_board, the exports from
nfl.research.daily_board. Nothing here fits, tunes or promotes anything.

WHY INCREMENTAL EXECUTION IS SLICE-BASED AND NOT FILE-BASED.

The capture bot rewrites whole vintage files on a schedule. Measured during
the SF@LA window, the schedules file moved eight times while the SF@LA slice
inside it never changed once. Rerunning a game because a file it reads was
rewritten would burn a Sunday recomputing forecasts that cannot differ. So the
hash is over the ROWS THIS GAME CONSUMES, and a whole-file change with an
unchanged slice is UNCHANGED_REUSED.

PHASES ARE INFORMATION STATES, NOT CLOCK TIMES, AND THEY ARE PER GAME.

A 1pm kickoff reaching POST_INACTIVES says nothing about a 4pm one. The slate
carries no single phase; each game carries its own, and post_inactives is
claimed for a game only when BOTH clubs' lists have resolved completely.

ONE GAME'S FAILURE IS ONE GAME'S FAILURE. Every game runs independently and a
raised exception becomes a named refusal for that game alone. The run ends
with "N complete / M blocked" and never with a silent omission.

Nothing here is a bet, an edge, an expected value or a tier.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import json
import pathlib
import sys
import time
import traceback

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State   # noqa: E402
from nfl.capture import coverage as COV                               # noqa: E402
from nfl.research import daily_board as RB                            # noqa: E402
from nfl.product import daily_board as PB                             # noqa: E402
from nfl.tools import ingest_inactives as II                          # noqa: E402

SPEC_VERSION = 'slate-runner-1'

PHASES = ('morning', 'pre_inactives', 'post_inactives', 'final')

STATE_DIR = _REPO / 'nfl' / 'research' / 'slate_state'
OUT_ROOT = _REPO / 'nfl' / 'research' / 'daily'

# Sources whose consumed slice decides whether a game must be recomputed.
SLICE_SOURCES = ('schedules', 'depth_charts', 'weekly_rosters', 'injuries')


class Timer:
    """Wall clock per stage. Latency is measured here, never described."""

    def __init__(self):
        self.stages = collections.OrderedDict()
        self._t0 = time.perf_counter()

    def stage(self, name):
        return _Stage(self, name)

    def add(self, name, seconds):
        self.stages[name] = round(self.stages.get(name, 0.0) + seconds, 4)

    @property
    def total(self):
        return round(time.perf_counter() - self._t0, 4)


class _Stage:
    def __init__(self, timer, name):
        self.timer, self.name = timer, name

    def __enter__(self):
        self.t = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.timer.add(self.name, time.perf_counter() - self.t)
        return False


# --------------------------------------------------------- 1. discovery
def discover_slate(date_str, season=2026, week=1):
    """Every game kicking off on `date`, from the captured schedule vintage.

    No game list is supplied by hand. If the schedule snapshot is missing this
    refuses rather than inventing kickoff times, which is the same rule
    load_week_plan already applies.
    """
    plan = COV.load_week_plan(season, week)
    if plan.state is not State.PASS:
        return Outcome.blocked(
            'SLATE_SCHEDULE_UNAVAILABLE',
            f'no captured schedule to discover a slate from: '
            f'{plan.state.name}[{plan.code}]', cause=Cause.DATA)
    seen = {}
    for c in plan.value:
        d = c.as_dict()
        ko = str(d.get('kickoff_utc') or '')
        if ko[:10] != date_str:
            continue
        gid = d['game_id']
        if gid in seen:
            continue
        parts = gid.split('_')
        seen[gid] = {'game_id': gid,
                     'away': parts[2] if len(parts) > 3 else None,
                     'home': parts[3] if len(parts) > 3 else None,
                     'teams': tuple(parts[2:4]) if len(parts) > 3 else (),
                     'kickoff_utc': ko, 'season': season, 'week': week}
    if not seen:
        return Outcome.blocked(
            'SLATE_NO_GAMES_ON_DATE',
            f'the captured schedule carries no game kicking off on '
            f'{date_str}', cause=Cause.DATA, date=date_str)
    return Outcome.ok('SLATE_DISCOVERED', value=[seen[k] for k in sorted(seen)],
                      n_games=len(seen), date=date_str)


def inactives_state(game_id):
    """Whether BOTH clubs' official lists have resolved for this game.

    PARTIAL IS NOT POST. One club's list is not the game's list, and a game
    whose second club has not resolved stays PRE_INACTIVES however complete
    the first looks.
    """
    p = RB.LIVE / game_id / 'INACTIVES_INGESTION.json'
    if not p.exists():
        return {'state': 'NO_OFFICIAL_LIST', 'by_team': {}, 'complete': False}
    rec = json.loads(p.read_text())
    by = {}
    for s in rec.get('steps') or []:
        if isinstance(s.get('inactive_by_team'), dict):
            by = {t: len(v) for t, v in s['inactive_by_team'].items()}
    teams = set(rec.get('teams') or by)
    complete = bool(by) and all(by.get(t) for t in teams) and len(by) >= 2
    return {'state': 'POST_INACTIVES_COMPLETE' if complete
            else ('PARTIAL_INACTIVES' if by else 'NO_OFFICIAL_LIST'),
            'by_team': by, 'complete': complete,
            'n_resolved': sum(by.values()) if by else 0}


def phase_of(game, now=None):
    """The game's own information state. Never the slate's."""
    now = now or dt.datetime.now(dt.timezone.utc)
    ko = game.get('kickoff_utc') or ''
    inact = inactives_state(game['game_id'])
    try:
        kick = dt.datetime.fromisoformat(ko.replace('Z', '+00:00'))
    except ValueError:
        return 'morning', inact
    if now >= kick:
        return 'final', inact
    if inact['complete']:
        return 'post_inactives', inact
    return ('pre_inactives' if (kick - now) <= dt.timedelta(hours=3)
            else 'morning'), inact


# ------------------------------------------- 2. changed-slice detection
def consumed_slices(game, info_sources):
    """{source: {'slice_sha': ..., 'n_rows': ...}} for one game.

    Reuses ingest_inactives.consumed_slice rather than reimplementing it, so
    the runner and the ingestion path can never disagree about what a game
    actually consumes.
    """
    out = {}
    for src in SLICE_SOURCES:
        info = (info_sources or {}).get(src) or {}
        sha = info.get('sha256')
        if not sha:
            out[src] = {'slice_sha': None, 'n_rows': 0,
                        'why': 'source absent from the information set'}
            continue
        h, n = II.consumed_slice(src, sha, game['season'], game['week'],
                                 game['teams'], game['game_id'])
        out[src] = {'slice_sha': h, 'n_rows': n, 'file_sha16': sha[:16]}
    return out


def state_path(date_str, candidate):
    return STATE_DIR / f'{date_str}_{candidate}.json'


def load_state(date_str, candidate):
    p = state_path(date_str, candidate)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text()).get('games') or {}
    except ValueError:
        return {}


def save_state(date_str, candidate, games):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state_path(date_str, candidate).write_text(json.dumps(
        {'artifact': 'NFL_SLATE_SLICE_STATE', 'spec_version': SPEC_VERSION,
         'date': date_str, 'candidate': candidate,
         'written_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
         'meaning': ('the consumed-slice hashes a game was last forecast '
                     'from. A whole-file rewrite with an unchanged slice is '
                     'not a reason to recompute.'),
         'games': games}, indent=1) + '\n')


def slice_verdict(prev, now):
    """(changed, [sources that moved]). Absence of prior state means NEW."""
    if not prev:
        return True, ['no prior slice state recorded']
    moved = [s for s in SLICE_SOURCES
             if (prev.get(s) or {}).get('slice_sha')
             != (now.get(s) or {}).get('slice_sha')]
    return bool(moved), moved


# ------------------------------------------- 4. external status packet
STATUS_REQUIRED = ('team', 'player', 'status_type', 'source_authority',
                   'source_url', 'published_at', 'retrieved_at')

# Only these authorities may carry an OFFICIAL status. A secondary report is
# recorded as what it is and is never elevated.
OFFICIAL_AUTHORITIES = ('official_league', 'official_club')


def load_external_status(path):
    """The structured external status packet, with provenance preserved.

    EVERY required field or the row is refused. A packet missing published_at
    cannot be placed against a kickoff, and one missing source_authority
    cannot be told apart from a reporter's expectation -- which is exactly the
    distinction this project has spent the most effort protecting.
    """
    p = pathlib.Path(path)
    if not p.exists():
        return Outcome.blocked(
            'EXTERNAL_STATUS_FILE_ABSENT', f'no status packet at {p}',
            cause=Cause.DATA, path=str(p))
    rows = list(csv.DictReader(open(p)))
    if not rows:
        return Outcome.fail('EXTERNAL_STATUS_FILE_EMPTY',
                            f'{p} parsed to zero rows; an empty packet is an '
                            f'error, not an absence of status')
    missing_cols = [c for c in STATUS_REQUIRED if c not in rows[0]]
    if missing_cols:
        return Outcome.fail(
            'EXTERNAL_STATUS_SCHEMA_INCOMPLETE',
            f'the packet is missing {missing_cols}. Provenance is not '
            f'optional: without it a secondary report and an official list '
            f'are indistinguishable.', missing=missing_cols)
    kept, refused, elevated = [], [], []
    for i, r in enumerate(rows):
        blank = [c for c in STATUS_REQUIRED if not (r.get(c) or '').strip()]
        if blank:
            refused.append({'row': i, 'blank_fields': blank})
            continue
        auth = (r.get('source_authority') or '').strip().lower()
        rec = dict(r)
        rec['is_official'] = auth in OFFICIAL_AUTHORITIES
        # NEVER SILENTLY ELEVATE. A secondary report keeps its own authority
        # and is marked as not official, whatever its status_type claims.
        if not rec['is_official'] and 'official' in (
                r.get('status_type') or '').lower():
            rec['elevation_refused'] = (
                f"status_type claims official but source_authority is "
                f"{r.get('source_authority')!r}; recorded as secondary")
            elevated.append({'row': i, 'team': r.get('team'),
                             'player': r.get('player'),
                             'source_authority': r.get('source_authority')})
        kept.append(rec)
    return Outcome.ok(
        'EXTERNAL_STATUS_READ', value=kept, n_rows=len(rows), n_kept=len(kept),
        n_refused_incomplete=len(refused), refused=refused[:10],
        n_elevation_refused=len(elevated), elevation_refused=elevated[:10],
        n_official=sum(1 for r in kept if r['is_official']))


# ------------------------------------------------- 3. per-game execution
def _information_set(game, written_at):
    from nfl.research.shadow import information_set as IS
    info = IS.build(game['kickoff_utc'], observed_before=written_at)
    return info.get('sources') or {}


def run_game(game, candidate, prev_state, timer, written_at, dry_run=False,
             draws=1000, seed=20260908):
    """One game, start to finish, never raising into the slate.

    Returns (record, action). The action is one of NEW_FORECAST,
    REFRESHED_INFORMATION_CHANGED, UNCHANGED_REUSED or BLOCKED_<REASON>.
    """
    gid = game['game_id']
    rec = {'game_id': gid, 'teams': list(game['teams']),
           'kickoff_utc': game['kickoff_utc'], 'candidate': candidate,
           'timing_seconds': {}}
    t_game = time.perf_counter()
    try:
        with timer.stage('data_readiness'):
            t = time.perf_counter()
            phase, inact = phase_of(game)
            rec['phase'] = phase
            rec['official_inactives'] = inact
            srcs = _information_set(game, written_at)
            rec['information_cutoff'] = written_at
            rec['n_information_sources'] = len(srcs)
            rec['timing_seconds']['data_readiness'] = round(
                time.perf_counter() - t, 4)

        if not srcs:
            rec['action'] = 'BLOCKED_NO_LAWFUL_INFORMATION_SET'
            rec['reason'] = ('no source resolves strictly before the cutoff, '
                             'so there is nothing lawful to forecast from')
            return rec, rec['action']

        with timer.stage('changed_slice_detection'):
            t = time.perf_counter()
            now_slices = consumed_slices(game, srcs)
            changed, moved = slice_verdict(prev_state.get('slices'),
                                           now_slices)
            rec['consumed_slices'] = now_slices
            rec['slices_moved'] = moved
            rec['timing_seconds']['changed_slice_detection'] = round(
                time.perf_counter() - t, 4)

        sealed = prev_state.get('sealed')
        if not changed and sealed and pathlib.Path(sealed).exists():
            rec['action'] = 'UNCHANGED_REUSED'
            rec['reason'] = ('every consumed slice is byte-identical to the '
                             'one this game was last forecast from')
            rec['sealed'] = sealed
            rec['recomputed'] = False
            rec['timing_seconds']['forecasting'] = 0.0
            return rec, rec['action']

        if dry_run:
            rec['action'] = ('NEW_FORECAST' if not sealed
                             else 'REFRESHED_INFORMATION_CHANGED')
            rec['reason'] = 'dry run: nothing was computed or sealed'
            rec['recomputed'] = False
            rec['dry_run'] = True
            return rec, rec['action']

        with timer.stage('forecasting'):
            t = time.perf_counter()
            out = _seal(game, candidate, written_at, draws, seed)
            rec['timing_seconds']['forecasting'] = round(
                time.perf_counter() - t, 4)
        rec.update(out)
        rec['recomputed'] = True
        rec['action'] = ('REFRESHED_INFORMATION_CHANGED' if sealed
                         else 'NEW_FORECAST')
        rec['reason'] = (f'consumed slice(s) moved: {moved}' if sealed
                         else 'no prior sealed forecast for this game')
        return rec, rec['action']
    except SystemExit as e:
        # make_board refuses by raising SystemExit with a named code.
        rec['action'] = f'BLOCKED_{str(e).split(":")[0][:60]}'
        rec['reason'] = str(e)[:300]
        rec['recomputed'] = False
        return rec, rec['action']
    except Exception as e:                                   # noqa: BLE001
        rec['action'] = f'BLOCKED_{type(e).__name__.upper()}'
        rec['reason'] = f'{type(e).__name__}: {e}'[:300]
        rec['traceback_tail'] = traceback.format_exc()[-400:]
        rec['recomputed'] = False
        return rec, rec['action']
    finally:
        rec['timing_seconds']['game_total'] = round(
            time.perf_counter() - t_game, 4)


def _seal(game, candidate, written_at, draws, seed):
    """Seal one research board through the existing mechanism."""
    from nfl.tools import make_board as MB
    label = ('V1_CANDIDATE' if candidate == 'V1'
             else f'V1_CANDIDATE_{candidate}')
    gid = game['game_id']
    inact = PB.official_inactive_ids(gid)
    phase, st = phase_of(game)
    out_dir = (RB.LIVE / gid /
               f"{'post_inactives' if st['complete'] else 'pre_inactives'}"
               f"_{label}")
    summary, board, bdir = MB.build_one(
        game['season'], game['week'], gid, written_at, str(out_dir),
        draws=draws, seed=seed, model_configuration=label,
        inactive_ids=sorted(inact) if inact else None)
    return {'sealed': str(bdir), 'model_configuration': label,
            'n_players': (board or {}).get('n_players'),
            'n_draws': (board or {}).get('n_draws'),
            'promoted': False}


def _decompose(records):
    """Separate the one-time process cost from the marginal per-game cost."""
    fc = [r['timing_seconds'].get('forecasting') for r in records
          if r.get('recomputed') and r['timing_seconds'].get('forecasting')]
    if not fc:
        return {'n_forecast': 0,
                'note': 'nothing was recomputed, so there is no forecasting '
                        'time to decompose'}
    first, rest = fc[0], sorted(fc[1:])
    med = rest[len(rest) // 2] if rest else None
    return {'n_forecast': len(fc),
            'first_forecast_seconds': round(first, 2),
            'median_subsequent_forecast_seconds': (round(med, 2) if med
                                                   else None),
            'implied_one_time_setup_seconds': (round(first - med, 2)
                                               if med else None),
            'marginal_cost_per_extra_game_seconds': (round(med, 2) if med
                                                     else None),
            'note': ('the first forecast in a process pays a setup the rest '
                     'do not; a single-game refresh is dominated by it')}


# ----------------------------------------------------- 6. orchestration
def run(date_str, candidate='R8', market=None, external_status=None,
        phase=None, out_dir=None, dry_run=False, season=2026, week=1,
        written_at=None, draws=1000, seed=20260908):
    timer = Timer()
    out = pathlib.Path(out_dir or (OUT_ROOT / date_str))
    guard = RB.assert_never_writes_into_product(out)
    if guard.state is not State.PASS:
        return guard
    out.mkdir(parents=True, exist_ok=True)
    written_at = written_at or dt.datetime.now(
        dt.timezone.utc).replace(microsecond=0).isoformat().replace(
            '+00:00', 'Z')

    with timer.stage('slate_discovery'):
        disc = discover_slate(date_str, season, week)
    if disc.state is not State.PASS:
        return disc
    games = disc.value

    ext = None
    if external_status:
        with timer.stage('external_status'):
            ext = load_external_status(external_status)

    prev = load_state(date_str, candidate)
    records, actions, new_state = [], collections.Counter(), {}
    for g in games:
        rec, action = run_game(g, candidate, prev.get(g['game_id']) or {},
                               timer, written_at, dry_run, draws, seed)
        # A game whose own phase is behind the requested one is REPORTED, not
        # forced. `--phase post_inactives` is a filter on what is ready, never
        # a claim that it is.
        if phase and rec.get('phase') and PHASES.index(
                rec['phase']) < PHASES.index(phase):
            rec['phase_filter'] = (
                f"requested {phase}; this game is at {rec['phase']}")
        records.append(rec)
        actions[action.split('_')[0] if action.startswith('BLOCKED')
                else action] += 1
        if rec.get('sealed'):
            new_state[g['game_id']] = {'slices': rec.get('consumed_slices'),
                                       'sealed': rec['sealed'],
                                       'written_at': written_at,
                                       'action': action}
        elif prev.get(g['game_id']):
            new_state[g['game_id']] = prev[g['game_id']]
    if not dry_run:
        save_state(date_str, candidate, new_state)

    # 5. THE MARKET IS JOINED ONLY NOW, after every football board is sealed.
    with timer.stage('market_join_and_export'):
        exp = RB.build(date_str, candidate=candidate, market_path=market,
                       out_dir=str(out))

    complete = [r for r in records if not r['action'].startswith('BLOCKED')]
    blocked = [r for r in records if r['action'].startswith('BLOCKED')]
    awaiting = [r for r in records
                if not (r.get('official_inactives') or {}).get('complete')]
    ev = exp.evidence if exp.state is State.PASS else {}
    status = {
        'artifact': 'NFL_SLATE_STATUS', 'spec_version': SPEC_VERSION,
        'namespace': 'research', 'date': date_str, 'candidate': candidate,
        'requested_phase': phase, 'promoted': False,
        'generated_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'information_cutoff': written_at,
        'games_total': len(records),
        'games_ready': len(complete),
        'games_blocked': len(blocked),
        'games_awaiting_inactives': len(awaiting),
        'games_refreshed': sum(1 for r in records
                               if r['action'] == 'REFRESHED_INFORMATION_CHANGED'),
        'games_new': sum(1 for r in records if r['action'] == 'NEW_FORECAST'),
        'games_unchanged': sum(1 for r in records
                               if r['action'] == 'UNCHANGED_REUSED'),
        'models_recomputed': sum(1 for r in records if r.get('recomputed')),
        'total_modeled_markets': ev.get('n_rows', 0),
        'total_ranking_eligible_markets': ev.get('n_ranking_eligible', 0),
        'total_priority_markets': ev.get('n_priority', 0),
        'phase_by_game': {r['game_id']: r.get('phase') for r in records},
        'blocked_detail': [{'game_id': r['game_id'], 'action': r['action'],
                            'reason': r.get('reason')} for r in blocked],
        'awaiting_inactives_detail': [
            {'game_id': r['game_id'],
             'state': (r.get('official_inactives') or {}).get('state')}
            for r in awaiting],
        'external_status': (
            {'state': ext.state.name, 'code': ext.code,
             'n_kept': ext.evidence.get('n_kept'),
             'n_official': ext.evidence.get('n_official'),
             'n_refused_incomplete': ext.evidence.get('n_refused_incomplete'),
             'n_elevation_refused': ext.evidence.get('n_elevation_refused')}
            if ext is not None else None),
        'export': {'state': exp.state.name, 'code': exp.code},
        'runtime_seconds': {'total': timer.total, **timer.stages},
        # WHERE THE TIME ACTUALLY GOES, MEASURED RATHER THAN DESCRIBED.
        #
        # The first forecast in a process pays a one-time setup the rest do
        # not: measured on the 12-game 2026-09-13 slate, the first game cost
        # 75.7s and the median of the other eleven was 10.7s. So a one-game
        # refresh is dominated by warm-up, not by that game's football, and
        # the decomposition is reported so nobody plans a Sunday around a
        # per-game average that does not exist.
        'runtime_decomposition': _decompose(records),
        'runtime_by_game': {r['game_id']: r['timing_seconds']
                            for r in records},
        'games': records,
        'what_this_is_not': (
            'Orchestration only. No tier, no pick, no expected value, no '
            'threshold on model-market disagreement, and nothing promoted.'),
    }
    (out / 'SLATE_STATUS.json').write_text(
        json.dumps(status, indent=1, default=str) + '\n')
    return Outcome.ok(
        'SLATE_RUN_COMPLETE', value=str(out), spec_version=SPEC_VERSION,
        games_total=len(records), games_ready=len(complete),
        games_blocked=len(blocked), models_recomputed=status['models_recomputed'],
        runtime_seconds=status['runtime_seconds'],
        total_modeled_markets=status['total_modeled_markets'],
        total_ranking_eligible_markets=status['total_ranking_eligible_markets'],
        total_priority_markets=status['total_priority_markets'],
        out_dir=str(out))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--date', required=True)
    ap.add_argument('--candidate', default='R8')
    ap.add_argument('--phase', default=None, choices=list(PHASES))
    ap.add_argument('--market', default=None)
    ap.add_argument('--external-status-file', default=None)
    ap.add_argument('--out', default=None)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--week', type=int, default=1)
    ap.add_argument('--written-at', default=None)
    ap.add_argument('--draws', type=int, default=1000)
    a = ap.parse_args(argv)
    o = run(a.date, a.candidate, a.market, a.external_status_file, a.phase,
            a.out, a.dry_run, a.season, a.week, a.written_at, a.draws)
    if o.state is not State.PASS:
        print(f'{o.state.name}[{o.code}] {o.detail[:200]}')
        return 1
    e = o.evidence
    print(f'{e["games_ready"]} games complete / {e["games_blocked"]} blocked '
          f'({e["games_total"]} on the slate)')
    print(f'  models recomputed      : {e["models_recomputed"]}')
    print(f'  modeled markets        : {e["total_modeled_markets"]}')
    print(f'  ranking-eligible       : {e["total_ranking_eligible_markets"]}')
    print(f'  reduced candidate set  : {e["total_priority_markets"]}')
    rt = e['runtime_seconds']
    print(f'  runtime total          : {rt["total"]}s')
    for k, v in rt.items():
        if k != 'total':
            print(f'      {k:26s} {v}s')
    print(f'  -> {e["out_dir"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
