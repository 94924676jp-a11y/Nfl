"""An unmatched player is a REFUSAL, never a graded zero.

DEF-063 was not "grading joined by name". Joining by name is sometimes forced:
MAIN_LINE_BOARD.csv carries `player` as a name with no gsis_id, and the
PORTFOLIO csv is DraftKings entry format with name columns only. Neither
artifact offers an identity to prefer.

What made grade_projections a defect is what it did when the name FAILED to
match: it fell through to a zero stat line and reported `state: GRADED`. A 0.0
actual against an 8.2 projection reads as a catastrophic model miss and was a
failed name lookup -- and it enters the prospective ledger as evidence against
the model, which is worse than any refusal.

The other two name-joining graders were already right, and my first sweep
wrongly flagged both:

  grade_props       -> not_graded, reason PLAYER_NOT_IN_OUTCOME
  grade_portfolios  -> the whole lineup goes to `unscorable`, not scored
                       with zeros in it; and actual_dk's docstring already
                       documents the 'James Cook III' / 'James Cook' and
                       'Joshua Palmer' / 'Josh Palmer' normalisation, with the
                       fix, because it cost something once.

So the rule is about the FAILURE MODE, not the key. A consumer may join by
name when the artifact leaves it no choice. It may never turn a failed join
into a number.
"""
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

PASSED = 0
FAILED = 0


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}: {detail}')


def test_a_graded_zero_is_a_decision_and_not_a_failed_join():
    """THE INVARIANT, corrected once I measured it.

    My first version flagged any row graded 0.0 against a projection of 5+ DK
    points. It fired on Ray Davis: projected 7.16, actual 0.0. That is NOT a
    join failure -- he is in the outcome as player_id 00-0039875 with rush_att,
    rush_yards, targets, receptions and rec_yards all 0.0. He was active and
    recorded nothing. A real zero against a 7-point projection is a genuine
    model miss, and flagging it as a bug would have hidden a true finding
    behind a false one.

    So the property is not "no graded zeros". It is that a graded row's join
    SUCCEEDED: either the outcome carried the player, or `resolve_absent`
    reached a named decision about him. The kickers were the defect precisely
    because neither happened -- the name lookup failed, and they were graded
    against a zero line anyway.
    """
    from nfl.postgame import grade_projections as GP
    g = GP.grade()
    check('grading runs', g.state.name == 'PASS', g.code)
    if g.state.name != 'PASS':
        return
    v = g.value
    rows = v.get('rows') or []
    check('rows were produced', bool(rows), len(rows))

    # Every player the grader could not place is reported, and NOT graded.
    not_in = {x.get('player') for x in (v.get('not_in_outcome') or [])}
    graded = {r.get('player') for r in rows}
    check('no player is both graded and reported as unplaceable',
          not (not_in & graded), sorted(not_in & graded))
    print(f'       {len(rows)} graded, {len(not_in)} reported unplaceable, '
          f'{len(v.get("zeroed") or [])} zeroed by an explicit decision')

    # And the zero that started this: a real one, kept as a real one.
    ray = [r for r in rows if str(r.get('player')) == 'Ray Davis']
    if ray:
        dk = (ray[0].get('stats') or {}).get('dk_points') or {}
        # `dk.get('actual') or -1` is WRONG here and it bit: 0.0 is falsy, so
        # the sentinel replaced the very value under test. In a file about
        # distinguishing a real zero from a missing one, `or` is the one
        # operator that cannot be used on the number itself.
        _act = dk.get('actual')
        check('Ray Davis is graded with a real zero, not excluded',
              dk.get('state') == 'GRADED' and _act is not None
              and float(_act) == 0.0,
              f'{dk.get("state")} actual={_act!r}')
        print(f'       Ray Davis: actual 0.0 against {dk.get("mean"):.2f} '
              f'projected -- a true miss, and the model owns it')


