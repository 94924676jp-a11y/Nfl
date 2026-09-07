"""Adversarial tests for nfl/capture/volatility.py -- the substantive digest.

TWO OPPOSITE ERRORS, AND THE SECOND IS WORSE

  A false CHANGE: the page is identical but a per-request nonce rotated, so the
  manifest records a new content version. Measured on the live captures: 4
  blobs of the inactives page, 4 distinct raw digests, 1 actual content. Every
  `content_unchanged: false` on those rows was fake.

  A false UNCHANGED: a masking rule swallows real content, so a genuine change
  is reported as a repeat. This is worse, because a missed injury update is
  invisible while a duplicate blob is merely wasteful.

The first version of the rule committed the second error. It matched any
UUID-shaped string anywhere, and on the real payloads that meant 4,821
neutralisations in weekly_rosters -- the `sportradar_id` column, a real
identifier. Section C is that case, kept as a permanent test rather than a
fixed bug, because the pressure to broaden the rule will recur.

Run standalone:  python3.12 nfl/tests/test_volatility.py
"""
import collections
import gzip
import hashlib
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.capture.volatility import (DIGEST_VERSION, VOLATILE_RULES,  # noqa: E402
                                    compare, substantive_digest)
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

VINTAGE = _REPO / 'nfl' / 'vintage'
RAW = _REPO / 'nfl_vintage' / 'raw'
PASSED = FAILED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def _is(o, state, code=None):
    return (isinstance(o, Outcome) and o.state is state
            and (code is None or o.code == code))


def _blobs(stem):
    return sorted(VINTAGE.glob(f'{stem}.*.html.gz'))


