#!/usr/bin/env python3.12
"""PROSPECTIVE SEAL of the appearance successor for a 2026 week (default 5; --week W for later weeks). SHADOW_ONLY. Write-once, chmod 444.

    python3.12 nfl/prospective/appearance/seal_appearance_w5.py            # writes the seal (refused at/after kickoff)
    python3.12 nfl/prospective/appearance/seal_appearance_w5.py --dry-run  # builds it in memory, writes nothing

For EVERY 2026 week-5 game in the newest schedules capture, and for every RB / WR / TE in each club's PREGAME POOL,
it records per gated field (RB carries + targets, WR targets, TE targets):
  current production P(0) at the projection layer (1 - p_plays, production allocator),
  current production P(0) implied by the production draws (simulate_game_centred, FOOTBALL_ONLY centre),
  candidate P(0) (1 - pi, field-specific SC-APPEAR-1 rate), and the successor's simulated draw-level zero share
  (hurdle simulator), plus the full count histograms of both arms so the grader can score conditional CRPS.

PREGAME POOL (declared in docs/NFL_APPEARANCE_SUCCESSOR_PREREGISTRATION.md): a player is in a club's pool iff his most
recent 2026 panel row before week 5 carries that club. The panel holds 2026 weeks 1-3 only; WEEK 4 IS
MISSING_FROM_REPO (not 'no participation'), so it is never read as zero: the history window is the club's last 3 games
PRESENT in the panel (weeks 1-3 for every club). No week-5 information is read: the panel is truncated to weeks < 5
(pregame_panel), the football centre reads only club games with week < 5, and no inactive list exists yet, so every
pool member is UNKNOWN_ACTIVE_STATE (treated as eligible; forecasts are conditional on being active).

REFUSES (named): at or after the first week-5 kickoff (2026-10-09T00:15:00Z for 2026_05_TB_DAL), an existing seal
file, a prereg whose bytes do not match its lock, an empty schedule / pool / game.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import glob
import gzip
import hashlib
import importlib.util
import json
import os
import pathlib
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_CORE_PATH = _REPO / 'nfl/research/appearance/appearance_successor.py'
_spec = importlib.util.spec_from_file_location('appearance_successor', _CORE_PATH)
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)

from nfl.sim import football_points as FP  # noqa: E402
from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import forward_chain as FC  # noqa: E402
from nfl.tools import player_prior as PP  # noqa: E402

SEASON, WEEK = 2026, 5
OUT_DIR = _REPO / 'nfl/prospective/appearance'


def out_path(week):
    return OUT_DIR / f'APPEARANCE_SUCCESSOR_W{int(week)}_SEAL.json'


OUT = out_path(5)
PREREG = _REPO / 'docs/NFL_APPEARANCE_SUCCESSOR_PREREGISTRATION.md'
PREREG_LOCK = _REPO / 'nfl/prospective/appearance/APPEARANCE_SUCCESSOR_PREREG_LOCK.json'
PANEL = _REPO / 'nfl/derived/USAGE_HISTORY_2021_2026.json'
TEAM_GAME = _REPO / 'nfl/warehouse/TEAM_GAME.json'
FOOTBALL_POINTS = _REPO / 'nfl/sim/FOOTBALL_POINTS.json'
SCHEDULE_GLOB = str(_REPO / 'nfl/vintage/schedules.*.csv.gz')
#: Production's own draw count (showdown_draws.N_SIMS). MC SE of a per-unit P(0) <= 0.5/sqrt(2000) = 0.011.
N_SIMS = 2000
SEAL_SEED = 20261008
SCORED_FIELDS = {'RB': ('carries', 'targets'), 'WR': ('targets',), 'TE': ('targets',)}
SKILL = ('QB', 'RB', 'WR', 'TE')
ET = ZoneInfo('America/New_York')


class SealError(RuntimeError):
    def __init__(self, code, detail=''):
        self.code = code
        super().__init__(f'{code}: {detail}' if detail else code)


def canonical(doc):
    return json.dumps(doc, sort_keys=True, separators=(',', ':'), default=float)


def seal_hash(doc):
    return hashlib.sha256(canonical({k: v for k, v in doc.items() if k != 'seal_sha256'}).encode()).hexdigest()


def kickoff_utc(gameday, gametime):
    """nflverse gametime is US/Eastern local time; zoneinfo applies the DST rule (no fixed offset)."""
    if not gameday or not gametime:
        raise SealError('KICKOFF_UNKNOWN', f'{gameday} {gametime}')
    t = dt.datetime.strptime(f'{gameday} {gametime}', '%Y-%m-%d %H:%M').replace(tzinfo=ET)
    return t.astimezone(dt.timezone.utc)


def newest_schedule(pattern=SCHEDULE_GLOB):
    """Newest capture by mtime (name breaks ties), as gen_t90_schedule / classic_production_audit choose it."""
    hits = sorted(glob.glob(pattern), key=lambda p: (pathlib.Path(p).stat().st_mtime, p))
    if not hits:
        raise SealError('SCHEDULE_ABSENT', pattern)
    return pathlib.Path(hits[-1])


def week_games(path, season=SEASON, week=WEEK):
    with gzip.open(path, 'rt', newline='') as fh:
        rows = [r for r in csv.DictReader(fh) if r.get('season') == str(season) and r.get('week') == str(week)
                and (r.get('game_type') or 'REG') == 'REG']
    if not rows:
        raise SealError('NO_GAMES_IN_SCHEDULE', f'{path.name}: no {season} REG week {week}')
    out = []
    for r in rows:
        k = kickoff_utc(r['gameday'], r['gametime'])
        out.append({'game_id': r['game_id'], 'away': r['away_team'], 'home': r['home_team'],
                    'gameday': r['gameday'], 'gametime_et': r['gametime'], 'kickoff_utc': k.isoformat()})
    return sorted(out, key=lambda g: (g['kickoff_utc'], g['game_id']))


def schedule_agreement(games, pattern=SCHEDULE_GLOB, week=WEEK):
    """Every capture carrying 2026 week 5 must agree on each game's kickoff; disagreement is reported, never hidden."""
    want = {g['game_id']: g['kickoff_utc'] for g in games}
    n_with, disagree = 0, collections.Counter()
    for p in glob.glob(pattern):
        try:
            with gzip.open(p, 'rt', newline='') as fh:
                rows = [r for r in csv.DictReader(fh) if r.get('season') == str(SEASON) and r.get('week') == str(week)]
        except (OSError, EOFError, csv.Error):
            continue
        if not rows:
            continue
        n_with += 1
        for r in rows:
            if r['game_id'] in want and r.get('gameday') and r.get('gametime'):
                if kickoff_utc(r['gameday'], r['gametime']).isoformat() != want[r['game_id']]:
                    disagree[r['game_id']] += 1
    return {'n_captures_with_week': n_with, 'kickoff_disagreements': dict(disagree)}


