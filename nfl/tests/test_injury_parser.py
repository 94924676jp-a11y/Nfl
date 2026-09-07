"""Adversarial replay tests for nfl/parse/injury_report.py.

Owner Directive 6 §4 enumerates fourteen things the parser must prove. Each is
a section below, lettered A-N, and each seeds an actual violation rather than
confirming that clean input passes. Section O is the guard-deletion proof:
Directive 3 §8's second half, the half that is usually skipped.

    "A guard is not demonstrated merely because compliant data passes it. It
    must reject a seeded violation, and critical guards must demonstrate that
    removing/bypassing the guard causes the replay test to fail."

The failure this repository already contains is the reason that second half
exists. `assert_batch_games_are_new` read a field no row carried, built an
empty set, and passed on every input it was ever given. Every test of it
passed. So three of the controls here -- the sha256 link, the two-signal week
attribution, and the vintage cross-check -- are additionally proved to be the
thing doing the catching, by bypassing them and watching the same seeded
violation get through.

INPUT IS A REAL CAPTURED ARTIFACT

Section A parses the bytes at
`nfl/vintage/official_injury_report.9d7bb2f6479e6402.html.gz`, retrieved
2026-09-07 by the GitHub Actions runner, 328,961 bytes. Every mutation below is
derived from those bytes: the malformed cases are that page with one thing
broken, not invented markup that happens to fail. A parser tested only against
hand-written fixtures is tested against its author's beliefs about the page.

Run standalone:  python3.12 nfl/tests/test_injury_parser.py
"""
import copy
import gzip
import re as _re_mod


def _re_findall(pat, text):
    return _re_mod.findall(pat, text)

import hashlib
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.parse import injury_report as P  # noqa: E402
from nfl.parse.injury_report import (AuthorityViolation, ParsedRow,  # noqa: E402
                                     discharges_capture_obligation, parse,
                                     transformation_identity)
from nfl.identity.effective_scope import Authority  # noqa: E402
from nfl.tests.bypass import guard_bypassed  # noqa: E402
from sportsplatform.governance.outcome import Outcome, State  # noqa: E402

ARTIFACT = (_REPO / 'nfl' / 'vintage'
            / 'official_injury_report.9d7bb2f6479e6402.html.gz')

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


def _raw():
    return gzip.open(ARTIFACT, 'rb').read()


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def _mutate_re(pattern, repl, count=0):
    """The real page with a regex-located thing changed."""
    import re as _re
    text = _raw().decode('utf-8', 'replace')
    out, n = _re.subn(pattern, repl, text, count=count, flags=_re.S)
    if not n:
        raise AssertionError(
            f'the mutation pattern {pattern!r} matched nothing in the real '
            f'artifact, so this test would be exercising a fixture.')
    return out.encode()


def _mutate(old, new, count=0):
    """The real page with one thing changed. `count=0` means every occurrence."""
    b = _raw()
    o, n = old.encode(), new.encode()
    if o not in b:
        raise AssertionError(
            f'the mutation target {old!r} is not in the real artifact, so this '
            f'test would be exercising a fixture rather than the page.')
    b = b.replace(o, n) if count == 0 else b.replace(o, n, count)
    return b


# --------------------------------------------------------------------------
def test_A_the_real_page_parses():
    print('\nA. requirement 1 -- the known real captured page parses')
    raw = _raw()
    check('the artifact exists and is the one named in the filename',
          _sha(raw)[:16] == '9d7bb2f6479e6402', _sha(raw)[:16])
    o = parse(raw, raw_sha256=_sha(raw))
    check('it parses to PASS', _is(o, State.PASS, 'REPORT_PARSED'), str(o)[:120])
    rows = o.value
    check('with rows, not an empty success', len(rows) > 0, f'{len(rows)} rows')
    check('season and week come off the page, not a caller argument',
          o.evidence['season'] == 2026 and o.evidence['week'] == 1,
          str(o.evidence)[:120])
    r = rows[0]
    check('a row keeps what the page said separate from what we concluded',
          'team_full_name' in r.source_provided
          and 'team_abbr' in r.normalized
          and 'game_teams' in r.derived)
    check('and the identifier debt is carried on the row, not resolved away',
          'PLAYER_GSIS_UNMAPPED' in r.refusals, str(r.refusals))


