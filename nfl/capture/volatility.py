"""A second, DERIVED digest that ignores per-request rendering nonces.

THE MEASUREMENT THAT MOTIVATES IT, 2026-09-07

Eight live captures of the official cascade from the GitHub runner:

    official_inactives      4 blobs   4 distinct raw sha256   1 substantive
    official_injury_report  4 blobs   4 distinct raw sha256   1 substantive

and, as the counter-case that keeps the rule honest, the nflverse CSVs are
left completely untouched: 0 neutralisations in schedules, depth_charts and
weekly_rosters, whose UUID-shaped `sportradar_id` column is real content.

Every one of the eight is substantively identical. The pages embed per-request
UUIDs -- 100 of them on the inactives page, 45 on the injury report, in
`data-jsonid` attributes and the matching `<script id=...>` -- which rotate on
every render. Two captures twenty minutes apart differ on exactly two lines and
in exactly one respect: the UUID.

The consequences are the reason this module exists rather than a note:

  * every capture records `content_unchanged: false`, so the manifest asserts
    the page changed four times when it changed zero times. Directive 6 §8:
    a repeated capture "must not create a fake new content version";
  * `registry.bound_from_series` closes a vintage interval at the next capture
    with a DIFFERENT hash. Every hash differs, so every interval collapses to a
    point and the series carries no information about when content changed;
  * at the first T-90 window that makes the evidence unreadable in the way that
    matters most: the manifest cannot distinguish "the inactives list was
    published" from "the nonce rotated".

WHAT THIS MODULE IS AND IS NOT

It is a derived measurement recorded ALONGSIDE the raw digest. The raw sha256
stays authoritative and untouched -- it identifies the bytes, and the bytes are
what was retrieved. This digest identifies the CONTENT, and it can only ever be
used to say "these two captures are substantively the same".

It is not a deduplication policy. Blob storage still writes a new blob per
distinct raw digest, so the inflation above continues until the owner decides
otherwise. Changing what gets stored is a change to the capture system and is
not taken unilaterally.

Every neutralisation is declared, counted and reported. A masking rule that
quietly removed real content would turn a false "changed" into a false
"unchanged", which is the worse error of the two.
"""
from __future__ import annotations

import hashlib
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

DIGEST_VERSION = "substantive/1.0.0"

# Each rule names WHAT it neutralises and WHY that token cannot carry content.
# The bar is that the token must be structurally incapable of expressing an
# injury, a status or a roster fact -- not merely observed to change often.
# Each rule names WHAT it neutralises and WHY that token cannot carry content.
# The bar is that the token must be structurally incapable of expressing an
# injury, a status or a roster fact -- not merely observed to change often.
#
# THE FIRST VERSION OF THIS RULE WAS TOO BROAD AND THE INSTRUMENTATION CAUGHT IT
#
# It matched any UUID-shaped string anywhere in any payload. Run against the
# real captures it neutralised 4,821 tokens in weekly_rosters and 272 in
# schedules -- and those are not nonces, they are `sportradar_id`, a real column
# that identifies a player (Aaron Rodgers is
# 0ce48193-e2fa-466e-a986-33f751add206). Masking them would have turned a real
# roster change into a false "unchanged", which is the worse of the two errors
# and exactly what the paragraph above says the bar exists to prevent.
#
# So the rule is anchored to the two attribute positions where the nonce was
# actually measured, and a UUID sitting in a data field is left alone.
VOLATILE_RULES = (
    ("render_uuid_jsonid",
     re.compile(rb'data-jsonid="[0-9a-fA-F-]{36}"'),
     b'data-jsonid="<RENDER_UUID>"',
     "The lazy-load container's handle for its JSON payload. Minted per render, "
     "never leaves the document, nothing is keyed on it."),
    ("render_uuid_script_id",
     re.compile(rb'<script id="[0-9a-fA-F-]{36}"'),
     b'<script id="<RENDER_UUID>"',
     "The matching id on the payload script tag. Same handle, other end."),
)


def substantive_digest(raw: bytes) -> Outcome:
    """sha256 over the bytes with declared volatile tokens neutralised."""
    if not raw:
        return Outcome.blocked(
            "DIGEST_INPUT_EMPTY",
            "no bytes to digest. An empty input has no content digest, and "
            "returning the digest of nothing would compare equal to every "
            "other empty capture.", cause=Cause.DATA)
    masked = raw
    applied = {}
    for name, rx, repl, _why in VOLATILE_RULES:
        masked, n = rx.subn(repl, masked)
        applied[name] = n
    return Outcome.ok(
        "SUBSTANTIVE_DIGEST",
        value={
            "digest": hashlib.sha256(masked).hexdigest(),
            "digest_version": DIGEST_VERSION,
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "neutralised": applied,
            "bytes_before": len(raw), "bytes_after": len(masked),
            "authority": "DERIVED_DETERMINISTIC",
        },
        detail=f"{sum(applied.values())} volatile tokens neutralised "
               f"({applied}); {len(raw)} -> {len(masked)} bytes",
        **applied)


def compare(a: bytes, b: bytes) -> Outcome:
    """Are two captures substantively the same page?

    Deliberately three-valued rather than a boolean, because the interesting
    case is the middle one: identical content under two different raw digests
    is the nonce, and reporting it as "changed" is the defect.
    """
    da, db = substantive_digest(a), substantive_digest(b)
    from sportsplatform.governance.outcome import State
    for d in (da, db):
        if d.state is not State.PASS:
            return d
    raw_same = da.value["raw_sha256"] == db.value["raw_sha256"]
    sub_same = da.value["digest"] == db.value["digest"]
    if raw_same:
        return Outcome.ok("BYTES_IDENTICAL", value="BYTES_IDENTICAL",
                          detail="the same bytes; a repeat observation, not a "
                                 "new version.")
    if sub_same:
        return Outcome.ok(
            "CONTENT_IDENTICAL_NONCE_DIFFERS",
            value="CONTENT_IDENTICAL_NONCE_DIFFERS",
            detail="different bytes, identical content once declared render "
                   "nonces are neutralised. Recording this as a content change "
                   "is the fake new version Directive 6 §8 forbids.",
            neutralised=da.value["neutralised"])
    return Outcome.ok("CONTENT_CHANGED", value="CONTENT_CHANGED",
                      detail="the content differs beyond the declared volatile "
                             "tokens. This is a real new version.")