def prereg_check():
    if not PREREG.exists() or not PREREG_LOCK.exists():
        raise SealError('PREREG_NOT_LOCKED', 'the pre-registration and its lock must exist before the seal')
    lock = json.loads(PREREG_LOCK.read_text())
    h = A.sha_file(PREREG)
    if lock.get('prereg_sha256') != h:
        raise SealError('PREREG_MODIFIED_AFTER_LOCK', f'{h} != {lock.get("prereg_sha256")}')
    return h, lock


# ------------------------------------------------------------------------------------------- pregame context
def pool_by_club(panel, season, week):
    """{club: [gsis]} -- the player's most recent row (weeks < week) of `season` names the club."""
    out = collections.defaultdict(list)
    for g, ss in panel['players'].items():
        wk = ss.get(str(season)) or {}
        last = None
        for w in sorted((k for k in wk if int(k) < week), key=int):
            if wk[w].get('team'):
                last = wk[w]['team']
        if last:
            out[last].append(g)
    return {c: sorted(v) for c, v in out.items()}


def build_context(panel_full, pos_of, season=SEASON, week=WEEK):
    panel = A.pregame_panel(panel_full, season, week)
    pm, _inf = FC.positions_for_chain(panel, pos_of)
    posmap, src = {}, {}
    pools = pool_by_club(panel, season, week)
    for g in {g for v in pools.values() for g in v}:
        if pos_of.get(g):
            posmap[g], src[g] = pos_of[g], 'ROSTER'
        elif pm.get((g, season)):
            posmap[g], src[g] = pm[(g, season)], 'USAGE_INFERRED'
    gl = sorted(g for g in posmap if posmap[g] in SKILL)
    priors = FC.season_priors(panel, posmap, season, gl)
    ctx = {'season': season, 'panel': panel, 'pos_of': pos_of, 'posmap': posmap, 'pos_src': src, 'dressed': {},
           'priors': priors}
    ctx['team_weeks'] = A.club_team_weeks(panel, season)
    pools = {c: [g for g in v if posmap.get(g) in SKILL] for c, v in pools.items()}
    return ctx, pools


