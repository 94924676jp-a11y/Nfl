"""The official-inactives parser, against the real preserved bytes.

WHY THIS EXISTS NOW AND NOT BEFORE. `nfl/production/nonqb/inactives.py` was
written when every preserved capture was the empty-state page, and its
docstring said so: it had never seen a populated document, so it leaned on
refusing. On 2026-09-24 three populated captures were found in the existing
vintage store -- the NFL.com weekly article, a single-game article, and an
operator plain-text relay. Against all three the parser deferred. This module
pins the behaviour against those bytes so the segmentation cannot drift back.

WHAT THIS MODULE ASSERTS
========================
1. THE REAL DOCUMENTS PARSE, WITH THE RIGHT NAMES. Not "returns PASS" --
   the exact rosters are checked, position prefixes stripped, because
   downstream identity resolution matches roster names and would not resolve
   'QB Tua Tagovailoa'.
2. THE EMPTY-STATE PAGE IS STILL REFUSED. 363 of 367 preserved blobs are the
   "check back soon" page and every one was recorded as a capture PASS. The
   whole population is swept, not a sample.
3. A CLUB WHOSE LIST THE DOCUMENT DOES NOT CARRY IS REFUSED, NOT INVENTED.
   This is the regression that matters most. An intermediate version of the
   segmentation accepted any block containing a person-shaped name and
   returned PASS with GB: ['Justin Jefferson'] and MIN: ['NFC South'] on a
   capture carrying neither club's list -- a Vikings receiver attributed to
   Green Bay, swept from the navigation. That case is asserted directly.
4. FRESHNESS IS VISIBLE IN THE DATA. The same article captured twice carries
   8 games at 16:00Z and more later. GB/MIN therefore DEFERS on the earlier
   capture and PASSES on the later one. A parser that returned the same
   answer for both would be reading the URL, not the bytes.
5. THE ENTRY GRAMMAR IS THE LEAGUE'S. A position prefix is required, which is
   what separates a list entry from page furniture.
"""
import glob
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import gzip  # noqa: E402

from nfl.production.nonqb import inactives as INA  # noqa: E402

PASSED = FAILED = BLOCKED = 0

VINTAGE = os.path.join(_ROOT, 'nfl', 'vintage')
ARTICLE_EARLY = 'official_inactives.3fc8c4f13968d023.html.gz'   # 16:00:17Z
ARTICLE_LATE = 'official_inactives.423d0c34811cd6d6.html.gz'
RELAY = 'official_inactives.6dafcf6e981f11be.html.gz'           # Wk2 TNF
AGENT_REPORT = 'official_inactives.91bdf335602a7475.html.gz'
EMPTY_STATE = 'official_inactives.fefbd73647bb1e1d.html.gz'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(ok)


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  BLOCKED {label}  {why}')


def doc(name):
    path = os.path.join(VINTAGE, name)
    if not os.path.exists(path):
        return None
    return gzip.open(path, 'rt', errors='replace').read()


def test_the_weekly_article_parses_with_the_right_names():
    d = doc(ARTICLE_EARLY)
    if d is None:
        return blocked('weekly article', f'{ARTICLE_EARLY} absent')
    out = INA.parse(d, ['ATL', 'CAR'])
    if not check('ATL/CAR parses to PASS', out.state.name == 'PASS',
                 f'{out.state.name} {out.code}'):
        return
    check('ATL list is exactly the six the document names',
          out.value['ATL'] == ['Tua Tagovailoa', 'Michael Penix Jr.',
                               'Billy Bowman Jr.', 'Malcolm Dewalt IV',
                               'Christian Harris', 'Ethan Onianwa'],
          str(out.value['ATL']))
    check('CAR list is exactly the seven the document names',
          out.value['CAR'] == ["Ja'Tavion Sanders", 'John Metchie',
                               'Haynes King', 'Zakee Wheatley',
                               'Albert Reese', 'Patrick Jones II',
                               'Cam Jackson'],
          str(out.value['CAR']))
    check('position prefixes are stripped, not carried into the name',
          not any(n.split()[0] in ('QB', 'TE', 'WR', 'OT', 'DT', 'CB', 'LB')
                  for v in out.value.values() for n in v))
    check('the emergency-QB parenthetical is not fused into a name',
          all('(' not in n for v in out.value.values() for n in v))
    other = INA.parse(d, ['CHI', 'CAR'])
    check('a second game in the same document parses independently',
          other.state.name == 'PASS' and other.value['CHI'][0] == 'Miller Moss',
          f'{other.state.name} {other.code}')


