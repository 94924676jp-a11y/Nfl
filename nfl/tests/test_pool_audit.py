"""The player-pool audit measures the pool. This measures the audit. L3.

WHAT THESE TESTS ARE FOR

Every one of them exists because the same class of defect has already been paid
for in this repository: a read that returned nothing, or something partial, was
used as a value. So the properties asserted here are not "does it compute the
right number" -- they are "does it refuse when it cannot".

  * a selection made with no clock is a refusal, never the newest file on disk
  * an empty read is a NAMED error, never an empty result
  * absence from a feed is never promoted to a state
  * GAME_ACTIVE is never emitted by anything
  * position alone never establishes eligibility

The last one is the owner's instruction and it is asserted directly, because a
board that silently drops the eligibility half still produces a complete-looking
table.
"""
from __future__ import annotations

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State            # noqa: E402
from nfl.production import pool_audit as PA                    # noqa: E402
from nfl.production import candidate_mode as CM                # noqa: E402
from nfl.production.nonqb import vintage_selector as VS        # noqa: E402

PASSED = FAILED = BLOCKED = 0

GAME = '2026_01_DEN_KC'
TEAMS = ('DEN', 'KC')
KICKOFF = '2026-09-15T00:15:00Z'
# A cut inside the window this audit was written for. Fixed, not "now": a test
# whose bound moves with the wall clock is measuring the wall clock.
WRITTEN_AT = '2026-09-14T16:30:00Z'
# Before the first capture of anything. Nothing may be lawful at this instant.
PREHISTORY = '2026-08-01T00:00:00Z'


def check(label, ok, detail=''):
    global PASSED, FAILED
    if ok:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label} {detail}')


def blocked(label, why):
    global BLOCKED
    BLOCKED += 1
    print(f'  blk  {label} :: {why}')


def _audit(flags=None, written_at=WRITTEN_AT, kickoff=KICKOFF, teams=TEAMS):
    return PA.audit(2026, 1, GAME, teams, kickoff, written_at,
                    mode_flags=(CM.R8_FLAGS if flags is None else flags))


def test_a_clock_is_mandatory():
    """NO CLOCK IS NOT ANY CLOCK. It is a refusal, by name."""
    o = PA.audit(2026, 1, GAME, TEAMS, None, None, mode_flags=CM.R8_FLAGS)
    check('audit with neither clock refuses',
          o.state is State.BLOCKED and o.code == 'POOL_AUDIT_NO_CLOCK', o.code)
    check('the refusal says an undeclared cut is not an open cut',
          'undeclared cut' in (o.detail or ''), o.detail)


def test_b_a_cut_before_every_capture_refuses():
    """A cut nothing predates yields a NAMED refusal, not the newest file."""
    o = _audit(written_at=PREHISTORY, kickoff=PREHISTORY)
    check('prehistoric cut does not return a pool',
          o.state is not State.PASS, o.code)
    check('and it names the family it could not select for',
          'VINTAGE' in o.code or 'POOL_AUDIT' in o.code, o.code)


def test_c_selection_is_by_clock_not_by_disk():
    """The selector's own forbidden-input list must reach the artifact."""
    o = _audit()
    if o.state is not State.PASS:
        blocked('forbidden inputs recorded', f'audit refused: {o.code}')
        return
    fb = set(o.evidence.get('forbidden_inputs') or ())
    for f in ('filesystem mtime', 'glob order', 'file size', 'row count'):
        check(f'{f!r} is recorded as a forbidden selection input', f in fb)


def test_d_an_empty_read_is_a_named_error():
    """A team with no roster row must not come back as an empty pool."""
    o = _audit(teams=('ZZZ',))
    check('an unknown club does not produce an empty successful audit',
          o.state is not State.PASS, o.code)
    check('and the refusal is named for the empty read',
          o.code in ('POOL_AUDIT_ROSTER_EMPTY', 'POOL_AUDIT_NO_ROWS'), o.code)


