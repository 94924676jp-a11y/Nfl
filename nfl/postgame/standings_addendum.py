#!/usr/bin/env python3.12
"""Week-4 Early Only: the DraftKings standings ADDENDUM to the frozen postgame grade.

    python3.12 nfl/postgame/standings_addendum.py ingest --file contest-standings-196208416.csv --captured-at ...
    python3.12 nfl/postgame/standings_addendum.py grade

WHY AN ADDENDUM AND NOT A REGRADE. The postgame grade is frozen (nfl/dfs/salaries/postgame/
FROZEN_2026W4_EARLY.json, graded at d170f333, frozen at d1a91624) and its rule is that a later regrade
must reproduce those hashes or be written as a new, separately dated version. `classic_week.py ingest`
appends to raw/2026W4/PROVENANCE.jsonl, which is one of the frozen files, and `grade` rewrites the
frozen JSON. So the standings are stored under their own raw directory with their own provenance, and
everything they unlock -- finish, field ownership, the winner, duplication -- is written to new files.
Every frozen file is re-hashed before and after; a change to any of them fails the run.

WHAT THE EXPORT DOES NOT CARRY. A DK standings export has rank, points, lineup, %Drafted and FPTS. It has
no payout table, so cash line, winnings and ROI are NOT computed here (BLOCKED_PAYOUT_TABLE_NOT_SUPPLIED),
and no cash line is assumed. The lock is read from git via classic_week.locked(), never the working tree.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import json
import pathlib
import shutil
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402
from nfl.postgame import classic_week as W  # noqa: E402

RAW = _REPO / 'nfl/postgame/raw/2026W4_standings'
PROV = RAW / 'PROVENANCE.jsonl'
#: Addendum N >= 2 never touches addendum 1's frozen raw files: new standings go to their own directory
#: and provenance, and the grade writes ..._ADDENDUM_N.json. Set by main(); 1 is the original layout.
ADDENDUM = 1


def raw_dir(n):
    return RAW if n == 1 else _REPO / f'nfl/postgame/raw/2026W4_standings_addendum_{n}'


def prior_freezes():
    return sorted(OUT.glob('FROZEN_2026W4_EARLY_STANDINGS_ADDENDUM_*.json'))
OUT = _REPO / 'nfl/dfs/salaries/postgame'
FROZEN = OUT / 'FROZEN_2026W4_EARLY.json'


def frozen_hashes():
    out = {}
    for fz in [FROZEN] + prior_freezes():
        m = json.loads(fz.read_text())
        out.update({f: (hashlib.sha256((_REPO / f).read_bytes()).hexdigest() if (_REPO / f).exists() else None) == h
                    for f, h in m['sha256'].items()})
    return out


def ingest(src, captured_at, source):
    src = pathlib.Path(src)
    if not src.exists() or src.stat().st_size == 0:
        return Outcome.blocked('STANDINGS_FILE_EMPTY', str(src), cause=Cause.EMPTY_INPUT)
    rd = raw_dir(ADDENDUM)
    rd.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    dst = rd / f'DK_STANDINGS.{sha[:16]}.csv'
    if not dst.exists():
        shutil.copy2(src, dst)
        dst.chmod(0o444)
    rec = {'kind': 'DK_STANDINGS', 'file': str(dst.relative_to(_REPO)), 'sha256': sha, 'source': source,
           'captured_at': captured_at, 'original_name': src.name,
           'ingested_at': dt.datetime.now(dt.timezone.utc).isoformat(),
           'slate_scope': '2026W4 Early Only 8 games'}
    with (rd / 'PROVENANCE.jsonl').open('a') as fh:
        fh.write(json.dumps(rec) + '\n')
    return Outcome.ok('INGESTED', rec, f'{sha[:12]} -> {dst.name}')


def _load():
    out = []
    lines = []
    for n in range(1, ADDENDUM + 1):
        pv = raw_dir(n) / 'PROVENANCE.jsonl'
        if pv.exists():
            lines += pv.read_text().splitlines()
    for ln in lines:
        r = json.loads(ln)
        p = _REPO / r['file']
        if hashlib.sha256(p.read_bytes()).hexdigest() != r['sha256']:
            raise SystemExit(f'REFUSED: {p} changed since ingest')
        out.append((p, r))
    return out


def canon(lineup):
    return tuple(sorted(n for _s, n in lineup))


def grade():
    before = frozen_hashes()
    if not all(before.values()):
        return Outcome.fail('FROZEN_RECORD_ALREADY_CHANGED', f'{[f for f, ok in before.items() if not ok]}')
    lo = W.locked()
    if lo.state.value != 'PASS':
        return lo
    lock = lo.value
    ours = {r[0]: {'contest_id': r[2], 'fee': r[3]} for r in lock['upload']}
    frozen = json.loads((OUT / 'DK_2026W4_EARLY_POSTGAME.json').read_text())
    our_actual = {}
    with (OUT / 'DK_2026W4_EARLY_POSTGAME_PLAYERS.csv').open() as fh:
        for r in csv.DictReader(fh):
            if r.get('actual') not in (None, ''):
                our_actual[r['player']] = float(r['actual'])
    got = _load()
    if not got:
        return Outcome.blocked('STANDINGS_NOT_INGESTED', 'no standings ingested', cause=Cause.DATA)
    contests = {}
    for p, rec in got:
        rows = list(csv.DictReader(open(p, encoding='utf-8-sig')))
        ent = [r for r in rows if r.get('EntryId')]
        cids = {ours[r['EntryId']]['contest_id'] for r in ent if r['EntryId'] in ours}
        if len(cids) != 1:
            return Outcome.blocked('STANDINGS_CONTEST_UNKNOWN', f'{p.name}: our entries found for {sorted(cids)}',
                                   cause=Cause.DATA)
        cid = cids.pop()
        label = W.CONTESTS.get(cid, cid)
        field = [{'rank': int(r['Rank']), 'entry_id': r['EntryId'], 'user': (r['EntryName'] or '').split(' (')[0],
                  'points': float(r['Points'] or 0), 'lineup': W.parse_lineup(r['Lineup']),
                  'ours': r['EntryId'] in ours} for r in ent]
        n = len(field)
        empty = sum(1 for f in field if not f['lineup'])
        mine = sorted((f for f in field if f['ours']), key=lambda f: f['rank'])
        n_ours_upload = sum(1 for v in ours.values() if v['contest_id'] == cid)
        # DK lists a player ONCE PER ROSTER SLOT he was drafted in (e.g. RB 32.52% and FLEX 6.36%), so
        # total ownership is the sum over his rows. Keeping one row per name read Love as 6.36%.
        own = {}
        for r in rows:
            if r.get('Player'):
                o = own.setdefault(r['Player'].strip(), {'pct': 0.0, 'fpts': None, 'by_slot': {}})
                v = float((r['%Drafted'] or '0').rstrip('%'))
                o['pct'] = round(o['pct'] + v, 2)
                o['by_slot'][r.get('Roster Position')] = v
                if r.get('FPTS') not in (None, ''):
                    o['fpts'] = float(r['FPTS'])
        # DK's denominator is every entry, empty ones included, so the 9-slot total is 900 x filled / all.
        tot = sum(v['pct'] for v in own.values())
        n_all = len(ent)
        n_filled = sum(1 for r in ent if r.get('Lineup'))
        expect = 900.0 * n_filled / n_all
        if abs(tot - expect) > 0.5:
            return Outcome.fail('STANDINGS_OWNERSHIP_DOES_NOT_RECONCILE',
                                f'%Drafted sums to {tot:.2f}, expected {expect:.2f} (9 slots x filled/all entries)')
        # DK's own FPTS against ours (the frozen grade's component scoring)
        recon = [(nm, our_actual[nm], v['fpts']) for nm, v in own.items()
                 if nm in our_actual and v['fpts'] is not None and abs(our_actual[nm] - v['fpts']) > 0.05]
        n_checked = sum(1 for nm, v in own.items() if nm in our_actual and v['fpts'] is not None)
        # finish
        ranks = [f['rank'] for f in mine]
        pct = lambda r: r / n
        finish = {'field_size': n, 'empty_entries_in_field': empty, 'our_entries_in_file': len(mine),
                  'our_entries_uploaded': n_ours_upload, 'best_rank': ranks[0] if ranks else None,
                  'best_points': mine[0]['points'] if mine else None,
                  'median_rank': ranks[len(ranks) // 2] if ranks else None,
                  'in_top_0_1pct': sum(1 for r in ranks if pct(r) <= 0.001),
                  'in_top_1pct': sum(1 for r in ranks if pct(r) <= 0.01),
                  'in_top_5pct': sum(1 for r in ranks if pct(r) <= 0.05),
                  'in_top_10pct': sum(1 for r in ranks if pct(r) <= 0.10),
                  'in_top_20pct': sum(1 for r in ranks if pct(r) <= 0.20),
                  'rank_percentiles_of_our_entries': {q: (ranks[int(q / 100 * (len(ranks) - 1))] if ranks else None)
                                                      for q in (10, 25, 50, 75, 90)},
                  'entry_fee': sorted({ours[f['entry_id']]['fee'] for f in mine}),
                  'cash_winnings_roi': 'BLOCKED_PAYOUT_TABLE_NOT_SUPPLIED (the standings export carries no prizes)'}
        filled = [f for f in field if f['lineup']]
        fp = sorted(f['points'] for f in filled)
        mp = sorted(f['points'] for f in mine)
        cum = lambda f: sum(own.get(nm, {}).get('pct', 0.0) for nm in canon(f['lineup']))
        fc, mc = sorted(cum(f) for f in filled), sorted(cum(f) for f in mine)
        med = lambda a: a[len(a) // 2] if a else None
        finish['field_vs_ours'] = {
            'field_mean_points': round(sum(fp) / len(fp), 2), 'field_median_points': med(fp),
            'our_mean_points': round(sum(mp) / len(mp), 2), 'our_median_points': med(mp),
            'field_median_cumulative_ownership_pct': round(med(fc), 1),
            'our_median_cumulative_ownership_pct': round(med(mc), 1),
            'MEANING': 'cumulative ownership = sum of the nine players\' %Drafted; lower is less duplicated'}
        # winner and the gap to our best
        win = min(field, key=lambda f: f['rank'])
        best = mine[0] if mine else None
        pts = {nm: v['fpts'] for nm, v in own.items()}
        wset, bset = set(canon(win['lineup'])), set(canon(best['lineup'])) if best else set()
        gap = {'winner': {'user': win['user'], 'points': win['points'],
                          'lineup': [(s, nm, pts.get(nm), own.get(nm, {}).get('pct')) for s, nm in win['lineup']]},
               'our_best': None if not best else {'entry_id': best['entry_id'], 'rank': best['rank'], 'points': best['points'],
                                                  'lineup': [(s, nm, pts.get(nm), own.get(nm, {}).get('pct')) for s, nm in best['lineup']]},
               'gap_points': None if not best else round(win['points'] - best['points'], 2),
               'shared_players': sorted(wset & bset),
               'winner_only': [(nm, pts.get(nm)) for nm in sorted(wset - bset)],
               'ours_only': [(nm, pts.get(nm)) for nm in sorted(bset - wset)],
               'DECOMPOSITION': ('gap = sum(winner-only points) - sum(our-only points); shared players cancel')}
        if best:
            gap['check'] = round(sum(pts.get(nm) or 0 for nm in wset - bset) - sum(pts.get(nm) or 0 for nm in bset - wset), 2)
        # ownership vs our exposure (150 / 20 / 3 separately is the frozen exposure table; this contest only)
        ex = collections.Counter(nm for f in mine for nm in canon(f['lineup']))
        lev = []
        for nm, v in own.items():
            ours_pct = 100.0 * ex.get(nm, 0) / max(1, len(mine))
            lev.append({'player': nm, 'field_pct': v['pct'], 'our_pct': round(ours_pct, 1),
                        'leverage_pts': round(ours_pct - v['pct'], 1), 'fpts': v['fpts']})
        lev.sort(key=lambda x: -abs(x['leverage_pts']))
        # duplication: how many field entries share each of our lineups
        cnt = collections.Counter(canon(f['lineup']) for f in field if f['lineup'])
        dup = collections.Counter(cnt[canon(f['lineup'])] for f in mine)
        top_field_dupes = cnt.most_common(5)
        # field optimal-lineup comparison from the frozen grade
        optimum = (frozen.get('optimal_lineup') or {}).get('points') if isinstance(frozen.get('optimal_lineup'), dict) else None
        contests[cid] = {'label': label, 'file': rec['file'], 'sha256': rec['sha256'], 'finish': finish,
                         'ownership_reconciliation': {'sum_pct': round(tot, 2), 'expected': round(expect, 2),
                                                      'MEANING': 'DK %Drafted is over all entries incl. empty'},
                         'winner_gap': gap, 'ownership_leverage_top30': lev[:30],
                         'our_lineup_duplication': {'copies_in_field_including_ours': dict(sorted(dup.items())),
                                                    'n_unique_to_us': dup.get(1, 0)},
                         'field_most_duplicated': [{'lineup': list(k), 'n': v} for k, v in top_field_dupes],
                         'dk_fpts_reconciliation': {'n_checked': n_checked, 'n_mismatch': len(recon), 'mismatches': recon[:20],
                                                    'NOTE': ('DK is the official score. A mismatch is a finding against the '
                                                             'frozen grade, recorded here; the frozen record is not edited')},
                         'winner_vs_optimal': {'optimal': optimum, 'winner': win['points'],
                                               'winner_over_optimal': round(win['points'] / optimum, 3) if optimum else None}}
        own_csv = OUT / f'DK_2026W4_EARLY_STANDINGS_{label}_OWNERSHIP.csv'
        if own_csv.exists() and str(own_csv.relative_to(_REPO)) in frozen_hashes():
            continue          # already frozen by an earlier addendum; never rewritten
        with own_csv.open('w', newline='') as fh:
            wr = csv.DictWriter(fh, fieldnames=['player', 'field_pct', 'our_pct', 'leverage_pts', 'fpts'])
            wr.writeheader()
            wr.writerows(sorted(lev, key=lambda x: -x['field_pct']))
    doc = {'ARTIFACT': 'POSTGAME_STANDINGS_ADDENDUM', 'slate': '2026W4 Early Only',
           'graded_at': dt.datetime.now(dt.timezone.utc).isoformat(),
           'ADDENDUM_TO': {'freeze': str(FROZEN.relative_to(_REPO)), 'graded_at_commit': 'd170f333',
                           'frozen_at_commit': 'd1a91624'},
           'lock': {'commit': W.LOCK_COMMIT, 'upload_sha256': W.LOCK_UPLOAD_SHA256},
           'contests': contests,
           'contests_not_yet_supplied': sorted(set(W.CONTESTS) - set(contests)),
           'ONE_SLATE': 'one contest on one slate: observations for the ledger, not skill estimates'}
    name = 'DK_2026W4_EARLY_STANDINGS_ADDENDUM.json' if ADDENDUM == 1 else f'DK_2026W4_EARLY_STANDINGS_ADDENDUM_{ADDENDUM}.json'
    if ADDENDUM == 1 and prior_freezes():
        return Outcome.fail('ADDENDUM_1_IS_FROZEN', 'addendum 1 is frozen; grade with --addendum 2 or later')
    doc['addendum'] = ADDENDUM
    (OUT / name).write_text(json.dumps(doc, indent=1, default=str))
    after = frozen_hashes()
    if not all(after.values()):
        return Outcome.fail('FROZEN_RECORD_CHANGED_BY_ADDENDUM', f'{[f for f, ok in after.items() if not ok]}')
    return Outcome.ok('STANDINGS_ADDENDUM_GRADED', doc, f'{len(contests)} contest(s); frozen record intact ({len(after)} files)')


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    i = sub.add_parser('ingest')
    i.add_argument('--file', required=True)
    i.add_argument('--captured-at', required=True)
    i.add_argument('--source', default='DraftKings contest standings export, downloaded and uploaded by the owner')
    sub.add_parser('grade')
    ap.add_argument('--addendum', type=int, default=1)
    a = ap.parse_args()
    global ADDENDUM
    ADDENDUM = a.addendum
    o = ingest(a.file, a.captured_at, a.source) if a.cmd == 'ingest' else grade()
    print(o.state.value, o.code, o.detail)
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
