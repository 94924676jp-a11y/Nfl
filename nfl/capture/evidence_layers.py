"""FETCH_SUCCESS, STRUCTURAL_VALIDITY, PREDICTIVE_ELIGIBILITY.

THREE QUESTIONS THAT HAVE BEEN ANSWERED BY ONE WORD, AND THE WORD WAS `PASS`.

D20 is what happens when they are collapsed. `https://www.nfl.com/inactives/`
returned HTTP 200 over 400KB of rendered page, on time, inside a declared
window, from a scheduled executor that named its target before it fetched. Every
provenance question had the right answer. The page said:

    "Please check back soon for NFL Inactive Reports for this Season"

374 captures over nine days, every one recorded `state: PASS`, and 15 of week
one's 63 obligations were reported discharged on the strength of it.

Nothing in the fetch layer was wrong. That is the point. A source can be

  * fetched successfully,
  * structurally empty,
  * and therefore ineligible to discharge a forecast obligation,

all at the same time, and a vocabulary with one word for it cannot say so.

THE THREE LAYERS

  FETCH_SUCCESS          Did bytes arrive, intact, from the URL we asked for,
                         within the window, under a basis that can discharge?
                         HTTP status, digest, declaration, clock. It says
                         NOTHING about what the bytes contain.

  STRUCTURAL_VALIDITY    Do the bytes contain the entities they are supposed to
                         contain? The row container for html, the payload path
                         for json, the declared columns for csv -- each read
                         from the source's own declaration, never guessed. See
                         nfl/capture/payload_contract.py.

  PREDICTIVE_ELIGIBILITY May this evidence discharge THIS obligation for THIS
                         game? Scope, kind authority, window, basis, and the
                         two layers above. A structurally valid league-wide
                         document is not thereby evidence about one game.

MONOTONE, AND THAT IS THE WHOLE VALUE. Each layer presupposes the one before
it, so a verdict names the FIRST layer that failed and the reader learns where
the problem is rather than only that there is one. D20's captures are
FETCH_SUCCESS=True, STRUCTURAL_VALIDITY=False, and therefore
PREDICTIVE_ELIGIBILITY=False -- which reads, correctly, as "the capture network
is working and the source has nothing", a sentence the old vocabulary could not
form.

WHAT THIS MODULE IS AND IS NOT. It is the vocabulary and the composition rule.
It does not re-implement the checks -- `capture_vintage` owns fetch,
`payload_contract` owns structure, `coverage` owns eligibility -- because a
second implementation of a guard is a second thing to drift.
"""
import enum


class Layer(enum.Enum):
    """Ordered. A verdict names the FIRST layer that failed."""
    FETCH_SUCCESS = 1
    STRUCTURAL_VALIDITY = 2
    PREDICTIVE_ELIGIBILITY = 3