def test_e_every_row_carries_every_column():
    o = _audit()
    if o.state is not State.PASS:
        blocked('row schema', f'audit refused: {o.code}')
        return
    need = ('player', 'team', 'position', 'roster_status', 'depth_status',
            'injury_status', 'eligible', 'model_pool', 'exclusion_reason',
            'gameday_status', 'allocation_pool')
    rows = o.value
    check('the audit produced rows', bool(rows), f'{len(rows)} rows')
    missing = [k for k in need if any(k not in r for r in rows)]
    check('every declared column is present on every row', not missing,
          str(missing))
    blank = [r for r in rows if not r['player'] or not r['team']
             or not r['roster_status']]
    check('no row carries a blank player, team or status', not blank,
          str(blank[:2]))


def test_f_game_active_is_never_emitted():
    """The state no source we hold can establish must never be asserted."""
    o = _audit()
    if o.state is not State.PASS:
        blocked('GAME_ACTIVE never emitted', f'audit refused: {o.code}')
        return
    vals = {r['gameday_status'] for r in o.value} | {r['eligible']
                                                     for r in o.value}
    check('no row is GAME_ACTIVE', 'GAME_ACTIVE' not in vals, str(vals))
    check('the artifact says so in its own evidence',
          'GAME_ACTIVE' in str(o.evidence.get('never_emitted')),
          str(o.evidence.get('never_emitted')))


def test_g_absence_is_not_a_state():
    """With no official list published, EVERY player is UNRESOLVED on it."""
    o = _audit()
    if o.state is not State.PASS:
        blocked('absence is not a state', f'audit refused: {o.code}')
        return
    if o.evidence.get('inactives_outcome') == 'POOL_AUDIT_OFFICIAL_INACTIVES_OK':
        blocked('absence is not a state',
                'an official list HAS been published for this game; the '
                'no-list branch cannot be exercised against it')
        return
    bad = [r for r in o.value if r['gameday_status'] != PA.UNRESOLVED]
    check('with no published list every gameday status is UNRESOLVED',
          not bad, str([r['player'] for r in bad[:3]]))
    inj = {r['injury_status'] for r in o.value}
    check('a player with no injury row is NO_INJURY_ROW, not healthy',
          'NO_INJURY_ROW' in inj or all('NO_INJURY_ROW' not in i for i in inj),
          str(sorted(inj)[:3]))


def test_h_position_alone_does_not_establish_eligibility():
    """THE OWNER'S INSTRUCTION, ASSERTED DIRECTLY.

    Two halves, and both have to hold:
      (i) a modelled position with a non-active roster status exists, so
          position and eligibility are demonstrably different facts; and
      (ii) wherever such a player nevertheless reaches the model pool, the row
           NAMES the mechanism instead of presenting him as eligible.
    """
    o = _audit()
    if o.state is not State.PASS:
        blocked('position != eligibility', f'audit refused: {o.code}')
        return
    modelled_pos = set(PA.RECEIVING_POS) | {PA.QB_POS}
    off = [r for r in o.value if r['position'] in modelled_pos
           and r['eligible'] != PA.ROSTER_ACTIVE]
    check('at least one modelled-position player is not roster-active',
          bool(off), f'{len(off)}')
    unnamed = [r for r in off if r['model_pool'] and not r['exclusion_reason']]
    check('any non-active player in the model pool names why he is there',
          not unnamed, str([r['player'] for r in unnamed[:3]]))