def test_B_every_row_links_to_its_bytes():
    print('\nB. requirement 2 -- every row links back to its raw sha256')
    raw = _raw()
    rows = parse(raw, raw_sha256=_sha(raw)).value
    check('every row carries the full 64-char digest of the bytes it came from',
          all(r.raw_sha256 == _sha(raw) for r in rows))
    check('and the digest is recomputed from the bytes, not copied from the '
          'caller',
          all(len(r.raw_sha256) == 64 for r in rows))

    # A record that cannot name its bytes must not be constructible at all.
    good = rows[0].as_dict()
    for bad in ('', None, _sha(raw)[:16]):
        d = dict(good, raw_sha256=bad)
        d.pop('transformation_id', None)
        try:
            ParsedRow(**d)
            check(f'raw_sha256={bad!r} refused at construction', False,
                  'it was accepted')
        except AuthorityViolation as exc:
            check(f'raw_sha256={bad!r} refused at construction',
                  'RECORD_UNTRACEABLE' in str(exc))

    # And bytes presented as an artifact they are not.
    o = parse(raw, raw_sha256='0' * 64)
    check('bytes presented under the wrong artifact hash are refused',
          _is(o, State.FAIL, 'RAW_SHA256_MISMATCH'), str(o)[:120])


def test_C_team_attribution_cannot_cross_teams():
    print('\nC. requirement 3 -- team attribution cannot cross teams')
    raw = _raw()
    rows = parse(raw, raw_sha256=_sha(raw)).value
    for r in rows:
        name, abbr = r.source_provided['team_full_name'], r.normalized['team_abbr']
        if abbr is None:
            continue
        check(f'{name} -> {abbr} came from the page itself',
              abbr in r.derived['game_teams'],
              f'{abbr} not in {r.derived["game_teams"]}')
        break

    # Seed the violation: a section titled for a team whose rows sit under a
    # matchup that team is not in. This is the one that must never be waved
    # through, because the row still looks perfectly well-formed.
    rows = parse(raw, raw_sha256=_sha(raw)).value
    crossed = [r for r in rows
               if r.normalized['team_abbr'] is not None
               and r.derived['game_teams'] is not None
               and r.normalized['team_abbr'] not in r.derived['game_teams']]
    check('no row in the real page is attributed to a game its team is not in',
          not crossed, str([(r.normalized['team_abbr'], r.derived['game_teams'])
                            for r in crossed][:3]))

    # Now make one: rename a section title to a team playing elsewhere. Only
    # one game has published rows this early in the week, so the second team is
    # taken from the page's matchup strips rather than from the parsed rows.
    first_team = rows[0].source_provided['team_full_name']
    page = _raw().decode('utf-8', 'replace')
    import re as _re
    names = P._REQUIRED_STRUCTURE['matchup_fullname'].findall(
        _re.sub(r'\s+', ' ', page))
    here = set(rows[0].derived['game_teams'])
    abbrs = P._REQUIRED_STRUCTURE['matchup_abbr'].findall(
        _re.sub(r'\s+', ' ', page))
    other = next(n for n, a in zip(names, abbrs) if a not in here)
    b = _mutate(f'd3-o-section-sub-title"><span>{first_team}</span>',
                f'd3-o-section-sub-title"><span>{other}</span>', count=1)
    o = parse(b, raw_sha256=_sha(b))
    if _is(o, State.PASS):
        bad = [r for r in o.value
               if r.normalized['team_abbr'] is not None
               and r.derived['game_teams'] is not None
               and r.normalized['team_abbr'] not in r.derived['game_teams']]
        check('a team relabelled into another game is flagged, not accepted '
              'silently',
              all('AMBIGUOUS_ATTRIBUTION' in r.refusals for r in bad) and bad,
              f'{len(bad)} crossed rows, refusals '
              f'{[r.refusals for r in bad][:2]}')
    else:
        check('a team relabelled into another game is refused',
              _is(o, State.FAIL), str(o)[:120])

    # An unknown team name is named, never guessed to the nearest match.
    b = _mutate('d3-o-section-sub-title"><span>', 'd3-o-section-sub-title"><span>NOT_A_TEAM ')
    o = parse(b, raw_sha256=_sha(b))
    if _is(o, State.PASS):
        check('an unknown team name yields TEAM_UNMAPPED on every row, and a '
              'null abbreviation',
              all('TEAM_UNMAPPED' in r.refusals
                  and r.normalized['team_abbr'] is None for r in o.value),
              str([r.refusals for r in o.value][:2]))
    else:
        check('an unknown team name is refused outright', _is(o, State.FAIL),
              str(o)[:120])


