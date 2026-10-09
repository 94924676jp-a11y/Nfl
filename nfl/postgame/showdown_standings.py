#!/usr/bin/env python3.12
"""Slate-generic DraftKings Showdown contest standings: which lineups DK held, how they finished, and the field.

    python3.12 nfl/postgame/showdown_standings.py CONFIG.json STANDINGS_CSV [STANDINGS_CSV ...]

Reads the owner-exported `contest-standings-<contest_id>.csv` files (header and lineup grammar exactly as
nfl/field/showdown_history_calibration.py validates them), preserves each content-addressed and read-only under the
config's raw_dir, and writes <tag>_STANDINGS.json beside the postgame document.

WHAT IT ESTABLISHES, AND HOW
  ACCEPTED LINEUPS   our entry ids are found in the standings; the lineup DK held for each is compared with every
                     frozen portfolio's lineup for that entry id. A generated CSV is a candidate; this is what DK held.
  SCORER PARITY      DK's points for every one of our entries must equal our points recomputed from nflverse actuals.
                     Any mismatch is reported by entry -- it would mean our scorer and DK's disagree.
  FINISH             rank, field size and percentile per entry; the field's winning score and score quantiles.
  FIELD              captain and flex %Drafted (DK's own numbers), our exposure beside them, and how many field entries
                     share each of our lineups exactly (duplication).

WHAT IT CANNOT ESTABLISH
  Winnings. The standings export carries no payout table and no per-entry prize, so winnings and net stay UNKNOWN
  unless a DK entry-history export (Winnings_* columns) is supplied. Entry fees are known from the DKEntries export.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.field import showdown_history_calibration as HC  # noqa: E402
from nfl.postgame import showdown_postgame as SP  # noqa: E402


class StandingsError(RuntimeError):
    pass


def need(c, code, detail=''):
    if not c:
        raise StandingsError(f'{code}: {detail}')


def preserve(src, raw_dir):
    b = pathlib.Path(src).read_bytes()
    text = b.decode('utf-8-sig')
    rows = list(csv.reader(io.StringIO(text)))
    need(rows and rows[0] == HC.EXPECTED_HEADER, 'SCHEMA', str(rows[0] if rows else None))
    cid = pathlib.Path(src).stem.rsplit('-', 1)[-1]
    need(cid.isdigit(), 'CONTEST_ID_NOT_IN_FILENAME', str(src))
    h = hashlib.sha256(b).hexdigest()
    raw_dir.mkdir(parents=True, exist_ok=True)
    dst = raw_dir / f'DK_STANDINGS_{cid}.{h[:16]}.csv.gz'
    if not dst.exists():
        dst.write_bytes(gzip.compress(b, mtime=0))
        dst.chmod(0o444)
    rec = {'contest_id': cid, 'file': SP._rel(dst), 'sha256_uncompressed': h, 'bytes': len(b),
           'captured_at': dt.datetime.now(dt.timezone.utc).isoformat(), 'source': 'owner upload (DK contest standings export)'}
    pj = raw_dir / 'STANDINGS_PROVENANCE.jsonl'
    seen = [json.loads(x) for x in pj.read_text().splitlines() if x.strip()] if pj.exists() else []
    if not any(r['sha256_uncompressed'] == h for r in seen):
        with pj.open('a') as f:
            f.write(json.dumps(rec) + '\n')
    return cid, rows, rec


def parse(rows, cid):
    entries, empty, own = [], 0, {}
    for i, r in enumerate(rows[1:], start=2):
        need(len(r) in (9, 11), 'ROW_WIDTH', f'{cid} line {i}: {len(r)}')
        if r[1].strip():
            if not r[5].strip():
                empty += 1
            else:
                c, f = HC.parse_lineup(r[5].strip(), i)
                entries.append({'rank': int(r[0]), 'entry_id': r[1].strip(), 'user': r[2].rsplit(' (', 1)[0].strip(),
                                'points': float(r[4]), 'cpt': c, 'flex': f})
        if len(r) == 11 and r[7].strip():
            own[(r[7].strip(), r[8].strip())] = {'pct_drafted': float(r[9].rstrip('%')), 'fpts': float(r[10])}
    need(entries and own, 'EMPTY_STANDINGS', cid)
    return entries, empty, own


def our_entries(export):
    """{entry_id: (contest_id, fee)} from the DKEntries export the portfolios were built for."""
    out = {}
    for r in list(csv.reader(open(export, encoding='utf-8-sig')))[1:]:
        if r and r[0].strip().isdigit():
            out[r[0].strip()] = (r[2].strip(), float(r[3].replace('$', '') or 0))
    need(out, 'NO_ENTRIES_IN_EXPORT', str(export))
    return out


def run(config_path, standings_paths, write=True):
    cfg = json.loads(pathlib.Path(config_path).read_text())
    pg = json.loads((_REPO / cfg['out_dir'] / f"{cfg['tag']}_POSTGAME.json").read_text())
    pts = {k: float(v['dk_A']) for k, v in pg['player_actuals'].items()}
    sd = _REPO / cfg['forecast_scenario_dir']
    state = json.loads(next(sd.glob('SHOWDOWN_*_STATE.json')).read_text())
    nk = SP._name_key(state)
    export = next(_REPO / p['path'] for p in cfg['portfolios'] if p['format'] == 'UPLOAD')
    ours = our_entries(export)
    # every frozen portfolio's lineup per entry id (sorted flex), for identification
    cand = {}
    for p in cfg['portfolios']:
        path = _REPO / p['path']
        lu = SP.lineups_from_final(path) if p['format'] == 'FINAL_LINEUPS' else SP.lineups_from_upload(path, state)
        cand[p['name']] = {e: (c, tuple(sorted(f))) for _, e, c, f in lu if e}
    raw = _REPO / cfg['raw_dir']
    out = {'ARTIFACT': 'SHOWDOWN_STANDINGS', 'tag': cfg['tag'], 'game': cfg['game'], 'contests': {},
           'NOT_A_FORECAST_INPUT': True}
    all_ident = collections.Counter()
    for sp_ in standings_paths:
        cid, rows, rec = preserve(sp_, raw)
        need(cid in cfg['contests'], 'CONTEST_NOT_IN_CONFIG', cid)
        entries, empty, own = parse(rows, cid)
        n_field = len(entries) + empty
        pts_field = np.array([e['points'] for e in entries])
        mine = [e for e in entries if e['entry_id'] in ours]
        expected = [e for e, (c, _f) in ours.items() if c == cid]
        missing = sorted(set(expected) - {e['entry_id'] for e in mine})
        ident, parity_bad, rows_out = collections.Counter(), [], []
        lineup_count = collections.Counter((e['cpt'], e['flex']) for e in entries)
        for e in mine:
            held = (e['cpt'], e['flex'])
            match = sorted(n for n, m in cand.items() if m.get(e['entry_id']) == held)
            key = '+'.join(match) if match else 'NONE_OF_THE_FROZEN_PORTFOLIOS'
            ident[key] += 1
            ours_pts = SP.score_lineup(e['cpt'], e['flex'], pts, nk)
            if abs(ours_pts - e['points']) > 0.011:
                parity_bad.append({'entry_id': e['entry_id'], 'dk': e['points'], 'ours': ours_pts})
            rows_out.append({'entry_id': e['entry_id'], 'rank': e['rank'], 'points': e['points'],
                             'percentile_beaten': round(float((pts_field < e['points']).mean()), 4),
                             'captain': e['cpt'], 'flex': list(e['flex']), 'held_matches': match,
                             'field_copies_of_this_lineup': lineup_count[held]})
        all_ident.update(ident)
        mp = np.array([r['points'] for r in rows_out]) if rows_out else np.array([])
        cpt_own = {n: v['pct_drafted'] for (n, slot), v in own.items() if slot == 'CPT'}
        flex_own = {n: v['pct_drafted'] for (n, slot), v in own.items() if slot == 'FLEX'}
        our_cpt = collections.Counter(r['captain'] for r in rows_out)
        our_any = collections.Counter(x for r in rows_out for x in [r['captain'], *r['flex']])
        n_ours = max(1, len(rows_out))
        players = sorted(set(cpt_own) | set(flex_own), key=lambda n: -(cpt_own.get(n, 0) + flex_own.get(n, 0)))
        fee = sum(ours[e][1] for e in expected)
        out['contests'][cid] = {
            'provenance': rec, 'field_entries': n_field, 'field_entries_with_lineup': len(entries),
            'our_entries_expected': len(expected), 'our_entries_found': len(mine), 'our_entries_missing': missing,
            'accepted_lineup_identification': dict(ident), 'scorer_parity_mismatches': parity_bad,
            'winning_score': float(pts_field.max()),
            'field_score_quantiles': {q: round(float(np.percentile(pts_field, q)), 2) for q in (50, 75, 80, 90, 95, 99, 99.9)},
            'ours': {'best_rank': int(min(r['rank'] for r in rows_out)) if rows_out else None,
                     'best_points': float(mp.max()) if mp.size else None,
                     'median_points': float(np.median(mp)) if mp.size else None,
                     'n_top_1pct': int((mp >= np.percentile(pts_field, 99)).sum()) if mp.size else 0,
                     'n_top_10pct': int((mp >= np.percentile(pts_field, 90)).sum()) if mp.size else 0,
                     'n_top_20pct': int((mp >= np.percentile(pts_field, 80)).sum()) if mp.size else 0,
                     'n_top_25pct': int((mp >= np.percentile(pts_field, 75)).sum()) if mp.size else 0,
                     'entries': sorted(rows_out, key=lambda r: r['rank'])},
            'duplication': {'our_lineups_unique_in_field': sum(1 for r in rows_out if r['field_copies_of_this_lineup'] == 1),
                            'mean_field_copies': round(float(np.mean([r['field_copies_of_this_lineup'] for r in rows_out])), 2) if rows_out else None,
                            'max_field_copies': max((r['field_copies_of_this_lineup'] for r in rows_out), default=None)},
            'ownership': [{'player': n, 'field_cpt_pct': cpt_own.get(n), 'field_flex_pct': flex_own.get(n),
                           'our_cpt_pct': round(100 * our_cpt[n] / n_ours, 1),
                           'our_rostered_pct': round(100 * our_any[n] / n_ours, 1)} for n in players],
            'financial': {'entry_fees_total': round(fee, 2), 'winnings': 'UNKNOWN', 'net': 'UNKNOWN',
                          'why_unknown': 'the standings export carries no payout table or per-entry prize; a DK '
                                         'entry-history export (Winnings_* columns) settles it'}}
    out['accepted_lineup_identification_all'] = dict(all_ident)
    out['written_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    if write:
        (_REPO / cfg['out_dir'] / f"{cfg['tag']}_STANDINGS.json").write_text(json.dumps(out, indent=1) + '\n')
    return out


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    try:
        doc = run(argv[0], argv[1:])
    except StandingsError as e:
        print(f'REFUSED {e}')
        return 4
    print(json.dumps(doc['accepted_lineup_identification_all']))
    for cid, c in doc['contests'].items():
        o = c['ours']
        print(cid, 'field', c['field_entries'], 'found', c['our_entries_found'], '/', c['our_entries_expected'],
              'winner', c['winning_score'], 'our best', o['best_points'], 'rank', o['best_rank'],
              'parity mismatches', len(c['scorer_parity_mismatches']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