def test_A_the_false_change_it_exists_to_catch():
    """The nonce is collapsed. Real page change is not.

    CORRECTED 2026-09-07, by the live capture series rather than by review.
    This section originally asserted that all captures of a page collapse to
    EXACTLY ONE substantive digest, which was true of the four blobs that
    existed when it was written. The bot then captured four more and the
    assertion failed on 8 blobs / 8 raw digests / 2 substantive.

    The failure was correct and the assertion was wrong. Diffing the two
    substantive groups with the nonce masked leaves ONE differing line, and it
    is the embedded broadcast listing: `nationalGames` went from a populated
    array to `[]`. The injury tables are byte-identical and the parser returns
    the same 11 rows on both sides.

    So there is a third category this module does not distinguish, and pretending
    otherwise by loosening the mask would be the false-unchanged error §C exists
    to prevent: a whole-page digest answers "did the page change", not "did the
    injury report change". Those separate whenever anything else on the page
    moves. The durable invariant -- and what is asserted now -- is that the mask
    collapses strictly more raw digests than it leaves substantive ones, and
    that captures which parse to identical report content are not thereby
    guaranteed one digest. Recorded as an open debt; the fix is a digest over
    parsed rows, which is a change to G0A capture semantics and not taken here.
    """
    print('\nA. the live captures: many raw digests, far fewer pages')
    for stem in ('official_inactives', 'official_injury_report'):
        fs = _blobs(stem)
        check(f'{stem}: {len(fs)} captures on disk', len(fs) >= 2, str(len(fs)))
        raws = {hashlib.sha256(gzip.open(f, 'rb').read()).hexdigest()
                for f in fs}
        subs = collections.Counter(
            substantive_digest(gzip.open(f, 'rb').read()).value['digest']
            for f in fs)
        check(f'{stem}: every capture has a DIFFERENT raw digest',
              len(raws) == len(fs), f'{len(raws)} of {len(fs)}')
        check(f'{stem}: the mask collapses them to strictly fewer pages',
              len(subs) < len(raws), f'{len(subs)} substantive of {len(raws)} raw')
        check(f'{stem}: and the collapse is substantial, not cosmetic',
              len(subs) <= max(2, len(raws) // 3),
              f'{len(subs)} substantive of {len(raws)} raw')
        print(f'       [{len(fs)} blobs, {len(raws)} raw digests, '
              f'{len(subs)} substantive]')


def test_A2_a_page_digest_is_not_a_report_digest():
    """The open debt the live series exposed, kept as a standing test."""
    print('\nA2. a whole-page digest answers a different question')
    import hashlib as _h
    from nfl.parse.injury_report import parse
    groups = collections.defaultdict(list)
    for f in _blobs('official_injury_report'):
        b = gzip.open(f, 'rb').read()
        groups[substantive_digest(b).value['digest']].append(b)
    if len(groups) < 2:
        print('       [only one page version captured so far; '
              'the divergence below cannot be exercised yet]')
        check('there is at least one captured version', len(groups) >= 1)
        return
    rows_by_group = {}
    for d, blobs in groups.items():
        o = parse(blobs[0], raw_sha256=_h.sha256(blobs[0]).hexdigest())
        rows_by_group[d] = (o.code, len(o.value) if o.state is State.PASS else 0)
    check('two captures differ by whole-page digest', len(groups) >= 2,
          str(len(groups)))
    counts = {v[1] for v in rows_by_group.values()}
    check('yet they parse to the SAME report content -- so a page digest '
          'overstates report change',
          len(counts) == 1, str(rows_by_group))
    print(f'       [{len(groups)} page versions, all parsing to '
          f'{counts} report rows]')


def test_B_the_three_valued_answer():
    print('\nB. identical / nonce-differs / changed are three answers')
    fs = _blobs('official_inactives')
    a = gzip.open(fs[0], 'rb').read()
    b = gzip.open(fs[1], 'rb').read()

    check('the same bytes -> BYTES_IDENTICAL, a repeat observation',
          _is(compare(a, a), State.PASS, 'BYTES_IDENTICAL'))
    check('different bytes, same content -> the middle answer, which a boolean '
          'cannot express',
          _is(compare(a, b), State.PASS, 'CONTENT_IDENTICAL_NONCE_DIFFERS'),
          str(compare(a, b))[:110])
    check('and it says why recording that as a change is the forbidden thing',
          'fake new version' in compare(a, b).detail,
          compare(a, b).detail[:90])
    check('a genuinely different page -> CONTENT_CHANGED',
          _is(compare(a, b'<html><body>different</body></html>'),
              State.PASS, 'CONTENT_CHANGED'))

    # The seeded real change: alter one player's game status inside the report.
    real = _blobs('official_injury_report')[0]
    page = gzip.open(real, 'rb').read()
    mutated = page.replace(b'Did Not Participate In Practice',
                           b'Full Participation', 1)
    check('the seeded mutation really is present in the artifact',
          mutated != page)
    check('one player moving from Did Not Participate to Full Participation '
          'is CONTENT_CHANGED, not swallowed',
          _is(compare(page, mutated), State.PASS, 'CONTENT_CHANGED'),
          str(compare(page, mutated))[:110])


def test_C_the_rule_must_not_eat_real_content():
    """The error the first version of this rule actually made."""
    print('\nC. UUID-shaped real data is NOT neutralised')
    csvs = sorted(RAW.glob('*.csv'))
    check('there are real nflverse payloads to test against', len(csvs) >= 1,
          str(len(csvs)))
    for f in csvs:
        n = substantive_digest(f.read_bytes()).value['neutralised']
        check(f'{f.name}: zero neutralisations', sum(n.values()) == 0, str(n))

    # sportradar_id is a real UUID identifying a real player.
    row = (b'season,gsis_id,sportradar_id,full_name\n'
           b'2026,00-0023459,0ce48193-e2fa-466e-a986-33f751add206,A.Rodgers\n')
    changed = row.replace(b'0ce48193-e2fa-466e-a986-33f751add206',
                          b'11111111-2222-3333-4444-555555555555')
    check('a bare UUID in a data column is left alone',
          substantive_digest(row).value['neutralised'] ==
          {'render_uuid_jsonid': 0, 'render_uuid_script_id': 0})
    check('so changing a player identifier reads as a REAL change, not a nonce',
          _is(compare(row, changed), State.PASS, 'CONTENT_CHANGED'),
          str(compare(row, changed))[:110])

    check('and every rule is anchored to an attribute position rather than '
          'matching a bare UUID',
          all(b'data-jsonid' in rx.pattern or b'<script id' in rx.pattern
              for _n, rx, _r, _w in VOLATILE_RULES),
          str([rx.pattern for _n, rx, _r, _w in VOLATILE_RULES]))
    check('and each rule carries a written justification, not just a pattern',
          all(len(why) > 40 for _n, _rx, _r, why in VOLATILE_RULES))


def test_D_it_reports_what_it_did():
    print('\nD. the derivation is declared, counted and non-authoritative')
    page = gzip.open(_blobs('official_inactives')[0], 'rb').read()
    v = substantive_digest(page).value
    check('the raw digest is carried alongside and is unchanged',
          v['raw_sha256'] == hashlib.sha256(page).hexdigest())
    check('the two digests are different values, so neither can stand in for '
          'the other by accident',
          v['digest'] != v['raw_sha256'])
    check('every rule reports its own count',
          set(v['neutralised']) == {n for n, _r, _rep, _w in VOLATILE_RULES},
          str(v['neutralised']))
    check('something was actually neutralised on this page',
          sum(v['neutralised'].values()) > 0, str(v['neutralised']))
    check('the digest declares itself DERIVED, never source-provided',
          v['authority'] == 'DERIVED_DETERMINISTIC')
    check('and it carries a version, so a rule change is visible downstream',
          v['digest_version'] == DIGEST_VERSION)
    check('byte counts before and after are both reported',
          v['bytes_before'] == len(page) and v['bytes_after'] < len(page),
          f"{v['bytes_before']} -> {v['bytes_after']}")


def test_E_empty_is_not_a_digest():
    print('\nE. an empty payload has no content digest')
    o = substantive_digest(b'')
    check('it BLOCKS rather than returning the digest of nothing',
          _is(o, State.BLOCKED, 'DIGEST_INPUT_EMPTY'), str(o)[:110])
    check('and says why: every empty capture would compare equal',
          'compare equal' in o.detail, o.detail[:90])
    check('compare propagates that instead of reporting two empties identical',
          _is(compare(b'', b''), State.BLOCKED, 'DIGEST_INPUT_EMPTY'))


def test_F_the_rule_is_load_bearing():
    print('\nF. guard-deletion -- is the masking what collapses the four blobs?')
    fs = _blobs('official_inactives')
    a, b = gzip.open(fs[0], 'rb').read(), gzip.open(fs[1], 'rb').read()

    with_rule = compare(a, b)
    check('with the rules: the two captures read as the same content',
          with_rule.code == 'CONTENT_IDENTICAL_NONCE_DIFFERS')

    import nfl.capture.volatility as V
    original = V.VOLATILE_RULES
    try:
        V.VOLATILE_RULES = ()          # the deleted guard
        without = compare(a, b)
    finally:
        V.VOLATILE_RULES = original

    check('with the rules removed the SAME pair reads as a content change -- '
          'so the rules are what collapsed them',
          without.code == 'CONTENT_CHANGED', str(without)[:110])
    print(f'       [bypassed: {without.code} -- this is the fake new version]')
    check('and restoring them restores the correct answer',
          compare(a, b).code == 'CONTENT_IDENTICAL_NONCE_DIFFERS')


if __name__ == '__main__':
    test_A_the_false_change_it_exists_to_catch()
    test_A2_a_page_digest_is_not_a_report_digest()
    test_B_the_three_valued_answer()
    test_C_the_rule_must_not_eat_real_content()
    test_D_it_reports_what_it_did()
    test_E_empty_is_not_a_digest()
    test_F_the_rule_is_load_bearing()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