def fitted_objects(panel_full, pos_of, ctx):
    fr = A.fit_field_rates(panel_full, pos_of, A.F1._dressed(A.FIT_SEASON))
    sc_rates = {(p, f): fr['rates'][(p, f, A.N_PRIOR)] for p, f in A.GATED_CELLS}
    depth = A.V.depth_shares(ctx['panel'], pos_of)        # production default (through=None) on the PREGAME panel
    groups = A.V.group_shares(ctx['panel'], pos_of)
    ir = A.V.int_rate(ctx['panel'], pos_of)['int_per_attempt']
    return fr, sc_rates, depth, groups, ir


def football_table(team_game_rows=None):
    rows = team_game_rows if team_game_rows is not None else FP._rows()
    return FP.club_points_table(rows)


def game_record(ctx, pools, fr, sc_rates, depth, groups, ir, model, g, seed, table, n_sims=N_SIMS, week=WEEK,
                mode=None):
    home, away = g['home'], g['away']
    starter = A.P2.starter_proxy(ctx, week)
    arms = {}
    for c in (home, away):
        pool = pools.get(c) or []
        if not pool:
            return {'state': 'REFUSED', 'code': 'EMPTY_CLUB_POOL', 'club': c}
        a = A.club_arms(ctx, depth, groups, sc_rates, c, week, starter, pool, ctx['team_weeks'],
                        qual_requires_dressed=False)
        if a is None:
            return {'state': 'REFUSED', 'code': 'CLUB_NOT_PROJECTABLE', 'club': c}
        for r in a['cur'] + a['cand']:
            r['eligibility'] = AV.UNKNOWN_ACTIVE_STATE
        arms[c] = a
    fc = FP.centre_for_game(home, away, ctx['season'], week, table=table)
    if fc is None:
        return {'state': 'REFUSED', 'code': 'NO_FOOTBALL_CENTRE'}
    centre = A.centre_from_tv(arms)
    rows_cur = [r for c in (home, away) for r in A.harness_rows(arms[c]['cur'])]
    rows_cand = [r for c in (home, away) for r in A.harness_rows(arms[c]['cand'])]
    rb_cur = {A.S.player_key(r['name'], r['team']): r for r in rows_cur}
    rb_cand = {A.S.player_key(r['name'], r['team']): r for r in rows_cand}
    try:
        sp_cur = A.build_spec(rows_cur, home, away, fc)
        sp_cand = A.build_spec(rows_cand, home, away, fc)
    except A.SuccessorError as e:
        return {'state': 'REFUSED', 'code': e.code}
    gates = {}
    for c in (home, away):
        gates.update(A.gates_for(arms[c]['cand'], arms[c]['hist'], fr, c))
    t0 = time.time()
    e_cur = A.end_to_end(model, sp_cur, centre, rb_cur, ir, n_sims, seed)
    e_suc = A.end_to_end(model, sp_cand, centre, rb_cand, ir, n_sims, seed, gates=gates, mode=mode)
    units = []
    for c in (home, away):
        a = arms[c]
        for rc, rn in zip(a['cur'], a['cand']):
            gs, pos = rc['_dk'], rc['position']
            if pos not in SCORED_FIELDS or ctx['pos_src'].get(gs) != 'ROSTER':
                continue
            key = A.S.player_key(gs, c)
            tf = A.P2.TABLE_FIELD[pos]
            for f in SCORED_FIELDS[pos]:
                xc = np.asarray(A.field_counts(e_cur['stat_draws'][key], f), float)
                xs = np.asarray(A.field_counts(e_suc['stat_draws'][key], f), float)
                dkc = np.asarray(e_cur['draws_final'][key], float)
                dks = np.asarray(e_suc['draws_final'][key], float)
                pi = gates[key][f]
                units.append({
                    'game_id': g['game_id'], 'club': c, 'opponent': away if c == home else home, 'gsis': gs,
                    'position': pos, 'field': f, 'eligibility': AV.UNKNOWN_ACTIVE_STATE,
                    'rank_table': ((rc.get('allocation') or {}).get(tf) or {}).get('depth_rank_in_group'),
                    'h_last3_present': a['hist'][(gs, f)], 'qualifies_sc_appear_1': a['qual'][(gs, f)],
                    'pi_candidate': round(pi, 6),
                    'p_plays_current': float((rc.get('p_plays') or {}).get(f, 1.0)),
                    'p_plays_sc_appear_1': float((rn.get('p_plays') or {}).get(f, 1.0)),
                    'P0_projection_current': round(1.0 - float((rc.get('p_plays') or {}).get(f, 1.0)), 6),
                    'P0_projection_candidate': round(1.0 - pi, 6),
                    'P0_draws_current': round(float((xc == 0).mean()), 6),
                    'P0_draws_successor': round(float((xs == 0).mean()), 6),
                    'expected_current': round(float(rc.get(f) or 0.0), 4),
                    'expected_candidate': round(float(rn.get(f) or 0.0), 4),
                    'mean_draws_current': round(float(xc.mean()), 4),
                    'mean_draws_successor': round(float(xs.mean()), 4),
                    'P_dk_zero_current': round(float((dkc == 0).mean()), 6),
                    'P_dk_zero_successor': round(float((dks == 0).mean()), 6),
                    'hist_current': A.histogram(xc), 'hist_successor': A.histogram(xs)})
    return {'state': 'SEALED', 'game_id': g['game_id'], 'home': home, 'away': away, 'kickoff_utc': g['kickoff_utc'],
            'seed': seed, 'n_sims': n_sims, 'football_centre': fc, 'volume_centre': centre,
            'pool_size': {c: len(pools.get(c) or []) for c in (home, away)},
            'hurdle_counts': e_suc['counts'],
            'volume_centre_within_tol': {'current': e_cur['sim']['volume_centre']['all_within_tol'],
                                         'successor': e_suc['sim']['volume_centre']['all_within_tol']},
            'unallocated_fraction': {'current': e_cur['sim']['unallocated_fraction'],
                                     'successor': e_suc['sim']['unallocated_fraction']},
            'seconds': round(time.time() - t0, 1), 'units': units}


