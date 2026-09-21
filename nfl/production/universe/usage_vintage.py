"""The widest LAWFUL play-by-play, including the governed vintage store.

THE DEFECT, MEASURED 2026-09-21

`current_season_nonqb_panel._capture` globs exactly one directory,
`nfl/research/postgame/`, and requires a sibling `.provenance.json`. The
governed vintage store is not on that path. For 2026 the widest blob it can
see carries TEN week-1 games. The vintage store holds a manifested capture of
the same week carrying SIXTEEN, and the six it adds include `2026_01_DAL_NYG`
and `2026_01_DEN_KC` -- both clubs of the Monday night game.

So a layer asking "what did the Giants do in week one?" was told nothing, and
"nothing" is indistinguishable from "no usage" unless somebody names it. That
is the Phase-1 failure class exactly: a step returned something partial and
the partial answer was read as the answer.

WHY THE ACCEPTED PANEL IS NOT EDITED HERE

`current_season_nonqb_panel` feeds the accepted R8 and Q9 chain. Changing
which bytes it selects changes an accepted model's inputs, which is a
production change and belongs in its own decision with its own before-and-
after. This module is the CANDIDATE-side loader: it sees the whole governed
corpus, it reports the difference against what the accepted panel sees, and
it leaves the accepted panel bit-for-bit alone.

THE COUNTING IS NOT REIMPLEMENTED

`COUNTING_RULES`, `BLANK`, `_f` and `_one` are IMPORTED from the accepted
panel. There is therefore no second copy of "what is a target" to drift from
the first, and the reconciliation the panel records (a throwaway is not a
target; BUF 28 not 29) holds here unchanged. What differs between the two
modules is which bytes are read, and only that.
"""
from __future__ import annotations

import collections
import csv
import datetime as _dt
import glob
import gzip
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.nonqb.current_season_nonqb_panel import (      # noqa: E402
    BLANK, COUNTING_RULES, PBP_GLOB, _f, _one)
from sportsplatform.governance.outcome import (                    # noqa: E402
    Cause, Outcome)

SPEC_VERSION = 'nfl-usage-widest-lawful-1'
MANIFEST = 'nfl/vintage_manifest.jsonl'


def _iso(s):
    try:
        t = _dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
        return t if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)
    except (TypeError, ValueError):
        return None


def _games(path) -> set:
    g = set()
    with gzip.open(path, 'rt', errors='ignore') as fh:
        for r in csv.DictReader(fh):
            if r.get('game_id'):
                g.add(r['game_id'])
    return g


def candidates(season: int, as_of: str) -> Outcome:
    """Every lawful 2026 play-by-play blob this checkout holds, both stores.

    A blob is lawful when its retrieval clock is at or before `as_of`.
    Retrieval is never earlier than publication, so the direction is
    conservative -- the same reading the vintage selector documents.
    """
    cut = _iso(as_of)
    if cut is None:
        return Outcome.blocked(
            'USAGE_CUT_UNPARSEABLE',
            f'{as_of!r} is not a timestamp, and a corpus selected without a '
            f'clock is a corpus that may contain its own answer.',
            cause=Cause.GOVERNANCE)
    found, dropped = [], []

    # 1. The directory the accepted panel reads.
    for f in sorted(glob.glob(str(_REPO / (PBP_GLOB % season)))):
        prov = pathlib.Path(str(f).replace('.csv.gz', '.csv.provenance.json'))
        if not prov.exists():
            continue
        p = json.loads(prov.read_text())
        t = _iso(p.get('retrieved_at'))
        rec = {'blob': pathlib.Path(f).name, 'path': f,
               'store': 'research_postgame', 'clock': p.get('retrieved_at'),
               'n_games_declared': len(p.get('games') or [])}
        (found if (t and t <= cut) else dropped).append(rec)

    # 2. The governed vintage store, which the accepted panel cannot see.
    man = _REPO / MANIFEST
    if man.exists():
        seen = set()
        for line in man.read_text().splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get('source') != 'pbp' or d.get('season') != season:
                continue
            blob = (d.get('value') or {}).get('blob')
            if not blob or blob in seen:
                continue
            p = pathlib.Path(blob)
            if not p.exists():
                p = _REPO / 'nfl' / 'vintage' / p.name
                if not p.exists():
                    continue
            seen.add(blob)
            stamp = (d.get('capture_id') or '').split('.')[0]
            t = _iso(stamp.replace('T', 'T').rstrip('Z') + 'Z'
                     if stamp else None)
            rec = {'blob': p.name, 'path': str(p), 'store': 'vintage',
                   'clock': stamp, 'n_games_declared': None,
                   'capture_id': d.get('capture_id')}
            (found if (t and t <= cut) else dropped).append(rec)

    if not found:
        return Outcome.blocked(
            'USAGE_NO_LAWFUL_CAPTURE',
            f'no play-by-play capture for {season} in either store is lawful '
            f'before {as_of}. {len(dropped)} blob(s) were dropped by the '
            f'clock.', cause=Cause.DATA, dropped=dropped)
    for rec in found:
        rec['games'] = sorted(_games(rec['path']))
        rec['n_games'] = len(rec['games'])
    found.sort(key=lambda r: -r['n_games'])
    return Outcome.ok(
        'USAGE_CAPTURES_ENUMERATED', value=found,
        n_lawful=len(found), n_dropped_by_clock=len(dropped),
        dropped=dropped, as_of=as_of,
        detail=f'{len(found)} lawful blob(s); widest is {found[0]["blob"]} '
               f'with {found[0]["n_games"]} game(s)')


