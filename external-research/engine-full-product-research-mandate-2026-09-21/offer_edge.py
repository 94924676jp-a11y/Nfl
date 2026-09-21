"""Offer-specific betting-edge evaluation, kept downstream of model validation.

FINDING 6. THESE ARE TWO DIFFERENT CLAIMS AND REVISION 2 RAN THEM TOGETHER.

G-XX-2 asks: over a prospective log, clustered by week, does the model beat
the de-vig market on a proper score for this prop family, with an interval
excluding zero? That is a statement ABOUT THE MODEL. It is aggregate,
historical, and price-free.

Whether a PARTICULAR offer at a PARTICULAR price right now has positive
expected value is a different question with different inputs, and a favorable
answer to the first does not imply a favorable answer to the second. The model
can beat the closing line on average across a season and still be behind the
price in front of you, because:

  - the edge is estimated on a family, and this offer is one member of it;
  - the price offered is not the de-vig consensus the comparison was made
    against, and the hold on this book at this moment is its own quantity;
  - the line may not be the line the family was scored at (alternate lines,
    half-point differences, and a push rule that changes the payout support);
  - the offer has a timestamp, and a price seen five minutes ago is not the
    price available now;
  - the EV estimate has Monte Carlo error of its own, which the family-level
    proper-score interval says nothing about.

So the scope verdict for P1.<family> stays a statement about model validity,
and NOTHING in this module can promote it. An offer is evaluated only when its
scope is already DEPLOYABLE, and it then gets its own verdict, its own
interval and its own refusals.

NO SPORTSBOOK QUANTITY FLOWS UPSTREAM. Price, line, hold and EV are read here
and nowhere else. They are never inputs to the football model; the mandate
forbids it and this module is the only place they appear.

This is an unaccepted specification. It evaluates no real offer and authorises
no wager. CANDIDATE_NOT_ACCEPTED_BASELINE / V2 NOT YET EARNED.
"""
from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

SPEC_VERSION = "offer-edge-1"

EV_POSITIVE = "EV_POSITIVE"
EV_INCLUDES_ZERO = "EV_INCLUDES_ZERO"
EV_NEGATIVE = "EV_NEGATIVE"
NOT_EVALUATED = "NOT_EVALUATED"
OFFER_VERDICTS = (EV_POSITIVE, EV_INCLUDES_ZERO, EV_NEGATIVE, NOT_EVALUATED)

#: Settlement conventions. `PUSH_REFUND` is the ordinary whole-number line:
#: an exact landing returns the stake. `NO_PUSH` is the half-point line where
#: the outcome cannot land on it. Which one applies changes the support of
#: the payout and therefore the EV, so it is required rather than assumed.
PUSH_REFUND = "PUSH_REFUND"
NO_PUSH = "NO_PUSH"
PUSH_LOSS = "PUSH_LOSS"
SETTLEMENT_RULES = (PUSH_REFUND, NO_PUSH, PUSH_LOSS)


@dataclass(frozen=True)
class Offer:
    """One price, on one side, at one moment, with its settlement rule."""
    market_id: str
    family: str
    player_id: str
    game_id: str
    side: str                       # "OVER" or "UNDER"
    line: float
    american_odds: int
    settlement_rule: str
    book: str
    observed_at: str                # ISO8601, when the price was seen
    stake_currency: str = "UNIT"


@dataclass
class OfferEdge:
    offer: Offer
    verdict: str
    ev_per_unit: Optional[float] = None
    ev_interval: Optional[Sequence[float]] = None
    p_win: Optional[float] = None
    p_push: Optional[float] = None
    p_lose: Optional[float] = None
    mc_se: Optional[float] = None
    decimal_payout: Optional[float] = None
    refusals: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def american_to_decimal(odds: int) -> float:
    """Decimal payout per unit staked, returned stake included."""
    if odds == 0:
        raise ValueError("american odds of zero is not a price")
    return 1.0 + (odds / 100.0 if odds > 0 else 100.0 / abs(odds))


def implied_probability(odds: int) -> float:
    """The book's implied probability WITH the vig still in it."""
    return 1.0 / american_to_decimal(odds)


def two_way_hold(over_odds: int, under_odds: int) -> float:
    """The book's hold on a two-way market. Reported, never subtracted here."""
    return implied_probability(over_odds) + implied_probability(under_odds) - 1.0


