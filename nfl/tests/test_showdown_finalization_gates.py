#!/usr/bin/env python3.12
"""Owner finalization gates 2026-10-05: DK input gate, relaxation ladder, upload verifier."""
import collections
import csv
import pathlib
import sys
import tempfile

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO))

from nfl.tools import showdown_portfolio as SP  # noqa: E402

EXPORT = _REPO / 'nfl/dfs/salaries/raw/DKEntries_PIT_CLE_SHOWDOWN_2026W4.csv'
P = F = 0


def check(ok, what):
    global P, F
    P, F = P + bool(ok), F + (not ok)
    print(f"  {'ok  ' if ok else 'FAIL'} {what}")


def test_dk_input_gate():
    o = SP.dk_input_gate(EXPORT)
    v = o.value or o.evidence
    check(o.state.value == 'PASS', f'the real PIT@CLE export passes ({o.code})')
    check(v['dk_player_rows'] == 2 * v['football_players'], f"{v['dk_player_rows']} DK rows = 2 x {v['football_players']} people")
    check(sum(c['entries'] for c in v['contests'].values()) == v['n_entries'], 'entry counts by contest sum to the total')
    rows = list(csv.reader(open(EXPORT, newline='', encoding='utf-8-sig')))
    for i, r in enumerate(rows):
        if 'Roster Position' in r and 'Salary' in r:
            ph = {h: j for j, h in enumerate(r)}
            for q in rows[i + 1:]:
                if len(q) > ph['Salary'] and q[ph['Roster Position']] == 'CPT':
                    q[ph['Salary']] = str(int(q[ph['Salary']]) + 100)
                    break
            break
    with tempfile.TemporaryDirectory() as d:
        bad = pathlib.Path(d) / 'bad.csv'
        csv.writer(open(bad, 'w', newline='')).writerows(rows)
        o2 = SP.dk_input_gate(bad)
    check(o2.state.value == 'FAIL' and 'CPT_NOT_1_5X' in o2.detail, 'a CPT salary off 1.5x is refused by name')


def test_ladder_fills_or_blocks():
    # 6 people A..F plus G; candidates all share A, so level 0 (player cap 50%) cannot fill 4 entries
    people = list('ABCDEFG')
    seats = [['A'] + [p for p in people[1:] if p != x] for x in people[1:]]
    seats = [s[:6] for s in seats]
    n_w = 50
    rng = np.random.default_rng(1)
    hit = rng.random((len(seats), n_w)) < 0.3
    cr = [{'first_place_proxy': float(h.mean()), 'structural_duplication_index': 0} for h in hit]
    P0 = SP.select(hit, cr, seats, 4, n_w, SP.LADDER[0])
    check(P0['short'] > 0, f'level 0 is short ({len(P0["chosen"])}/4) when every candidate shares one person')
    Pl, log = SP.ladder(hit, cr, seats, 4, n_w)
    check(len(log) >= 2 and all(e['built'] <= e['needed'] for e in log), f'each rung is logged ({len(log)} rungs)')
    check(Pl['short'] == 0 or Pl['relaxation_level'] == SP.LADDER[-1]['level'],
          f"ladder ends filled or at the last rung (level {Pl['relaxation_level']}, short {Pl['short']})")
    Pn, _ = SP.ladder(hit[:1], cr[:1], seats[:1], 3, n_w)
    check(Pn['short'] == 2, 'one candidate cannot fill three entries at any rung: short stays visible (-> FINALIZATION_BLOCKED)')