def usage_season(season: int, as_of: str, before_week: int = None) -> Outcome:
    """Per (week, club, player) usage from the WIDEST lawful blob.

    Row shape and counting match `current_season_nonqb_panel.usage_season`
    exactly, because the rules are imported from it. `before_week` drops any
    week at or after the one being forecast, so the forecast week is never in
    its own evidence.
    """
    co = candidates(season, as_of)
    if co.state.name != 'PASS':
        return co
    cands = co.value
    pick = cands[0]

    accepted = [c for c in cands if c['store'] == 'research_postgame']
    accepted_best = max((c['n_games'] for c in accepted), default=0)
    accepted_games = set(max(accepted, key=lambda c: c['n_games'])['games']) \
        if accepted else set()
    extra = sorted(set(pick['games']) - accepted_games)

    per = collections.defaultdict(lambda: dict(BLANK))
    weeks = collections.Counter()
    with gzip.open(pick['path'], 'rt', errors='ignore') as fh:
        for r in csv.DictReader(fh):
            w = r.get('week')
            if not r.get('posteam') or w is None:
                continue
            try:
                wi = int(float(w))
            except (TypeError, ValueError):
                continue
            if before_week is not None and wi >= before_week:
                continue
            if _one(r.get('two_point_attempt')):
                continue
            club = r['posteam']
            weeks[wi] += 1
            if _one(r.get('rush_attempt')):
                pid = (r.get('rusher_player_id') or '').strip()
                if pid:
                    d = per[(wi, club, pid)]
                    d['carries'] += 1
                    d['rush_yards'] += _f(r.get('rushing_yards'))
                    if (_f(r.get('yardline_100')) or 99) <= 20:
                        d['rz_carries'] += 1
            if _one(r.get('pass_attempt')):
                pid = (r.get('receiver_player_id') or '').strip()
                if pid:
                    d = per[(wi, club, pid)]
                    d['targets'] += 1
                    if (_f(r.get('yardline_100')) or 99) <= 20:
                        d['rz_targets'] += 1
                    if _one(r.get('complete_pass')):
                        d['receptions'] += 1
                        d['rec_yards'] += _f(r.get('receiving_yards'))
    if not per:
        return Outcome.blocked(
            'USAGE_NO_ROWS_BEFORE_WEEK',
            f'{pick["blob"]} carries no play before week {before_week}. An '
            f'empty corpus is an error, not a set of weeks in which nobody '
            f'touched the ball.', cause=Cause.DATA, blob=pick['blob'])

    team = collections.defaultdict(lambda: dict(BLANK))
    for (wi, club, _p), d in per.items():
        t = team[(wi, club)]
        for k in BLANK:
            t[k] += d[k]
    rows = {}
    for (wi, club, pid), d in per.items():
        t = team[(wi, club)]
        rows[(wi, club, pid)] = {
            'team': club, 'player_id': pid, 'season': season, 'week': wi, **d,
            'appeared_by_opportunity': (d['carries'] + d['targets']) > 0,
            'carry_share': (d['carries'] / t['carries']
                            if t['carries'] else None),
            'target_share': (d['targets'] / t['targets']
                             if t['targets'] else None),
        }
    # The same conservation the accepted panel enforces. A share that does not
    # sum to one means opportunity was lost or invented in the counting.
    bad = []
    for (wi, club), t in team.items():
        for key, tot in (('carry_share', t['carries']),
                         ('target_share', t['targets'])):
            if not tot:
                continue
            s = sum(r[key] for r in rows.values()
                    if r['team'] == club and r['week'] == wi
                    and r[key] is not None)
            if abs(s - 1.0) > 1e-9:
                bad.append({'week': wi, 'team': club, 'share': key, 'sum': s})
    if bad:
        return Outcome.fail(
            'USAGE_SHARES_DO_NOT_CONSERVE',
            f'{len(bad)} club-week share sum(s) are not 1.0 to 1e-9.',
            cause=Cause.DATA, offending=bad)

    return Outcome.ok(
        'USAGE_MEASURED_WIDEST_LAWFUL', value=rows,
        spec_version=SPEC_VERSION, season=season, as_of=as_of,
        before_week=before_week, blob=pick['blob'], store=pick['store'],
        clock=pick['clock'], n_rows=len(rows),
        n_games=pick['n_games'], games=pick['games'],
        weeks=sorted(weeks),
        clubs=sorted({c for (_w, c) in team}),
        counting_rules=COUNTING_RULES,
        counting_imported_from='current_season_nonqb_panel',
        accepted_panel_sees_n_games=accepted_best,
        games_the_accepted_panel_cannot_see=extra,
        discrepancy_note=(
            'the accepted panel globs nfl/research/postgame/ only and cannot '
            'see the governed vintage store. Those games are absent from its '
            'corpus, where absence is indistinguishable from zero usage '
            'unless it is named. This module names it and changes nothing '
            'about the accepted panel.'),
        detail=f'{len(rows)} row(s) from {pick["blob"]} '
               f'({pick["n_games"]} game(s)); the accepted panel sees '
               f'{accepted_best}, missing {len(extra)}')
