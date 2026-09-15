"""Replays D20: the inactives capture that passed over a page with no players.

Written during TASK ZERO reconciliation with main, 2026-09-15, by opening the
committed blobs rather than trusting the manifest rows that describe them.

THE DEFECT

  https://www.nfl.com/inactives/ served, for the whole of Week 1 2026, an
  empty-state page. Its own body text reads:

      "Please check back soon for NFL Inactive Reports for this Season"

  Zero <table>. Zero <tr>. Not one player name. Three hundred and seventy-four
  consecutive captures of it recorded PASS / CAPTURED with a non-zero
  n_data_rows, and eight of those were declared eligible to discharge the
  2026_01_DEN_KC inactives obligation with refusals == [].

  capture_vintage.py has the right guard for this and it could not fire. A
  zero-marker HTML payload returns DEFERRED("SOURCE_HAS_NO_ROWS_YET"),
  deliberately, so that an unpublished page is recorded as a debt. But the
  marker vocabulary for this source is the single word "inactive" and that word
  appears up to 41 times in the page's own chrome: title, meta description,
  og:url, canonical link, the ad and analytics config blobs, a visually-hidden
  h1, the placeholder promo, and the news-tile link attributes -- and, once, the
  empty-state sentence itself. The page's written statement that it has no data
  counted as one unit of evidence that it has data.

THE REPAIR, AND WHY IT IS NOT A THRESHOLD

  The marker vocabulary is UNCHANGED. Tuning words until the empty page fails is
  exactly the move that produced the defect -- a previous pass had this source
  passing on four incidental "questionable"s. Instead the source now declares
  the SHAPE its rows live in (`SourceSpec.row_container`), and a payload that
  carries the subject word but not one row container is deferred as the debt it
  is.

  That is a declared property of the source, not a quantity fitted to data.
  Measured over every committed blob, and this is the two-sided bar:

      official_injury_report   <tr> present in 374 of 374   -> 374 PASS
      official_inactives       <tr> present in   0 of 392   -> 392 DEFERRED

  Section D is the half that matters and the half usually skipped: a guard that
  rejects the bad page is worthless if it also rejects the good one. Section E
  proves the guard is load-bearing rather than decorative.

WHAT THIS TEST DOES NOT DO

  It does not assert that the historical manifest rows are correct. They are
  not, and they stay. Capture evidence is append-only and is never rewritten to
  make a later tree green; the 374 PASS rows remain PASS, annotated by D20.
  Section C measures that debt rather than erasing it.

Run standalone:  python3.12 nfl/tests/test_inactives_substance.py
"""
import dataclasses
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


def _records(source='official_inactives', pass_only=True):
    out = []
    for line in MANIFEST.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get('source') != source:
            continue
        if pass_only and (r.get('state') != 'PASS'
                          or not (r.get('value') or {}).get('blob')):
            continue
        out.append(r)
    out.sort(key=lambda r: r['capture_id'])
    return out


def _blob_text(blob):
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


def _verdict(spec, text):
    """Replays the html substance branch of capture_vintage for one payload."""
    markers = tuple(spec.content_markers or ())
    rc = tuple(getattr(spec, 'row_container', ()) or ())
    n = sum(text.lower().count(m.lower()) for m in markers)
    rows_present = (not rc) or any(c.lower() in text.lower() for c in rc)
    if n and not rows_present:
        return 'DEFERRED_SOURCE_HAS_NO_ROWS_YET', n
    if n == 0:
        return 'DEFERRED_zero_markers', n
    return 'PASS', n


def _eligible_for_target(rec):
    de = (rec.get('value') or {}).get('discharge_eligibility') or {}
    for t in (de.get('targets') or []):
        if (t.get('game_id') == TARGET and t.get('kind') == 'inactives'
                and t.get('eligible') and not t.get('refusals')):
            return True
    return False


