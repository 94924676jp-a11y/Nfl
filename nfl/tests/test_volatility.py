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
PASSED = FAILED = BLOCKED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')


def blocked(label, why):
    """A check that could not run. Counted apart and never as a pass."""
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label} -- {why}')


def _is(o, state, code=None):
    return (isinstance(o, Outcome) and o.state is state
            and (code is None or o.code == code))


def _blobs(stem):
    return sorted(VINTAGE.glob(f'{stem}.*.html.gz'))


def _nonce_pair(stem):
    """Two captures that differ ONLY by the render nonce, chosen by content.

    THIS IS THE THIRD TIME THE GROWING CAPTURE SERIES HAS BROKEN A TEST OF MINE
    that assumed a fixed snapshot of it. Sections B and F used blobs[0] and
    blobs[1] -- whichever two sorted first -- and asserted they were the same
    page. That held for the four blobs that existed when it was written and
    stopped holding as the bot captured more, because some pairs now differ for
    real (see A2).

    The property under test was never about those two files; it is that a pair
    sharing a substantive digest is reported as nonce-differing. So the pair is
    now SELECTED by that property, and if no such pair exists the test says so
    rather than passing on whatever happened to sort first.
    """
    groups = collections.defaultdict(list)
    for f in _blobs(stem):
        b = gzip.open(f, 'rb').read()
        groups[substantive_digest(b).value['digest']].append(b)
    for blobs in groups.values():
        for i in range(len(blobs)):
            for j in range(i + 1, len(blobs)):
                if blobs[i] != blobs[j]:
                    return blobs[i], blobs[j]
    return None, None


def _changed_pair(stem):
    """Two captures whose substantive content genuinely differs, or (None, None)."""
    groups = collections.defaultdict(list)
    for f in _blobs(stem):
        b = gzip.open(f, 'rb').read()
        groups[substantive_digest(b).value['digest']].append(b)
    keys = list(groups)
    if len(keys) < 2:
        return None, None
    return groups[keys[0]][0], groups[keys[1]][0]


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
        # WITHDRAWN 2026-09-07, owner directive. This used to assert
        #     len(subs) <= max(2, len(raws) // 3)
        # which is a LIVE-DATA RATIO, not an invariant. It was calibrated at 8
        # blobs and failed at 43/15 for an entirely legitimate reason: as the
        # season approaches, the page's embedded broadcast listing is edited
        # ("Week 1 NFL action at" -> "Week 1 NFL at", "NFL Week 3" -> "Week 1"),
        # so genuine page versions accumulate. Counting them is measuring the
        # season, not the mask. The ratio is not loosened, incremented, rekeyed
        # to today's count, deleted or xfailed -- it is replaced by section N,
        # which tests the property it was standing in for: render-only churn
        # collapses, genuine content survives.
        check(f'{stem}: the mask never INCREASES distinctness',
              len(subs) <= len(raws), f'{len(subs)} vs {len(raws)}')
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
    a, b = _nonce_pair('official_inactives')
    if a is None:
        blocked('the nonce-differing comparison',
                'no two captures of official_inactives currently share a '
                'substantive digest while differing in bytes')
        return
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
    a, b = _nonce_pair('official_inactives')
    if a is None:
        blocked('the guard-deletion proof',
                'no nonce-only pair currently exists to replay')
        return
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




# ==========================================================================
# N. THE INVARIANT THE WITHDRAWN RATIO WAS STANDING IN FOR
#
# Owner directive, 2026-09-07: the durable property is not "few substantive
# digests". It is
#
#     presentation/render-only churn collapses under the substantive digest,
#     while genuine football-content changes remain distinct.
#
# Eight required proofs, constructed where a controlled mutation is the only
# honest way to isolate one variable, and drawn from the live series where a
# real historical example exists.
# ==========================================================================
import random as _random
import re as _re

_UUID = _re.compile(rb'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
                    rb'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')


def _fresh_uuid(rng):
    h = '%032x' % rng.getrandbits(128)
    return f'{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}'.encode()


def _rotate_nonces(raw, seed=7):
    """Rotate ONLY the UUIDs sitting in the two declared nonce positions."""
    rng = _random.Random(seed)
    out = raw
    for rx in (_re.compile(rb'(data-jsonid=")[0-9a-fA-F-]{36}(")'),
               _re.compile(rb'(<script id=")[0-9a-fA-F-]{36}(")')):
        out = rx.sub(lambda m: m.group(1) + _fresh_uuid(rng) + m.group(2), out)
    return out