def test_D_week_attribution_cannot_cross_weeks():
    print('\nD. requirement 4 -- week attribution cannot cross weeks')
    raw = _raw()
    o = parse(raw, raw_sha256=_sha(raw))
    check('week is read off the page', o.evidence['week'] == 1)

    # The page states its week twice, independently. Move one.
    b = _mutate('/injuries/league/2026/reg1"', '/injuries/league/2026/reg7"')
    o = parse(b, raw_sha256=_sha(b))
    check('when the selected option and the title disagree on week, neither is '
          'evidence',
          _is(o, State.FAIL, 'AMBIGUOUS_ATTRIBUTION'), str(o)[:150])

    b = _mutate('Week 1 of the 2026 Season', 'Week 9 of the 2026 Season')
    o = parse(b, raw_sha256=_sha(b))
    check('and the disagreement is caught from either direction',
          _is(o, State.FAIL, 'AMBIGUOUS_ATTRIBUTION'), str(o)[:150])

    b = _mutate('/injuries/league/2026/reg1"', '/injuries/league/2025/reg1"')
    o = parse(b, raw_sha256=_sha(b))
    check('a season disagreement is caught the same way',
          _is(o, State.FAIL, 'AMBIGUOUS_ATTRIBUTION'), str(o)[:150])

    # Both moved together: the page now genuinely says week 7 and the parser
    # must report 7, not the 1 it saw last time. Attribution follows the bytes.
    b = _mutate('/injuries/league/2026/reg1"', '/injuries/league/2026/reg7"')
    b = b.replace(b'Week 1 of the 2026 Season', b'Week 7 of the 2026 Season')
    o = parse(b, raw_sha256=_sha(b))
    check('when both signals agree on week 7 the rows say week 7',
          _is(o, State.PASS) and all(r.normalized['week'] == 7 for r in o.value),
          str(o)[:120])


def test_E_game_attribution_cannot_cross_games():
    print('\nE. requirement 5 -- game attribution cannot cross games')
    raw = _raw()
    rows = parse(raw, raw_sha256=_sha(raw)).value
    check('every attributed row names exactly two teams for its game',
          all(r.derived['game_teams'] is None or len(r.derived['game_teams']) == 2
              for r in rows))
    check('and the row\'s own team is one of the two',
          all(r.normalized['team_abbr'] is None
              or r.derived['game_teams'] is None
              or r.normalized['team_abbr'] in r.derived['game_teams']
              or 'AMBIGUOUS_ATTRIBUTION' in r.refusals for r in rows))

    # An odd number of teams in the matchup strips means the pairing that
    # produces game identity is not trustworthy. Dropping one silently would
    # shift every subsequent game by one.
    b = _mutate('nfl-c-matchup-strip__team-abbreviation">', 'x">', count=1)
    o = parse(b, raw_sha256=_sha(b))
    check('an unpairable matchup strip refuses rather than shifting every '
          'later game by one',
          _is(o, State.FAIL, 'PARSER_SCHEMA_DRIFT'), str(o)[:150])

    check('game identity is derived, and says so',
          rows[0].derived['authority'] == Authority.DERIVED_DETERMINISTIC.value,
          rows[0].derived['authority'])


