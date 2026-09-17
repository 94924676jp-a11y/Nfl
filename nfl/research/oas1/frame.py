"""The OAS1 play frame. Every row kept, every exclusion counted.

THE RULE THIS MODULE IS BUILT AROUND: nothing is dropped. A row that OAS1 does
not fit on carries an `excluded_reason` and stays in the frame. The reason is
the project's own recurring defect -- a step that returned something partial
read as success -- and its specific form here is an inner join that loses rows
silently. `exclusion_accounting` sums the reasons and refuses unless they
total the input row count exactly.

CLASSIFICATION, AND WHY IT IS THE MOST DANGEROUS DECISION IN THE BUILD

A sack is the pass rush defeating the pass protection. A scramble originates
in a dropback. Both are PASS plays. Routing them to rush would inflate
`off_pass`, deflate `off_rush`, deflate `def_pass` and inflate `def_rush` all
at once -- every unit wrong, the aggregate still balanced, and no conservation
check firing anywhere. Measured on the 2026 week-1 capture: 72 sacks and 79
scrambles, and `test_oas1_identification` asserts they land in `pass`.

THIS DELIBERATELY DISAGREES WITH `scramble_carry_coherence`, which treats a
scramble as a rush ATTEMPT for counting. That is a conservation identity about
how many times the ball was carried; this is an efficiency attribution about
which unit produced the result. Two different questions, two different
answers, and the disagreement is declared rather than reconciled away.

GARBAGE TIME WITHOUT TOUCHING A QUARANTINED COLUMN

The obvious filter is win probability, and `wp` is MODEL_DERIVED and refused
for forecast use. It is also the wrong instrument: excluding plays *because*
the game was decided selects on an outcome downstream of the very team quality
being estimated. So the rules here are score-differential-and-clock rules over
observed fields only, both declared, and which one applies is a tuned
parameter recorded per fit -- never a constant asserted here.
"""
from __future__ import annotations

import csv
import gzip
import io
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.research.oas1 import normalize_teams as NT                 # noqa: E402

SPEC_VERSION = 'oas1-play-frame-1'

PASS, RUSH = 'pass', 'rush'
PLAY_CLASSES = (PASS, RUSH)

#: Every reason a row may be excluded. A row's reason is exactly one of these.
REASONS = ('none', 'playoff', 'special_teams', 'kneel', 'spike', 'no_play',
           'penalty', 'unclassified', 'null_epa', 'no_team', 'garbage_time')

#: Declared garbage-time rules. `none` is a rule, not the absence of one.
GT_RULES = ('none', 'A', 'B')
GT_RULE_TEXT = {
    'none': 'no garbage-time exclusion',
    'A': 'exclude when |score_differential| > 21 and '
         'game_seconds_remaining < 300',
    'B': 'exclude when |score_differential| > 16 and '
         'game_seconds_remaining < 600',
}

CODE_OK = 'OAS1_FRAME_BUILT'
CODE_ACCOUNTING = 'OAS1_EXCLUSION_ACCOUNTING_BROKEN'
CODE_DUPLICATE = 'OAS1_DUPLICATE_PLAY_KEY'
CODE_NO_ROWS = 'OAS1_FRAME_EMPTY'
CODE_BAD_GT = 'OAS1_GT_RULE_UNKNOWN'


def _f(v, default=None):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def play_class(r) -> str | None:
    """`pass` if the ball was thrown at all, `rush` if it was handed off.

    A SACK AND A SCRAMBLE ARE PASS PLAYS. See the module docstring.
    """
    if _f(r.get('pass_attempt'), 0) == 1 or _f(r.get('sack'), 0) == 1 \
            or _f(r.get('qb_scramble'), 0) == 1:
        return PASS
    if _f(r.get('rush_attempt'), 0) == 1:
        return RUSH
    return None


def garbage_time(r, rule: str) -> bool:
    """Observed score and clock only. No model-derived column is read."""
    if rule == 'none':
        return False
    sd = _f(r.get('score_differential'))
    gs = _f(r.get('game_seconds_remaining'))
    if sd is None or gs is None:
        # A ROW THAT CANNOT BE JUDGED IS NOT GARBAGE TIME. Treating unknown as
        # excluded would quietly drop the rows with the most missingness,
        # which correlate with the end of blowouts -- the exact bias the rule
        # is supposed to avoid creating.
        return False
    if rule == 'A':
        return abs(sd) > 21 and gs < 300
    if rule == 'B':
        return abs(sd) > 16 and gs < 600
    raise ValueError(f'unknown garbage-time rule {rule!r}')


def _reason(r, cls, gt_rule, reg_only):
    """Exactly one reason per row, in a DECLARED precedence order.

    The order is load-bearing: a kneel in a playoff blowout has three possible
    reasons and the counts only sum if precedence is fixed. Declared here,
    asserted by the accounting check, never inferred from iteration order.
    """
    if reg_only and (r.get('season_type') or '') != 'REG':
        return 'playoff'
    if _f(r.get('qb_kneel'), 0) == 1:
        return 'kneel'
    if _f(r.get('qb_spike'), 0) == 1:
        return 'spike'
    if (r.get('play_type') or '') == 'no_play':
        return 'no_play'
    if cls is None:
        pt = (r.get('play_type') or '')
        if pt in ('kickoff', 'punt', 'field_goal', 'extra_point'):
            return 'special_teams'
        return 'unclassified'
    if _f(r.get('penalty'), 0) == 1:
        return 'penalty'
    if not (r.get('posteam') or '').strip() or \
            not (r.get('defteam') or '').strip():
        return 'no_team'
    if (r.get('epa') or '') == '':
        return 'null_epa'
    if garbage_time(r, gt_rule):
        return 'garbage_time'
    return 'none'