def _any_blob(stem='official_injury_report'):
    fs = _blobs(stem)
    return gzip.open(fs[0], 'rb').read() if fs else None


def _dig(b):
    return substantive_digest(b).value['digest']


def _raw(b):
    return hashlib.sha256(b).hexdigest()


def test_N1_nonce_rotation_collapses():
    print('\nN1. identical content, rotated render nonce -> collapses')
    b = _any_blob()
    if b is None:
        check('a captured page exists to mutate', False, 'no blobs')
        return
    r = _rotate_nonces(b)
    n_before = substantive_digest(b).value['neutralised']
    check('the rotation actually changed the bytes', r != b)
    check('the raw digests differ, as they must', _raw(r) != _raw(b))
    check('the substantive digests are IDENTICAL', _dig(r) == _dig(b),
          f'{_dig(b)[:12]} vs {_dig(r)[:12]}')
    o = compare(b, r)
    check('and compare() names it as the nonce, not a content change',
          o.value == 'CONTENT_IDENTICAL_NONCE_DIFFERS', str(o)[:90])
    print(f'       [{sum(n_before.values())} nonce tokens rotated; '
          f'raw changed, content did not]')


def test_N2_the_declared_mask_scope_is_exactly_what_it_claims():
    """Requirement 2, read honestly.

    "Presentation-only churn collapses WHERE INTENDED." Intent here is the
    declared rule set, and it is exactly two rules, both anchored to an
    attribute position. Whitespace and serialization churn are deliberately
    OUTSIDE it: no rule was ever declared for them and none was measured on
    these pages. Adding one to make a test pass would be an unmeasured mask,
    and the module's own bar -- "structurally incapable of expressing an
    injury, a status or a roster fact" -- is not something whitespace has been
    shown to meet on a page whose tables are whitespace-formatted. So this
    section proves the boundary rather than pretending it is elsewhere.
    """
    print('\nN2. the declared masking scope, and its deliberate boundary')
    names = [r[0] for r in VOLATILE_RULES]
    check('exactly two rules are declared', len(VOLATILE_RULES) == 2, str(names))
    check('both are anchored to an attribute position, not a bare UUID',
          all(b'data-jsonid="' in r[1].pattern or b'<script id="' in r[1].pattern
              for r in VOLATILE_RULES),
          str([r[1].pattern for r in VOLATILE_RULES]))
    check('every rule carries a stated reason it cannot express content',
          all(isinstance(r[3], str) and len(r[3]) > 30 for r in VOLATILE_RULES))
    b = _any_blob()
    ws = b.replace(b'\n', b'\n ', 1)
    check('whitespace churn is NOT collapsed -- no rule is declared for it, '
          'and inventing one here would be an unmeasured mask',
          _dig(ws) != _dig(b))
    check('and the module says so by reporting what it neutralised',
          set(substantive_digest(b).value['neutralised']) == set(names))
    # A bare UUID in a data field must survive: this is the 4,821-token defect
    # the first version of the rule would have caused in weekly_rosters.
    payload = b'sportradar_id,0ce48193-e2fa-466e-a986-33f751add206,Rodgers'
    other = b'sportradar_id,11111111-2222-3333-4444-555555555555,Rodgers'
    check('a UUID in a DATA field is not masked -- it is a player identity',
          _dig(payload) != _dig(other))


def test_N3_genuine_content_changes_survive():
    print('\nN3. a genuine player/status change does NOT collapse')
    b = _any_blob()
    muts = [
        ('a report status', b'Questionable', b'Out'),
        ('a practice status', b'Did Not Participate In Practice',
         b'Full Participation in Practice'),
        ('an injury text', b'Knee', b'Hamstring'),
    ]
    n_applied = 0
    for label, a, c in muts:
        if a not in b:
            print(f'       [{label}: token {a!r} not present in this capture]')
            continue
        m = b.replace(a, c, 1)
        n_applied += 1
        check(f'{label}: changing it changes the substantive digest',
              _dig(m) != _dig(b))
        check(f'{label}: and compare() calls it a real new version',
              compare(b, m).value == 'CONTENT_CHANGED')
    check('at least one real content mutation was exercised', n_applied >= 1,
          str(n_applied))
    # And the mutation must survive nonce rotation on top of it.
    for label, a, c in muts:
        if a in b:
            m = _rotate_nonces(b.replace(a, c, 1), seed=99)
            check('a content change plus a nonce rotation is still a content '
                  'change', compare(b, m).value == 'CONTENT_CHANGED')
            break


