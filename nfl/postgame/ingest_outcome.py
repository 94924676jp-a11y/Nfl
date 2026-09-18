"""Build the DET @ BUF outcome artifact from governed sources, or refuse.

TWO ARTIFACTS, BECAUSE THEY BECAME AVAILABLE AT DIFFERENT TIMES

  FINAL_SCORE.json   the final score. Available 2026-09-18 from nfldata
                     `games.csv`, which carries the completed week-2 row.
  OUTCOME.json       the full result: final score AND a per-player stat line
                     for every player. NOT available -- the nflverse weekly
                     player build still carries week 1 only.

They are separate files rather than one file that grows, because a partial
box score written into the outcome path would be read as the outcome. The
grading gate requires `players` and refuses the partial artifact, which is the
behaviour that keeps a half-measurement from being reported as a measurement.

WHAT THE FINAL SCORE CAN AND CANNOT GRADE. It settles which side scored 41 --
Buffalo -- and nothing else. **The sealed board emits no score and no game
total.** Its team layer is snaps, dropbacks, carries, targets and red-zone
carries; there is no points distribution anywhere in the artifact. So the
72-point game cannot be scored against this model at all, and the gap is the
subject of the shared-game-environment work, not a grade.

THE RAW BYTES ARE SAVED BEFORE THEY ARE PARSED, and the hash recorded is the
hash of what was actually read.
"""
from __future__ import annotations

import csv
import datetime as _dt
import gzip
import hashlib
import io
import json
import pathlib
import sys
import urllib.request

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import artifact_claim as AC             # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State    # noqa: E402
from nfl.postgame import outcome as OC                                 # noqa: E402

SPEC_VERSION = 'nfl-postgame-ingest-1'
SEASON, WEEK = '2026', '2'
GAMES_URL = ('https://raw.githubusercontent.com/nflverse/nfldata/master/'
             'data/games.csv')
STATS_URL = ('https://github.com/nflverse/nflverse-data/releases/download/'
             'stats_player/stats_player_week_2026.csv')
RAW = OC.DIR / 'raw'
SCORE = OC.DIR / 'FINAL_SCORE.json'

#: nflverse field-goal columns -> the DraftKings distance buckets
#: `statline.StatLine.fg_made_by_bucket` uses. A kicker's DK points are
#: distance-weighted, so summing `fg_made` alone would underpay a 50-yarder.
FG_BUCKETS = {
    'FG<20': 'fg_made_0_19', 'FG20s': 'fg_made_20_29',
    'FG30s': 'fg_made_30_39', 'FG40s': 'fg_made_40_49',
    'FG50+': ('fg_made_50_59', 'fg_made_60_'),
}

#: nflverse weekly column -> the stat name `outcome.STATS` declares. Explicit,
#: because `attempts` means passing attempts here and `carries` does not.
COLS = {
    'pass_att': 'attempts', 'pass_cmp': 'completions',
    'pass_yards': 'passing_yards', 'pass_td': 'passing_tds',
    'interceptions': 'passing_interceptions',
    'rush_att': 'carries', 'rush_yards': 'rushing_yards',
    'rush_td': 'rushing_tds',
    'targets': 'targets', 'receptions': 'receptions',
    'rec_yards': 'receiving_yards', 'rec_td': 'receiving_tds',
}

NOT_PUBLISHED = 'WEEK_NOT_PUBLISHED_BY_SOURCE'


def _now():
    return _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def fetch(url, *, stem) -> Outcome:
    """Read the bytes, hash them, write them down, and only then parse."""
    try:
        body = urllib.request.urlopen(url, timeout=90).read()
    except Exception as e:                                    # noqa: BLE001
        return Outcome.blocked(
            'SOURCE_UNREACHABLE', f'{url}: {type(e).__name__} {e}',
            cause=Cause.NETWORK, url=url)
    if not body:
        return Outcome.fail(
            'SOURCE_RETURNED_NOTHING',
            f'{url} returned 0 bytes. An empty response is an error, not an '
            f'empty week.', cause=Cause.DATA, url=url)
    sha = hashlib.sha256(body).hexdigest()
    RAW.mkdir(parents=True, exist_ok=True)
    p = RAW / f'{stem}.{sha[:16]}.csv.gz'
    if not p.exists():
        p.write_bytes(gzip.compress(body))
    return Outcome.ok(
        'SOURCE_READ', value=body.decode('utf-8', 'replace'),
        detail=f'{len(body)} bytes, sha256 {sha[:16]}, raw at {p.name}',
        url=url, sha256=sha, n_bytes=len(body), raw_path=str(p),
        retrieved_at_utc=_now())


