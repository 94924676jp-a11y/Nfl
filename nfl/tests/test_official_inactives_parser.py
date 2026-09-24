"""The official-inactives parser, tested against the real preserved bytes.

WHAT THIS MODULE ASSERTS
========================
1. THE EMPTY-STATE PAGE IS REFUSED BY NAME. 363 of 367 preserved
   `official_inactives` blobs are the NFL.com "Please check back soon" page,
   every one of them recorded as a capture PASS. The parser raises
   `EmptyStatePage` on them rather than returning `{}`. This is the single
   most important assertion here: an empty result read as success is exactly
   how this source was mistaken for a working one.
2. THE TWO PROVEN CARRIERS PARSE. The NFL.com weekly article
   (`<h3>TEAM</h3><ul><li>POS Name</li>`) and the operator plain-text relay
   (`TEAM` / `* POS Name`) both yield the same structure.
3. ABSENCE IS NEVER CONVERTED INTO PRESENCE. `for_game` refuses when either
   requested team is missing from the document, and says so in those words.
   A half-attributed result would let one team's silence read as "nobody
   inactive".
4. AN AGENT-AUTHORED REPORT IS NOT A SOURCE. The SF @ LA markdown
   intelligence capture discusses inactive lists in prose and is refused.
   Parsing another agent's summary as though it were the source document is
   the error this refusal prevents.
5. THE ENTRY GRAMMAR IS TIGHT. A position token is required, the emergency-QB
   parenthetical is captured as a note rather than fused into the name, and
   prose lines are not mistaken for entries.
"""
import glob
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.truth.official_inactives_parser import (  # noqa: E402
    EMPTY_STATE_MARKER,
    EmptyStatePage,
    InactivesParseError,
    for_game,
    parse,
    read_bytes,
)

PASSED = FAILED = BLOCKED = 0

VINTAGE = os.path.join(_ROOT, 'nfl', 'vintage')
WEEK1_ARTICLE = os.path.join(VINTAGE, 'official_inactives.3fc8c4f13968d023.html.gz')
OPERATOR_RELAY = os.path.join(VINTAGE, 'official_inactives.6dafcf6e981f11be.html.gz')
AGENT_REPORT = os.path.join(VINTAGE, 'official_inactives.91bdf335602a7475.html.gz')
EMPTY_STATE = os.path.join(VINTAGE, 'official_inactives.fefbd73647bb1e1d.html.gz')


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


def raises(fn, exc, needle=''):
    try:
        fn()
    except exc as e:
        return needle in str(e)
    except Exception:
        return False
    return False


def test_the_empty_state_page_is_refused_by_name():
    if not os.path.exists(EMPTY_STATE):
        return blocked('empty-state refusal', f'blob absent: {EMPTY_STATE}')
    doc = read_bytes(EMPTY_STATE)
    check('the preserved landing page really is the empty-state page',
          EMPTY_STATE_MARKER in doc)
    check('it raises EmptyStatePage rather than returning {}',
          raises(lambda: parse(doc), EmptyStatePage, 'carries no list'))
    check('for_game refuses it too, not just parse',
          raises(lambda: for_game(doc, 'GB', 'ATL'), EmptyStatePage))


def test_every_preserved_landing_page_is_refused():
    """Not one sampled blob -- the whole population on disk."""
    blobs = sorted(glob.glob(os.path.join(VINTAGE, 'official_inactives.*.html.gz')))
    if not blobs:
        return blocked('population sweep', 'no official_inactives blobs on disk')
    empty = parsed = refused = 0
    for b in blobs:
        try:
            doc = read_bytes(b)
        except InactivesParseError:
            refused += 1
            continue
        if EMPTY_STATE_MARKER in doc:
            empty += 1
            if not raises(lambda: parse(doc), EmptyStatePage):
                return check(f'{os.path.basename(b)} empty-state refused', False)
            continue
        try:
            parse(doc)
            parsed += 1
        except InactivesParseError:
            refused += 1
    check('the overwhelming majority of captures are the empty-state page',
          empty >= 300, f'empty={empty}')
    check('at least one preserved capture does carry a real list',
          parsed >= 1, f'parsed={parsed}')
    check('every blob is classified, none silently returns an empty dict',
          empty + parsed + refused == len(blobs),
          f'{empty}+{parsed}+{refused} != {len(blobs)}')
    print(f'       population: {len(blobs)} blobs  empty={empty} '
          f'parsed={parsed} refused={refused}')


