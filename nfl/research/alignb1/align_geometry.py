"""ALIGN-B1: pre-snap alignment from player coordinates. Rule-based, frozen.

Implements exactly the geometry predeclared in predeclaration_alignb1.md
(sha256 e8260091a125a5ecdc60cc8e153fb6fbbc5075594188d6ba84b647dd17ccfd62).
Every threshold here appears in that file and was fixed before this module was
written.

NO FTN DATA IS USED, as a label, a threshold, a tie-break or anything else.

ABSTENTION IS A RESULT. `AMBIGUOUS` carries a machine-readable cause so the
review queue can be triaged, and so a high abstention rate is visible as the
finding it would be rather than hidden inside an accuracy number.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

# --- frozen thresholds, from the pre-registration -------------------------
BACKFIELD_DEPTH = 1.5      # yards behind the LOS to count as backfield
BACKFIELD_GAP = 3.0        # lateral yards from the tackle, inside the box
INLINE_DEPTH = 1.0         # yards: on the line of scrimmage
INLINE_GAP = 1.5           # yards from the tackle: attached
DETACHED_GAP = 6.0         # beyond this, a receiver is split rather than flexed
BUNCH_SEPARATION = 1.5     # closer than this to a same-side eligible -> unstable
MOTION_SPEED = 1.0         # yd/s lateral: alignment is not yet set
N_OL_REQUIRED = 5

WIDE, SLOT = 'WIDE', 'SLOT'
INLINE_TE, DETACHED_TE = 'INLINE_TE', 'DETACHED_TE'
BACKFIELD, AMBIGUOUS = 'BACKFIELD', 'AMBIGUOUS'
CLASSES = (WIDE, SLOT, INLINE_TE, DETACHED_TE, BACKFIELD, AMBIGUOUS)


@dataclass
class Player:
    pid: str
    x: float                    # along the field; offense advances +x
    y: float                    # lateral, 0..53.33
    is_ol: bool = False
    is_qb: bool = False
    eligible: bool = True
    vy: float = 0.0             # lateral speed, yd/s
    position: Optional[str] = None


@dataclass
class Frame:
    los_x: float
    ball_y: float
    players: list = field(default_factory=list)
    stable: bool = True         # False -> NO_STABLE_FRAME for the whole play


def _abstain(cause):
    return AMBIGUOUS, cause


def classify_frame(fr: Frame) -> dict:
    """Return {player_id: (class, cause_or_None)} for one pre-snap frame."""
    out = {}
    if not fr.stable:
        return {p.pid: _abstain('NO_STABLE_FRAME') for p in fr.players}

    ol = [p for p in fr.players if p.is_ol]
    if len(ol) < N_OL_REQUIRED:
        # core and therefore `gap` are undefined. Refusing is the only honest
        # answer; guessing a tackle position would fabricate the reference the
        # whole taxonomy is measured against.
        return {p.pid: _abstain('OL_NOT_IDENTIFIABLE') for p in fr.players}

    left_tackle_y = min(p.y for p in ol)
    right_tackle_y = max(p.y for p in ol)

    elig = [p for p in fr.players if p.eligible and not p.is_ol and not p.is_qb]
    for p in fr.players:
        if p.is_ol or p.is_qb:
            continue
        if any(v is None or (isinstance(v, float) and math.isnan(v))
               for v in (p.x, p.y, fr.los_x, fr.ball_y)):
            out[p.pid] = _abstain('NULL_COORDINATE'); continue
        if abs(p.vy) > MOTION_SPEED:
            out[p.pid] = _abstain('IN_MOTION'); continue

        side = 1.0 if p.y >= fr.ball_y else -1.0
        tackle_y = right_tackle_y if side > 0 else left_tackle_y
        gap = abs(p.y - tackle_y)
        depth = fr.los_x - p.x

        same_side = [q for q in elig
                     if q.pid != p.pid
                     and ((q.y >= fr.ball_y) if side > 0 else (q.y < fr.ball_y))]
        # bunch/stack: y-order is unstable, so "who is outside" is unstable
        if any(abs(q.y - p.y) < BUNCH_SEPARATION for q in same_side):
            out[p.pid] = _abstain('BUNCH_OR_STACK'); continue
        n_outside = sum(1 for q in same_side
                        if abs(q.y - fr.ball_y) > abs(p.y - fr.ball_y))

        if depth >= BACKFIELD_DEPTH and gap <= BACKFIELD_GAP:
            out[p.pid] = (BACKFIELD, None)
        elif depth <= INLINE_DEPTH and gap <= INLINE_GAP:
            out[p.pid] = (INLINE_TE, None)
        elif INLINE_GAP < gap <= DETACHED_GAP:
            out[p.pid] = (DETACHED_TE, None)
        elif gap > DETACHED_GAP and n_outside >= 1:
            out[p.pid] = (SLOT, None)
        elif gap > DETACHED_GAP and n_outside == 0:
            out[p.pid] = (WIDE, None)
        else:
            out[p.pid] = _abstain('NO_RULE_MATCHED')
    return out


def accept_or_review(result: dict) -> dict:
    """Split into automatically accepted labels and a review queue (s.F)."""
    acc = {k: v[0] for k, v in result.items() if v[0] != AMBIGUOUS}
    rev = {k: v[1] for k, v in result.items() if v[0] == AMBIGUOUS}
    n = len(result)
    return {'accepted': acc, 'review': rev,
            'review_rate': (len(rev) / n) if n else None,
            'n': n}