def final_score() -> Outcome:
    got = fetch(GAMES_URL, stem='nfldata_games')
    if got.state is not State.PASS:
        return got
    rows = [r for r in csv.DictReader(io.StringIO(got.value))
            if r.get('game_id') == OC.GAME_ID]
    if not rows:
        return Outcome.fail(
            'GAME_ROW_ABSENT', f'{OC.GAME_ID} is not in {GAMES_URL}',
            cause=Cause.DATA)
    r = rows[0]
    home, away = r.get('home_score'), r.get('away_score')
    if not home or not away:
        return Outcome.blocked(
            NOT_PUBLISHED,
            f'{OC.GAME_ID} is listed but carries no score yet '
            f'(home={home!r} away={away!r}).', cause=Cause.DATA)
    return Outcome.ok(
        'FINAL_SCORE_CAPTURED',
        value={'game_id': OC.GAME_ID,
               'home_team': r['home_team'], 'home_score': int(home),
               'away_team': r['away_team'], 'away_score': int(away),
               'total': int(home) + int(away),
               'source': GAMES_URL,
               'source_sha256': got.evidence['sha256'],
               'retrieved_at_utc': got.evidence['retrieved_at_utc'],
               'raw_path': got.evidence['raw_path'],
               'grades_nothing_in_the_model': (
                   'the sealed board emits no score and no game total. Its '
                   'team layer is snaps, dropbacks, carries, targets and '
                   'red-zone carries. This score settles which side scored '
                   '41 and cannot be scored against the model.')},
        detail=f'{r["away_team"]} {away} @ {r["home_team"]} {home}',
        spec_version=SPEC_VERSION, **{k: got.evidence[k]
                                      for k in ('sha256', 'retrieved_at_utc')})


def player_lines() -> Outcome:
    got = fetch(STATS_URL, stem='nflverse_stats_player_week')
    if got.state is not State.PASS:
        return got
    rows = list(csv.DictReader(io.StringIO(got.value)))
    weeks = sorted({r.get('week') for r in rows if r.get('week')})
    mine = [r for r in rows
            if r.get('season') == SEASON and r.get('week') == WEEK
            and r.get('team') in ('DET', 'BUF')]
    if not mine:
        return Outcome.blocked(
            NOT_PUBLISHED,
            f'the weekly player build carries weeks {weeks} and no week-{WEEK} '
            f'DET/BUF rows. {len(rows)} row(s) read, sha256 '
            f'{got.evidence["sha256"][:16]}. This is a publication lag at the '
            f'source, not a parse failure -- nothing is inferred to fill it.',
            cause=Cause.DATA, weeks_present=weeks, n_rows=len(rows),
            sha256=got.evidence['sha256'],
            retrieved_at_utc=got.evidence['retrieved_at_utc'])

    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    players = {}
    for r in mine:
        nm = r.get('player_display_name') or r.get('player_name')
        buckets = {}
        for b, col in FG_BUCKETS.items():
            cols = (col,) if isinstance(col, str) else col
            v = sum(num(r.get(c)) for c in cols)
            if v:
                buckets[b] = v
        kicking = {'fg_made': num(r.get('fg_made')),
                   'fg_att': num(r.get('fg_att')),
                   'xp_made': num(r.get('pat_made')),
                   'xp_att': num(r.get('pat_att')),
                   'fg_made_by_bucket': buckets}
        players[nm] = {'team': r.get('team'), 'position': r.get('position'),
                       'player_id': r.get('player_id'),
                       **{k: num(r.get(c)) for k, c in COLS.items()},
                       'kicking': kicking}
    return Outcome.ok(
        'PLAYER_LINES_CAPTURED', value=players,
        detail=f'{len(players)} player row(s) for week {WEEK}',
        spec_version=SPEC_VERSION, sha256=got.evidence['sha256'],
        retrieved_at_utc=got.evidence['retrieved_at_utc'],
        source=STATS_URL)


def build() -> Outcome:
    """FINAL_SCORE.json always when available; OUTCOME.json only when whole."""
    sc = final_score()
    if sc.state is State.PASS:
        OC.DIR.mkdir(parents=True, exist_ok=True)
        SCORE.write_text(json.dumps(sc.value, indent=1, sort_keys=True))
        claim = AC.claim(SCORE, schema=['home_score', 'away_score', 'source'],
                         label=SCORE.name, quiet=True)
        if claim.state is not State.PASS:
            return claim
    pl = player_lines()
    if pl.state is not State.PASS:
        return Outcome.blocked(
            OC.CODE_MISSING,
            f'final score: {sc.state.value}[{sc.code}] {sc.detail}; player '
            f'lines: {pl.state.value}[{pl.code}] {pl.detail} '
            f'OUTCOME.json is NOT written -- a partial box score is not an '
            f'outcome artifact, and writing one would let a half-measurement '
            f'be reported as a measurement.',
            cause=Cause.DATA, spec_version=SPEC_VERSION,
            final_score_state=sc.state.value,
            player_lines_state=pl.state.value,
            player_lines_code=pl.code,
            weeks_present=pl.evidence.get('weeks_present'),
            assigned_to='docs/AGENT_OUTBOX.md OUT-023')
    if sc.state is not State.PASS:
        return sc
    art = {'game_id': OC.GAME_ID,
           'source': f'{GAMES_URL} + {STATS_URL}',
           'retrieved_at_utc': pl.evidence['retrieved_at_utc'],
           'source_sha256': {'games': sc.evidence['sha256'],
                             'stats_player_week': pl.evidence['sha256']},
           'final_score': sc.value,
           'players': pl.value,
           'spec_version': SPEC_VERSION}
    OC.ARTIFACT.write_text(json.dumps(art, indent=1, sort_keys=True))
    claim = AC.claim(OC.ARTIFACT, schema=list(OC.REQUIRED),
                     label=OC.ARTIFACT.name, quiet=True)
    if claim.state is not State.PASS:
        return claim
    return Outcome.ok(
        'OUTCOME_ARTIFACT_BUILT', value=art,
        detail=f'{sc.detail}; {len(pl.value)} player row(s); '
               f'sha256 {claim.evidence["sha256"][:16]}',
        spec_version=SPEC_VERSION)


def main() -> int:
    o = build()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state is State.PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())