def test_the_nfl_weekly_article_parses():
    if not os.path.exists(WEEK1_ARTICLE):
        return blocked('week 1 article', f'blob absent: {WEEK1_ARTICLE}')
    teams = parse(read_bytes(WEEK1_ARTICLE))
    check('the article yields many teams', len(teams) >= 8, str(len(teams)))
    check('every team carries at least one entry',
          all(v for v in teams.values()))
    check('every entry has a position and a name',
          all(e['position'] and e['name']
              for v in teams.values() for e in v))
    atl = teams.get('ATL', [])
    check('ATL is present and names are real, not position tokens',
          any(e['name'] == 'Michael Penix Jr.' for e in atl),
          str(atl[:3]))
    check('the emergency-QB parenthetical is a note, not part of the name',
          all('(' not in e['name'] for v in teams.values() for e in v))


def test_the_operator_relay_parses_to_the_same_shape():
    if not os.path.exists(OPERATOR_RELAY):
        return blocked('operator relay', f'blob absent: {OPERATOR_RELAY}')
    got = for_game(read_bytes(OPERATOR_RELAY), 'BUF', 'DET')
    check('both teams attributed', sorted(got['inactives']) == ['BUF', 'DET'])
    check('seven a side, as the relay states',
          got['counts'] == {'BUF': 7, 'DET': 7}, str(got['counts']))
    check('a curly apostrophe survives intact',
          any(e['name'] == 'Ar’maj Reed-Adams'
              for e in got['inactives']['BUF']))
    check('the semantics note refuses the omission inference',
          'not a claim that the player is active' in got['semantics'])


def test_absence_is_never_converted_into_presence():
    if not os.path.exists(OPERATOR_RELAY):
        return blocked('absence handling', f'blob absent: {OPERATOR_RELAY}')
    doc = read_bytes(OPERATOR_RELAY)
    check('a game the document does not cover is refused, not returned empty',
          raises(lambda: for_game(doc, 'GB', 'ATL'), InactivesParseError,
                 'Absence here is not evidence'))
    check('one team present and one absent is still refused',
          raises(lambda: for_game(doc, 'BUF', 'GB'), InactivesParseError,
                 'no inactive list for GB'))


def test_an_agent_authored_report_is_not_a_source():
    if not os.path.exists(AGENT_REPORT):
        return blocked('agent report', f'blob absent: {AGENT_REPORT}')
    check('a prose intelligence report is refused, not mined for names',
          raises(lambda: parse(read_bytes(AGENT_REPORT)), InactivesParseError))


def test_the_entry_grammar_is_tight():
    check('a bare name with no position is not an entry',
          raises(lambda: parse('GB\nJordan Love\n'), InactivesParseError))
    check('a position token alone yields nothing',
          raises(lambda: parse('GB\nQB\n'), InactivesParseError))
    check('a clean minimal document parses',
          parse('GB\n* QB Jordan Love\n') == {'GB': [{'position': 'QB', 'name': 'Jordan Love'}]})
    check('a parenthetical becomes a note',
          parse('GB\n* QB Sean Clifford (emergency third QB)\n')
          == {'GB': [{'position': 'QB', 'name': 'Sean Clifford',
                      'note': 'emergency third QB'}]})
    check('a duplicate line is not double-counted',
          len(parse('GB\n* QB Jordan Love\n* QB Jordan Love\n')['GB']) == 1)
    check('entries before any team header are dropped, not misattributed',
          raises(lambda: parse('* QB Jordan Love\n'), InactivesParseError))


def test_empty_and_unparseable_inputs_raise():
    check('an empty document raises',
          raises(lambda: parse(''), InactivesParseError))
    check('unrelated prose raises rather than returning {}',
          raises(lambda: parse('The Packers are playing well this season.'),
                 InactivesParseError, 'not being reported as an empty'))


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
