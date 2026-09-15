"""Replays D20: the inactives capture that passed over a page with no players.

Written during TASK ZERO reconciliation with main, 2026-09-15, by opening the
committed blobs rather than trusting the manifest rows that describe them.

THE DEFECT

  https://www.nfl.com/inactives/ served, for the whole of Week 1 2026, an
  empty-state page. Its own body text reads:

      "Please check back soon for NFL Inactive Reports for this Season"

  It carries zero <table> and zero <tr>. Thirty-seven consecutive captures of
  it recorded state PASS / code CAPTURED / n_data_rows 41, and eight of those
  were declared eligible to discharge the 2026_01_DEN_KC inactives obligation
  with refusals == [].

  capture_vintage.py:345 has the right guard for this and it never fires. A
  zero-marker html payload returns DEFERRED("SOURCE_HAS_NO_ROWS_YET"),
  deliberately, so that an unpublished page is recorded as a debt. But the
  marker vocabulary for this source is the single word "inactive"
  (registry.py:234) and that word appears 41 times in the page's own chrome:
  title, meta description, og:url, canonical link, the ad and analytics config
  blobs, the visually-hidden h1, the placeholder promo, the news-tile link
  attributes -- and, once, the empty-state sentence itself. The page's
  declaration that it has no data is counted as evidence that it has data.
  n_data_rows is then set to that count (capture_vintage.py:358), so a count of
  navigation furniture is laundered into a row count.

SECTIONS B AND C FAIL ON PURPOSE. They are the defect, not a fix.

  The repair bar is TWO-SIDED and only one side can be tested from this
  repository today. A repair must make the committed empty blob stop passing
  AND must leave a blob carrying real inactive rows still passing. No
  positive-control blob exists here -- the source never published one -- so
  tightening the markers until section B goes green would be untestable against
  the half that matters. Do not do it. The endpoint question is OUT-016.

  Section A is the evidence and passes today. Section D is the positive control
  and reports NOT_EXECUTED, which is not a pass and must not be summarised as one.

Run standalone:  python3.12 nfl/tests/test_inactives_substance.py
"""
import gzip
import json
import os
import pathlib
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from nfl.capture import registry as reg                            # noqa: E402

PASSED = FAILED = 0
NOT_EXECUTED = []

ROOT = pathlib.Path(__file__).resolve().parents[2]
VINTAGE = ROOT / 'nfl' / 'vintage'
MANIFEST = ROOT / 'nfl' / 'vintage_manifest.jsonl'

# The page's own words. If this string is present the page is telling us, in
# English, that it has nothing.
EMPTY_STATE = 'Please check back soon for NFL Inactive Reports'

TARGET = '2026_01_DEN_KC'


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def not_executed(label, why):
    NOT_EXECUTED.append((label, why))
    print(f'  NOT_EXECUTED {label}  {why}')


def _records():
    """Every official_inactives manifest row, in capture order."""
    out = []
    for line in MANIFEST.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get('source') == 'official_inactives':
            out.append(r)
    out.sort(key=lambda r: r['capture_id'])
    return out


def _blob_text(blob):
    """Decompressed text of a manifest blob path, or None if absent."""
    fp = pathlib.Path(blob)
    if not fp.is_absolute():
        fp = ROOT / fp
    if not fp.exists():
        fp = VINTAGE / pathlib.Path(blob).name
    if not fp.exists():
        return None
    raw = fp.read_bytes()
    if fp.name.endswith('.gz'):
        raw = gzip.decompress(raw)
    return raw.decode('utf-8', 'replace')


def _eligible_for_target(rec):
    """True if this record was declared able to discharge TARGET's inactives."""
    v = rec.get('value') or {}
    de = v.get('discharge_eligibility') or {}
    for t in (de.get('targets') or []):
        if (t.get('game_id') == TARGET and t.get('kind') == 'inactives'
                and t.get('eligible') and not t.get('refusals')):
            return True
    return False


