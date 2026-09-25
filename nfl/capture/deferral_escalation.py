"""A debt that spans its own event window is not a debt, it is a defect.

WHAT "NOT YET" STOPPED MEANING

`SOURCE_HAS_NO_ROWS_YET` is an honest verdict about one artifact: this page
rendered, carries its subject word, and contains no row container, so the source
has not published. On a Tuesday that is exactly right.

Measured 2026-09-25 on the `capture-prod` lineage: `official_inactives` returned
that verdict on **every one of 48 captures a day for ten consecutive days**,
2026-09-16 through 2026-09-25, including all eleven attempts inside the ATL @ GB
window of 2026-09-24T20:06Z to 2026-09-25T01:06Z. Independently checked against
the committed blobs: **0 of 367 contain `<tr`, `<table` or `<tbody`**, and
**363 of 367 contain the string "check back soon"**. No `__NEXT_DATA__`, no
`window.__INITIAL`.

So the word "YET" was carrying a claim nobody had checked. The condition is not
temporal and will not resolve: the configured URL is a landing page, and the
rows have never been in the bytes it returns. Ten days of "not yet" for
something that is structurally "not here".

TWO ESCALATIONS, AND THEY ARE DIFFERENT DEFECTS

  SOURCE_PATH_CANNOT_YIELD_ROWS      no capture has EVER carried a row
                                     container. The endpoint is mis-specified;
                                     no amount of waiting or parser work on this
                                     path will help. Fix the URL.
  CONTENT_PRESENT_EXTRACTION_EMPTY   row containers ARE present and extraction
                                     still yields nothing. That is a parser or
                                     coverage defect on a page that does have
                                     the data.

Collapsing them would send somebody to rewrite a parser for a page that does not
contain the data, which is the more expensive of the two mistakes.

  DEBT_WITHIN_WINDOW                 deferred, and the expected publication
                                     window has not closed. Legitimately not
                                     yet, and left alone.

WHY THE WINDOW MATTERS

Zero rows means different things at different times. For an event-driven source
the meaning of silence changes as the event approaches, so the escalation is
keyed to the window in which rows are expected to exist, not to a count of
consecutive failures. A source that defers for a week in the off-season is fine;
one that defers through ninety minutes before kickoff is not.

LIMITS
  This reads capture records and stored blobs. It cannot tell a mis-specified
  URL from a source that removed its own data, and it does not fetch anything.
  A hit is a question for a human; the counts are what was committed, not what
  the internet did.
"""
from __future__ import annotations

import datetime as dt
import gzip
from pathlib import Path

SPEC_VERSION = 'deferral-escalation/1.0.0'

DEFERRED_EMPTY = 'SOURCE_HAS_NO_ROWS_YET'

CANNOT_YIELD = 'SOURCE_PATH_CANNOT_YIELD_ROWS'
EXTRACTION_EMPTY = 'CONTENT_PRESENT_EXTRACTION_EMPTY'
DEBT_WITHIN_WINDOW = 'DEBT_WITHIN_WINDOW'
NO_WINDOW_DECLARED = 'NO_WINDOW_DECLARED'

#: Row containers that indicate the data is present in the fetched bytes at all.
ROW_CONTAINERS = ('<tr', '<table', '<tbody')

#: Markers that a page deferred rendering to JavaScript. Distinguished from a
#: landing page because the remedy differs: render it, versus find the real URL.
SHELL_MARKERS = ('__next_data__', 'window.__initial')

#: When rows are expected to exist, per source, relative to kickoff. official
#: inactives publish about 90 minutes out; the window closes at kickoff.
EXPECTED_WINDOW_H = {
    'official_inactives': (-1.5, 0.0),
}


class EscalationError(RuntimeError):
    """A structural coverage defect was about to be carried as a debt."""