# --------------------------------------------------------------------------
def test_a_the_committed_blobs_carry_no_inactive_players():
    """THE EVIDENCE. What is actually on disk."""
    print('\nA. what the captured pages actually contain')
    recs = [r for r in _records() if r['capture_id'] >= '20260914T220000Z']
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
    check("every one carries the page's own empty-state sentence",
          empty == len(recs), f'{empty} of {len(recs)}')
    check('across all of them there is not one <table>', tables == 0, str(tables))
    check('across all of them there is not one <tr>', rows == 0, str(rows))

    elig = [r for r in recs if _eligible_for_target(r)]
    check(f'and some were still declared eligible to discharge {TARGET}',
          len(elig) >= 1, f'{len(elig)} eligible')
    print(f'       ({len(elig)} eligible captures over {tables} tables '
          f'and {rows} rows of data)')


def test_b_the_marker_count_alone_cannot_tell_the_difference():
    """WHY THE VOCABULARY WAS NOT TOUCHED. The word is in the furniture."""
    print('\nB. the subject word is not the subject')
    spec = reg.BY_NAME['official_inactives']
    markers = tuple(spec.content_markers or ())
    worst = 0
    for r in _records():
        t = _blob_text(r['value']['blob'])
        if t is None or EMPTY_STATE not in t:
            continue
        worst = max(worst, sum(t.lower().count(m.lower()) for m in markers))
    check('a page with zero inactive players still scores markers',
          worst > 0,
          'if this ever reads 0 the vocabulary was tuned, which is the move '
          'that caused the defect')
    print(f'       (worst empty page scores {worst} on {markers!r} -- title, '
          f'meta, og:url,\n        ad/analytics config, hidden h1, placeholder '
          f'promo, news-tile attributes,\n        and the empty-state sentence '
          f'itself)')
    check('so the repair must not be a marker threshold',
          tuple(spec.content_markers) == ('inactive',),
          f'vocabulary changed to {spec.content_markers!r}')


def test_c_the_historical_debt_is_measured_not_erased():
    """The bad rows stay. Append-only evidence is never rewritten."""
    print('\nC. the historical manifest rows, left standing')
    bad = []
    for r in _records():
        v = r['value']
        t = _blob_text(v['blob'])
        if t is None or EMPTY_STATE not in t:
            continue
        if v.get('n_data_rows'):
            bad.append((r['capture_id'], v['n_data_rows']))
    check('the defective rows are still present and still say PASS',
          len(bad) > 0,
          'they must not be deleted or rewritten -- see D20')
    counts = sorted({n for _, n in bad})
    print(f'       ({len(bad)} rows, n_data_rows in {counts}, '
          f'{bad[0][0]} .. {bad[-1][0]})')
    check('and the count matches what D20 records', len(bad) == 374,
          f'{len(bad)} -- if this drifts, D20 needs updating, not this test')


def test_d_the_two_sided_bar_replayed_over_every_committed_blob():
    """THE HALF THAT MATTERS. Rejecting the bad page is worthless alone."""
    print('\nD. two-sided: the good source must still pass')
    results = {}
    for name in ('official_injury_report', 'official_inactives'):
        spec = reg.BY_NAME[name]
        tally = {}
        for r in _records(source=name):
            t = _blob_text(r['value']['blob'])
            if t is None:
                continue
            v, _ = _verdict(spec, t)
            tally[v] = tally.get(v, 0) + 1
        results[name] = tally
        print(f'       {name}: {tally}')

    inj = results['official_injury_report']
    ina = results['official_inactives']
    check('POSITIVE CONTROL: every injury-report capture still passes',
          set(inj) == {'PASS'} and inj['PASS'] > 0, str(inj))
    check('NEGATIVE CONTROL: every empty inactives capture is now deferred',
          set(ina) == {'DEFERRED_SOURCE_HAS_NO_ROWS_YET'} and ina and
          list(ina.values())[0] > 0, str(ina))
    check('and it is deferred, never failed -- an unpublished source is a '
          'debt, not an error',
          'FAIL' not in str(ina))