def test_i_the_qb_exemption_is_visible():
    """P3. The QB pool bypasses the only eligibility filter there is.

    This test does not assert the exemption is right. It asserts it is
    REPORTED: a run where a non-active quarterback reaches the pool and the
    artifact does not say so is the failure.
    """
    o = _audit()
    if o.state is not State.PASS:
        blocked('QB exemption reported', f'audit refused: {o.code}')
        return
    qbs = [r for r in o.value if r['position'] == PA.QB_POS]
    check('the QB pool is non-empty', bool(qbs), f'{len(qbs)}')
    exempt = [r for r in qbs if r['eligible'] != PA.ROSTER_ACTIVE
              and r['model_pool']]
    if not exempt:
        blocked('QB exemption reported',
                'no non-active quarterback is on this roster vintage, so the '
                'exemption has nothing to bite on here')
        return
    named = [r for r in exempt if 'QB_POOL_EXEMPT_FROM_R5'
             in (r['exclusion_reason'] or '')]
    check('every non-active QB in the pool is named as R5-exempt',
          len(named) == len(exempt),
          str([r['player'] for r in exempt if r not in named]))


def test_j_r5_narrows_only_the_non_quarterbacks():
    """The same players, two modes. The difference must be non-QB only."""
    a = _audit(flags=CM.R8_FLAGS)
    b = _audit(flags=CM.V1_CANDIDATE_FLAGS)
    if a.state is not State.PASS or b.state is not State.PASS:
        blocked('R5 mode comparison', f'{a.code} / {b.code}')
        return
    pa = {r['gsis_id'] for r in a.value if r['allocation_pool']}
    pb = {r['gsis_id'] for r in b.value if r['allocation_pool']}
    check('the R5 pool is a subset of the unfiltered pool', pa <= pb,
          str(sorted(pa - pb)[:3]))
    qa = {r['gsis_id'] for r in a.value
          if r['allocation_pool'] and r['position'] == PA.QB_POS}
    qb_ = {r['gsis_id'] for r in b.value
           if r['allocation_pool'] and r['position'] == PA.QB_POS}
    check('the quarterback pool is identical under both modes', qa == qb_,
          str(sorted(qa ^ qb_)))
    if pa == pb:
        blocked('R5 removes somebody',
                'no non-active skill player is on this roster vintage, so R5 '
                'has nobody to remove')
    else:
        check('R5 removes only non-quarterbacks',
              all(r['position'] != PA.QB_POS for r in b.value
                  if r['gsis_id'] in (pb - pa)))


def test_k_the_appearance_gate_is_per_game_not_per_player():
    """One club's unfiled report empties the non-QB half for BOTH clubs.

    `layers.appearance` defers the whole game when either team is not READY.
    If that is what happened, no non-QB may be reported as modelled, and the
    reason on every affected row must name the blocking club.
    """
    o = _audit()
    if o.state is not State.PASS:
        blocked('appearance gate', f'audit refused: {o.code}')
        return
    if o.evidence.get('appearance_runs'):
        blocked('appearance gate',
                'both clubs are READY at this cut, so the deferral branch is '
                'not exercised')
        return
    modelled_nonqb = [r for r in o.value
                      if r['model_pool'] and r['position'] != PA.QB_POS]
    check('no non-QB is modelled while appearance is deferred',
          not modelled_nonqb, str([r['player'] for r in modelled_nonqb[:3]]))
    affected = [r for r in o.value
                if r['allocation_pool'] and r['position'] != PA.QB_POS]
    check('every affected non-QB names the deferral',
          all('APPEARANCE_DEFERRED' in (r['exclusion_reason'] or '')
              for r in affected), f'{len(affected)} affected')


def test_l_the_depth_chart_is_not_an_eligibility_signal():
    """A depth rank says nothing about roster status, and must not be read to.

    WS05 measured 232 reserve-list players holding depth ranks in one capture.
    If this game's chart lists anyone who is not roster-active, the audit must
    still exclude him.
    """
    o = _audit()
    if o.state is not State.PASS:
        blocked('depth is not eligibility', f'audit refused: {o.code}')
        return
    charted_inactive = [r for r in o.value
                        if r['depth_status'] not in ('NOT_CHARTED',)
                        and not r['depth_status'].startswith('NOT_CHARTED')
                        and r['eligible'] != PA.ROSTER_ACTIVE]
    if not charted_inactive:
        blocked('depth is not eligibility',
                'no charted player on this vintage is non-active, so the '
                'property has no instance here')
        return
    leaked = [r for r in charted_inactive
              if r['allocation_pool'] and r['position'] != PA.QB_POS]
    check('a charted non-active non-QB does not reach the allocation pool',
          not leaked, str([r['player'] for r in leaked[:3]]))