#: Which layer each capture code belongs to. A code absent from this map is a
#: code nobody has classified, and `layer_of` says so rather than guessing --
#: an unclassified refusal silently treated as a fetch problem is how a
#: substance problem gets retried forever.
CODE_LAYER = {
    # --- FETCH_SUCCESS ---------------------------------------------------
    'CAPTURED': Layer.FETCH_SUCCESS,
    'PRESERVED_BY_DELIVERY': Layer.FETCH_SUCCESS,
    'CAPTURED_BY_DELIVERY': Layer.FETCH_SUCCESS,
    'NO_EGRESS': Layer.FETCH_SUCCESS,
    'LOCAL_EXECUTOR_NO_EGRESS': Layer.FETCH_SUCCESS,
    'SOURCE_RAISED': Layer.FETCH_SUCCESS,
    'SOURCE_NOT_YET_PUBLISHED': Layer.FETCH_SUCCESS,
    'ENDPOINT_NOT_YET_VERIFIED': Layer.FETCH_SUCCESS,
    'PAYLOAD_MISSING': Layer.FETCH_SUCCESS,
    'EMPTY_PAYLOAD_200': Layer.FETCH_SUCCESS,
    'RAW_ARTIFACT_NOT_PERSISTED': Layer.FETCH_SUCCESS,
    'RAW_ARTIFACT_MISSING_ON_DISK': Layer.FETCH_SUCCESS,
    'PERSISTED_CONTENT_SHA256_MISMATCH': Layer.FETCH_SUCCESS,
    'PERSISTED_DIGEST_ABSENT_HISTORICAL': Layer.FETCH_SUCCESS,

    # --- STRUCTURAL_VALIDITY ---------------------------------------------
    # Bytes arrived and are intact. The question is what is in them.
    'SOURCE_HAS_NO_ROWS_YET': Layer.STRUCTURAL_VALIDITY,
    'HEADER_ONLY_PAYLOAD': Layer.STRUCTURAL_VALIDITY,
    'HTML_SHELL_OR_EMPTY': Layer.STRUCTURAL_VALIDITY,
    'JSON_UNPARSEABLE': Layer.STRUCTURAL_VALIDITY,
    'JSON_EMPTY_DOCUMENT': Layer.STRUCTURAL_VALIDITY,
    'SCHEMA_COLUMNS_ABSENT': Layer.STRUCTURAL_VALIDITY,
    'SCHEMA_COLUMNS_PRESENT_BUT_EMPTY': Layer.STRUCTURAL_VALIDITY,

    # --- PREDICTIVE_ELIGIBILITY ------------------------------------------
    # Bytes are real and well-formed. The question is whether they may
    # discharge THIS obligation for THIS game.
    'SOURCE_NOT_AUTHORISED_FOR_KIND': Layer.PREDICTIVE_ELIGIBILITY,
    'BASIS_CANNOT_DISCHARGE': Layer.PREDICTIVE_ELIGIBILITY,
    'NO_WINDOW_REMAINS': Layer.PREDICTIVE_ELIGIBILITY,
    'PRIOR_WINDOWS_MISSED': Layer.PREDICTIVE_ELIGIBILITY,
    'ORPHAN_BLOB_NOT_FROM_AN_OBSERVATION': Layer.PREDICTIVE_ELIGIBILITY,
    'NO_DECLARATION_BLOCK': Layer.PREDICTIVE_ELIGIBILITY,
    'DECLARED_BUT_REFUSED': Layer.PREDICTIVE_ELIGIBILITY,
    'EXCLUDED_VENUE': Layer.PREDICTIVE_ELIGIBILITY,
}


def layer_of(code):
    """The layer a capture code belongs to, or None if nobody classified it."""
    return CODE_LAYER.get(code)


def verdict(*, fetch_ok, structural_ok=None, eligible=None, code=None):
    """Compose the three answers into one that names where it stopped.

    `structural_ok` and `eligible` may be None meaning NOT ASKED -- because the
    layer before them failed, or because the source declares no contract. None
    is never silently read as True; the result records it as unasked.
    """
    out = {
        'FETCH_SUCCESS': bool(fetch_ok),
        'STRUCTURAL_VALIDITY': structural_ok,
        'PREDICTIVE_ELIGIBILITY': eligible,
        'code': code,
        'code_layer': layer_of(code).name if layer_of(code) else None,
    }
    if not fetch_ok:
        out['stopped_at'] = Layer.FETCH_SUCCESS.name
    elif structural_ok is False:
        out['stopped_at'] = Layer.STRUCTURAL_VALIDITY.name
    elif eligible is False:
        out['stopped_at'] = Layer.PREDICTIVE_ELIGIBILITY.name
    else:
        out['stopped_at'] = None
    # A CAPTURE MAY DISCHARGE ONLY IF ALL THREE SAID YES. Not two of three, and
    # never "the first one said yes and the others were not asked".
    out['may_discharge'] = (bool(fetch_ok) and structural_ok is True
                            and eligible is True)
    return out