def test_N4_raw_sha_stays_distinct():
    print('\nN4. the raw digest is untouched by any of this')
    b = _any_blob()
    r = _rotate_nonces(b)
    check('different raw bytes give different raw sha256', _raw(r) != _raw(b))
    check('identical raw bytes give identical raw sha256', _raw(b) == _raw(b))
    fs = _blobs('official_injury_report')
    raws = [_raw(gzip.open(f, 'rb').read()) for f in fs]
    check('and every live capture still has its own raw digest',
          len(set(raws)) == len(raws), f'{len(set(raws))} of {len(raws)}')


def test_N5_the_digest_is_derivative_not_a_replacement():
    print('\nN5. the substantive digest never replaces raw provenance')
    b = _any_blob()
    v = substantive_digest(b).value
    check('the value carries the raw sha256 alongside it',
          v['raw_sha256'] == _raw(b))
    check('and labels itself derived', v['authority'] == 'DERIVED_DETERMINISTIC')
    check('and carries its own version', v['digest_version'] == DIGEST_VERSION)
    check('the two digests are different values', v['digest'] != v['raw_sha256'])
    # Provenance and discharge must key on the RAW digest, never on this one.
    import inspect
    from nfl.capture import coverage as _C
    src = inspect.getsource(_C._blob_ok)
    check('coverage._blob_ok verifies the RAW sha256, not the substantive one',
          'sha256' in src and 'substantive' not in src, src[:0] or 'see source')
    for mod in ('nfl/capture/coverage.py', 'nfl/capture/execution.py'):
        t = pathlib.Path(_REPO / mod).read_text()
        check(f'{mod} does not import or key anything on the substantive digest',
              'substantive_digest' not in t)


def test_N6_historical_render_only_duplication_collapses():
    print('\nN6. real captures that differ ONLY by nonce, from the live series')
    total_pairs = 0
    for stem in ('official_inactives', 'official_injury_report'):
        fs = _blobs(stem)
        by = collections.defaultdict(list)
        for f in fs:
            by[_dig(gzip.open(f, 'rb').read())].append(f)
        collapsed = [(d, g) for d, g in by.items() if len(g) > 1]
        check(f'{stem}: at least one group of captures collapses',
              bool(collapsed), f'{len(by)} groups from {len(fs)} blobs')
        for _d, g in collapsed:
            a, c = gzip.open(g[0], 'rb').read(), gzip.open(g[1], 'rb').read()
            total_pairs += 1
            check(f'{stem}: {g[0].name[:38]} vs {g[1].name[:38]} -- raw differs',
                  _raw(a) != _raw(c))
            check(f'{stem}: and compare() reports the nonce, not a change',
                  compare(a, c).value == 'CONTENT_IDENTICAL_NONCE_DIFFERS')
            break
    check('the live series really does contain render-only duplication',
          total_pairs >= 1, str(total_pairs))