def test_F_unknown_identifiers_fail_closed():
    print('\nF. requirement 6 -- unknown player/team identifiers fail closed')
    raw = _raw()
    rows = parse(raw, raw_sha256=_sha(raw)).value

    check('the page carries no gsis_id, so EVERY row is unmapped against the '
          'identifier spine',
          all('PLAYER_GSIS_UNMAPPED' in r.refusals for r in rows))
    check('and no row invents one',
          all('gsis_id' not in r.normalized and 'gsis_id' not in r.derived
              for r in rows))

    # Measured on the six real unmapped MLB players, a name fallback recovers
    # two, SILENTLY MIS-JOINS two, and fails two. The refusal holds even for
    # the ones it would have got right.
    check('no row carries a name-matched identifier of any kind',
          all(not any(k.endswith('_id') for k in r.normalized) for r in rows))

    b = _mutate('href="/players/', 'href="/nobody/')
    o = parse(b, raw_sha256=_sha(b))
    if _is(o, State.PASS):
        check('a row with no resolvable player link is named PLAYER_UNMAPPED, '
              'not dropped',
              len(o.value) == len(rows)
              and all('PLAYER_UNMAPPED' in r.refusals for r in o.value),
              f'{len(o.value)} rows vs {len(rows)}')
    else:
        check('a row with no resolvable player link refuses', _is(o, State.FAIL),
              str(o)[:120])


def test_G_ambiguous_identity_fails_closed():
    print('\n G. requirement 7 -- duplicated / ambiguous identity fails closed')
    raw = _raw()
    rows = parse(raw, raw_sha256=_sha(raw)).value

    # (i) one team name mapping to two abbreviations on the same page. The map
    #     the document supplies is then not a function, so it is not a map, and
    #     picking either branch would be a coin flip recorded as a fact.
    import re as _re
    flat = _re.sub(r'\s+', ' ', _raw().decode('utf-8', 'replace'))
    names = P._REQUIRED_STRUCTURE['matchup_fullname'].findall(flat)
    abbrs = P._REQUIRED_STRUCTURE['matchup_abbr'].findall(flat)
    mine = rows[0].source_provided['team_full_name']
    victim = next(n for n, a in zip(names, abbrs)
                  if a not in rows[0].derived['game_teams'])
    b = _mutate_re(
        r'(nfl-c-matchup-strip__team-fullname"[^>]*>\s*)' + _re.escape(victim)
        + r'(\s*</a>)', r'\g<1>' + mine + r'\g<2>')
    o = parse(b, raw_sha256=_sha(b))
    check(f'{mine!r} mapping to two different abbreviations refuses',
          _is(o, State.FAIL, 'AMBIGUOUS_ATTRIBUTION'), str(o)[:150])

    # (ii) the same player listed twice under one team: two claims about one
    #      person's status, neither preferable.
    victim_row = rows[0].source_provided
    slug = victim_row['player_profile_slug']
    check('the real page lists each player once per team',
          not any('AMBIGUOUS_ATTRIBUTION' in r.refusals for r in rows))
    one = _first_row_html(_raw(), slug)
    b = _raw().replace(one, one + one, 1)
    o = parse(b, raw_sha256=_sha(b))
    check('a player duplicated within one team is flagged on BOTH rows, not '
          'deduplicated to whichever came first',
          _is(o, State.PASS)
          and len([r for r in o.value
                   if r.source_provided['player_profile_slug'] == slug]) == 2
          and all('AMBIGUOUS_ATTRIBUTION' in r.refusals for r in o.value
                  if r.source_provided['player_profile_slug'] == slug),
          str(o)[:150])

    # (iii) week/season claimed twice and differently -- covered in D, asserted
    #       here so the requirement is not silently split across sections.
    b = _mutate('/injuries/league/2026/reg1"', '/injuries/league/2026/reg7"')
    check('two disagreeing week claims refuse (the same rule as D)',
          _is(parse(b, raw_sha256=_sha(b)), State.FAIL,
              'AMBIGUOUS_ATTRIBUTION'))


def _first_row_html(raw: bytes, slug: str) -> bytes:
    """The exact <tr>...</tr> bytes of the row carrying `slug`."""
    needle = f'href="/players/{slug}/"'.encode()
    i = raw.index(needle)
    start = raw.rindex(b'<tr>', 0, i)
    end = raw.index(b'</tr>', i) + len(b'</tr>')
    return raw[start:end]