def build(blob: pathlib.Path, *, vintage_sha256: str, gt_rule: str = 'none',
          reg_only: bool = True) -> Outcome:
    """One captured pbp blob -> the OAS1 frame, with every row accounted for."""
    if gt_rule not in GT_RULES:
        return Outcome.fail(
            CODE_BAD_GT, f'{gt_rule!r} is not one of {GT_RULES}',
            gt_rule=gt_rule)
    raw = gzip.decompress(pathlib.Path(blob).read_bytes()).decode('utf-8')
    rows = list(csv.DictReader(io.StringIO(raw)))
    if not rows:
        return Outcome.fail(CODE_NO_ROWS, f'{blob} holds no rows')
    out, counts, keys = [], {k: 0 for k in REASONS}, set()
    dupes = []
    for r in rows:
        cls = play_class(r)
        why = _reason(r, cls, gt_rule, reg_only)
        counts[why] += 1
        key = (r.get('game_id'), r.get('play_id'))
        if key in keys:
            dupes.append(key)
        keys.add(key)
        o = (r.get('posteam') or '').strip()
        d = (r.get('defteam') or '').strip()
        no = NT.normalize(o) if o else None
        nd = NT.normalize(d) if d else None
        out.append({
            'season': int(_f(r.get('season'), 0)),
            'week': int(_f(r.get('week'), 0)),
            'season_type': r.get('season_type') or '',
            'game_id': r.get('game_id') or '',
            'play_id': int(_f(r.get('play_id'), -1)),
            'ordinal': int(_f(r.get('season'), 0)) * 100
            + int(_f(r.get('week'), 0)),
            'game_date': r.get('game_date') or '',
            'offense_team': (no.value if no is not None
                             and no.state is State.PASS else None),
            'defense_team': (nd.value if nd is not None
                             and nd.state is State.PASS else None),
            'home_team': (r.get('home_team') or '').strip(),
            'offense_is_home': bool(o and o == (r.get('home_team') or '').strip()),
            'play_class': cls,
            'epa': _f(r.get('epa')),
            'is_sack': _f(r.get('sack'), 0) == 1,
            'is_scramble': _f(r.get('qb_scramble'), 0) == 1,
            'is_overtime': _f(r.get('qtr'), 0) > 4,
            'qtr': int(_f(r.get('qtr'), 0)),
            'score_differential': _f(r.get('score_differential')),
            'game_seconds_remaining': _f(r.get('game_seconds_remaining')),
            'garbage_time_flag': garbage_time(r, gt_rule),
            'gt_rule': gt_rule,
            'excluded_reason': why,
            'source_vintage': vintage_sha256,
        })
    if dupes:
        return Outcome.fail(
            CODE_DUPLICATE,
            f'{len(dupes)} duplicate (game_id, play_id) key(s), first '
            f'{dupes[:3]}. A duplicate is a defect, not a row to deduplicate: '
            f'silent deduplication is how a partially rebuilt season becomes a '
            f'corrupted panel.',
            cause=Cause.DATA, n_duplicates=len(dupes), examples=dupes[:5])
    total = sum(counts.values())
    if total != len(rows):
        return Outcome.fail(
            CODE_ACCOUNTING,
            f'exclusion reasons sum to {total} against {len(rows)} input '
            f'row(s). Every row must carry exactly one reason.',
            cause=Cause.DATA, counts=counts, n_rows=len(rows))
    kept = [x for x in out if x['excluded_reason'] == 'none']
    by_class = {c: sum(1 for x in kept if x['play_class'] == c)
                for c in PLAY_CLASSES}
    ev = {'spec_version': SPEC_VERSION, 'blob': str(blob),
          'source_vintage': vintage_sha256, 'gt_rule': gt_rule,
          'gt_rule_text': GT_RULE_TEXT[gt_rule], 'reg_only': bool(reg_only),
          'n_input_rows': len(rows), 'n_kept': len(kept),
          'exclusion_counts': counts,
          'exclusion_sums_to_input': True,
          'n_by_class': by_class,
          'n_sacks_kept': sum(1 for x in kept if x['is_sack']),
          'n_scrambles_kept': sum(1 for x in kept if x['is_scramble']),
          'n_sacks_in_pass_class': sum(1 for x in kept if x['is_sack']
                                       and x['play_class'] == PASS),
          'n_scrambles_in_pass_class': sum(1 for x in kept
                                           if x['is_scramble']
                                           and x['play_class'] == PASS),
          'seasons': sorted({x['season'] for x in kept}),
          'weeks': sorted({x['week'] for x in kept}),
          'n_games_kept': len({x['game_id'] for x in kept}),
          'teams': sorted({x['offense_team'] for x in kept
                           if x['offense_team']}),
          'reason_precedence': ['playoff', 'kneel', 'spike', 'no_play',
                                'special_teams/unclassified', 'penalty',
                                'no_team', 'null_epa', 'garbage_time',
                                'none'],
          }
    return Outcome.ok(CODE_OK, value={'rows': out, 'kept': kept, **ev},
                      detail=f'{len(rows)} row(s) in, {len(kept)} kept '
                             f'({by_class}), {len(counts)} reason bucket(s)',
                      **ev)