def test_N7_historical_genuine_changes_survive():
    print('\nN7. real captures that differ for a REAL reason stay distinct')
    fs = _blobs('official_injury_report')
    by = collections.defaultdict(list)
    for f in fs:
        by[_dig(gzip.open(f, 'rb').read())].append(f)
    groups = sorted(by.items(), key=lambda kv: -len(kv[1]))
    if len(groups) < 2:
        print('       [only one page version captured so far]')
        check('at least one version exists', len(groups) >= 1)
        return
    a = gzip.open(groups[0][1][0], 'rb').read()
    c = gzip.open(groups[1][1][0], 'rb').read()
    check('two live captures are substantively different',
          compare(a, c).value == 'CONTENT_CHANGED')

    def masked(x):
        for _n, rx, rep, _w in VOLATILE_RULES:
            x = rx.sub(rep, x)
        return x

    ma, mc = masked(a), masked(c)
    check('they still differ AFTER masking -- so it is not the nonce',
          ma != mc)
    # The differing region must not itself be UUID-shaped: if it were, the mask
    # would be leaking a nonce and that WOULD be a production defect. Compared
    # LINE BY LINE. A byte-level SequenceMatcher over two 200KB pages is
    # quadratic and hung the suite; line granularity is both fast and what a
    # human would actually read.
    la, lc = ma.split(b'\n'), mc.split(b'\n')
    check('the two masked pages have the same line count -- so the difference '
          'is a substitution, not a structural rewrite',
          len(la) == len(lc), f'{len(la)} vs {len(lc)}')
    difflines = [(i, x, y) for i, (x, y) in enumerate(zip(la, lc)) if x != y]
    check('only a small number of lines differ', 0 < len(difflines) <= 5,
          str(len(difflines)))
    # The test has to isolate the DIFFERING REGION, not the line. The first
    # version asked whether the differing LINE carried a UUID and failed --
    # correctly, and for the wrong reason: line 62 is a single 42KB embedded
    # JSON blob that legitimately contains broadcast UUIDs a long way from
    # anything that changed. Comparing comma-separated tokens keeps the pieces
    # small enough to name exactly what moved, and is linear where a byte-level
    # SequenceMatcher on 42KB is not.
    import difflib
    changed_tokens = []
    for _i, x, y in difflines:
        tx, ty = x.split(b','), y.split(b',')
        sm = difflib.SequenceMatcher(None, tx, ty, autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != 'equal':
                changed_tokens.extend(tx[i1:i2] + ty[j1:j2])
    check('the differing region is a handful of tokens, not the whole line',
          0 < len(changed_tokens) <= 40, str(len(changed_tokens)))
    uuidish = [t for t in changed_tokens if _UUID.search(t)]
    check('and not one CHANGED token is UUID-shaped -- the mask is not '
          'leaking a nonce', not uuidish, str(uuidish[:3]))
    print(f'       [{len(changed_tokens)} changed tokens, 0 UUID-shaped; '
          f'first: {changed_tokens[0][:80]!r}]')
    i, x, y = difflines[0]
    lo = next((k for k in range(min(len(x), len(y))) if x[k] != y[k]), 0)
    print(f'       [line {i} differs from byte {lo}; the difference is '
          f'editorial page copy, not a token]')
    print(f'         A: {x[max(0, lo - 45):lo + 45]!r}')
    print(f'         B: {y[max(0, lo - 45):lo + 45]!r}')
    ctx = x[max(0, lo - 400):lo + 400]
    check('the differing text is page prose, not a token',
          b'NFL' in ctx or b'Description' in ctx,
          x[max(0, lo - 60):lo + 60].decode('utf8', 'replace'))


def test_N8_guard_deletion_collapse_disappears():
    print('\nN8. GUARD DELETION -- empty the rule set and the nonce reads as a '
          'content change')
    import nfl.capture.volatility as VOL
    b = _any_blob()
    r = _rotate_nonces(b)
    check('with the rules: the rotation is recognised as the nonce',
          compare(b, r).value == 'CONTENT_IDENTICAL_NONCE_DIFFERS')
    original = VOL.VOLATILE_RULES
    try:
        VOL.VOLATILE_RULES = ()
        leaked = VOL.compare(b, r).value
    finally:
        VOL.VOLATILE_RULES = original
    check('with the rules deleted: the SAME pair reads as CONTENT_CHANGED -- '
          'so the rule set is what collapses it',
          leaked == 'CONTENT_CHANGED', str(leaked))
    # And the second guard: dropping only the script-id rule must still leave
    # the jsonid rule doing its job on a page that carries both.
    fs = _blobs('official_inactives')
    if fs:
        bb = gzip.open(fs[0], 'rb').read()
        rr = _rotate_nonces(bb, seed=11)
        try:
            VOL.VOLATILE_RULES = original[:1]
            partial = VOL.compare(bb, rr).value
        finally:
            VOL.VOLATILE_RULES = original
        check('dropping the script-id rule alone breaks the collapse on a page '
              'that carries both nonce positions',
              partial == 'CONTENT_CHANGED', str(partial))


if __name__ == '__main__':
    test_A_the_false_change_it_exists_to_catch()
    test_A2_a_page_digest_is_not_a_report_digest()
    test_B_the_three_valued_answer()
    test_C_the_rule_must_not_eat_real_content()
    test_D_it_reports_what_it_did()
    test_E_empty_is_not_a_digest()
    test_F_the_rule_is_load_bearing()
    test_N1_nonce_rotation_collapses()
    test_N2_the_declared_mask_scope_is_exactly_what_it_claims()
    test_N3_genuine_content_changes_survive()
    test_N4_raw_sha_stays_distinct()
    test_N5_the_digest_is_derivative_not_a_replacement()
    test_N6_historical_render_only_duplication_collapses()
    test_N7_historical_genuine_changes_survive()
    test_N8_guard_deletion_collapse_disappears()
    tail = f', {BLOCKED} blocked' if BLOCKED else ''
    print(f'\n{PASSED} passed, {FAILED} failed{tail}')
    sys.exit(1 if FAILED else 0)
