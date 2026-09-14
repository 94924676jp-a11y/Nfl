"""WS-A research harness: the appearance V1-presence leak, four bases, five arms.

RESEARCH ONLY. Nothing here is imported by production. Every production module
is imported read-only; `appearance_r8.featurise` is CALLED, never restated, and
the one place this file builds a feature tail of its own asserts against R8's
own output first (`_assert_tail_split`).

Preregistration: nfl/research/remediation/ws_a/PREREG_appearance_leak.md
sha256 b14738a0a4a262cccba416b6d76e3b80db4340b46f1ab144d0546bfe8f368dda
"""
from __future__ import annotations

import collections
import pathlib
import sys
import time

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[4]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p1'),
           str(_REPO / 'nfl' / 'research' / 'p2'),
           str(_REPO / 'nfl' / 'research' / 'p3')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import State          # noqa: E402
from nfl.production.nonqb import appearance_model as AM      # noqa: E402
from nfl.production.nonqb import appearance_r7 as R7         # noqa: E402
from nfl.production.nonqb import appearance_r8 as R8         # noqa: E402

SPEC_VERSION = 'ws-a-appearance-leak-1'
PREREG_SHA256 = 'b14738a0a4a262cccba416b6d76e3b80db4340b46f1ab144d0546bfe8f368dda'
EVAL_SEASONS = (2022, 2023, 2024, 2025)
L2 = 1.0
BOOT = 1000
SEED = 20260914

V1_KEYS = R8.V1_NUMERIC + ('f_weeks_since_appear', 'f_n_teammates_out',
                           'f_practice_seq', 'f_practice_improving',
                           'f_practice_worsening')
# 12 value/flag pairs + weeks_since + n_teammates_out + improving + worsening
# + the `v1 is None` column.
V1_TAIL_LEN = 2 * len(R8.V1_NUMERIC) + 5

# Refused inputs, by name, checked against the feature-name list this harness
# builds. Same list nfl/research/q6/frame.py already uses.
FORBIDDEN_INPUTS = ('weekly_rosters.status', 'roster_status', 'status_ina',
                    'inactive_list', 'spread', 'vegas', 'total_line', 'odds',
                    'final_', 'realized_', 'postgame', 'price', 'book')

_S = {}


class HarnessError(RuntimeError):
    """A named failure. Zeros and empties are errors, not results."""


def _key(s, w, t, pid):
    return (int(s), int(w), t, pid)


# ------------------------------------------------------------------ loading
def load():
    if _S:
        return _S
    t0 = time.time()
    fr = R8.enriched_frame()
    if fr.state is not State.PASS:
        raise HarnessError(f'WS_A_FRAME_UNAVAILABLE {fr.code}')
    urows = fr.value
    if not urows:
        raise HarnessError('WS_A_FRAME_EMPTY')
    st = AM.stage_inputs()
    if st.state is not State.PASS:
        raise HarnessError(f'WS_A_INPUTS_UNAVAILABLE {st.code}')
    M, A, F = AM._frozen()
    kick = A.kickoffs()
    inj, _ = A.injuries(kick)
    dep = A.depth()
    panel = A.build(kick, inj, dep)
    if not panel:
        raise HarnessError('WS_A_PANEL_EMPTY')
    cols = AM._panel_columns()
    in_panel = {_key(r['season'], r['week'], r['team'], r['gsis_id'])
                for r in panel}
    _S.update({'urows': urows, 'panel': panel, 'cols': cols, 'M': M, 'A': A,
               'F': F, 'inj': inj, 'dep': dep, 'kick': kick,
               'in_panel': in_panel, 'frame_evidence': fr.evidence,
               'load_seconds': round(time.time() - t0, 1)})
    return _S


# --------------------------------------------------- panel-shaped zero rows
def synth_row(s, w, t, pid, pos, cols, dna):
    """A zero-opportunity panel-shaped row, exactly as production builds one.

    `appearance_model.prospective_rows` zeroes every integer column and keeps
    only the identity fields and a game_id, so team_* carry zero here too. No
    target-week feature reads a target-week team total -- `f_vac_*` reads the
    PREVIOUS team-week -- so this is the same row production would build.

    `dna` is `None` when the row stands for a game not yet played, which is
    what production has at serve, and 1 for a historical row whose player is
    known not to have appeared.
    """
    z = {c: 0 for c in cols}
    z.update({'season': int(s), 'week': int(w), 'team': t, 'gsis_id': pid,
              'position': pos, 'player_name': pid,
              'game_id': f'{int(s)}_{int(w):02d}_{t}',
              'offense_pct': (0.0 if dna == 1 else None),
              'did_not_appear': dna, 'ord': int(s) * 100 + int(w)})
    return z


def _walk_and_enrich(rows):
    S = load()
    A, M, F, inj, dep = S['A'], S['M'], S['F'], S['inj'], S['dep']
    walked = AM._walk(A, M, rows, inj, dep)
    F.enrich(walked, inj)
    return walked


def _block(r):
    return {k: r.get(k) for k in V1_KEYS}