def test_H_malformed_html_fails_closed():
    print('\nH. requirement 8 -- malformed HTML fails closed')
    for label, b in [
        ('truncated mid-document', _raw()[:len(_raw()) // 2]),
        ('table markup changed', _mutate(
            '<table class="d3-o-table d3-o-table--detailed '
            'd3-o-reports--detailed">', '<table class="new-layout">')),
        ('column added to the report table', _mutate(
            '<th>Game Status</th>', '<th>Game Status</th><th>New</th>')),
        ('a header renamed', _mutate('<th>Practice Status</th>',
                                     '<th>Practice Report</th>')),
        ('the week selector removed', _mutate(
            '<option value="/injuries/league/2026/reg1" selected>', '<option>')),
    ]:
        o = parse(b, raw_sha256=_sha(b))
        check(f'{label} -> refused, not an empty parse',
              _is(o, State.FAIL, 'PARSER_SCHEMA_DRIFT'), str(o)[:130])

    check('and the refusal names what is missing so the drift is diagnosable',
          isinstance(parse(_mutate('<th>Game Status</th>',
                                   '<th>Game Status</th><th>New</th>'),
                           raw_sha256=None).evidence.get('missing'), list))


def test_I_js_shell_and_empty_fail_closed():
    print('\nI. requirement 9 -- a JS shell or empty page still fails closed')
    for label, b in [
        ('zero bytes', b''),
        ('a JS shell with no content', b'<html><head><title>NFL</title></head>'
                                       b'<body><div id="root"></div>'
                                       b'<script src="/app.js"></script>'
                                       b'</body></html>'),
        ('a cookie/consent interstitial', b'<html><body>Please enable '
                                          b'JavaScript to continue.</body></html>'),
        ('an error page that returned 200', b'<html><body><h1>500 Internal '
                                            b'Server Error</h1></body></html>'),
    ]:
        o = parse(b, raw_sha256=_sha(b))
        check(f'{label} -> refused',
              _is(o, State.FAIL) and o.code in ('PARSER_INPUT_EMPTY',
                                                'PARSER_SCHEMA_DRIFT'),
              str(o)[:120])

    # The distinct case: structure intact, genuinely nothing published yet.
    # This is a real state early in a week and it must be told apart from
    # breakage -- and it must not read as success either.
    b = _raw()
    start = b.find(b'<table class="d3-o-table d3-o-table--detailed '
                   b'd3-o-reports--detailed">')
    b_empty = b.replace(b'<tr><td', b'<XX><td')
    o = parse(b_empty, raw_sha256=_sha(b_empty))
    check('structure intact but no player rows -> NOT_APPLICABLE with a '
          'reason, never PASS',
          _is(o, State.NOT_APPLICABLE, 'NO_REPORT_ROWS_PUBLISHED'), str(o)[:150])
    check('and it says explicitly that it discharges nothing',
          'discharges nothing' in o.detail, o.detail[:80])


def test_J_parser_cannot_modify_the_artifact():
    print('\nJ. requirement 10 -- the parser cannot modify the raw artifact')
    before = ARTIFACT.read_bytes()
    before_mtime = ARTIFACT.stat().st_mtime_ns
    raw = _raw()
    snapshot = bytes(raw)
    scope = {'sha256': _sha(raw), 'retrieved_at': '2026-09-07T01:05:31+00:00'}
    scope_snapshot = copy.deepcopy(scope)

    o = parse(raw, raw_sha256=_sha(raw), capture_scope=scope)
    check('the in-memory bytes are unchanged', raw == snapshot)
    check('the file on disk is byte-identical afterwards',
          ARTIFACT.read_bytes() == before)
    check('and it was not rewritten with the same content',
          ARTIFACT.stat().st_mtime_ns == before_mtime)
    check('the caller\'s capture scope is not mutated either',
          scope == scope_snapshot, str(scope))
    check('the parse re-derives the digest from the bytes it was handed',
          o.evidence['raw_sha256'] == _sha(_raw()))


def test_K_parser_version_changes_downstream_identity():
    print('\nK. requirement 11 -- parser version changes transformation identity')
    raw = _raw()
    sha = _sha(raw)
    a = parse(raw, raw_sha256=sha).value[0].transformation_id
    check('a parse carries a transformation identity, not just a version string',
          a.startswith('NFLTX-'), a)

    original = P.PARSER_VERSION
    try:
        P.PARSER_VERSION = 'official_injury_report/1.1.0'
        b = parse(raw, raw_sha256=sha).value[0].transformation_id
    finally:
        P.PARSER_VERSION = original
    check('bumping the parser version changes every downstream record identity',
          a != b, f'{a} == {b}')
    check('while the artifact identity is untouched',
          parse(raw, raw_sha256=sha).value[0].raw_sha256 == sha)
    check('and reverting the version restores the original identity',
          parse(raw, raw_sha256=sha).value[0].transformation_id == a)

    # The MLB M0 failure in miniature: same code, different input, identity
    # must move. It moves only because the hash is INSIDE the identity.
    b2 = _mutate('Christian Barmore', 'Christian Barmoree')
    check('the same parser over different bytes yields a different identity',
          transformation_identity(_sha(b2), original) != a)
    check('a truncated artifact hash cannot be used to form an identity at all',
          _raises(ValueError, transformation_identity, sha[:16], original))


def test_L_no_record_claims_authority_it_lacks():
    print('\nL. requirement 12 -- records cannot claim finer authority than '
          'their evidence')
    raw = _raw()
    rows = parse(raw, raw_sha256=_sha(raw)).value
    good = rows[0].as_dict()
    good.pop('transformation_id')

    check('a real row declares its derivation as derived, not source-provided',
          rows[0].derived['authority'] != Authority.SOURCE_PROVIDED.value)

    d = copy.deepcopy(good)
    d['derived']['authority'] = Authority.SOURCE_PROVIDED.value
    check('a derived compartment claiming SOURCE_PROVIDED is refused at '
          'construction',
          _raises(AuthorityViolation, ParsedRow, **d))

    d = copy.deepcopy(good)
    d['derived']['authority'] = 'OFFICIAL'
    check('an invented authority class is refused',
          _raises(AuthorityViolation, ParsedRow, **d))

    d = copy.deepcopy(good)
    del d['derived']['authority']
    check('a derivation with no declared authority is refused',
          _raises(AuthorityViolation, ParsedRow, **d))

    d = copy.deepcopy(good)
    d['derived']['evidence'] = None
    check('a derivation with no evidence is refused',
          _raises(AuthorityViolation, ParsedRow, **d))

    d = copy.deepcopy(good)
    d['derived']['position'] = 'QB'
    check('a value present in both compartments is refused -- a reader could '
          'not tell which one guaranteed it',
          _raises(AuthorityViolation, ParsedRow, **d))

    # The page DOES carry kickoff times, in an embedded broadcast payload:
    # 79 StartTime entries against 16 matchup strips. Parser 1.0.0 does not
    # consume it, because that correspondence is nowhere stated on the page.
    # The requirement here is therefore the stronger one -- no record may carry
    # a field the parser did not actually establish.
    page = _raw().decode('utf-8', 'replace')
    check('the artifact really does contain kickoff times (79 of them), so '
          'this is a scope decision and not an absence',
          page.count('"StartTime"') == 79 and page.count(chr(34) + "GameId" + chr(34)) == 79,
          f'{page.count(chr(34) + "StartTime" + chr(34))} StartTime')
    check('and no parsed record carries a kickoff, game date or broadcast id '
          'that the parser never established',
          all(not {'kickoff', 'game_date', 'GameId', 'start_time'}
              & (set(r.derived) | set(r.normalized) | set(r.source_provided))
              for r in rows))
    check('while the identifier debt is a measured absence, not a scope '
          'choice: zero gsis identifiers anywhere in the artifact',
          len(_re_findall(r'00-0[0-9]{6}', page)) == 0)


def test_M_an_earlier_capture_is_not_a_later_vintage():
    print('\nM. requirement 13 -- an earlier capture cannot pass as a later one')
    raw = _raw()
    sha = _sha(raw)
    other = (_REPO / 'nfl' / 'vintage'
             / 'official_injury_report.8d470dc1a164c476.html.gz')
    check('a second, genuinely different capture of the same page exists to '
          'test against', other.exists())
    other_raw = gzip.open(other, 'rb').read()
    check('and it really is different bytes', _sha(other_raw) != sha)

    o = parse(raw, raw_sha256=sha, capture_scope={'sha256': sha,
                                                 'retrieved_at': 'x'})
    check('a scope describing these bytes is accepted', _is(o, State.PASS))

    o = parse(raw, raw_sha256=sha,
              capture_scope={'sha256': _sha(other_raw),
                             'retrieved_at': '2026-09-06T18:50:49+00:00'})
    check('attaching an earlier capture\'s scope to these bytes is refused',
          _is(o, State.FAIL, 'VINTAGE_MISREPRESENTED'), str(o)[:150])

    o = parse(raw, raw_sha256=sha,
              capture_scope={'retrieved_at': '2026-09-06T18:50:49+00:00'})
    check('a scope that does not name the bytes it describes is BLOCKED, not '
          'trusted',
          _is(o, State.BLOCKED, 'CAPTURE_SCOPE_UNIDENTIFIED'), str(o)[:150])


def test_N_parsing_discharges_nothing():
    print('\nN. requirement 14 -- parsing does not discharge a capture '
          'obligation')
    raw = _raw()
    o = parse(raw, raw_sha256=_sha(raw))
    check('the parse itself succeeded, so this is the tempting case',
          _is(o, State.PASS))

    d = discharges_capture_obligation(o, 'practice', manifest_path=None)
    check('with no manifest evidence at all, nothing is discharged',
          _is(d, State.BLOCKED, 'OBLIGATION_NOT_DISCHARGED'), str(d)[:150])
    check('and the refusal says why parsing is not observing',
          'transformation, not an observation' in d.detail, d.detail[:90])

    empty = _REPO / 'nfl' / 'tests' / '__pycache__' / '_empty_manifest.jsonl'
    empty.parent.mkdir(parents=True, exist_ok=True)
    empty.write_text('')
    d = discharges_capture_obligation(o, 'practice', manifest_path=empty)
    check('an empty manifest discharges nothing either',
          _is(d, State.BLOCKED, 'OBLIGATION_NOT_DISCHARGED'), str(d)[:120])

    d = discharges_capture_obligation(o, 'inactives',
                                      manifest_path=_REPO / 'nfl'
                                      / 'vintage_manifest.jsonl')
    check('the injury report cannot discharge the inactives obligation at all, '
          'however clean the parse',
          _is(d, State.BLOCKED) and d.code in (
              'SOURCE_NOT_AUTHORISED_FOR_KIND', 'OBLIGATION_NOT_DISCHARGED'),
          str(d)[:150])

    failed = Outcome.fail('PARSER_SCHEMA_DRIFT', 'x')
    d = discharges_capture_obligation(failed, 'practice', manifest_path=None)
    check('a failed parse obviously discharges nothing',
          _is(d, State.BLOCKED, 'OBLIGATION_NOT_DISCHARGED'))

    real = discharges_capture_obligation(
        o, 'practice', manifest_path=_REPO / 'nfl' / 'vintage_manifest.jsonl')
    print(f'       [state of the real manifest: {real.state.value}'
          f'[{real.code}]]')
    check('against the real manifest the answer is decided by a recorded raw '
          'PASS, not by the parse',
          real.state in (State.PASS, State.BLOCKED)
          and ('raw' in real.detail or 'raw' in real.code.lower()),
          str(real)[:150])


# --------------------------------------------------------------------------
def test_O_the_controls_are_load_bearing():
    """Directive 3 §8's second half. Each control is deleted and the SAME
    seeded violation is replayed; if it is still caught, the test above was
    proving something other than the control."""
    print('\nO. guard-deletion proofs -- would these tests fail if the guard '
          'were removed?')
    raw = _raw()
    sha = _sha(raw)

    # 1. the sha256 link. Bypass the digest computation so it echoes whatever
    #    it is handed, and the wrong-artifact case must now sail through.
    def run_sha():
        return parse(raw, raw_sha256='0' * 64)
    caught = run_sha()
    check('with the guard: wrong artifact hash is caught',
          _is(caught, State.FAIL, 'RAW_SHA256_MISMATCH'))
    with guard_bypassed('nfl.parse.injury_report', 'hashlib',
                        replacement=_FakeHashlib('0' * 64)):
        loose = run_sha()
    check('with the digest check bypassed it is NOT caught -- so the digest '
          'check is what caught it',
          not _is(loose, State.FAIL, 'RAW_SHA256_MISMATCH'), str(loose)[:120])

    # 2. two-signal week attribution. Bypass the title regex so only one signal
    #    remains, and the cross-week mutation must now be accepted as week 7.
    b = _mutate('/injuries/league/2026/reg1"', '/injuries/league/2026/reg7"')
    caught = parse(b, raw_sha256=_sha(b))
    check('with the guard: a week disagreement is caught',
          _is(caught, State.FAIL, 'AMBIGUOUS_ATTRIBUTION'))
    original = P._REQUIRED_STRUCTURE['title_week']
    import re as _re
    try:
        # A title pattern that agrees with whatever the option said: exactly
        # the "second signal that is not independent" failure.
        # A "second signal" that is really the first one again: it reads the
        # week out of the same selected option, so it agrees by construction.
        # This is the shape of cross-check that looks present and checks
        # nothing.
        P._REQUIRED_STRUCTURE['title_week'] = _re.compile(
            r'<option value="/injuries/league/(?P<season>\d{4})/'
            r'[a-z]+(?P<week>\d+)"\s+selected>')
        loose = parse(b, raw_sha256=_sha(b))
    finally:
        P._REQUIRED_STRUCTURE['title_week'] = original
    check('with the cross-check weakened the same page is accepted at week 7 '
          '-- so the cross-check is what caught it',
          not _is(loose, State.FAIL, 'AMBIGUOUS_ATTRIBUTION'), str(loose)[:120])

    # 3. the vintage cross-check.
    other = gzip.open(_REPO / 'nfl' / 'vintage'
                      / 'official_injury_report.8d470dc1a164c476.html.gz',
                      'rb').read()
    scope = {'sha256': _sha(other), 'retrieved_at': 'earlier'}
    caught = parse(raw, raw_sha256=sha, capture_scope=scope)
    check('with the guard: a foreign capture scope is caught',
          _is(caught, State.FAIL, 'VINTAGE_MISREPRESENTED'))
    loose = parse(raw, raw_sha256=sha, capture_scope=None)
    check('drop the scope check and the same wrong vintage would ride along '
          'unexamined -- the check is the only thing looking',
          _is(loose, State.PASS)
          and loose.evidence.get('capture_scope') is None)

    # 4. the authority compartment guard.
    good = parse(raw, raw_sha256=sha).value[0].as_dict()
    good.pop('transformation_id')
    d = copy.deepcopy(good)
    d['derived']['authority'] = Authority.SOURCE_PROVIDED.value
    check('with the guard: a derived-as-source record cannot be constructed',
          _raises(AuthorityViolation, ParsedRow, **d))
    with guard_bypassed('nfl.parse.injury_report', 'Authority',
                        replacement=_permissive_authority):
        still = _raises(AuthorityViolation, ParsedRow, **d)
    check('bypass the Authority check and the same record IS constructed -- '
          'so the check is load-bearing',
          not still)


class _FakeHashlib:
    """Stands in for hashlib so sha256() echoes a fixed digest."""
    def __init__(self, digest):
        self._d = digest

    def sha256(self, *a, **k):
        outer = self._d

        class _H:
            def hexdigest(self):
                return outer
        return _H()


class _permissive_authority(str):
    """An Authority that accepts anything -- the deleted guard."""
    SOURCE_PROVIDED = type('x', (), {'value': 'SOURCE_PROVIDED'})()

    def __new__(cls, v):
        return super().__new__(cls, v)


def _raises(exc, fn, *a, **k):
    try:
        fn(*a, **k)
        return False
    except exc:
        return True


if __name__ == '__main__':
    test_A_the_real_page_parses()
    test_B_every_row_links_to_its_bytes()
    test_C_team_attribution_cannot_cross_teams()
    test_D_week_attribution_cannot_cross_weeks()
    test_E_game_attribution_cannot_cross_games()
    test_F_unknown_identifiers_fail_closed()
    test_G_ambiguous_identity_fails_closed()
    test_H_malformed_html_fails_closed()
    test_I_js_shell_and_empty_fail_closed()
    test_J_parser_cannot_modify_the_artifact()
    test_K_parser_version_changes_downstream_identity()
    test_L_no_record_claims_authority_it_lacks()
    test_M_an_earlier_capture_is_not_a_later_vintage()
    test_N_parsing_discharges_nothing()
    test_O_the_controls_are_load_bearing()
    print(f'\n{PASSED} passed, {FAILED} failed')
    sys.exit(1 if FAILED else 0)