# --------------------------------------------------------------------------
def test_a_the_committed_blobs_carry_no_inactive_players():
    """THE EVIDENCE. Passes today: this section states what is on disk."""
    print('\nA. what the captured pages actually contain')
    recs = [r for r in _records() if r.get('state') == 'PASS'
            and (r.get('value') or {}).get('blob')]
    recs = [r for r in recs if r['capture_id'] >= '20260914T220000Z']
    check('there are captures in and after the DEN@KC window',
          len(recs) >= 8, f'{len(recs)} found')

    empty = tables = rows = 0
    for r in recs:
        t = _blob_text(r['value']['blob'])
        if t is None:
            continue
        if EMPTY_STATE in t:
            empty += 1
        tables += len(re.findall(r'<table', t))
        rows += len(re.findall(r'<tr[ >]', t))
    check('every one carries the page\'s own empty-state sentence',
          empty == len(recs), f'{empty} of {len(recs)}')
    check('across all of them there is not one <table>', tables == 0, str(tables))
    check('across all of them there is not one <tr>', rows == 0, str(rows))

    elig = [r for r in recs if _eligible_for_target(r)]
    check(f'and some were still declared eligible to discharge {TARGET}',
          len(elig) >= 1, f'{len(elig)} eligible')
    print(f'       ({len(elig)} eligible captures over {tables} tables '
          f'and {rows} rows of data)')


def test_b_BUG_the_marker_vocabulary_is_satisfied_by_page_chrome():
    """FAILS ON PURPOSE. The marker count is furniture, not players."""
    print('\nB. BUG -- the substance guard is satisfied by navigation')
    spec = reg.BY_NAME['official_inactives']
    markers = tuple(getattr(spec, 'content_markers', ()) or ())
    print(f'       content_markers = {markers!r}')

    recs = [r for r in _records() if r.get('state') == 'PASS'
            and (r.get('value') or {}).get('blob')
            and r['capture_id'] >= '20260914T220000Z']
    worst = 0
    for r in recs:
        t = _blob_text(r['value']['blob'])
        if t is None:
            continue
        n = sum(t.lower().count(m.lower()) for m in markers)
        worst = max(worst, n)

    # BUG: capture_vintage.py:345 only defers when the marker count is ZERO.
    # A page with no players scores 41, so the guard is unreachable for this
    # source and the count becomes n_data_rows at :358.
    check('a page with zero inactive players scores zero markers',
          worst == 0,
          f'it scores {worst}; every one is chrome -- title, meta, og:url, '
          f'canonical, ad/analytics config, hidden h1, placeholder promo, and '
          f'news-tile link attributes. One of them is the empty-state sentence '
          f'itself.')


def test_c_BUG_the_recorded_row_count_is_not_a_row_count():
    """FAILS ON PURPOSE. n_data_rows describes the chrome, not the data."""
    print('\nC. BUG -- n_data_rows over a page with no rows')
    bad = []
    for r in _records():
        v = r.get('value') or {}
        if r.get('state') != 'PASS' or not v.get('blob'):
            continue
        t = _blob_text(v['blob'])
        if t is None or EMPTY_STATE not in t:
            continue
        n = v.get('n_data_rows')
        if n:
            bad.append((r['capture_id'], n))
    # BUG: a page that says it has nothing must not report rows.
    check('no capture of the empty page reports data rows',
          not bad,
          f'{len(bad)} do, all reporting {sorted({n for _, n in bad})} rows; '
          f'first {bad[0][0] if bad else "-"}, last {bad[-1][0] if bad else "-"}')


def test_d_positive_control_a_page_that_does_carry_rows_still_passes():
    """NOT_EXECUTED. The other half of the repair bar, and it has no input."""
    print('\nD. positive control -- real rows must still pass')
    have = []
    for r in _records():
        v = r.get('value') or {}
        if not v.get('blob'):
            continue
        t = _blob_text(v['blob'])
        if t is not None and EMPTY_STATE not in t and '<table' in t:
            have.append(r['capture_id'])
    if have:
        check('a positive-control blob exists and carries a table',
              True, f'{len(have)} candidates')
    else:
        not_executed(
            'no committed blob carries real inactive rows',
            'the source never published a populated page in this corpus, so '
            'the half of the repair bar that protects real data CANNOT be '
            'tested here. Tightening markers to make section B green without '
            'this control would be untestable in the direction that matters. '
            'See OUT-016.')


if __name__ == '__main__':
    test_a_the_committed_blobs_carry_no_inactive_players()
    test_b_BUG_the_marker_vocabulary_is_satisfied_by_page_chrome()
    test_c_BUG_the_recorded_row_count_is_not_a_row_count()
    test_d_positive_control_a_page_that_does_carry_rows_still_passes()
    print(f'\n{PASSED} passed, {FAILED} failed, '
          f'{len(NOT_EXECUTED)} NOT_EXECUTED')
    for label, why in NOT_EXECUTED:
        print(f'  NOT_EXECUTED: {label} -- {why}')
    sys.exit(1 if FAILED else 0)