def _ts(capture_id: str):
    c = (capture_id or '').split('.')[0].rstrip('Z')
    try:
        return dt.datetime.strptime(c, '%Y%m%dT%H%M%S').replace(
            tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def blob_evidence(blob_dir: Path, pattern: str) -> dict:
    """Over every committed blob: did ANY of them carry a row container?"""
    n = rows = shell = landing = 0
    for p in sorted(Path(blob_dir).glob(pattern)):
        try:
            raw = p.read_bytes()
            if p.name.endswith('.gz'):
                raw = gzip.decompress(raw)
            text = raw.decode('utf-8', 'replace').lower()
        except (OSError, EOFError, gzip.BadGzipFile):
            continue
        n += 1
        if any(c in text for c in ROW_CONTAINERS):
            rows += 1
        if any(m in text for m in SHELL_MARKERS):
            shell += 1
        if 'check back soon' in text:
            landing += 1
    return {'n_blobs': n, 'n_with_row_container': rows,
            'n_js_shell': shell, 'n_landing_page': landing}


def classify(source: str, deferrals, evidence: dict, kickoffs=(),
             now=None) -> dict:
    """One verdict for a source's accumulated deferrals.

    `deferrals` are capture timestamps that came back DEFERRED_EMPTY.
    `kickoffs` are kickoff times whose windows should have contained rows.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    win = EXPECTED_WINDOW_H.get(source)
    spanned = []
    if win:
        lo_h, hi_h = win
        for k in kickoffs:
            lo, hi = (k + dt.timedelta(hours=lo_h),
                      k + dt.timedelta(hours=hi_h))
            if hi > now:
                continue                      # window still open
            if any(lo <= d <= hi for d in deferrals):
                spanned.append(k.isoformat())
    out = {
        'spec_version': SPEC_VERSION,
        'source': source,
        'n_deferrals': len(deferrals),
        'windows_spanned_with_no_rows': spanned,
        **evidence,
    }
    if not win:
        out['verdict'] = NO_WINDOW_DECLARED
        out['reading'] = (
            'no expected publication window is declared for this source, so a '
            'deferral cannot be judged late. Declaring one is the fix.')
        return out
    if not spanned:
        out['verdict'] = DEBT_WITHIN_WINDOW
        out['reading'] = 'no closed expected window has been missed'
        return out
    if evidence['n_blobs'] and evidence['n_with_row_container'] == 0:
        out['verdict'] = CANNOT_YIELD
        out['reading'] = (
            f"{evidence['n_with_row_container']} of {evidence['n_blobs']} "
            f"committed captures carry a row container, and "
            f"{len(spanned)} closed publication window(s) passed with rows "
            f"still absent. The path cannot yield rows; rewriting the parser "
            f"cannot help because the data is not in these bytes."
            + (f" {evidence['n_landing_page']} of {evidence['n_blobs']} say "
               f"'check back soon'." if evidence['n_landing_page'] else '')
            + (f" {evidence['n_js_shell']} carry a JS-shell marker, so "
               f"rendering may be the remedy rather than a new URL."
               if evidence['n_js_shell'] else
               ' No JS-shell marker is present, so this is a landing page '
               'rather than an unrendered one.'))
        return out
    out['verdict'] = EXTRACTION_EMPTY
    out['reading'] = (
        f"row containers appear in {evidence['n_with_row_container']} of "
        f"{evidence['n_blobs']} captures and extraction still yielded nothing "
        f"across {len(spanned)} closed window(s). The data is in the bytes; "
        f"the extractor is the defect.")
    return out


def assert_no_structural_debt(report: dict) -> dict:
    """Refuse to carry a structural coverage defect as an open debt."""
    if report['verdict'] in (CANNOT_YIELD, EXTRACTION_EMPTY):
        raise EscalationError(
            f"{report['source']}: {report['verdict']} -- {report['reading']} "
            f"This is a coverage defect and must not remain filed as "
            f"{DEFERRED_EMPTY}.")
    return report
