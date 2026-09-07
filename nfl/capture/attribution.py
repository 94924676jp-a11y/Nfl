"""RETIRED 2026-09-07 by Directive 7 §6. Superseded by nfl/capture/execution.py.

WHAT THIS MODULE DID AND WHY IT IS GONE

It computed a capture's target set from `retrieved_at` -- a clock that exists
only after the bytes have arrived -- and wrote the result onto the manifest row
as `discharge_claims`. Directive 7 §6 forbids exactly that:

    "Do not infer the target set after the fact from timestamps alone."

And §2 sets the standard it could not meet: a row may carry a game_id only
because "this capture execution was intentionally scheduled to satisfy that
game's evidence obligation". A timestamp cannot express intent. Under the old
module a capture that wandered into a window by coincidence and one taken
because the window was open produced identical records.

`nfl/capture/execution.py` replaces it: intent is DECLARED before the fetch, and
the bytes are judged against the declaration afterwards.

WHY THIS FILE IS A STUB RATHER THAN A DELETION

Directive 7 §3 warns against a second competing mechanism. A deleted file can be
re-added by someone who remembers it working; a stub that raises cannot be
called back into service by accident, and it carries the reason. The one
function kept live is the legacy READER, because rows written before today still
sit in the manifest and must remain describable -- they simply discharge nothing.
"""
from __future__ import annotations


class RetiredMechanism(RuntimeError):
    """Raised if anything tries to use the post-hoc attribution path."""


CLAIM_VERSION = "discharge_claim/1.0.0-RETIRED"

_WHY = (
    "attribution.claims_for is retired. It inferred a capture's target set from "
    "retrieved_at after the bytes arrived, which Directive 7 §6 forbids, and it "
    "could not distinguish an intentional capture from a coincidental one. Use "
    "nfl.capture.execution.declare() BEFORE fetching, then "
    "nfl.capture.execution.eligibility() on the result."
)


def claims_for(*_a, **_k):
    raise RetiredMechanism(_WHY)


def week_plan_for(*_a, **_k):
    raise RetiredMechanism(_WHY)


def claimed_game_ids(manifest_value: dict) -> list:
    """Game ids a PRE-DIRECTIVE-7 row claimed. For reading history only.

    These claims discharge nothing and coverage does not consult this function.
    It exists so the old rows can be counted and described rather than becoming
    unreadable, which would be its own kind of quiet loss.
    """
    block = (manifest_value or {}).get("discharge_claims") or {}
    return [c["game_id"] for c in block.get("claims", []) if c.get("game_id")]