def input_hashes(schedule_path):
    prov = json.loads((A.F1.HIST / 'PROVENANCE.json').read_text())
    snap24 = next(_REPO / x['file'] for x in prov['files'] if x['kind'] == 'snap_counts_2024')
    files = {'panel': PANEL, 'schedule': schedule_path, 'team_game': TEAM_GAME, 'football_points': FOOTBALL_POINTS,
             'snap_counts_2024_fit': snap24}
    return {k: {'path': str(pathlib.Path(p).relative_to(_REPO)), 'sha256': A.sha_file(p)} for k, p in files.items()}


def code_hashes():
    files = [pathlib.Path(__file__).resolve(), _CORE_PATH, A.P2.__file__ if hasattr(A.P2, '__file__') else None]
    out = {str(pathlib.Path(f).resolve().relative_to(_REPO)): A.sha_file(f) for f in files if f}
    out[str(A._HERE.relative_to(_REPO) / 'sc_appear_1_forward.py')] = A.sha_file(A._HERE / 'sc_appear_1_forward.py')
    out.update({f'production:{k}': v for k, v in A.production_hashes().items()})
    return out


def build(now_fn=None, schedule_path=None, panel=None, team_game_rows=None, games_filter=None, n_sims=N_SIMS,
          log=print, week=WEEK):
    now_fn = now_fn or (lambda: dt.datetime.now(dt.timezone.utc))
    sched = pathlib.Path(schedule_path) if schedule_path else newest_schedule()
    games = week_games(sched, SEASON, week)
    first = min(dt.datetime.fromisoformat(g['kickoff_utc']) for g in games)
    if now_fn() >= first:
        raise SealError('SEAL_AFTER_KICKOFF', f'now {now_fn().isoformat()} >= first kickoff {first.isoformat()}')
    if panel is None:
        po = PP.load_panel()
        if po.state.value != 'PASS':
            raise SealError('PANEL_ABSENT')
        panel = po.value
    pos_of = PP.position_index()
    ctx, pools = build_context(panel, pos_of, SEASON, week)
    if not pools:
        raise SealError('EMPTY_POOL')
    weeks_present = sorted({int(w) for ss in ctx['panel']['players'].values() for w in (ss.get(str(SEASON)) or {})})
    fr, sc_rates, depth, groups, ir = fitted_objects(panel, pos_of, ctx)
    model = A.load_model()
    table = football_table(team_game_rows)
    recs = {}
    for i, g in enumerate(games):
        if games_filter and g['game_id'] not in games_filter:
            continue
        rec = game_record(ctx, pools, fr, sc_rates, depth, groups, ir, model, g, SEAL_SEED + 1000 * (week - WEEK) + i,
                          table, n_sims, week=week)
        rec.setdefault('kickoff_utc', g['kickoff_utc'])
        recs[g['game_id']] = rec
        log(f"  {g['game_id']}: {rec['state']} {rec.get('code', '')} units={len(rec.get('units', []))} "
            f"{rec.get('seconds', '')}s")
    sealed = [r for r in recs.values() if r['state'] == 'SEALED']
    if not sealed or not any(r['units'] for r in sealed):
        raise SealError('NO_SEALED_UNITS')
    doc = {
        'ARTIFACT': f'APPEARANCE_SUCCESSOR_W{week}_SEAL', 'STATUS': 'SHADOW_ONLY', 'season': SEASON, 'week': week,
        'EVIDENCE_CLASS': 'PROSPECTIVE FORECAST, UNGRADED. Not evidence of anything until graded after the games.',
        'first_kickoff_utc': first.isoformat(), 'schedule_capture': sched.name,
        'schedule_agreement': schedule_agreement(games, week=week),
        'panel_2026_weeks_present': weeks_present,
        'weeks_missing_from_repo': [w for w in range(1, week) if w not in weeks_present],
        'MISSING_WEEKS_RULE': ('a week below the sealed week that is absent from the committed panel is '
                               'MISSING_FROM_REPO, NOT no-participation, and is never read as zero; histories use the '
                               'club\'s last 3 games PRESENT in the panel; club volume, priors, depth table and football '
                               'centre use only rows that exist (TEAM_GAME rows without points are dropped by '
                               'football_points._rows). For week 5: 2026 week 4 is MISSING_FROM_REPO'),
        'POOL_DEFINITION': (f'player whose most recent 2026 panel row before week {week} carries the club; position '
                            'from the roster index (USAGE_INFERRED positions are allocated but NOT sealed); no '
                            f'information from week {week} or later'),
        'ELIGIBILITY': ('every pool member is UNKNOWN_ACTIVE_STATE (no inactive list exists pregame): treated as eligible; '
                        'pi is P(>= 1 | active); the grader scores a unit only if the player is found dressed and never '
                        'scores an undressed sealed player as zero'),
        'CANDIDATE': {'allocation': 'SC-APPEAR-1 rate hooked at proj_v1 line 879 for qualifiers (h = 3), production '
                                    'allocator otherwise', 'gate': 'strict hurdle, zero-truncated positive part',
                      'positive_part': A.POSITIVE_PART, 'pi': A.rates_json(fr), 'pi_fit_through': fr['through'],
                      'gated_cells': [f'{p}|{f}' for p, f in A.GATED_CELLS]},
        'CURRENT': 'production allocator (depth table through=None on the pregame panel) -> production '
                   'simulate_game_centred, FOOTBALL_ONLY centre, n_calib = n_sims',
        'HARNESS': ('sc_appear_1_production_path / forward_chain harness: claims from V.project_player with priors '
                    f'through {SEASON - 1}, club volume from weeks < {week}, QB starter proxy from prior pass attempts. NOT the live '
                    'showdown path (no role state, no captured chart)'),
        'n_sims': n_sims, 'seed_base': SEAL_SEED + 1000 * (week - WEEK), 'int_rate': ir,
        'games': recs,
        'n_games_in_schedule': len(games), 'n_games_sealed': len(sealed),
        'n_units': sum(len(r['units']) for r in sealed),
        'n_players': len({(u['club'], u['gsis']) for r in sealed for u in r['units']}),
        'code_sha256': code_hashes(), 'input_sha256': input_hashes(sched),
    }
    return doc