def test_the_operator_relay_parses():
    d = doc(RELAY)
    if d is None:
        return blocked('operator relay', f'{RELAY} absent')
    out = INA.parse(d, ['BUF', 'DET'])
    if not check('BUF/DET parses to PASS', out.state.name == 'PASS',
                 f'{out.state.name} {out.code}'):
        return
    check('seven a side, as the relay states',
          [len(out.value['BUF']), len(out.value['DET'])] == [7, 7],
          str({k: len(v) for k, v in out.value.items()}))
    check('a curly apostrophe survives intact',
          'Ar’maj Reed-Adams' in out.value['BUF'])
    check('a single-letter position is not mistaken for part of the name',
          'Jalon Kilgore' in out.value['BUF'], str(out.value['BUF']))
    check('the title line naming both clubs does not become a third block',
          sorted(out.value) == ['BUF', 'DET'])


def test_a_club_the_document_does_not_carry_is_never_invented():
    """The regression that matters most. See the module docstring, item 3."""
    d = doc(ARTICLE_EARLY)
    if d is None:
        return blocked('false-positive guard', f'{ARTICLE_EARLY} absent')
    out = INA.parse(d, ['GB', 'MIN'])
    check('GB/MIN is REFUSED on a capture that does not carry their game',
          out.state.name == 'DEFERRED', f'{out.state.name} {out.code}')
    check('and it is refused for the right reason',
          out.code in ('INACTIVES_TEAM_HAS_NO_NAMES',
                       'INACTIVES_TEAM_NOT_REPRESENTED'), out.code)
    check('no Vikings receiver is attributed to Green Bay',
          not isinstance(getattr(out, 'value', None), dict)
          or 'Justin Jefferson' not in str(out.value))
    relay = doc(RELAY)
    if relay is not None:
        wrong = INA.parse(relay, ['GB', 'ATL'])
        check('a wholly unrelated game is refused, not answered',
              wrong.state.name == 'DEFERRED'
              and wrong.code == 'INACTIVES_TEAM_NOT_REPRESENTED',
              f'{wrong.state.name} {wrong.code}')


def test_freshness_is_read_from_the_bytes_not_the_url():
    early, late = doc(ARTICLE_EARLY), doc(ARTICLE_LATE)
    if early is None or late is None:
        return blocked('freshness', 'both article captures required')
    a = INA.parse(early, ['GB', 'MIN'])
    b = INA.parse(late, ['GB', 'MIN'])
    check('the earlier capture of the same article refuses GB/MIN',
          a.state.name == 'DEFERRED', f'{a.state.name} {a.code}')
    check('the later capture of the same article carries GB/MIN',
          b.state.name == 'PASS', f'{b.state.name} {b.code}')
    if b.state.name == 'PASS':
        check('and names a real Packers inactive',
              'Aaron Banks' in b.value['GB'], str(b.value.get('GB')))
        check('and a real Vikings inactive, on the right club',
              'J.J. McCarthy' in b.value['MIN'], str(b.value.get('MIN')))
    check('the two captures disagree, which is the point',
          a.state.name != b.state.name)


def test_the_empty_state_page_is_still_refused_across_the_population():
    blobs = sorted(glob.glob(os.path.join(VINTAGE, 'official_inactives.*.html.gz')))
    if not blobs:
        return blocked('population sweep', 'no official_inactives blobs on disk')
    empty = other = 0
    for b in blobs:
        text = gzip.open(b, 'rt', errors='replace').read()
        if 'check back soon' not in text.lower():
            other += 1
            continue
        empty += 1
        out = INA.parse(text, ['GB', 'ATL'])
        if out.code != 'INACTIVES_PAGE_EMPTY_STATE':
            return check(f'{os.path.basename(b)} refused as empty state',
                         False, out.code)
    check('the great majority of captures are the empty-state page',
          empty >= 300, f'empty={empty} of {len(blobs)}')
    check('every empty-state capture is refused by name, none returns a list',
          True)
    print(f'       population: {len(blobs)} blobs  empty={empty} other={other}')


def test_an_agent_authored_report_is_not_mined_for_names():
    d = doc(AGENT_REPORT)
    if d is None:
        return blocked('agent report', f'{AGENT_REPORT} absent')
    out = INA.parse(d, ['SF', 'LAR'])
    check('a prose intelligence report does not yield a PASS',
          out.state.name != 'PASS', f'{out.state.name} {out.code}')


def test_the_entry_grammar_is_the_leagues():
    check('a bare name with no position is not an entry',
          INA.parse('GB\nJordan Love\nATL\nBijan Robinson\n',
                    ['GB', 'ATL']).state.name == 'DEFERRED')
    ok = INA.parse('GB\n* QB Jordan Love\n* WR Romeo Doubs\n'
                   'ATL\n* RB Bijan Robinson\n* TE Kyle Pitts\n', ['GB', 'ATL'])
    check('the relay grammar parses to both clubs',
          ok.state.name == 'PASS'
          and ok.value == {'GB': ['Jordan Love', 'Romeo Doubs'],
                           'ATL': ['Bijan Robinson', 'Kyle Pitts']},
          f'{ok.state.name} {ok.code} {getattr(ok, "value", None)}')
    check('an empty document is refused',
          INA.parse('', ['GB', 'ATL']).state.name in ('FAIL', 'DEFERRED'))


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