def test_e_the_guard_is_load_bearing():
    """Remove the declaration and the empty page must start passing again."""
    print('\nE. bypass -- the guard is not decorative')
    spec = reg.BY_NAME['official_inactives']
    bypassed = dataclasses.replace(spec, row_container=())
    blob = next((r['value']['blob'] for r in _records()
                 if EMPTY_STATE in (_blob_text(r['value']['blob']) or '')), None)
    if blob is None:
        not_executed('no empty-state blob to seed the bypass with',
                     'section A would have failed first')
        return
    t = _blob_text(blob)
    live, _ = _verdict(spec, t)
    stub, n = _verdict(bypassed, t)
    check('with row_container declared, the empty page is refused',
          live == 'DEFERRED_SOURCE_HAS_NO_ROWS_YET', live)
    check('with it stripped, the same bytes pass again',
          stub == 'PASS', f'{stub} -- if this is not PASS the guard is not '
                          f'what is doing the work')
    print(f'       (bypassed verdict PASS on {n} chrome markers -- '
          f'this is the defect, reproduced on demand)')


def test_f_every_html_source_declares_the_shape_of_its_rows():
    """The generalisation. A word-only source is the next D20."""
    print('\nF. no html source may be judged by words alone')
    for spec in reg.REGISTRY:
        if getattr(spec, 'content_kind', None) != 'html':
            continue
        rc = tuple(getattr(spec, 'row_container', ()) or ())
        check(f'  {spec.name} declares a row_container', bool(rc),
              'an html source judged only by a marker word can pass over a '
              'landing page about its own data')


def test_g_the_delivered_markdown_captures_are_not_suppressed():
    """The near-miss. A row container is a claim about HTML and nothing else.

    The first cut of the coverage-layer check asked every official_inactives row
    for a <tr>, and so refused the 18 DELIVERED game-anchored captures -- which
    are markdown, written by the networked agent, and which carry the only real
    inactive lists in the store. It would have suppressed the genuine evidence
    while claiming to protect evidence quality: the defect under repair, pointed
    the other way. Caught by test_capture_obligations section E expecting 18 and
    reading 0.
    """
    print('\nG. the delivered captures must survive the repair')
    from nfl.capture import coverage as C
    kinds = {}
    for r in _records():
        v = r['value']
        kinds.setdefault(v.get('content_kind'), []).append(r['capture_id'])
    check('the store holds both shapes under this source name',
          set(kinds) == {'html', None}, str({k: len(v) for k, v in kinds.items()}))
    print(f'       ({len(kinds.get("html", []))} html landing pages, '
          f'{len(kinds.get(None, []))} delivered)')

    for cid in kinds.get(None, [])[:1]:
        rec = next(r for r in _records() if r['capture_id'] == cid)
        ok, why = C._has_declared_rows('official_inactives', rec['value'])
        check('  a delivered (non-html) capture is NOT refused for lacking <tr>',
              ok, str(why))
    for cid in kinds.get('html', [])[:1]:
        rec = next(r for r in _records() if r['capture_id'] == cid)
        ok, why = C._has_declared_rows('official_inactives', rec['value'])
        check('  and an html landing page still is',
              (not ok) and why == 'SOURCE_HAS_NO_ROWS_YET', str(why))

    ev = C.performed_from_manifest(str(MANIFEST)).evidence
    check('the 18 delivered game-anchored rows stay visible as uncredited',
          ev['n_uncredited_game_anchored'] == 18,
          str(ev['n_uncredited_game_anchored']))
    excl = [x for x in ev['artifact_excluded']
            if x['reason'] == 'SOURCE_HAS_NO_ROWS_YET']
    check('and exactly the 374 landing pages are excluded, not 392',
          len(excl) == 374, str(len(excl)))


if __name__ == '__main__':
    test_a_the_committed_blobs_carry_no_inactive_players()
    test_b_the_marker_count_alone_cannot_tell_the_difference()
    test_c_the_historical_debt_is_measured_not_erased()
    test_d_the_two_sided_bar_replayed_over_every_committed_blob()
    test_e_the_guard_is_load_bearing()
    test_f_every_html_source_declares_the_shape_of_its_rows()
    test_g_the_delivered_markdown_captures_are_not_suppressed()
    print(f'\n{PASSED} passed, {FAILED} failed, '
          f'{len(NOT_EXECUTED)} NOT_EXECUTED')
    for label, why in NOT_EXECUTED:
        print(f'  NOT_EXECUTED: {label} -- {why}')
    sys.exit(1 if FAILED else 0)
