#!/usr/bin/env python3.12
"""ONE command: slate file in, legal DK portfolio out, or a named stage refusal.

WHY THIS EXISTS. The owner had to come to this session to get 48 lineups. That is the
whole diagnosis: the project was functioning as a research lab that produces evidence,
not a product that produces a portfolio. Twelve artifacts and a defect ledger are not a
Sunday deliverable.

So this is the end-to-end path, with a single owner and a single output:

    ingest slate -> verify identity -> ingest availability -> determine current role
    -> projections (proprietary, else governed fallback) -> candidate generation
    -> portfolio selection -> legality validation -> DK upload CSV

Every stage either PRODUCES or REFUSES with a named code, and the run ALWAYS emits one
status board saying where it got to. A stage that cannot run does not stop the board from
existing; it appears on the board as the reason the product is degraded.

WHAT THIS IS HONEST ABOUT. There is no joint simulator. Correlation here comes from
declared structural rules -- a quarterback with his own pass catchers, an optional opposing
bring-back, no team defence against our own quarterback -- and NOT from simulated football.
So the board reports `CORRELATION_HEURISTIC_NOT_SIMULATION`, and ceiling, duplication and
expected payout are UNKNOWN rather than invented. A portfolio built this way is a
FALLBACK-mode product and says so in its own status line.

WHAT IT REFUSES TO DO. It will not roster a player reported absent. It will not exceed the
salary cap. It will not emit a CSV with a blank cell. It will not describe a fallback
number as ours. It will not overwrite the owner's own entry file.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import itertools
import json
import pathlib
import random
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.tools import availability as AV  # noqa: E402
from nfl.tools import fc_context as FC  # noqa: E402
from nfl.tools import product_readiness as PRD  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

SPEC_VERSION = 'slate-to-portfolio-1'

SALARY_CAP = 50_000
SLOTS = ('QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX', 'DST')
FLEX_OK = ('RB', 'WR', 'TE')
DK_HEADER = ('Entry ID', 'Contest Name', 'Contest ID', 'Entry Fee',
             'QB', 'RB', 'RB', 'WR', 'WR', 'WR', 'TE', 'FLEX', 'DST')

#: Declared structural correlation rules. Not simulated -- stated.
MIN_STACK = 1          # a QB must have at least one of his own pass catchers
MAX_STACK = 2          # and at most two, absent a distribution saying more is right
MAX_OVERLAP = 6        # of 9 roster spots, between any two lineups in the portfolio
MAX_PLAYER_EXPOSURE = 0.60
MAX_QB_EXPOSURE = 0.35
SEED = 20260927

STATUS_FULL = 'FULL_PROPRIETARY'
STATUS_HYBRID = 'HYBRID'
STATUS_FALLBACK = 'FALLBACK'

POST = _REPO / 'nfl/dfs/salaries/DK_WEEK3_TODAY_STATE_POST_INACTIVES.json'
OUT_BOARD = _REPO / 'nfl/dfs/salaries/SLATE_STATUS_BOARD.json'
OUT_MD = _REPO / 'nfl/dfs/salaries/SLATE_STATUS_BOARD.md'
OUT_CSV = _REPO / 'nfl/dfs/salaries/DK_UPLOAD_GENERATED.csv'


def _stage(name, outcome, **extra):
    return {'stage': name, 'state': outcome.state.value, 'code': outcome.code,
            'detail': outcome.detail, **extra}


# --- stages ------------------------------------------------------------------
def s1_ingest_slate(entries_csv):
    if not entries_csv.exists():
        return Outcome.fail('SLATE_ENTRY_FILE_ABSENT', f'{entries_csv} not found')
    rows = list(csv.reader(entries_csv.open(newline='', encoding='utf-8-sig')))
    hdr = [c.strip() for c in rows[0]]
    need = ('Entry ID', 'Contest Name', 'Contest ID', 'Entry Fee')
    if any(c not in hdr for c in need):
        return Outcome.fail('SLATE_ENTRY_SCHEMA', f'header lacks one of {need}')
    ei = hdr.index('Entry ID')
    ents = [{'entry_id': r[ei].strip(),
             'contest_name': r[hdr.index('Contest Name')].strip(),
             'contest_id': r[hdr.index('Contest ID')].strip(),
             'entry_fee': r[hdr.index('Entry Fee')].strip()}
            for r in rows[1:] if len(r) > ei and r[ei].strip()]
    if not ents:
        return Outcome.fail('SLATE_NO_ENTRIES', 'no row carries a nonblank Entry ID')
    return Outcome.ok('SLATE_INGESTED', ents, f'{len(ents)} entries',
                      n=len(ents),
                      contests=dict(collections.Counter(e['contest_id'] for e in ents)))


def s2_verify_identity():
    if not POST.exists():
        return Outcome.fail('IDENTITY_STATE_ABSENT', f'{POST.name} not built')
    post = json.loads(POST.read_text())
    players = post['players']
    if len(players) != PRD.EXPECTED_UNIVERSE:
        return Outcome.fail('UNIVERSE_SIZE_MISMATCH',
                            f'{len(players)} rows against an expected '
                            f'{PRD.EXPECTED_UNIVERSE}')
    unmatched = [v['name'] for v in players.values()
                 if v.get('identity') in (None, 'UNMATCHED')]
    return Outcome.ok('IDENTITY_VERIFIED', post,
                      f'{len(players)} rows, {len(unmatched)} unmatched',
                      n=len(players), n_unmatched=len(unmatched))


def s3_availability(post):
    players = post['players']
    c = collections.Counter(v['current_availability']['status'] for v in players.values())
    absent = [k for k, v in players.items()
              if v['current_availability']['status'] in AV.ABSENT_STATUSES]
    clubs = {v['team'] for v in players.values()}
    return Outcome.ok('AVAILABILITY_RESOLVED', {'absent': set(absent), 'counts': dict(c)},
                      f'{len(absent)} reported absent, {len(clubs)} clubs',
                      n_absent=len(absent), n_clubs=len(clubs), counts=dict(c))


def s4_current_role(post):
    players = post['players']
    pred = {k for k, v in players.items()
            if (v.get('predicted_lineup_context') or {})
            .get('in_predicted_starting_group')}
    missing = [k for k, v in players.items() if not v.get('today_expected_role')]
    if missing:
        return Outcome.fail('ROLE_STATE_INCOMPLETE',
                            f'{len(missing)} players carry no role state')
    return Outcome.ok('ROLE_RESOLVED', pred,
                      f'{len(pred)} predicted starters of {len(players)}',
                      n_predicted=len(pred))


def s5_projections(post, absent):
    """Proprietary where available, governed fallback otherwise, UNAVAILABLE never zero."""
    players = post['players']
    fcr = FC.load()
    fb = {}
    if fcr.state is State.PASS:
        joined, _, _ = FC.join_to_dk(fcr.value, players)
        fb = {k: ((v.get(FC.CONTEXT_KEY) or {}).get('FC Proj'))
              for k, v in joined.items()}
    proj, modes = {}, collections.Counter()
    for k, v in players.items():
        if k in absent:
            modes['NOT_PROJECTED_REPORTED_ABSENT'] += 1
            continue
        m = fb.get(k)
        if isinstance(m, (int, float)) and m > 0:
            proj[k] = {'mean': m, 'mode': 'EXTERNAL_FC_FALLBACK',
                       'is_proprietary': False}
            modes['EXTERNAL_FC_FALLBACK'] += 1
        else:
            modes['PROJECTION_UNAVAILABLE'] += 1
    if not proj:
        return Outcome.fail('NO_PROJECTION_OF_ANY_KIND',
                            'neither proprietary nor authorised fallback produced a '
                            'single usable number, so no portfolio can be built')
    n_prop = sum(1 for p in proj.values() if p['is_proprietary'])
    status = (STATUS_FULL if n_prop == len(proj) else
              STATUS_HYBRID if n_prop else STATUS_FALLBACK)
    by_pos = collections.Counter(players[k]['position'] for k in proj)
    cover = {}
    for pos in PRD.REQUIRED_POSITIONS:
        need = sum(1 for v in players.values() if v['position'] == pos)
        cover[pos] = {'rosterable': need, 'projected': by_pos[pos],
                      'pct': round(100 * by_pos[pos] / need, 1) if need else None}
    return Outcome.ok('PROJECTIONS_READY',
                      {'proj': proj, 'status': status, 'coverage': cover},
                      f'{len(proj)} usable, status {status}',
                      modes=dict(modes), status=status, coverage=cover,
                      n_proprietary=n_prop)


def _pools(players, proj):
    by_pos = collections.defaultdict(list)
    for k, p in proj.items():
        v = players[k]
        by_pos[v['position']].append(
            {'dk_id': k, 'name': v['name'], 'pos': v['position'], 'team': v['team'],
             'opp': v['opponent'], 'salary': v['salary'], 'mean': p['mean'],
             'value': p['mean'] / (v['salary'] / 1000.0) if v['salary'] else 0.0})
    for pos in by_pos:
        by_pos[pos].sort(key=lambda r: -r['mean'])
    return by_pos


def s6_candidates(players, proj, n_target=4000):
    """Structurally correlated candidates. Structure is declared, not simulated."""
    rng = random.Random(SEED)
    pool = _pools(players, proj)
    qbs = [q for q in pool['QB'] if q['mean'] >= 8.0]
    if not qbs or not pool['DST']:
        return Outcome.fail('CANDIDATE_POOL_EMPTY',
                            f'{len(qbs)} usable QBs and {len(pool["DST"])} DSTs')
    cands, seen = [], set()
    tries = 0
    while len(cands) < n_target and tries < n_target * 60:
        tries += 1
        qb = rng.choice(qbs)
        mates = [r for r in pool['WR'] + pool['TE'] if r['team'] == qb['team']]
        if len(mates) < MIN_STACK:
            continue
        k = rng.randint(MIN_STACK, min(MAX_STACK, len(mates)))
        stack = rng.sample(mates, k)
        # optional bring-back from the opposing club, any position
        opp = [r for r in pool['WR'] + pool['TE'] + pool['RB'] if r['team'] == qb['opp']]
        bring = [rng.choice(opp)] if (opp and rng.random() < 0.65) else []
        picked = [qb] + stack + bring
        used = {r['dk_id'] for r in picked}
        # a DST that opposes our own QB is a contradictory scoring story
        dsts = [d for d in pool['DST'] if d['team'] != qb['opp']]
        if not dsts:
            continue
        dst = rng.choice(dsts)
        picked.append(dst)
        used.add(dst['dk_id'])
        need = collections.Counter(SLOTS)
        have = collections.Counter(r['pos'] for r in picked if r['pos'] != 'DST')
        # fill remaining slots cheapest-first among value leaders, randomised
        order = ['RB', 'RB', 'WR', 'WR', 'WR', 'TE']
        for pos in order:
            if have[pos] >= need[pos]:
                continue
            opts = [r for r in pool[pos] if r['dk_id'] not in used][:28]
            if not opts:
                break
            r = rng.choice(opts)
            picked.append(r)
            used.add(r['dk_id'])
            have[pos] += 1
        # FLEX
        flex_opts = [r for r in pool['RB'] + pool['WR'] + pool['TE']
                     if r['dk_id'] not in used][:40]
        if not flex_opts:
            continue
        picked.append(rng.choice(flex_opts))
        if len(picked) != 9:
            continue
        sal = sum(r['salary'] for r in picked)
        if sal > SALARY_CAP or sal < SALARY_CAP - 3500:
            continue
        key = tuple(sorted(r['dk_id'] for r in picked))
        if key in seen:
            continue
        seen.add(key)
        cands.append({
            'players': picked, 'salary': sal,
            'proj_total': round(sum(r['mean'] for r in picked), 2),
            'qb': qb['name'], 'qb_club': qb['team'], 'qb_opp': qb['opp'],
            'stack': [r['name'] for r in stack],
            'stack_size': len(stack),
            'bring_back': [r['name'] for r in bring] or None,
            'dst': dst['team'],
            'ids': key,
        })
    if len(cands) < 200:
        return Outcome.fail('CANDIDATE_POOL_TOO_SMALL',
                            f'{len(cands)} candidates after {tries} attempts')
    cands.sort(key=lambda c: -c['proj_total'])
    return Outcome.ok('CANDIDATES_GENERATED', cands, f'{len(cands)} candidates',
                      n=len(cands), attempts=tries)


def s7_select(cands, n_entries):
    """Joint selection with declared overlap and exposure caps."""
    chosen, exp, qb_exp = [], collections.Counter(), collections.Counter()
    max_p = max(1, int(MAX_PLAYER_EXPOSURE * n_entries))
    max_q = max(1, int(MAX_QB_EXPOSURE * n_entries))
    for c in cands:
        if len(chosen) >= n_entries:
            break
        if qb_exp[c['qb']] >= max_q:
            continue
        if any(exp[i] >= max_p for i in c['ids']):
            continue
        if any(len(set(c['ids']) & set(o['ids'])) > MAX_OVERLAP for o in chosen):
            continue
        chosen.append(c)
        qb_exp[c['qb']] += 1
        for i in c['ids']:
            exp[i] += 1
    if len(chosen) < n_entries:
        return Outcome.fail(
            'PORTFOLIO_UNDERFILLED',
            f'{len(chosen)} of {n_entries} lineups satisfy the declared caps '
            f'(overlap<={MAX_OVERLAP}, player<={MAX_PLAYER_EXPOSURE:.0%}, '
            f'QB<={MAX_QB_EXPOSURE:.0%}). Loosen a cap deliberately or widen the pool; '
            f'do not silently fill with duplicates.',
            n_selected=len(chosen), n_required=n_entries)
    return Outcome.ok('PORTFOLIO_SELECTED', chosen, f'{len(chosen)} lineups',
                      n=len(chosen))


def s8_validate(chosen, players, absent, entries):
    fails = []
    for i, c in enumerate(chosen):
        ids = [r['dk_id'] for r in c['players']]
        if len(set(ids)) != 9:
            fails.append({'lineup': i, 'code': 'PLAYER_DUPLICATED_IN_LINEUP'})
        if c['salary'] > SALARY_CAP:
            fails.append({'lineup': i, 'code': 'SALARY_OVER_CAP', 'detail': c['salary']})
        bad = [players[x]['name'] for x in ids if x in absent]
        if bad:
            fails.append({'lineup': i, 'code': 'REPORTED_INACTIVE_PLAYER_IN_LINEUP',
                          'detail': bad})
        if any(x not in players for x in ids):
            fails.append({'lineup': i, 'code': 'DK_ID_NOT_IN_UNIVERSE'})
        counts = collections.Counter(players[x]['position'] for x in ids if x in players)
        if counts['QB'] != 1 or counts['DST'] != 1:
            fails.append({'lineup': i, 'code': 'SLOT_STRUCTURE_ILLEGAL',
                          'detail': dict(counts)})
    if len(chosen) != len(entries):
        fails.append({'code': 'ENTRY_COUNT_MISMATCH',
                      'detail': f'{len(chosen)} lineups for {len(entries)} entries'})
    if fails:
        return Outcome.fail('PORTFOLIO_ILLEGAL', f'{len(fails)} legality failure(s)',
                            failures=fails[:20], n=len(fails))
    return Outcome.ok('PORTFOLIO_LEGAL', len(chosen),
                      f'{len(chosen)} lineups, every check clean')


def s9_emit_csv(chosen, entries, players, out=OUT_CSV):
    rows = [list(DK_HEADER)]
    for e, c in zip(entries, chosen):
        by_pos = collections.defaultdict(list)
        for r in c['players']:
            by_pos[r['pos']].append(r)
        cells, used = [], set()
        for slot in SLOTS:
            if slot == 'FLEX':
                pick = next((r for p in ('RB', 'WR', 'TE') for r in by_pos[p]
                             if r['dk_id'] not in used), None)
            else:
                pick = next((r for r in by_pos[slot] if r['dk_id'] not in used), None)
            if pick is None:
                return Outcome.fail('CSV_BLANK_CELL',
                                    f'entry {e["entry_id"]} slot {slot} unfilled')
            used.add(pick['dk_id'])
            cells.append(f'{pick["name"]} ({pick["dk_id"]})')
        rows.append([e['entry_id'], e['contest_name'], e['contest_id'], e['entry_fee']]
                    + cells)
    with out.open('w', newline='', encoding='utf-8') as fh:
        csv.writer(fh).writerows(rows)
    return Outcome.ok('CSV_WRITTEN', str(out.relative_to(_REPO)),
                      f'{len(rows) - 1} entry rows',
                      sha256=hashlib.sha256(out.read_bytes()).hexdigest())


# --- the run -----------------------------------------------------------------
def run(entries_csv):
    board = {'artifact': 'SLATE_STATUS_BOARD', 'spec_version': SPEC_VERSION,
             'generated_at_utc': dt.datetime.now(dt.UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
             'entry_file': str(entries_csv), 'stages': [], 'slate_status': None,
             'CORRELATION_BASIS': (
                 'CORRELATION_HEURISTIC_NOT_SIMULATION. Structure comes from declared '
                 'rules -- a quarterback with 1-2 of his own pass catchers, an optional '
                 'opposing bring-back, never a team defence against our own quarterback. '
                 'It does NOT come from simulated football, so ceiling, duplication and '
                 'expected payout are UNKNOWN rather than estimated.'),
             'unknown_by_design': ['lineup_ceiling', 'duplication_probability',
                                   'expected_payout', 'first_place_probability',
                                   'projected_ownership']}

    r1 = s1_ingest_slate(entries_csv)
    board['stages'].append(_stage('ingest_slate', r1, evidence=dict(r1.evidence)))
    if r1.state is not State.PASS:
        return _finish(board)
    entries = r1.value

    r2 = s2_verify_identity()
    board['stages'].append(_stage('verify_identity', r2, evidence=dict(r2.evidence)))
    if r2.state is not State.PASS:
        return _finish(board)
    post = r2.value

    r3 = s3_availability(post)
    board['stages'].append(_stage('availability', r3, evidence=dict(r3.evidence)))
    absent = r3.value['absent'] if r3.state is State.PASS else set()

    r4 = s4_current_role(post)
    board['stages'].append(_stage('current_role', r4, evidence=dict(r4.evidence)))

    r5 = s5_projections(post, absent)
    board['stages'].append(_stage('projections', r5, evidence=dict(r5.evidence)))
    if r5.state is not State.PASS:
        return _finish(board)
    proj = r5.value['proj']
    board['slate_status'] = r5.value['status']
    board['projection_coverage'] = r5.value['coverage']

    r6 = s6_candidates(post['players'], proj)
    board['stages'].append(_stage('candidate_generation', r6,
                                  evidence=dict(r6.evidence)))
    if r6.state is not State.PASS:
        return _finish(board)

    r7 = s7_select(r6.value, len(entries))
    board['stages'].append(_stage('portfolio_selection', r7, evidence=dict(r7.evidence)))
    if r7.state is not State.PASS:
        return _finish(board)
    chosen = r7.value

    r8 = s8_validate(chosen, post['players'], absent, entries)
    board['stages'].append(_stage('legality_validation', r8, evidence=dict(r8.evidence)))
    if r8.state is not State.PASS:
        return _finish(board)

    r9 = s9_emit_csv(chosen, entries, post['players'])
    board['stages'].append(_stage('dk_upload_csv', r9, evidence=dict(r9.evidence)))

    board['portfolio'] = _summarise(chosen, post['players'])
    return _finish(board)


def _summarise(chosen, players):
    exp = collections.Counter()
    qb = collections.Counter()
    dst = collections.Counter()
    for c in chosen:
        for r in c['players']:
            exp[r['name']] += 1
        qb[c['qb']] += 1
        dst[c['dst']] += 1
    ov = [len(set(a['ids']) & set(b['ids']))
          for a, b in itertools.combinations(chosen, 2)]
    return {
        'n_lineups': len(chosen),
        'salary': {'min': min(c['salary'] for c in chosen),
                   'max': max(c['salary'] for c in chosen)},
        'proj_total': {'min': min(c['proj_total'] for c in chosen),
                       'max': max(c['proj_total'] for c in chosen)},
        'top_player_exposure': {k: f'{100 * v / len(chosen):.1f}%'
                                for k, v in exp.most_common(10)},
        'qb_exposure': {k: f'{100 * v / len(chosen):.1f}%' for k, v in qb.most_common()},
        'dst_exposure': {k: f'{100 * v / len(chosen):.1f}%' for k, v in dst.most_common()},
        'stack_sizes': dict(collections.Counter(c['stack_size'] for c in chosen)),
        'bring_back_rate': f'{100 * sum(1 for c in chosen if c["bring_back"]) / len(chosen):.1f}%',
        'max_pairwise_overlap': max(ov) if ov else None,
        'mean_pairwise_overlap': round(sum(ov) / len(ov), 2) if ov else None,
        'lineups': [{'qb': c['qb'], 'stack': c['stack'], 'bring_back': c['bring_back'],
                     'dst': c['dst'], 'salary': c['salary'],
                     'proj_total': c['proj_total'],
                     'players': [r['name'] for r in c['players']]} for c in chosen],
    }


def _finish(board):
    reached = [s['stage'] for s in board['stages'] if s['state'] == 'PASS']
    stopped = next((s for s in board['stages'] if s['state'] != 'PASS'), None)
    board['stages_passed'] = reached
    board['stopped_at'] = stopped['stage'] if stopped else None
    board['stopped_code'] = stopped['code'] if stopped else None
    board['product_delivered'] = any(s['stage'] == 'dk_upload_csv'
                                     and s['state'] == 'PASS'
                                     for s in board['stages'])
    board['SATURDAY_RULE'] = (
        'If the system cannot autonomously produce a complete legal lineup portfolio from '
        'a slate file by Saturday, it is not production-ready for Sunday. '
        + ('This run DID produce one.' if board['product_delivered']
           else f'This run did NOT: stopped at {board["stopped_at"]} '
                f'({board["stopped_code"]}).'))
    OUT_BOARD.write_text(json.dumps(board, indent=2, default=str) + '\n')
    OUT_MD.write_text(_render(board))
    return board


def _render(b):
    L = ['# Slate status board', '',
         f'**SLATE STATUS: {b.get("slate_status") or "NOT_REACHED"}**  ',
         f'Generated {b["generated_at_utc"]} · entry file `{b["entry_file"]}`', '']
    cov = b.get('projection_coverage') or {}
    if cov:
        L += ['## Projection coverage', '', '| pos | rosterable | projected | % |',
              '|---|--:|--:|--:|']
        for p, c in cov.items():
            L.append(f'| {p} | {c["rosterable"]} | {c["projected"]} | {c["pct"]}% |')
        L.append('')
    L += ['## Pipeline', '', '| stage | state | code |', '|---|---|---|']
    for s in b['stages']:
        L.append(f'| {s["stage"]} | **{s["state"]}** | `{s["code"]}` |')
    p = b.get('portfolio')
    L += ['', '## Portfolio', '']
    if p:
        L += [f'**{p["n_lineups"]} legal lineups.** salary '
              f'{p["salary"]["min"]}–{p["salary"]["max"]}, projected total '
              f'{p["proj_total"]["min"]}–{p["proj_total"]["max"]}, max pairwise overlap '
              f'{p["max_pairwise_overlap"]}/9 (mean {p["mean_pairwise_overlap"]}), '
              f'bring-back rate {p["bring_back_rate"]}.', '',
              f'QB exposure: {p["qb_exposure"]}', '',
              f'Stack sizes: {p["stack_sizes"]}', '']
    else:
        L += [f'NOT PRODUCED. Stopped at `{b["stopped_at"]}` with '
              f'`{b["stopped_code"]}`.', '']
    L += ['## Honesty', '', b['CORRELATION_BASIS'], '',
          f'UNKNOWN by design: {", ".join(b["unknown_by_design"])}', '',
          '## Saturday rule', '', b['SATURDAY_RULE'], '']
    return '\n'.join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--entries', default=str(
        _REPO / 'nfl/dfs/salaries/raw/DKEntries_EARLY_ONLY_2026W3_62.csv'))
    a = ap.parse_args()
    b = run(pathlib.Path(a.entries))
    print(f'SLATE STATUS: {b.get("slate_status") or "NOT_REACHED"}')
    for s in b['stages']:
        mark = ' ' if s['state'] == 'PASS' else 'X'
        print(f' {mark} {s["state"]:6s} {s["stage"]:22s} {s["code"]}')
    print(f'\nproduct delivered: {b["product_delivered"]}')
    if b.get('portfolio'):
        p = b['portfolio']
        print(f'  {p["n_lineups"]} lineups, salary {p["salary"]}, '
              f'proj {p["proj_total"]}, max overlap {p["max_pairwise_overlap"]}/9')
        print(f'  QB exposure: {p["qb_exposure"]}')
        print(f'  stacks: {p["stack_sizes"]}  bring-back {p["bring_back_rate"]}')
    print(f'\n{b["SATURDAY_RULE"]}')
    return 0 if b['product_delivered'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