# ------------------------------------------------------------- the S-serve basis
def serve_blocks(season, week, flip_labels=False):
    """Production's serve basis, replayed on a historical week.

    Panel truncated to `ord < season*100+week`, then one zero-opportunity row
    per union candidate at that week, exactly as `_prospective` appends
    prospective rows to the historical panel. No row at or after the target
    week enters any player's history.

    `flip_labels` is the S2 structural test: it sets the target-week rows'
    `did_not_appear` to their realised value instead of None. If any target-week
    feature moves, a target-week label is reaching a target-week feature.
    """
    S = load()
    o = int(season) * 100 + int(week)
    base = [dict(r) for r in S['panel'] if r['ord'] < o]
    tw = [r for r in S['urows'] if r['s'] * 100 + r['w'] == o]
    if not tw:
        raise HarnessError(f'WS_A_NO_UNION_ROWS {season} week {week}')
    syn = [synth_row(r['s'], r['w'], r['t'], r['pid'], r['pos'], S['cols'],
                     (1 - int(r['appeared'])) if flip_labels else None)
           for r in tw]
    walked = _walk_and_enrich(base + syn)
    out = {}
    for r in walked:
        if r['ord'] == o:
            out[_key(r['season'], r['week'], r['team'], r['gsis_id'])] = _block(r)
    if len(out) != len(tw):
        raise HarnessError(
            f'WS_A_SERVE_BLOCK_COUNT {len(out)} != {len(tw)} for {season}w{week}')
    return out


# ------------------------------------------------------------ the U-union basis
def union_blocks():
    """The V1 block recomputed over the union candidate universe.

    The panel extended with a zero-opportunity row for every union candidate
    the panel lacks, walked once. Every union frame row then carries a block,
    so block presence is a constant rather than a function of the label.
    """
    S = load()
    missing = [r for r in S['urows']
               if _key(r['s'], r['w'], r['t'], r['pid']) not in S['in_panel']]
    bad = [r for r in missing if r['appeared']]
    if bad:
        raise HarnessError(f'WS_A_UNION_APPEARER_OFF_PANEL n={len(bad)}')
    syn = [synth_row(r['s'], r['w'], r['t'], r['pid'], r['pos'], S['cols'], 1)
           for r in missing]
    walked = _walk_and_enrich([dict(r) for r in S['panel']] + syn)
    out = {}
    for r in walked:
        out[_key(r['season'], r['week'], r['team'], r['gsis_id'])] = _block(r)
    hit = sum(1 for r in S['urows']
              if _key(r['s'], r['w'], r['t'], r['pid']) in out)
    if hit != len(S['urows']):
        raise HarnessError(f'WS_A_UNION_BLOCK_COVERAGE {hit}/{len(S["urows"])}')
    return out, len(missing)


# ---------------------------------------------------------------- featurisers
def _assert_tail_split():
    """The last V1_TAIL_LEN columns of R8.featurise are the whole V1 block.

    Verified against R8's own output rather than asserted: a row featurised
    with and without a block must differ ONLY in that tail.
    """
    r0 = {'w': 5, 'pos': 'WR', 'rank': 2, 'n_cur': 3, 'v1': None}
    r1 = dict(r0)
    r1['v1'] = {k: (0.5 if k in R8.V1_NUMERIC else 2) for k in V1_KEYS}
    a, b = R8.featurise(r0, 1.2), R8.featurise(r1, 1.2)
    n = len(a) - V1_TAIL_LEN
    if a[:n] != b[:n]:
        raise HarnessError('WS_A_TAIL_SPLIT_WRONG head moved with the block')
    if a[n:] == b[n:]:
        raise HarnessError('WS_A_TAIL_SPLIT_WRONG tail did not move')
    return n


HEAD_LEN = _assert_tail_split()


def head(r, k):
    f = R8.featurise(r, k)
    return f[:HEAD_LEN]


def tail_present(blk):
    """R8's V1 tail for a row that HAS the block, minus the presence column."""
    f = []
    for key in R8.V1_NUMERIC:
        v = blk.get(key)
        f.append(0.0 if v is None else float(v))
        f.append(1.0 if v is None else 0.0)
    v = blk.get('f_weeks_since_appear')
    f.append(min(v or 9, 9) / 9.0)
    f.append(min(float(blk.get('f_n_teammates_out') or 0.0), 3.0) / 3.0)
    f.append(float(blk.get('f_practice_improving') or 0.0))
    f.append(float(blk.get('f_practice_worsening') or 0.0))
    return f


TAIL_NAMES = ([x for key in R8.V1_NUMERIC
               for x in (f'v1_{key}', f'v1_{key}_is_missing')]
              + ['v1_f_weeks_since_appear', 'v1_f_n_teammates_out',
                 'v1_f_practice_improving', 'v1_f_practice_worsening'])


def featurise_base(r, k, _means=None):
    return R8.featurise(r, k)


def featurise_a(r, k, means):
    f = head(r, k)
    blk = r.get('v1')
    if blk is None:
        f.extend(means)
    else:
        f.extend(tail_present(blk))
    return f


def featurise_b(r, k, _means=None):
    blk = r.get('v1')
    if blk is None:
        raise HarnessError('WS_A_B_BLOCK_ABSENT a union-basis row has no block')
    return head(r, k) + tail_present(blk)


def featurise_a0(r, k, _means=None):
    return head(r, k)


def a_means(train_rows):
    """Candidate A's imputation constants: the mean of each transformed V1
    column over the TRAINING rows that carry the block. Estimated at every
    walk-forward cut from strictly earlier seasons; never chosen."""
    acc = None
    n = 0
    for r in train_rows:
        blk = r.get('v1')
        if blk is None:
            continue
        v = tail_present(blk)
        acc = np.array(v, float) if acc is None else acc + np.asarray(v, float)
        n += 1
    if not n:
        raise HarnessError('WS_A_A_MEANS_EMPTY no training row carries a block')
    return list(acc / n)
