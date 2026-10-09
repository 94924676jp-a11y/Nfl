#!/usr/bin/env python3.12
"""A football player universe for a Classic slate built from the CAPTURED roster, with no DraftKings file.

    python3.12 nfl/tools/research_universe.py 2026W5 --raw-dir nfl/dfs/salaries/raw/classic_early_2026W5 \
        --as-of 2026-10-09T20:00:00Z --out OUT_DIR

WHY. Football forecasting needs a list of the players who can play; it does not need DraftKings' ids or
prices. The classic state builder used to take that list only from a DKEntries export, so a slate with no
entries file could not be projected at all, and contest entry assignment blocked player research. This
builds the universe from the nflverse weekly roster capture (GSIS-derived) instead:

  who        roster status ACT at the slate week, positions QB/RB/WR/TE (FB carried as RB), on the clubs of
             the slate's games; one team defence per club. DEV (practice squad) is EXCLUDED without an
             elevation record, and the count is stated; RES/RET/EXE are excluded and counted
  games      the schedule capture's games at the slate kickoff (gameday and gametime, ET)
  ids        synthetic `RU-<gsis_id>` / `RU-DST-<club>`. They are not DK ids, so nothing built on this
             universe can be uploaded; `universe_kind` says so in every row
  salary     None. Prices are a contest-assignment input, never a football one

It fetches nothing and models nothing.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.dfs.salaries import early_only as EO  # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

CODE = 'RESEARCH_UNIVERSE_BUILT'
KIND = 'RESEARCH_UNIVERSE_NOT_UPLOADABLE'
SKILL = {'QB': 'QB', 'RB': 'RB', 'FB': 'RB', 'WR': 'WR', 'TE': 'TE'}
FLEX = {'RB': 'RB/FLEX', 'WR': 'WR/FLEX', 'TE': 'TE/FLEX', 'QB': 'QB', 'DST': 'DST'}


def _one(raw_dir, stem):
    m = sorted(pathlib.Path(raw_dir).resolve().glob(f'{stem}.*.csv.gz'))
    if len(m) != 1:
        raise FileNotFoundError(f'{stem}: expected exactly one capture in {raw_dir}, found {len(m)}')
    b = m[0].read_bytes()
    return list(csv.DictReader(gzip.decompress(b).decode('utf-8').splitlines())), m[0], hashlib.sha256(b).hexdigest()


def build(slate_id: str, raw_dir) -> Outcome:
    files = EO.slate_files(slate_id)
    kick = files['kickoff']                                   # 'MM/DD/YYYY HH:MMPM ET'
    mm, dd, yyyy = kick.split(' ')[0].split('/')
    hhmm = kick.split(' ')[1]
    h, mi = int(hhmm[:2]) % 12 + (12 if hhmm.endswith('PM') else 0), hhmm[3:5]
    gameday, gametime = f'{yyyy}-{mm}-{dd}', f'{h:02d}:{mi}'
    games, gpath, gsha = _one(raw_dir, 'NFLVERSE_GAMES_2026')
    slate = [g for g in games if g['gameday'] == gameday and g['gametime'] == gametime
             and g['game_type'] == 'REG']
    if not slate:
        return Outcome.blocked('RESEARCH_UNIVERSE_NO_GAMES', f'no schedule game at {gameday} {gametime}',
                               cause=Cause.EMPTY_INPUT)
    weeks = {g['week'] for g in slate}
    if len(weeks) != 1:
        return Outcome.fail('RESEARCH_UNIVERSE_GAMES_SPAN_WEEKS', f'weeks {sorted(weeks)}')
    week = weeks.pop()
    side = {}
    for g in slate:
        side[g['away_team']] = (g['away_team'], g['home_team'])
        side[g['home_team']] = (g['away_team'], g['home_team'])
    roster, rpath, rsha = _one(raw_dir, 'NFLVERSE_ROSTER_WEEKLY_2026')
    wk = [r for r in roster if r['week'] == week and r['team'] in side]
    if not wk:
        return Outcome.blocked('RESEARCH_UNIVERSE_NO_ROSTER_WEEK', f'roster capture has no week {week} rows',
                               cause=Cause.EMPTY_INPUT)
    missing_clubs = sorted(set(side) - {r['team'] for r in wk})
    if missing_clubs:
        return Outcome.blocked('RESEARCH_UNIVERSE_CLUB_WITHOUT_ROSTER', f'{missing_clubs}', cause=Cause.DATA)
    excluded = collections.Counter()
    out = []
    gi = {c: f'{a}@{hm} {kick}' for c, (a, hm) in side.items()}
    for r in sorted(wk, key=lambda r: (r['team'], r['position'], r['full_name'])):
        pos = SKILL.get(r['position'])
        if pos is None:
            continue
        if r['status'] != 'ACT':
            excluded[r['status']] += 1
            continue
        a, hm = side[r['team']]
        out.append({'dk_id': f"RU-{r['gsis_id']}", 'dk_name': r['full_name'], 'name_and_id': None,
                    'dk_pos': pos, 'roster_position': FLEX[pos], 'flex_eligible': pos != 'QB',
                    'salary': None, 'dk_team': r['team'], 'team': r['team'], 'game_info': gi[r['team']],
                    'kickoff': kick, 'away': a, 'home': hm,
                    'gsis_id_from_roster': r['gsis_id'], 'universe_kind': KIND})
    for c, (a, hm) in sorted(side.items()):
        out.append({'dk_id': f'RU-DST-{c}', 'dk_name': f'{c} DST', 'name_and_id': None, 'dk_pos': 'DST',
                    'roster_position': 'DST', 'flex_eligible': False, 'salary': None, 'dk_team': c, 'team': c,
                    'game_info': gi[c], 'kickoff': kick, 'away': a, 'home': hm, 'universe_kind': KIND})
    blob = json.dumps(out, sort_keys=True).encode()
    return Outcome.ok(CODE, value=out, detail=f'{len(out)} rows, {len(slate)} games, week {week}',
                      sha256=hashlib.sha256(blob).hexdigest(), sha256_matches_declared=True,
                      universe_kind=KIND, week=int(week),
                      n_rows=len(out), n_by_pos=dict(collections.Counter(r['dk_pos'] for r in out)),
                      excluded_non_act_by_status=dict(excluded),
                      DEV_POLICY='practice-squad players are excluded: no elevation record is captured',
                      sources={'schedule': {'file': str(gpath.relative_to(_REPO)), 'sha256': gsha},
                               'roster': {'file': str(rpath.relative_to(_REPO)), 'sha256': rsha}})


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--raw-dir', required=True)
    ap.add_argument('--as-of', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args(argv)
    from nfl.tools import classic_slate_state as CS
    u = build(a.slate_id, a.raw_dir)
    print(f'{u.state.value}[{u.code}] {u.detail}')
    if u.state.value != 'PASS':
        return 2
    st = CS.build(a.slate_id, as_of=a.as_of, research_universe=u)
    print(f'{st.state.value}[{st.code}] {st.detail}')
    od = pathlib.Path(a.out)
    od.mkdir(parents=True, exist_ok=True)
    (od / f'RESEARCH_UNIVERSE_{a.slate_id}.json').write_text(json.dumps(
        {'evidence': u.evidence, 'rows': u.value}, indent=1, default=str) + '\n')
    if st.state.value != 'PASS':
        (od / f'RESEARCH_STATE_{a.slate_id}.REFUSAL.json').write_text(json.dumps(
            {'code': st.code, 'detail': st.detail, 'evidence': st.evidence}, indent=1, default=str) + '\n')
        return 2
    (od / f'RESEARCH_STATE_{a.slate_id}.json').write_text(json.dumps(st.value, indent=1, default=str) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