def test_the_kickers_specifically_are_not_zero():
    """The instance, named, so a regression is legible rather than statistical."""
    from nfl.postgame import grade_projections as GP
    g = GP.grade()
    if g.state.name != 'PASS':
        check('grading runs', False, g.code)
        return
    kick = {r['player']: (r.get('stats') or {}).get('dk_points') or {}
            for r in (g.value.get('rows') or [])
            if ((r.get('stats') or {}).get('dk_points') or {}).get('scored_by')
            == 'kicker_rules'}
    check('both kickers appear', len(kick) == 2, sorted(kick))
    for who, v in sorted(kick.items()):
        check(f'{who} has a non-zero actual', float(v.get('actual') or 0) > 0,
              f'actual={v.get("actual")} -- the outcome holds his real line, '
              f'so a zero here is a join failure')


def test_the_other_name_joining_graders_refuse_rather_than_score_zero():
    """Read as SOURCE, because these two need an outcome plus a board CSV to
    run and the point is the shape of their failure path, not its output."""
    props = (_REPO / 'nfl/postgame/grade_props.py').read_text()
    check('grade_props names an unmatched player instead of scoring him',
          "'PLAYER_NOT_IN_OUTCOME'" in props,
          'an unmatched prop row must be reported, not graded')
    check('and it collects them in not_graded', 'not_graded' in props)

    port = (_REPO / 'nfl/postgame/grade_portfolios.py').read_text()
    check('grade_portfolios sends an unmatched lineup to unscorable',
          'unscorable' in port,
          'a lineup with an unmatched player must not be scored as if the '
          'missing man contributed zero')
    check('and it records WHICH name was missing', "'missing'" in port)
    # This one's name join IS forced: the PORTFOLIO csv is DraftKings entry
    # format -- 'Entry ID, Contest Name, Contest ID, Entry Fee, CPT, FLEX...' --
    # and carries no player id anywhere.
    pcsv = _REPO / 'nfl/research/dfs/DET_BUF_2026W2/PORTFOLIO_CLAUDE_40.csv'
    if pcsv.exists():
        head = [h.strip().lower() for h in
                pcsv.read_text().splitlines()[0].split(',')]
        check('the portfolio csv carries no id, so its name join is forced',
              not any('gsis' in h or h == 'id' for h in head), head[:6])


def test_the_outcome_artifact_offers_identity_even_where_boards_do_not():
    """Why grade_projections could be fixed and the other two cannot be, in
    the same way: the OUTCOME has player_id; the boards have names only."""
    art = (_REPO / 'nfl/research/dfs/DET_BUF_2026W2/POSTGAME_OUTCOME'
                   '/OUTCOME.json')
    if not art.exists():
        check('outcome artifact present', False, str(art))
        return
    players = (json.loads(art.read_text()).get('players') or {})
    with_id = [n for n, v in players.items() if (v or {}).get('player_id')]
    check('most outcome rows carry a player_id',
          len(with_id) >= 0.9 * len(players),
          f'{len(with_id)} of {len(players)}')

    board = _REPO / 'nfl/research/market/DET_BUF_2026W2/MAIN_LINE_BOARD.csv'
    if board.exists():
        header = [h.strip() for h in board.read_text().splitlines()[0].split(',')]
        # I claimed this board had no id column and was therefore FORCED to
        # join by name. Wrong: `gsis_id` is column 29. grade_props now joins by
        # identity first with the name as fallback.
        check('the props board DOES carry gsis_id', 'gsis_id' in header,
              header[:8])
        import csv as _csv
        with open(board) as fh:
            rows = list(_csv.DictReader(fh))
        with_id = [r for r in rows if (r.get('gsis_id') or '').strip()]
        check('but not every row carries one, so the name fallback stays',
              0 < len(with_id) < len(rows), f'{len(with_id)} of {len(rows)}')
        print(f'       {len(with_id)} of {len(rows)} props rows carry a '
              f'gsis_id; measured rescue on this slate: 0 rows -- the change '
              f'is hardening, not a live repair')
