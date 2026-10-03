"""Does a payload contain the thing it is a payload OF?

D20 / D22. THE ONE QUESTION, ASKED THE SAME WAY FOR EVERY CONTENT KIND.

A capture check that reads HTTP status, byte count, line count, a keyword, or a
generic tag count is answering "did bytes arrive". That is a different question
from "did evidence arrive", and the gap between them is where this project's
most expensive defects live:

  D20  official_inactives served a page whose own body read "Please check back
       soon for NFL Inactive Reports for this Season". The marker word
       "inactive" appears 41 times in the page's chrome -- title, meta, og:url,
       ad config, news-tile attributes -- and once inside that very sentence, so
       the page's written statement that it had NO data counted as one unit of
       evidence that it had data. 374 captures, nine days, every one PASS.

  D22  The json check counts the ENVELOPE. ESPN's injuries document is
       {injuries: [32 teams], season, status, timestamp} and scores 32 + 3 = 35
       against 800 real injury entries. Empty every team's list and it STILL
       scores 35 -- byte-for-byte indistinguishable from healthy. Remove the
       injuries key altogether and the three remaining scalars score 3, which
       passes. The csv check counts rows and never looks at a column; this
       project has already shipped an export of 7,926 rows with every
       meaningful column blank.

So each source DECLARES where its entities live, and this module goes and
looks.

OWNER RULE 1 (2026-10-02). A source that declares nothing used to pass
unconditionally -- an empty payload included -- because "nothing declared"
was read as "nothing to check". That is a validator returning ok=True having
measured nothing. It now returns ok=False with code
PAYLOAD_CONTRACT_NOT_EXECUTED (evidence state/cause NOT_EXECUTED), which is
distinct from SOURCE_HAS_NO_ROWS_YET (the contract ran and found no rows) and
from SCHEMA_COLUMNS_ABSENT (the contract ran and the document is wrong). The
remedy is a declaration in nfl/capture/registry.py read from a real sample,
never a guessed one.

Returns (ok, code, evidence). `ok=False` with CODE_EMPTY is a DEBT -- the
source published nothing yet -- never an error: SOURCE_HAS_NO_ROWS_YET is the
same verdict capture_vintage already used for an unpublished page.
"""
import csv as _csv
import io

#: Declared so a capture row can prove WHICH contract shape judged it. A
#: provenance field reading "unknown" is a provenance field that has not been
#: filled in, and `capture_release` was recording exactly that.
SPEC_VERSION = 'payload_contract/1.0.0'

CODE_EMPTY = 'SOURCE_HAS_NO_ROWS_YET'
#: OWNER RULE 1 (2026-10-02): the contract had no declaration to execute.
CODE_NOT_EXECUTED = 'PAYLOAD_CONTRACT_NOT_EXECUTED'


def _not_executed(declaration: str, **ev) -> tuple:
    """A check with nothing declared did not run. It cannot say ok=True."""
    return False, CODE_NOT_EXECUTED, {declaration: None, 'state': CODE_NOT_EXECUTED,
                                      'cause': 'NOT_EXECUTED', 'n_measured': 0,
                                      'missing_declaration': declaration, **ev}


def json_entities(doc, path):
    """Every entity at `path`, where "*" means "each element of this list".

    Counting these is the whole point: `len(doc)` counts the envelope.
    """
    if not path:
        return None                      # nothing declared, nothing claimed
    cur = [doc]
    for key in path:
        nxt = []
        for node in cur:
            if key == '*':
                if isinstance(node, list):
                    nxt.extend(node)
                continue
            if isinstance(node, dict) and key in node:
                nxt.append(node[key])
        cur = nxt
    out = []
    for node in cur:
        if isinstance(node, list):
            out.extend(node)
        elif node is not None:
            out.append(node)
    return out


def check_json(doc, spec):
    path = tuple(getattr(spec, 'payload_path', ()) or ())
    if not path:
        # OWNER RULE 1 (2026-10-02): no payload_path, no entity count, no PASS.
        return _not_executed('payload_path')
    ents = json_entities(doc, path)
    n = len(ents or [])
    ev = {'payload_path': list(path), 'n_entities': n}
    if n < 1:
        return False, CODE_EMPTY, ev
    return True, None, ev


def check_csv(text, spec):
    """Present in the header is a promise. Populated on a row is evidence."""
    req = tuple(getattr(spec, 'required_columns', ()) or ())
    anyof = tuple(getattr(spec, 'substantive_any_of', ()) or ())
    if not req and not anyof:
        # OWNER RULE 1 (2026-10-02): no required_columns and no
        # substantive_any_of means no column was ever looked at.
        return _not_executed('required_columns', substantive_any_of=None)
    rows = list(_csv.reader(io.StringIO(text)))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        return False, CODE_EMPTY, {'n_rows': 0}
    header = [h.strip() for h in rows[0]]
    body = rows[1:]
    ev = {'required_columns': list(req), 'substantive_any_of': list(anyof),
          'n_data_rows': len(body)}

    missing = [c for c in req if c not in header]
    if missing:
        ev['missing_from_header'] = missing
        return False, 'SCHEMA_COLUMNS_ABSENT', ev

    def populated(col):
        i = header.index(col)
        return any(len(r) > i and r[i].strip() for r in body)

    blank = [c for c in req if not populated(c)]
    if blank:
        # A COLUMN PRESENT AND EMPTY IN EVERY ROW is the 7,926-row defect
        # exactly, and it is not the same fact as a column that is absent.
        ev['present_but_blank_in_every_row'] = blank
        return False, 'SCHEMA_COLUMNS_PRESENT_BUT_EMPTY', ev

    if anyof:
        have = [c for c in anyof if c in header and populated(c)]
        ev['substantive_columns_populated'] = have
        if not have:
            return False, CODE_EMPTY, ev
    return True, None, ev


def check_html(text, spec):
    """D20's check, restated here so all three kinds read from one place."""
    want = tuple(getattr(spec, 'row_container', ()) or ())
    if not want:
        # OWNER RULE 1 (2026-10-02): no row_container declared, nothing looked for.
        return _not_executed('row_container')
    low = text.lower()
    hit = [c for c in want if c.lower() in low]
    ev = {'row_container': list(want), 'row_container_found': hit}
    if not hit:
        return False, CODE_EMPTY, ev
    return True, None, ev