def write_seal(doc, out=None, now_fn=None):
    now_fn = now_fn or (lambda: dt.datetime.now(dt.timezone.utc))
    out = pathlib.Path(out) if out else out_path(doc['week'])
    if out.exists():
        raise SealError('SEAL_EXISTS_WRITE_ONCE', str(out))
    now = now_fn()
    first = dt.datetime.fromisoformat(doc['first_kickoff_utc'])
    if now >= first:
        raise SealError('SEAL_AFTER_KICKOFF', f'now {now.isoformat()} >= first kickoff {first.isoformat()}')
    h, lock = prereg_check()
    doc = dict(doc)
    doc['prereg'] = {'path': str(PREREG.relative_to(_REPO)), 'sha256': h, 'locked_at': lock.get('locked_at')}
    doc['written_at'] = now.isoformat()
    doc['seal_sha256'] = seal_hash(doc)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'x') as fh:                       # 'x': refuses if another writer got there first
        fh.write(canonical(doc))
    os.chmod(out, 0o444)
    back = json.loads(out.read_text())
    if back.get('seal_sha256') != seal_hash(back) or out.stat().st_size == 0:
        raise SealError('SEAL_READBACK_MISMATCH')
    return out, doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--games', nargs='*')
    ap.add_argument('--n-sims', type=int, default=N_SIMS)
    ap.add_argument('--week', type=int, default=WEEK)
    a = ap.parse_args()
    if not a.dry_run and out_path(a.week).exists():
        raise SealError('SEAL_EXISTS_WRITE_ONCE', str(out_path(a.week)))
    doc = build(games_filter=a.games, n_sims=a.n_sims, week=a.week)
    if a.dry_run:
        print(json.dumps({k: doc[k] for k in ('n_games_in_schedule', 'n_games_sealed', 'n_units', 'n_players',
                                              'first_kickoff_utc')}, indent=1))
        return 0
    p, d = write_seal(doc)
    print(f"VERIFIED {p.relative_to(_REPO)} ({p.stat().st_size} bytes, seal_sha256 {d['seal_sha256']}, "
          f"written_at {d['written_at']})")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