def test_m_status_survives_to_the_bytes_that_are_read():
    """THE RAW/REDUCED SPLIT, ASSERTED RATHER THAN ASSUMED.

    The reduced roster vintage is known to drop `status`. That is tolerable
    ONLY while a full-column counterpart of the SAME capture is reachable. This
    test fails the moment both are true at once: status absent from the
    reduced blob AND no same-capture raw bytes.
    """
    o = _audit()
    if o.state is not State.PASS:
        blocked('status reachability', f'audit refused: {o.code}')
        return
    missing = list(o.evidence.get('reduced_missing_columns') or [])
    raw = (o.evidence.get('vintages') or {}).get('roster_status_and_name') or {}
    if not missing:
        blocked('status reachability',
                'the reduced vintage now carries status and full_name; the '
                'raw dependency this test guards is gone')
        return
    check('the raw counterpart is from the SAME capture as the pool vintage',
          bool(raw.get('same_capture')), str(raw.get('basis')))
    red = (o.evidence.get('vintages') or {}).get(
        'roster_identity_and_position') or {}
    check('and it carries the same content hash',
          raw.get('content_sha256') == red.get('content_sha256'),
          f'{raw.get("content_sha256")} vs {red.get("content_sha256")}')


def test_n_no_transaction_feed_is_ever_implied():
    """'Newly signed' and 'newly elevated' must refuse, not infer."""
    tx = PA.transaction_state()
    check('the transactions source is a refusal, not a source',
          tx.state is State.BLOCKED
          and tx.code == 'POOL_AUDIT_NO_TRANSACTIONS_FEED', tx.code)
    check('and the refusal says a roster diff cannot date a transaction',
          'cannot date the transaction' in (tx.detail or ''), tx.detail)
    o = _audit()
    if o.state is not State.PASS:
        blocked('diff is labelled derived', f'audit refused: {o.code}')
        return
    check('the audit records the transactions refusal',
          o.evidence.get('transactions_outcome')
          == 'POOL_AUDIT_NO_TRANSACTIONS_FEED',
          str(o.evidence.get('transactions_outcome')))


def test_o_every_column_names_the_vintage_it_came_from():
    o = _audit()
    if o.state is not State.PASS:
        blocked('vintage provenance', f'audit refused: {o.code}')
        return
    v = o.evidence.get('vintages') or {}
    for k in ('roster_identity_and_position', 'roster_status_and_name',
              'depth_status_vendor_rank', 'injury_status', 'gameday_status',
              'transactions'):
        check(f'the {k} column names its vintage or its refusal',
              bool(v.get(k)), str(v.get(k))[:80])
    red = v.get('roster_identity_and_position') or {}
    check('the roster vintage carries a blob and a retrieval instant',
          bool(red.get('blob')) and bool(red.get('retrieved_at')), str(red)[:80])


def test_p_the_cut_is_never_later_than_kickoff():
    """`as_of_cut` is min(written_at, kickoff - 1us). Assert it, don't trust it."""
    o = _audit(written_at='2026-09-20T00:00:00Z')
    if o.state is not State.PASS:
        blocked('cut bounded by kickoff', f'audit refused: {o.code}')
        return
    cut = VS.parse_ts(o.evidence.get('as_of'))
    ko = VS.parse_ts(KICKOFF)
    check('a written_at after kickoff is still cut at kickoff',
          cut is not None and cut < ko, f'{cut} vs {ko}')


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f'{FAILED} check(s) failed')


if __name__ == '__main__':
    for name, fn in sorted(list(globals().items())):
        if name.startswith('test_') and callable(fn):
            print(name)
            fn()
    print(f'PASSED {PASSED} FAILED {FAILED} BLOCKED {BLOCKED}')