def test_verifier_catches_tampering():
    rows = list(csv.reader(open(EXPORT, newline='', encoding='utf-8-sig')))
    hdr = rows[0]
    entries = [r for r in rows[1:] if r and r[0].strip().isdigit()]
    for i, r in enumerate(rows):
        if 'Roster Position' in r and 'Salary' in r:
            ph = {h: j for j, h in enumerate(r)}
            pool = [q for q in rows[i + 1:] if len(q) > ph['Salary'] and q[ph['ID']].strip()]
            break
    cpt = [q for q in pool if q[ph['Roster Position']] == 'CPT']
    flex = [q for q in pool if q[ph['Roster Position']] == 'FLEX']
    with tempfile.TemporaryDirectory() as d:
        up = pathlib.Path(d) / 'up.csv'
        c = min(cpt, key=lambda q: int(q[ph['Salary']]))
        fl = [q for q in sorted(flex, key=lambda q: int(q[ph['Salary']])) if q[ph['Name']] != c[ph['Name']]][:5]
        if len({q[ph['TeamAbbrev']] for q in fl + [c]}) < 2:
            fl[-1] = next(q for q in flex if q[ph['TeamAbbrev']] != c[ph['TeamAbbrev']] and q[ph['Name']] != c[ph['Name']])
        e = entries[0]
        good = [e[0], e[1], e[2], e[3], c[ph['ID']]] + [q[ph['ID']] for q in fl]
        csv.writer(open(up, 'w', newline='')).writerows([hdr[:4] + ['CPT'] + ['FLEX'] * 5, good])
        v = SP.verify_upload(up, EXPORT)
        check(v.state.value == 'PASS', f'a legal cheap lineup verifies ({v.code} {(v.evidence or {}).get("violations")})')
        dup = good[:5] + [good[5]] * 5
        csv.writer(open(up, 'w', newline='')).writerows([hdr[:4] + ['CPT'] + ['FLEX'] * 5, dup])
        check(SP.verify_upload(up, EXPORT).state.value == 'FAIL', 'a repeated person is caught')
        swap = [e[0], e[1], e[2], e[3], fl[0][ph['ID']], c[ph['ID']]] + [q[ph['ID']] for q in fl[1:]]
        csv.writer(open(up, 'w', newline='')).writerows([hdr[:4] + ['CPT'] + ['FLEX'] * 5, swap])
        check(SP.verify_upload(up, EXPORT).state.value == 'FAIL', 'a FLEX id in the CPT slot is caught')
        wrong = ['999'] + good[1:]
        csv.writer(open(up, 'w', newline='')).writerows([hdr[:4] + ['CPT'] + ['FLEX'] * 5, wrong])
        check(SP.verify_upload(up, EXPORT).state.value == 'FAIL', 'an entry id not in the export is caught')


def test_swap_polish():
    # textbook greedy trap: G covers 7 of 12 worlds; A and B cover 6 each, disjoint, together all 12.
    n_w = 12
    G = [0, 1, 2, 6, 7, 8, 9]
    A, B = list(range(6)), list(range(6, 12))
    hit = np.zeros((3, n_w), dtype=bool)
    for r, ws in enumerate((G, A, B)):
        hit[r, ws] = True
    seats = [list('ABCDEF'), list('GHIJKL'), list('MNOPQR')]
    cr = [{'first_place_proxy': float(h.mean()), 'structural_duplication_index': 0} for h in hit]
    P, _ = SP.ladder(hit, cr, seats, 2, n_w)
    check(sorted(P['chosen']) == [0, 1] and abs(P['coverage'] - 10 / 12) < 1e-9, 'greedy takes the trap (10/12)')
    Q = SP.swap_polish(hit, seats, P, 2, n_w)
    check(sorted(Q['chosen']) == [1, 2] and Q['coverage'] == 1.0, f"polish escapes it (12/12, chose {sorted(Q['chosen'])})")
    check(Q['greedy']['chosen'] == P['chosen'] and Q['polish']['lineups_changed'] == 1, 'the greedy result is kept beside it')
    # random pools: the polish never lowers the objective and never breaks a cap, the overlap rule or distinctness
    rng = np.random.default_rng(3)
    people = [f'p{i}' for i in range(14)]
    for trial in range(6):
        seats = [list(rng.choice(people, 6, replace=False)) for _ in range(80)]
        hit = rng.random((80, 60)) < 0.12
        cr = [{'first_place_proxy': float(h.mean()), 'structural_duplication_index': 0} for h in hit]
        P, _ = SP.ladder(hit, cr, seats, 8, 60)
        if P['short']:
            continue
        Q = SP.swap_polish(hit, seats, P, 8, 60)
        rung = SP.LADDER[Q['relaxation_level']]
        exp = collections.Counter(k for i in Q['chosen'] for k in seats[i])
        cexp = collections.Counter(seats[i][0] for i in Q['chosen'])
        ok = (Q['objective']['value'] >= P['objective']['value'] - 1e-12 and len(set(Q['chosen'])) == 8
              and max(exp.values()) <= Q['caps']['player'] and max(cexp.values()) <= Q['caps']['captain']
              and all(len(set(seats[i]) & set(seats[j])) <= rung['overlap'] for i in Q['chosen'] for j in Q['chosen'] if i != j))
        check(ok, f"trial {trial}: objective {P['objective']['value']:.4f} -> {Q['objective']['value']:.4f}, caps/overlap held")


for t in (test_dk_input_gate, test_ladder_fills_or_blocks, test_verifier_catches_tampering, test_swap_polish):
    print('##', t.__name__)
    t()
print(f'\nPASSED {P} FAILED {F}')
sys.exit(1 if F else 0)
