#!/usr/bin/env python3.12
"""Hard Rock price history: the store, the closing-line refusal, and seal-before-price.

WHY THERE IS NO CLOSING-LINE VALUE TODAY, measured rather than assumed. The repository holds exactly
ONE Hard Rock board: `HR_NYG_LAR_BOARD_2026-09-21T2320Z.csv`, 969 rows over 12 market types for one
game. It carries 74 distinct `ts_utc` values, which looks like a time series and is not: the ages span
0.4 to 8.9 minutes, so those are the per-row capture moments inside a single ~10-minute scrape. One
game, one pass. A market observed once has no movement, so closing-line value, line-movement
diagnostics and edge-bucket calibration are all UNCOMPUTABLE, and this module returns a named refusal
for each rather than a number built from one point.

WHAT AN OBSERVATION IS, AND THE FIRST VERSION GOT IT WRONG. The board carries a stable composite key
per PRICED SIDE, and which column holds it depends on the market. A one-sided market -- moneyline,
point spread -- carries `price_id` with `price`. A two-sided market -- every player prop, total points,
team total -- carries `over_id` and `under_id` with `over` and `under`, and leaves `price_id` EMPTY.
Requiring `price_id` refused 791 of 969 rows, which is 12 market types including every receiving-yards
line. That is the "field names were guessed instead of read from the schema" defect, and the refusal
caught it rather than dropping the rows silently.

So the unit is one observation per priced SIDE: a two-sided row yields two, a one-sided row yields
one, and each carries its own key. One side's price at two capture times is two observations of that
side, so two boards of the same game at different times produce movement with no name matching.

THE ORDERING RULE, AND IT IS THE POINT OF THE MODULE. `capture/registry.py` already declares the
Hard Rock snapshot `DOWNSTREAM_COMPARATOR_ONLY` and not forecast-eligible, with the right reason: a
model that has seen the line is no longer independent evidence about the line. A declaration is not a
mechanism. So `comparable()` requires a SEAL whose `written_at` is at or before the price's capture
time. A price captured before the forecast was sealed could have been seen while the forecast was
being made, and a comparison against it measures nothing. That check is arithmetic on two timestamps
and it either passes or the comparison is refused.

WHAT THIS MODULE WILL NEVER DO. It does not adjust a projection toward a price, and it holds no code
path that could. Comparison is one direction: a sealed forecast is scored against a price, and the
price never travels back.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import glob
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

RAW_DIR = _REPO / 'nfl/market/raw'
STORE = _REPO / 'nfl/market/PRICE_HISTORY.json'

#: The board export's real columns. A file missing any is REFUSED whole: a board read without
#: `ts_utc` has no position in time, and a comparison against a price of unknown vintage is not a
#: weaker measurement, it is not a measurement.
REQUIRED_BOARD_COLUMNS = ('market', 'selection', 'points', 'is_main', 'over', 'under', 'price',
                          'ts_utc', 'age_min', 'price_id', 'over_id', 'under_id')

#: Every row must carry `ts_utc` and at least one of these. Which one depends on whether the market
#: is one-sided or two-sided, so requiring any single column would refuse most of a real board.
KEY_COLUMNS = ('price_id', 'over_id', 'under_id')

#: Minimum distinct capture passes per market before movement may be reported at all.
MIN_PASSES_FOR_MOVEMENT = 2

#: A capture pass is a scrape; rows inside one pass carry their own moments minutes apart. Two rows
#: whose times differ by less than this are the same pass, not movement. DECLARED from the observed
#: board, whose single pass spans 8.5 minutes end to end.
SAME_PASS_MINUTES = 20.0

CLV_UNCOMPUTABLE = 'CLOSING_LINE_VALUE_UNCOMPUTABLE_ONE_PASS'


def _parse_ts(s):
    try:
        return dt.datetime.fromisoformat(str(s).strip())
    except (ValueError, TypeError):
        return None


def load_board(path: pathlib.Path) -> Outcome:
    """One board CSV -> observations, or a named refusal. Never a partial read."""
    if not path.exists():
        return Outcome.blocked('BOARD_ABSENT', f'{path} does not exist', cause=Cause.DATA)
    rows = list(csv.DictReader(path.read_text(encoding='utf-8-sig').splitlines()))
    if not rows:
        return Outcome.fail('BOARD_EMPTY', f'{path.name} parsed to zero rows. An empty board is an '
                                           f'error, not a slate with no markets.')
    missing = [c for c in REQUIRED_BOARD_COLUMNS if c not in rows[0]]
    if missing:
        return Outcome.fail(
            'BOARD_SCHEMA_MISMATCH',
            f'{path.name} is missing {missing}, so it is refused rather than read around',
            columns_present=sorted(rows[0].keys()))
    obs, bad = [], []
    for r in rows:
        ts = _parse_ts(r.get('ts_utc'))
        sides = [(r.get('price_id'), r.get('price'), 'SINGLE'),
                 (r.get('over_id'), r.get('over'), 'OVER'),
                 (r.get('under_id'), r.get('under'), 'UNDER')]
        sides = [(k.strip(), (v or '').strip() or None, side)
                 for k, v, side in sides if (k or '').strip()]
        if ts is None or not sides:
            bad.append({'market': r.get('market'), 'selection': r.get('selection'),
                        'ts_utc': r.get('ts_utc'),
                        'why': ('UNPARSEABLE_TS' if ts is None
                                else f'NO_KEY_IN_ANY_OF_{list(KEY_COLUMNS)}')})
            continue
        for key, price, side in sides:
            obs.append({'price_id': key, 'side': side, 'market': r.get('market'),
                        'selection': r.get('selection'),
                        'points': (r.get('points') or '').strip() or None,
                        'price': price,
                        'is_main': str(r.get('is_main')).strip().lower() == 'true',
                        'ts_utc': ts.isoformat(), 'source_file': path.name})
    if bad:
        return Outcome.fail(
            'BOARD_UNDATED_OR_UNKEYED_ROWS',
            f'{len(bad)} of {len(rows)} rows in {path.name} have no parseable ts_utc or no key in '
            f'any of {list(KEY_COLUMNS)}. Refused whole: a row with no time cannot be placed before '
            f'or after a seal, and a row with no key cannot be matched to the same side in another '
            f'pass.',
            examples=bad[:5])
    return Outcome.ok('BOARD_LOADED', value={'file': path.name, 'n_observations': len(obs),
                                             'observations': obs})


def build(paths=None) -> Outcome:
    """Every board on disk, keyed by price_id, with passes counted per market."""
    files = ([pathlib.Path(p) for p in paths] if paths
             else sorted(pathlib.Path(p) for p in glob.glob(str(RAW_DIR / '*BOARD*.csv'))))
    if not files:
        return Outcome.blocked(
            'NO_HARD_ROCK_BOARDS', f'no *BOARD*.csv in {RAW_DIR.relative_to(_REPO)}',
            cause=Cause.DATA, outbox='docs/AGENT_OUTBOX.md OUT-043')
    by_id = collections.defaultdict(list)
    loaded, refused = [], []
    for f in files:
        o = load_board(f)
        if o.state.name != 'PASS':
            refused.append({'file': f.name, 'code': o.code, 'detail': o.detail})
            continue
        loaded.append({'file': f.name, 'n_observations': o.value['n_observations']})
        for ob in o.value['observations']:
            by_id[ob['price_id']].append(ob)
    if refused and not loaded:
        return Outcome.fail('ALL_BOARDS_REFUSED', f'{len(refused)} board(s) and none passed schema',
                            refused=refused)

    markets = {}
    multi = 0
    for pid, obs in by_id.items():
        obs.sort(key=lambda o: o['ts_utc'])
        passes = [obs[0]]
        for ob in obs[1:]:
            gap = ((_parse_ts(ob['ts_utc']) - _parse_ts(passes[-1]['ts_utc'])).total_seconds()
                   / 60.0)
            if gap >= SAME_PASS_MINUTES:
                passes.append(ob)
        if len(passes) >= MIN_PASSES_FOR_MOVEMENT:
            multi += 1
        markets[pid] = {'market': obs[0]['market'], 'selection': obs[0]['selection'],
                        'side': obs[0]['side'],
                        'is_main': obs[0]['is_main'], 'n_observations': len(obs),
                        'n_capture_passes': len(passes),
                        'first_ts': obs[0]['ts_utc'], 'last_ts': obs[-1]['ts_utc'],
                        'prices_by_pass': [{'ts_utc': p['ts_utc'], 'price': p['price'],
                                            'points': p['points']} for p in passes]}
    art = {
        'ARTIFACT': 'PRICE_HISTORY',
        'BOOK': 'Hard Rock Bet only',
        'WHAT_AN_OBSERVATION_IS': (
            'price_id is a stable composite key, so the same market at two capture times is two '
            'observations of one market and no name matching is needed.'),
        'SAME_PASS_MINUTES': (SAME_PASS_MINUTES, (
            'DECLARED. Rows inside one scrape carry their own moments minutes apart -- the one '
            'board on disk spans 8.5 minutes end to end -- so two rows closer together than this '
            'are the same pass and not movement.')),
        'files_loaded': loaded, 'files_refused': refused,
        'n_markets': len(markets),
        'n_markets_with_movement_measurable': multi,
        'markets': markets,
        'NEVER': ('no projection is adjusted toward a price by this module, and it holds no code '
                  'path that could. Comparison runs one way only.'),
    }
    STORE.write_text(json.dumps(art, indent=2))
    return Outcome.ok('PRICE_HISTORY_BUILT', value={
        'n_files': len(loaded), 'n_markets': len(markets),
        'n_markets_with_movement_measurable': multi, 'refused': refused})


def closing_line_value(price_id: str, store=None) -> Outcome:
    """Movement for one market, or a refusal. One pass is not a line to compare against."""
    art = store if store is not None else (json.loads(STORE.read_text()) if STORE.exists() else None)
    if art is None:
        return Outcome.blocked('PRICE_HISTORY_NOT_BUILT', f'{STORE.name} missing; run build()',
                               cause=Cause.DATA)
    m = (art.get('markets') or {}).get(price_id)
    if m is None:
        return Outcome.blocked('MARKET_NOT_IN_HISTORY', f'{price_id} has no observations',
                               cause=Cause.DATA)
    if m['n_capture_passes'] < MIN_PASSES_FOR_MOVEMENT:
        return Outcome.blocked(
            CLV_UNCOMPUTABLE,
            f'{price_id} was captured in {m["n_capture_passes"]} pass; closing-line value needs at '
            f'least {MIN_PASSES_FOR_MOVEMENT} passes at different times',
            cause=Cause.DATA,
            note=('this is the state of the whole store, not one unlucky market: every Hard Rock '
                  'market in this checkout was captured once. Reporting a movement of zero would '
                  'be reporting an absence as a measurement.'),
            outbox='docs/AGENT_OUTBOX.md OUT-043')
    first, last = m['prices_by_pass'][0], m['prices_by_pass'][-1]
    return Outcome.ok('CLOSING_LINE_VALUE', value={
        'price_id': price_id, 'n_passes': m['n_capture_passes'],
        'opening': first, 'closing': last,
        'CLOSING_MEANS': ('the last observed pass, which is the last price CAPTURED and not '
                          'necessarily the last price OFFERED. It is only a true close if a pass '
                          'ran near kickoff.')})


def comparable(seal: dict, observation: dict) -> Outcome:
    """May this sealed forecast be compared against this price? Timestamps decide, nothing else.

    The seal must be written at or before the price's capture time. A price that existed before the
    forecast was sealed could have been seen while the forecast was being built, and a comparison
    against it is not independent evidence about the line.
    """
    sw = _parse_ts(seal.get('written_at'))
    pt = _parse_ts(observation.get('ts_utc'))
    if sw is None or pt is None:
        return Outcome.fail('COMPARABILITY_TIMESTAMP_UNPARSEABLE',
                            f'seal.written_at={seal.get("written_at")!r} '
                            f'price.ts_utc={observation.get("ts_utc")!r}')
    if pt < sw:
        return Outcome.fail(
            'PRICE_PREDATES_THE_SEAL',
            f'the price was captured at {pt.isoformat()} and the forecast was sealed at '
            f'{sw.isoformat()}, {(sw - pt).total_seconds() / 60:.1f} minutes later. The line '
            f'existed before the forecast was sealed, so comparing them measures nothing about '
            f'whether we beat it.',
            seal_written_at=sw.isoformat(), price_ts_utc=pt.isoformat())
    ko = _parse_ts(seal.get('kickoff_utc'))
    if ko is not None and pt > ko:
        return Outcome.fail(
            'PRICE_IS_POST_KICKOFF',
            f'the price was captured at {pt.isoformat()}, after kickoff at {ko.isoformat()}. An '
            f'in-play price is not the price the forecast could have been acted on at.')
    return Outcome.ok('COMPARABLE', value={
        'seal_written_at': sw.isoformat(), 'price_ts_utc': pt.isoformat(),
        'minutes_seal_to_price': round((pt - sw).total_seconds() / 60.0, 1),
        'ORDER_HELD': 'forecast sealed, then price captured, then kickoff'})


def main() -> int:
    o = build()
    print(o.state, o.code, o.detail or '')
    if o.state.name == 'PASS':
        print(json.dumps(o.value, indent=2, default=str))
        art = json.loads(STORE.read_text())
        pid = next(iter(art['markets']), None)
        if pid:
            c = closing_line_value(pid, store=art)
            print(f'\nclosing line for {pid}:\n  {c.state} {c.code}\n  {c.detail or ""}')
        print(f'-> {STORE.relative_to(_REPO)}')
    else:
        print(json.dumps(o.evidence, indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