def evaluate_offer(
    offer: Offer,
    p_win: float,
    p_push: float,
    mc_se: float,
    *,
    scope_verdict: str,
    scope_id: str,
    now: Optional[str] = None,
    max_price_age_seconds: Optional[float] = None,
    z: float = 1.96,
) -> OfferEdge:
    """EV for one offer, refusing rather than guessing at every missing input.

    `p_win` and `p_push` come from the SAME weighted worlds the scope was
    validated on, at THIS offer's line -- not at the line the family was
    scored at. `mc_se` is the Monte Carlo standard error of `p_win` from the
    nested estimator in `nested_mc.py`, and it propagates into the EV interval
    because an EV computed from a noisy probability is itself noisy.
    """
    out = OfferEdge(offer=offer, verdict=NOT_EVALUATED)

    # A MODEL THAT IS NOT VALIDATED PRICES NOTHING. This is the separation:
    # the scope verdict is an input here and can never be an output.
    if scope_verdict != "DEPLOYABLE":
        out.refusals.append(
            f"SCOPE_NOT_DEPLOYABLE:{scope_id}:{scope_verdict}")
    if offer.settlement_rule not in SETTLEMENT_RULES:
        out.refusals.append(
            f"SETTLEMENT_RULE_UNKNOWN:{offer.settlement_rule!r}")
    if offer.side not in ("OVER", "UNDER"):
        out.refusals.append(f"SIDE_UNKNOWN:{offer.side!r}")
    if not (0.0 <= p_win <= 1.0) or not (0.0 <= p_push <= 1.0) \
            or p_win + p_push > 1.0 + 1e-9:
        out.refusals.append(
            f"PROBABILITIES_NOT_A_DISTRIBUTION:win={p_win} push={p_push}")
    if offer.settlement_rule == NO_PUSH and p_push > 0.0:
        out.refusals.append(
            f"PUSH_MASS_ON_A_NO_PUSH_LINE:{p_push}. A half-point line the "
            f"outcome cannot land on must carry zero push probability; "
            f"non-zero mass means the line or the rule is wrong.")
    if max_price_age_seconds is not None:
        t0, t1 = _parse(offer.observed_at), _parse(now)
        if t0 is None or t1 is None:
            out.refusals.append("PRICE_TIMESTAMP_UNREADABLE")
        else:
            age = (t1 - t0).total_seconds()
            out.notes.append(f"price_age_seconds={age:.0f}")
            if age < 0:
                out.refusals.append("PRICE_OBSERVED_IN_THE_FUTURE")
            elif age > max_price_age_seconds:
                out.refusals.append(
                    f"PRICE_STALE:{age:.0f}s>{max_price_age_seconds:.0f}s. "
                    f"A price that is no longer available is not an edge.")
    if out.refusals:
        return out

    b = american_to_decimal(offer.american_odds)
    p_lose = max(0.0, 1.0 - p_win - p_push)
    if offer.settlement_rule == PUSH_REFUND:
        ev = p_win * (b - 1.0) + p_push * 0.0 + p_lose * (-1.0)
        d_ev_d_p = (b - 1.0) + 1.0            # win up, lose down
    elif offer.settlement_rule == NO_PUSH:
        ev = p_win * (b - 1.0) + p_lose * (-1.0)
        d_ev_d_p = (b - 1.0) + 1.0
    else:                                      # PUSH_LOSS
        ev = p_win * (b - 1.0) + (p_push + p_lose) * (-1.0)
        d_ev_d_p = (b - 1.0) + 1.0

    # THE EV INTERVAL INHERITS THE PROBABILITY'S MONTE CARLO ERROR. Linear in
    # p_win, so the delta method is exact for the first moment: an EV quoted
    # without it is a point estimate presented as a decision.
    ev_se = abs(d_ev_d_p) * mc_se
    lo, hi = ev - z * ev_se, ev + z * ev_se

    out.decimal_payout = b
    out.p_win, out.p_push, out.p_lose = p_win, p_push, p_lose
    out.ev_per_unit, out.ev_interval, out.mc_se = ev, (lo, hi), mc_se
    out.verdict = (EV_POSITIVE if lo > 0.0 else
                   EV_NEGATIVE if hi < 0.0 else EV_INCLUDES_ZERO)
    out.notes.append(
        "this is an offer-level EV at one price and one line. It is NOT the "
        "family-level proper-score comparison in G-XX-2 and neither implies "
        "the other.")
    return out


def _parse(ts):
    if not ts:
        return None
    try:
        t = _dt.datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=_dt.timezone.utc)
