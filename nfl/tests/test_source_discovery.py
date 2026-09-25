"""Discovery earns a pin against ten named checks, or it refuses by name.

The six cases the owner specified on 2026-09-25, plus the two that keep the pin
honest: a non-official host, and a consumer that resolves its own URL.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.capture import source_discovery as SD                   # noqa: E402

PASSED = 0
FAILED = 0

CUT = '2026-09-25T00:15:00+00:00'
REQ = {'game_id': '2026_03_ATL_GB',
       'teams': ('Falcons', 'Packers'),
       'roster_names': ('Cooper Rush', 'Jayden Reed'),
       'cutoff_utc': CUT, 'require_both_teams': True}

LANDING = ('<html><head><title>NFL Inactives</title></head><body>'
           'Please check back soon for NFL Inactive Reports for this Season'
           '</body></html>')

ARTICLE = ('<html><body><h1>Falcons vs Packers inactives</h1>'
           '<table><tbody>'
           '<tr><td>Cooper Rush</td></tr>'
           '<tr><td>Jayden Reed</td></tr>'
           '</tbody></table></body></html>')

HEADERS_ONLY = ('<html><body><h1>Falcons vs Packers inactives</h1>'
                '<table><tbody><tr><th>Player</th></tr></tbody></table>'
                '<p>Cooper Rush</p></body></html>')

WRONG_GAME = ('<html><body><h1>Chiefs vs Bills inactives</h1><table><tr><td>'
              'Patrick Mahomes</td></tr></table></body></html>')

ONE_TEAM = ('<html><body><h1>Falcons inactives</h1><table><tr><td>'
            'Cooper Rush</td></tr></table></body></html>')


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def raised(exc, fn, needle=None):
    try:
        fn()
    except exc as e:
        if needle is not None and needle not in str(e):
            return False, f'raised without {needle!r}: {e}'
        return True, ''
    except Exception as e:                                       # noqa: BLE001
        return False, f'raised {type(e).__name__} instead: {e}'
    return False, f'did not raise {exc.__name__}'


def _rows_parser(text: str):
    """Entries are <td> cells that are not header cells."""
    import re
    return [m for m in re.findall(r'<td>([^<]+)</td>', text)]


def _cand(text, url='https://www.nfl.com/inactives/', pub=CUT, store=True):
    d = {'text': text, 'url': url, 'published_at_utc': pub,
         'retrieved_at_utc': pub}
    if store:
        f = tempfile.NamedTemporaryFile('w', suffix='.html', delete=False)
        f.write(text)
        f.close()
        d['stored_path'] = f.name
    return d


def test_A_generic_landing_page_cannot_yield_rows():
    print('\nA. the current configured URL')
    r = SD.qualify(_cand(LANDING), REQ, parser=_rows_parser)
    check('it is refused', r['qualified'] is False, r['failed'])
    check('CONTENT_BEARING fails',
          r['checks']['CONTENT_BEARING'] == SD.FAIL, r['checks'])
    check('classed SOURCE_PATH_CANNOT_YIELD_ROWS',
          r['failure_class'] == SD.CANNOT_YIELD, r['failure_class'])


def test_B_a_content_bearing_official_article_passes():
    print('\nB. the artifact we actually want')
    r = SD.qualify(_cand(ARTICLE), REQ, parser=_rows_parser)
    check('all ten checks pass', r['qualified'] is True, r['failed'])
    check('two entries parsed', r['n_entries'] == 2, r['n_entries'])
    check('both clubs attributed', len(r['teams_present']) == 2,
          r['teams_present'])
    check('a digest of the STORED bytes is recorded', bool(r['sha256']))
    check('no failure class', r['failure_class'] is None, r['failure_class'])


def test_C_containers_without_entries_is_the_other_class():
    print('\nC. shape present, extractor silent')
    r = SD.qualify(_cand(HEADERS_ONLY), REQ, parser=_rows_parser)
    check('CONTENT_BEARING passes',
          r['checks']['CONTENT_BEARING'] == SD.PASS)
    check('PARSER_COMPATIBLE fails',
          r['checks']['PARSER_COMPATIBLE'] == SD.FAIL)
    check('classed CONTENT_PRESENT_EXTRACTION_EMPTY',
          r['failure_class'] == SD.EXTRACTION_EMPTY, r['failure_class'])
    check('and NOT confused with the cannot-yield class',
          r['failure_class'] != SD.CANNOT_YIELD)


def test_D_the_wrong_game_fails_attribution():
    print('\nD. a real inactives article about another game')
    r = SD.qualify(_cand(WRONG_GAME), REQ, parser=_rows_parser)
    check('GAME_ATTRIBUTION fails',
          r['checks']['GAME_ATTRIBUTION'] == SD.FAIL, r['checks'])
    check('and it is refused', r['qualified'] is False, r['failed'])
    check('PLAYER_NAME_PRESENCE also fails, independently',
          r['checks']['PLAYER_NAME_PRESENCE'] == SD.FAIL)


def test_E_one_team_does_not_discharge_a_two_team_obligation():
    print('\nE. completeness is not attribution')
    r = SD.qualify(_cand(ONE_TEAM), REQ, parser=_rows_parser)
    check('GAME_ATTRIBUTION passes on one club',
          r['checks']['GAME_ATTRIBUTION'] == SD.PASS)
    check('BOTH_TEAM_COVERAGE fails',
          r['checks']['BOTH_TEAM_COVERAGE'] == SD.FAIL)
    check('so it is refused', r['qualified'] is False, r['failed'])
    loose = SD.qualify(_cand(ONE_TEAM), dict(REQ, require_both_teams=False),
                       parser=_rows_parser)
    check('and passes when only one club is required',
          loose['checks']['BOTH_TEAM_COVERAGE'] == SD.PASS)


def test_F_publication_after_the_cut_is_illegal():
    print('\nF. discovery may range; a pin may not')
    late = SD.qualify(_cand(ARTICLE, pub='2026-09-25T02:00:00+00:00'), REQ,
                      parser=_rows_parser)
    check('CUTOFF_LEGAL fails', late['checks']['CUTOFF_LEGAL'] == SD.FAIL)
    check('and it is refused', late['qualified'] is False, late['failed'])
    unparseable = SD.qualify(_cand(ARTICLE, pub='sometime tuesday'), REQ,
                             parser=_rows_parser)
    check('an unparseable time is not a time',
          unparseable['checks']['PUBLICATION_TIME'] == SD.FAIL)


def test_G_a_non_official_host_is_not_this_source_family():
    print('\nG. a relay is a secondary source')
    r = SD.qualify(_cand(ARTICLE, url='https://www.rotowire.com/x'), REQ,
                   parser=_rows_parser)
    check('OFFICIAL_DOMAIN fails',
          r['checks']['OFFICIAL_DOMAIN'] == SD.FAIL, r['checks'])
    check('even though the content is right',
          r['checks']['CONTENT_BEARING'] == SD.PASS)


def test_H_unpreserved_bytes_and_missing_hash_fail_together():
    print('\nH. a capture that parsed and threw the bytes away')
    r = SD.qualify(_cand(ARTICLE, store=False), REQ, parser=_rows_parser)
    check('RAW_BYTES_PRESERVED fails',
          r['checks']['RAW_BYTES_PRESERVED'] == SD.FAIL)
    check('HASH_RECORDED fails with it',
          r['checks']['HASH_RECORDED'] == SD.FAIL)


def test_I_discover_pins_one_and_names_every_refusal():
    print('\nI. the pin, and what it refuses on the way')
    pages = {'https://www.nfl.com/inactives/': LANDING,
             'https://www.nfl.com/news/wrong': WRONG_GAME,
             'https://www.packers.com/news/inactives-week-3': ARTICLE}
    res = SD.discover(list(pages), REQ,
                      fetcher=lambda u: ({'text': pages[u],
                                          'published_at_utc': CUT}
                                         if u in pages else None),
                      parser=_rows_parser,
                      store_dir=tempfile.mkdtemp())
    check('one candidate pinned', res['pinned'] is not None, res['reading'])
    check('and it is the content-bearing one',
          res['pinned']['url'].endswith('inactives-week-3'),
          res['pinned']['url'])
    check('every candidate carries its own verdict',
          len(res['candidates']) == 3, len(res['candidates']))
    check('assert_pinned returns the pin',
          SD.assert_pinned(res)['url'] == res['pinned']['url'])


def test_J_no_qualifying_candidate_refuses_rather_than_choosing_a_near_miss():
    print('\nJ. eight of ten is a refusal')
    res = SD.discover(['https://www.nfl.com/inactives/'], REQ,
                      fetcher=lambda u: {'text': LANDING,
                                         'published_at_utc': CUT},
                      parser=_rows_parser, store_dir=tempfile.mkdtemp())
    ok, d = raised(SD.DiscoveryError, lambda: SD.assert_pinned(res),
                   'NO_QUALIFYING_ARTIFACT')
    check('it refuses and names the failures', ok, d)
    res2 = SD.discover(['https://www.nfl.com/x'], REQ,
                       fetcher=lambda u: None, parser=_rows_parser)
    check('a fetcher returning nothing is a named refusal too',
          res2['candidates'][0]['failed'] == ['FETCH_RETURNED_NOTHING'],
          res2['candidates'][0])


def test_K_a_consumer_may_not_resolve_its_own_source():
    print('\nK. a second information clock')
    pin = {'url': 'https://www.packers.com/news/inactives-week-3'}
    SD.assert_consumes_pin_only(pin, pin['url'])
    check('reading the pin is allowed', True)
    ok, d = raised(SD.DiscoveryError,
                   lambda: SD.assert_consumes_pin_only(
                       pin, 'https://www.nfl.com/inactives/'),
                   'PINNED_ARTIFACT_BYPASSED')
    check('reading anything else is refused', ok, d)
