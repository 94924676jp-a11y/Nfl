"""The capture obligations, proven where they can be proven and BLOCKED where they cannot.

WS-J. Seven properties the coordinator required, one section each. Every one of
them was true-by-inspection and untested on 2026-09-14, and the suite was green
for three days while the executor was dead and 47 perishable windows closed.

    1. the scheduled workflow actually runs          -- sections H, I, J, M, N
    2. a source fetch is attempted                   -- section M (BLOCKED)
    3. failures write explicit manifest evidence     -- sections D, E
    4. blobs cannot be written without manifest rows -- sections A, B, C, K
    5. a manifest cannot claim PASS with no capture  -- sections E, F, L
    6. basis_can_discharge represents authority      -- section G2
    7. T-90 and status jobs can discharge            -- sections I, K

WHAT IS BLOCKED AND WHY THAT IS NOT A GAP IN THE PROOF

Two of the required proofs need bytes from outside this checkout: that a source
fetch actually returns bytes, and that a cron entry actually fired on GitHub.
Both are recorded with `blocked()`, which the runner reports as BLOCKED and
which is explicitly NOT a pass. Neither is mocked. A mock of a fetch proves that
the mock returns what the mock was told to return, and this project has already
paid for that lesson: `nfl/research/parallel_pass/ws11/WS11_FALSE_GREEN_AUDIT.md`
names three P0 false greens of exactly that shape. The corresponding outbox
entries are asserted to exist by section N, so a blocked proof is a filed
request rather than a shrug.

Run standalone:  python3.12 nfl/tests/test_capture_obligations.py
"""
import datetime as dt
import gzip
import hashlib
import io
import json
import pathlib
import re
import sys
from contextlib import redirect_stdout

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.capture import coverage as C                                # noqa: E402
from nfl.tools import check_retention as R                           # noqa: E402
from nfl.tools import preflight_t90 as P                             # noqa: E402

MANIFEST = _REPO / 'nfl' / 'vintage_manifest.jsonl'
WF_DIR = _REPO / '.github' / 'workflows'
OUTBOX = _REPO / 'docs' / 'AGENT_OUTBOX.md'
MARKER = '/vintage/'

PASSED = FAILED = BLOCKED = 0


def check(label, cond, detail=''):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f'  ok   {label}')
    else:
        FAILED += 1
        print(f'  FAIL {label}  {detail}')
    return bool(cond)


def blocked(label, cause, detail):
    """A proof this executor cannot make. Recorded, never mocked, never a pass."""
    global BLOCKED
    BLOCKED += 1
    o = Outcome.blocked('PROOF_REQUIRES_NETWORK', detail, cause=cause,
                        proof=label)
    print(f'  BLKD {label}  [{o.evidence["cause"] if "cause" in o.evidence else cause.name}] {detail}')
    return o


def _row(**value):
    return json.dumps({'capture_id': 'x', 'source': 's', 'state': 'PASS',
                       'value': value})


# ---------------------------------------------------------------- A. the W3 invariant
def test_A_a_blob_cannot_be_written_without_a_manifest_row():
    """The defect that lost 2026-09-09, stated as an invariant and seeded.

    Fifty GitHub-Actions runs on 2026-09-08/09/10 committed a blob and appended
    zero manifest rows. 48 orphan blobs survive; the manifest holds no row at
    all dated 2026-09-09, including the four runs inside the NE@SEA T-90
    inactives window. The committed guard was `grep -qE '^manifest rows
    appended: [1-9]'` over stdout -- and those runs printed no summary line at
    all, which is exactly when a stdout guard can see least.
    """
    print('\nA. a run that writes a blob and no manifest row is refused')
    before = {'a.csv.gz'}
    after = {'a.csv.gz', 'b.csv.gz'}
    rows_before = [_row(blob='nfl/vintage/a.csv.gz')]

    o = R.assert_no_new_orphan(before, after, rows_before, MARKER)
    check('R9 refuses a new blob that no manifest row names',
          o.state is State.FAIL
          and o.code == 'BLOB_WRITTEN_WITHOUT_MANIFEST_ROW', str(o)[:140])
    check('  and it names the offending file rather than a count alone',
          o.evidence.get('new_orphans') == ['b.csv.gz'],
          str(o.evidence.get('new_orphans')))

    o = R.assert_rows_accompany_blobs(before, after, rows_before, rows_before)
    check('R10 refuses a run that added bytes and appended nothing',
          o.state is State.FAIL
          and o.code == 'BLOBS_WITHOUT_ANY_MANIFEST_APPEND', str(o)[:140])

    rows_after = rows_before + [_row(blob='nfl/vintage/b.csv.gz')]
    o = R.assert_no_new_orphan(before, after, rows_after, MARKER)
    check('  and both clear once the row exists', o.state is State.PASS,
          str(o)[:140])
    o = R.assert_rows_accompany_blobs(before, after, rows_before, rows_after)
    check('  R10 likewise', o.state is State.PASS, str(o)[:140])


def test_A2_the_guard_is_load_bearing():
    """Bypassed, the same input passes -- therefore the refusal came from it."""
    print('\nA2. guard deletion: the same run passes with the guard removed')
    before, after = {'a.csv.gz'}, {'a.csv.gz', 'b.csv.gz'}
    rows = [_row(blob='nfl/vintage/a.csv.gz')]
    check('with the guard, the run is refused',
          R.assert_no_new_orphan(before, after, rows, MARKER).state is State.FAIL)
    # The bypass: compare the store against itself, which is what a missing
    # before-state does. check_retention prints VACUOUS for exactly this.
    check('  comparing the store against itself passes it',
          R.assert_no_new_orphan(after, after, rows, MARKER).state is State.PASS)
    check('  and the tool refuses to call that a measurement',
          'VACUOUS' in (R.__doc__ or '') or 'vacuous' in (R.main.__doc__ or '')
          or 'VACUOUS' in (_REPO / 'nfl' / 'tools'
                           / 'check_retention.py').read_text())


# ---------------------------------------------------------------- B. the census scope
def test_B_the_orphan_census_covers_the_vintage_store():
    """W7. `R8 NO_ORPHAN_BLOBS` was green through the whole of W3."""
    print('\nB. the orphan census is pointed at the store that matters')
    cfg = R.STORES['vintage']
    root, man = pathlib.Path(cfg['blob_root']), pathlib.Path(cfg['manifest'])
    check('the vintage store is a named scope of check_retention',
          root.name == 'vintage' and man.name == 'vintage_manifest.jsonl',
          f'{root} {man}')
    blobs = {q.name for q in root.glob(cfg['glob'])}
    rows = [ln for ln in man.read_text().splitlines() if ln.strip()]
    o = R.assert_no_orphan_blobs_scoped(blobs, rows, MARKER)
    check('and it FAILS on the real store, which is the correct answer -- a '
          'guard that goes green on its first run against a store it has '
          'never checked is telling you it still is not checking',
          o.state is State.FAIL, str(o)[:140])
    check('  with exactly 48 orphans, the number WS13 counted independently',
          o.evidence.get('n_orphans') == 48, str(o.evidence.get('n_orphans')))


def test_B2_the_delivery_blob_is_not_a_49th_false_orphan():
    """RL-8's trap. `value.delivery.raw_evidence_blobs` is the only reference to
    `delivered_injury_evidence.df1dd90380b8d720.html.gz`; a collector reading
    `value.blob` alone reports it as an orphan and the 48 stop being credible."""
    print('\nB2. the delivery blob list is read, so the 48 are trustworthy')
    name = 'delivered_injury_evidence.df1dd90380b8d720.html.gz'
    check('the delivery blob exists on disk',
          (_REPO / 'nfl' / 'vintage' / name).exists())
    rows = [ln for ln in MANIFEST.read_text().splitlines() if ln.strip()]
    named = R.named_blobs(rows, MARKER)
    check('the collector reads it', named.state is State.PASS
          and name in named.value, str(named)[:140])
    only_blob = R.named_blobs(
        [_row(delivery={'raw_evidence_blobs': [f'nfl/vintage/{name}']})],
        MARKER)
    check('  from the nested delivery list alone',
          only_blob.state is State.PASS and name in only_blob.value,
          str(only_blob)[:140])


def test_C_an_unread_blob_location_refuses_rather_than_inventing_an_orphan():
    print('\nC. a blob reference the collector cannot read is a named refusal')
    row = json.dumps({'state': 'PASS',
                      'value': {'somewhere_new': 'nfl/vintage/zz.csv.gz'}})
    o = R.named_blobs([row], MARKER)
    check('an unread nesting BLOCKS the census',
          o.state is State.BLOCKED
          and o.code == 'BLOB_REFERENCE_LOCATION_UNKNOWN', str(o)[:140])
    check('  and names the file it could not account for',
          o.evidence.get('missed') == ['zz.csv.gz'],
          str(o.evidence.get('missed')))
    o = R.named_blobs(['{not json'], MARKER)
    check('an unparseable row BLOCKS rather than counting as zero blobs',
          o.state is State.BLOCKED and o.code == 'MANIFEST_ROW_UNPARSEABLE',
          str(o)[:140])


# ---------------------------------------------------------------- D/E. manifest evidence
def test_D_a_second_writer_cannot_be_absorbed_silently():
    """W5. 18 verified, game-anchored, pre-kickoff inactives rows stopped
    counting because a second writer stamped its own spec_version and nothing
    read it."""
    print('\nD. an unknown manifest schema BLOCKS the report')
    rows = [_row(retrieved_at='2026-09-13T16:00:00Z', sha256='a' * 64,
                 blob='nfl/vintage/x', spec_version='some-new-writer-9')]
    tmp = _REPO / 'nfl' / 'tests' / 'fixtures' / '_wsj_tmp_manifest.jsonl'
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp.write_text(rows[0] + '\n')
        o = C.performed_from_manifest(tmp, verify_artifacts=False)
        check('an unknown spec_version BLOCKS',
              o.state is State.BLOCKED
              and o.code == 'MANIFEST_SPEC_VERSION_UNKNOWN', str(o)[:140])
        check('  and names the schema it has never read',
              o.evidence.get('unknown_spec_versions') == ['some-new-writer-9'],
              str(o.evidence.get('unknown_spec_versions')))
    finally:
        tmp.unlink(missing_ok=True)
    check('the schemas actually present in the store are all declared',
          set(C.KNOWN_SPEC_VERSIONS) >= {None, 'official-inactives-1',
                                         'delivered_injuries/1.0.0'},
          str(C.KNOWN_SPEC_VERSIONS))


def test_E_every_pass_row_lands_in_exactly_one_named_class():
    print('\nE. the dispositions partition the store, with nothing absorbed')
    o = C.performed_from_manifest(MANIFEST)
    check('the real manifest reads', o.state is State.PASS, str(o)[:140])
    d = o.evidence['disposition_counts']
    check('every class is one of the declared names',
          set(d) == set(C.DISPOSITIONS), str(sorted(d)))
    check('and they sum to the PASS row count exactly',
          o.evidence['dispositions_partition_pass_rows']
          and sum(d.values()) == o.evidence['n_pass_rows'],
          f"{sum(d.values())} vs {o.evidence['n_pass_rows']}")
    check('the second writer is counted, not discarded',
          d['FOREIGN_SCHEMA'] > 0, str(d))
    check('  and its game-anchored rows are reported as uncredited evidence',
          o.evidence['n_uncredited_game_anchored'] == 18,
          str(o.evidence['n_uncredited_game_anchored']))


# ---------------------------------------------------------------- F. no backfill
def test_F_visibility_does_not_become_a_discharge():
    """The line that must not be crossed. Making the 18 rows VISIBLE must not
    make them COUNT: they carry no declaration, Directive 7 §6 refuses them, and
    a miss that is reported more informatively is still a miss."""
    print('\nF. nothing is backfilled: a miss stays missed')
    o = C.coverage(2026, 1, manifest_path=MANIFEST)
    e = o.evidence
    check('coverage still FAILS on the perishable windows',
          o.state is State.FAIL and o.code == 'PERISHABLE_WINDOWS_MISSED',
          str(o)[:140])
    # THE PREMISE THIS BLOCK USED TO CARRY WAS FALSE, TWICE OVER.
    #
    # It read: "the 48th is 2026_01_DEN_KC inactives ... it closed UNFILLED:
    # zero capture attempts were made inside it, because the capture executor
    # is halted." TASK ZERO (2026-09-15) disproved both halves.
    #
    #   The executor was never halted. That came from a stale remote-tracking
    #   ref. main captured continuously through 2026-09-15T13:06:52Z.
    #
    #   The window was not unattempted. EIGHT captures were taken inside it, by
    #   the workflow "NFL T-90 anchored capture", each with declared_before_fetch
    #   true and basis SCHEDULED_WINDOW_ANCHORED, each passing eligibility for
    #   2026_01_DEN_KC with refusals == [].
    #
    # DEN@KC is still a miss, for an entirely different and worse reason: all
    # eight fetched https://www.nfl.com/inactives/ while that page carried its
    # own empty-state sentence and not one <tr>. That is D20. The obligation was
    # attempted lawfully and the source had nothing.
    #
    # The counts moved 15/48 -> 28/35 for two compounding reasons, and both are
    # corrections rather than improvements: reconciling with main brought in 289
    # commits of capture evidence this branch did not hold, and D20's repair then
    # withdrew credit from 15 targets that were covered only by the empty page.
    # Nothing is backfilled. Bytes fetched now would be post-kickoff and could
    # not have informed a pregame board; writing them in afterwards would convert
    # a real miss into a fake capture, which is the one thing this module exists
    # to prevent.
    check('covered is 28 and missed is 35',
          e['covered'] == 28 and e['missed'] == 35,
          f"covered={e['covered']} missed={e['missed']}")
    check('  and DEN@KC inactives is among the misses, on D20 and not on '
          'executor silence',
          any(d['game_id'] == '2026_01_DEN_KC' and 'inactive' in d['label'].lower()
              for d in e['missed_detail']),
          str([d['label'] for d in e['missed_detail']
               if d['game_id'] == '2026_01_DEN_KC']))
    check('the two sub-counts partition the misses',
          e['missed_with_uncredited_evidence']
          + e['missed_with_no_evidence_at_all'] == e['missed'],
          f"{e['missed_with_uncredited_evidence']} + "
          f"{e['missed_with_no_evidence_at_all']} vs {e['missed']}")
    # WAS 12, NOW 13. These are game-anchored inactives bytes written under a
    # schema carrying no declaration block -- real evidence, correctly refused,
    # and the one category that must stay VISIBLE rather than be absorbed.
    #
    # I briefly wrote 0 here. That number was real output, and it was produced
    # by a defect of my own: the first cut of coverage._has_declared_rows asked
    # every official_inactives row for a <tr> and so suppressed the 18 DELIVERED
    # markdown captures, which are the only genuine inactive lists in the store.
    # A repair aimed at evidence quality was deleting the evidence. This check
    # is what caught it, which is the whole argument for asserting a number
    # rather than a direction.
    check('  misses holding uncredited game-anchored bytes stay visible',
          e['missed_with_uncredited_evidence'] == 13,
          str(e['missed_with_uncredited_evidence']))
    uncredited = {(d['game_id'], d['kind']) for d in e['uncredited_detail']}
    missed = {(d['game_id'], d['label']) for d in e['missed_detail']}
    check('  and every one of them is STILL in missed_detail',
          all((g, k) in {(a, b) for a, b in missed} for g, k in uncredited),
          str(sorted(uncredited - {(a, b) for a, b in missed})))
    check('  every uncredited row names its refusal',
          all(d['why_not_discharged'] for d in e['uncredited_detail']))
    check('eligible_targets still returns nothing for a foreign-schema row',
          C.eligible_targets({'game_id': '2026_01_BUF_HOU',
                              'spec_version': 'official-inactives-1'}) == [])


# ---------------------------------------------------------------- G. digests and authority
def test_G_a_reduce_row_with_no_persisted_digest_reads_as_UNCHECKABLE():
    """WS-K's trap, and it is the load-bearing one. Falling back to
    `value['sha256']` on a reduce row silently re-asserts the exact claim WS-K
    disproved: that field describes an upstream file that was never stored."""
    print('\nG. an absent persisted digest is never a pass and never a mismatch')
    blob = next(iter(sorted(
        (_REPO / 'nfl' / 'vintage').glob('official_inactives.*.html.gz'))))
    rel = str(blob.relative_to(_REPO))
    real = hashlib.sha256(gzip.open(blob, 'rb').read()).hexdigest()
    ok, why = C._blob_ok({'blob': rel, 'sha256': real})
    check('a plain row whose sha256 matches the stored bytes verifies',
          ok and why is None, str(why))
    ok, why = C._blob_ok({'blob': rel, 'sha256': real, 'durability': 'reduce'})
    check('the SAME row marked durability=reduce refuses -- no fallback, even '
          'when the fallback would have matched',
          (not ok) and why == 'PERSISTED_DIGEST_ABSENT_HISTORICAL', str(why))
    ok, why = C._blob_ok({'blob': rel, 'sha256': 'b' * 64,
                          'durability': 'reduce'})
    check('  and a WRONG sha256 on a reduce row still reads as uncheckable, '
          'not as a mismatch: those 152 rows are not evidence of corruption',
          (not ok) and why == 'PERSISTED_DIGEST_ABSENT_HISTORICAL', str(why))
    ok, why = C._blob_ok({'blob': rel, 'persisted_content_sha256': 'b' * 64})
    check('a WRONG persisted digest is a mismatch, because that digest does '
          'describe the stored bytes',
          (not ok) and why == 'PERSISTED_CONTENT_SHA256_MISMATCH', str(why))
    ex = C.performed_from_manifest(MANIFEST).evidence['artifact_excluded']
    codes = {x['reason'].split(':')[0] for x in ex}
    n_hist = sum(1 for x in ex
                 if x['reason'] == 'PERSISTED_DIGEST_ABSENT_HISTORICAL')
    # NOT A FROZEN COUNT ANY MORE. This read 152 against a 1,391-line manifest
    # and 424 against the 4,492-line one, because reduce rows arrive with the
    # corpus. A number that moves every time main captures is not an invariant,
    # and re-freezing it after every merge teaches nothing. What must hold is
    # the PROPERTY: every such row reads as uncheckable, never as a mismatch.
    check('on the real store, historically-uncheckable rows are present '
          'and counted', n_hist > 0, str(n_hist))
    check('  and not one reads as a content mismatch',
          'PERSISTED_CONTENT_SHA256_MISMATCH' not in codes, str(sorted(codes)))


def test_G2_basis_can_discharge_represents_authority_not_success():
    print('\nG2. the basis gate says what it means')
    from nfl.capture import execution as X
    check('a local invocation cannot discharge',
          X.declaration_basis({'is_github_actions': False})
          not in X.DISCHARGING_BASES)
    check('  nor can the periodic sweep',
          X.declaration_basis({'is_github_actions': True,
                               'workflow': 'NFL vintage capture',
                               'event_name': 'schedule'})
          not in X.DISCHARGING_BASES)
    check('  nor an unknown workflow, which fails safe to a sweep',
          X.declaration_basis({'is_github_actions': True, 'workflow': '?',
                               'event_name': 'schedule'})
          not in X.DISCHARGING_BASES)
    check('  nor a manual dispatch of the anchored workflow',
          X.declaration_basis({'is_github_actions': True,
                               'workflow': X.ANCHORED_WORKFLOW,
                               'event_name': 'workflow_dispatch'})
          not in X.DISCHARGING_BASES)
    check('the scheduled anchored workflow can',
          X.declaration_basis({'is_github_actions': True,
                               'workflow': X.ANCHORED_WORKFLOW,
                               'event_name': 'schedule'})
          in X.DISCHARGING_BASES)
    check('the liveness workflow is NOT an anchored name, so it can never '
          'discharge anything by existing',
          X.declaration_basis({'is_github_actions': True,
                               'workflow': 'NFL capture liveness',
                               'event_name': 'schedule'})
          not in X.DISCHARGING_BASES)


# ---------------------------------------------------------------- H. liveness
def test_H_a_silent_executor_is_detected():
    """The check that did not exist. Nothing in this repository noticed that
    every scheduled workflow stopped on 2026-09-11T03:38Z; coverage cannot,
    because a target is DEFERRED until its window closes."""
    print('\nH. silence is measured against the cadence the workflow declares')
    cad = P._baseline_cadence_minutes()
    check('the cadence is READ from nfl-capture.yml, not written in the check',
          cad.state is State.PASS and cad.value == 30, str(cad)[:120])
    ev = P.last_anchored_evidence()
    check('the last GitHub-Actions manifest row is found',
          ev.state is State.PASS, str(ev)[:140])
    # WAS PINNED TO 2026-09-11, "the day the executor stopped". It never
    # stopped -- see TASK_ZERO_RECONCILIATION.md section 1. Pinning a date here
    # froze a false premise into an assertion and kept it true-looking for four
    # days. The freshness of the last row is what H2 measures; this check only
    # requires that a row was found and dated.
    check('  and it carries a real timestamp',
          ev.value.tzinfo is not None, ev.value.isoformat())
    live = dict(P._live_state.__globals__)  # noqa: F841  (kept explicit below)
    res = P._live_state(2026, 1)
    by = {o.code for _l, o in res}
    # WAS ASSERTING SILENCE. The executor is alive, so asserting silence was
    # asserting the false premise. The capability to say SILENT is not dropped:
    # H2 already proves the check can say ALIVE on a fresh manifest, and
    # H3 below seeds a stale one and requires SILENT, so both directions stay
    # demonstrated rather than one being assumed from the other.
    check('the live-state run reports the executor as alive',
          'ANCHORED_EXECUTOR_ALIVE' in by, str(sorted(by)))
    check('  and the same run reports the prior losses rather than hiding them',
          'PRIOR_WINDOWS_MISSED' in by, str(sorted(by)))
    check('  and the orphan census',
          'ORPHAN_BLOB_NOT_FROM_AN_OBSERVATION' in by, str(sorted(by)))


def test_H2_the_liveness_check_clears_when_evidence_is_fresh():
    """It must be able to say yes, or it is a constant rather than a measure."""
    print('\nH2. a fresh manifest reads ALIVE')
    now = dt.datetime.now(dt.timezone.utc)
    fresh = json.dumps({
        'capture_id': now.strftime('%Y%m%dT%H%M%SZ'), 'state': 'PASS',
        'source': 's',
        'value': {'retrieved_at': now.isoformat().replace('+00:00', 'Z'),
                  'execution_target': {
                      'basis': 'SCHEDULED_WINDOW_ANCHORED',
                      'executor': {'is_github_actions': True,
                                   'workflow': 'NFL T-90 anchored capture'}}}})
    tmp = _REPO / 'nfl' / 'tests' / 'fixtures' / '_wsj_tmp_live.jsonl'
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        tmp.write_text(fresh + '\n')
        o = P.last_anchored_evidence(tmp)
        check('a row minutes old is found', o.state is State.PASS, str(o)[:140])
        gap = (now - o.value).total_seconds() / 60
        check('  and the gap is inside the two-tick horizon',
              gap <= P.MISSED_TICKS_BEFORE_DEAD * 30, f'{gap:.2f} min')
        stale = json.loads(fresh)
        old = now - dt.timedelta(hours=6)
        stale['value']['retrieved_at'] = old.isoformat().replace('+00:00', 'Z')
        tmp.write_text(json.dumps(stale) + '\n')
        o = P.last_anchored_evidence(tmp)
        gap = (now - o.value).total_seconds() / 60
        check('  and a six-hour-old row is outside it',
              gap > P.MISSED_TICKS_BEFORE_DEAD * 30, f'{gap:.2f} min')
        local = json.loads(fresh)
        local['value']['execution_target']['executor'][
            'is_github_actions'] = False
        tmp.write_text(json.dumps(local) + '\n')
        o = P.last_anchored_evidence(tmp)
        check('a LOCAL execution does not count as the executor being alive -- '
              'that is exactly the 2026-09-13 state, 32 local runs and no '
              'anchored evidence',
              o.state is State.FAIL
              and o.code == 'NO_GITHUB_ACTIONS_EVIDENCE_EVER', str(o)[:140])
    finally:
        tmp.unlink(missing_ok=True)


def test_H3_a_stale_executor_still_reads_SILENT():
    """The direction the live store can no longer exercise.

    Until TASK ZERO, section H asserted ANCHORED_EXECUTOR_SILENT against the
    real manifest, and it passed -- on a premise that was false. The executor
    had never stopped; a stale remote-tracking ref made it look that way. Now
    that main is reconciled the live store reads ALIVE, which is correct, and
    which means the SILENT branch is no longer reachable from real data.

    A branch no test can reach is a branch that will rot. This seeds the
    staleness directly so both verdicts stay demonstrated and neither is
    inferred from the other.
    """
    print('\nH3. a stale executor still reads SILENT')
    now = dt.datetime.now(dt.timezone.utc)
    original = P.last_anchored_evidence
    try:
        for hours, want_silent in ((0.2, False), (48.0, True)):
            stamp = now - dt.timedelta(hours=hours)
            P.last_anchored_evidence = (
                lambda *a, _s=stamp, **k: Outcome.ok('STUB', value=_s))
            by = {o.code for _l, o in P._live_state(2026, 1)}
            if want_silent:
                check(f'  {hours:g}h of silence reads SILENT',
                      'ANCHORED_EXECUTOR_SILENT' in by, str(sorted(by)))
            else:
                check(f'  {hours:g}h reads ALIVE',
                      'ANCHORED_EXECUTOR_ALIVE' in by, str(sorted(by)))
    finally:
        P.last_anchored_evidence = original
    check('and the real store is restored to the live reading',
          'ANCHORED_EXECUTOR_ALIVE'
          in {o.code for _l, o in P._live_state(2026, 1)})


# ---------------------------------------------------------------- I. the schedule fires
def test_I_a_cron_entry_fires_inside_the_next_window():
    print('\nI. the anchored schedule actually covers the window it is for')
    lo = dt.datetime(2026, 9, 14, 22, 45, tzinfo=dt.timezone.utc)
    hi = dt.datetime(2026, 9, 15, 0, 5, tzinfo=dt.timezone.utc)
    entries = re.findall(r"-\s*cron:\s*'([^']+)'",
                         (WF_DIR / 'nfl-t90.yml').read_text())
    check('the T-90 workflow carries cron entries', len(entries) == 16,
          str(len(entries)))
    hits = [e for e in entries if P.cron_fires_in(e, lo, hi)]
    check('at least one fires inside the DEN@KC T-90 window -- the last open '
          'week-1 obligation', len(hits) >= 1, str(hits))
    past_lo = dt.datetime(2026, 9, 13, 15, 30, tzinfo=dt.timezone.utc)
    past_hi = dt.datetime(2026, 9, 13, 16, 50, tzinfo=dt.timezone.utc)
    check('  and entries existed for the Sunday 13:00 ET slate too, so the '
          'crons were correct and simply never fired',
          any(P.cron_fires_in(e, past_lo, past_hi) for e in entries))
    future_lo = dt.datetime(2026, 10, 5, 17, 0, tzinfo=dt.timezone.utc)
    future_hi = dt.datetime(2026, 10, 5, 18, 20, tzinfo=dt.timezone.utc)
    check('NO entry fires in a week-5 window -- an absolute-date schedule '
          'silently expires, and that is now detectable',
          not any(P.cron_fires_in(e, future_lo, future_hi) for e in entries))


def test_I2_the_cron_evaluator_is_right():
    print('\nI2. the cron evaluator, against hand-computed answers')
    D = dt.datetime
    U = dt.timezone.utc
    cases = [
        ("*/5 23 9 9 *", D(2026, 9, 9, 23, 0, tzinfo=U),
         D(2026, 9, 9, 23, 10, tzinfo=U), True),
        ("*/5 23 9 9 *", D(2026, 9, 9, 22, 0, tzinfo=U),
         D(2026, 9, 9, 22, 59, tzinfo=U), False),
        ("50,55 22 9 9 *", D(2026, 9, 9, 22, 51, tzinfo=U),
         D(2026, 9, 9, 22, 54, tzinfo=U), False),
        ("50,55 22 9 9 *", D(2026, 9, 9, 22, 55, tzinfo=U),
         D(2026, 9, 9, 22, 55, tzinfo=U), True),
        ("0 20-23 7 9 *", D(2026, 9, 7, 21, 0, tzinfo=U),
         D(2026, 9, 7, 21, 0, tzinfo=U), True),
    ]
    for expr, lo, hi, want in cases:
        check(f'{expr!r} over {lo:%m-%d %H:%M}-{hi:%H:%M} -> {want}',
              P.cron_fires_in(expr, lo, hi) is want)
    # day-of-month and day-of-week are OR when both are restricted (POSIX and
    # GitHub both). 2026-09-14 is a Monday.
    check('DOM/DOW is an OR when both are restricted',
          P.cron_fires_in('0 12 1 9 1', D(2026, 9, 14, 12, 0, tzinfo=U),
                          D(2026, 9, 14, 12, 0, tzinfo=U)))
    check('  and an AND-style read would have said no',
          not P.cron_fires_in('0 12 1 9 *', D(2026, 9, 14, 12, 0, tzinfo=U),
                              D(2026, 9, 14, 12, 0, tzinfo=U)))


# ---------------------------------------------------------------- J/K. the workflows
def test_J_every_capture_workflow_carries_the_guards():
    print('\nJ. the guards are in every workflow that writes to the store')
    import yaml
    for name, job in (('nfl-capture.yml', 'capture'),
                      ('nfl-t90.yml', 'capture'),
                      ('nfl-status.yml', 'capture')):
        y = (WF_DIR / name).read_text()
        d = yaml.safe_load(y)
        steps = [s.get('name') or s.get('uses')
                 for s in d['jobs'][job]['steps']]
        idx = {s: i for i, s in enumerate(steps)}
        check(f'{name}: the store is snapshotted before the capture',
              idx.get('Snapshot the vintage store before capture', 99)
              < idx.get('Capture', -1), str(steps))
        check(f'{name}: the blob/manifest delta gate runs after the commit',
              any('without a manifest row' in s for s in steps)
              and idx['Commit anything captured']
              < next(i for s, i in idx.items()
                     if 'without a manifest row' in s), str(steps))
        check(f'{name}: the log-string row guard is still there too',
              'CAPTURE_WROTE_NO_MANIFEST_ROW' in y)
        check(f'{name}: the interpreter is asserted, not assumed',
              'INTERPRETER_TOO_OLD' in y)
        check(f'{name}: tee cannot mask the capture exit code',
              'PIPESTATUS[0]' in y and 'echo "exit=$?"' not in y)
        commit = next(i for s, i in idx.items() if 'Commit' in s)
        fail = next(i for s, i in idx.items() if 'Fail' in s)
        check(f'{name}: the commit still runs before the FAIL gate -- a '
              f'control failure must not discard captured bytes',
              commit < fail, f'commit={commit} fail={fail}')


def test_K_the_liveness_workflow_exists_and_cannot_capture():
    print('\nK. the liveness workflow is a detector, not another writer')
    import yaml
    f = WF_DIR / 'nfl-capture-liveness.yml'
    check('it exists', f.exists(), str(f))
    d = yaml.safe_load(f.read_text())
    check('it is scheduled', 'schedule' in (d.get(True) or d.get('on') or {}))
    check('with read-only permissions, so it can never append a manifest row '
          'or commit a blob',
          (d.get('permissions') or {}).get('contents') == 'read',
          str(d.get('permissions')))
    y = f.read_text()
    check('it does not invoke the capture tool', 'capture_vintage' not in y)
    check('it is NOT in the capture concurrency group, so it can never delay '
          'a T-90 window', d['concurrency']['group'] != 'nfl-vintage-capture',
          str(d['concurrency']))
    check('and it states the limit it cannot overcome',
          'Actions can detect GitHub Actions being off' in y)


def test_L_the_scheduler_gate_cannot_hide_a_failure():
    """`--gate scheduler` narrows the exit code. It must not narrow the report."""
    print('\nL. narrowing the gate does not narrow what is printed')
    check('the silent-executor code is gated',
          'ANCHORED_EXECUTOR_SILENT' in P.SCHEDULER_GATED_CODES)
    check('  as is a window with no cron entry',
          'WINDOW_HAS_NO_CRON_ENTRY' in P.SCHEDULER_GATED_CODES)
    check('the unrecoverable prior losses are NOT gated, deliberately',
          'PRIOR_WINDOWS_MISSED' not in P.SCHEDULER_GATED_CODES)
    argv = sys.argv[:]
    buf = io.StringIO()
    try:
        sys.argv = ['preflight', '--season', '2026', '--week', '1',
                    '--gate', 'scheduler']
        with redirect_stdout(buf):
            rc = P.main()
    finally:
        sys.argv = argv
    out = buf.getvalue()
    # WAS rc == 1. With the executor alive, the scheduler gate has nothing to
    # gate, so the run exits 0 and the non-gated failures are still printed.
    # The assertion that matters is the one below it -- that a non-gated
    # failure is reported in full rather than swallowed by a clean exit --
    # and that is now the load-bearing half of this test.
    check('the run exits cleanly once the scheduler gate has nothing to gate',
          rc == 0, str(rc))
    check('a NON-gated failure is still printed in full',
          'PRIOR_WINDOWS_MISSED' in out and 'ORPHAN_BLOB' in out)
    check('  and is labelled as reported rather than silently dropped',
          'reported, not gating' in out)
    check('the summary never claims zero failing while the store says '
          'otherwise', '0 failing' not in out, out[-400:])


# ---------------------------------------------------------------- M/N. the network ceiling
def test_M_a_live_source_fetch_cannot_be_proven_here():
    blocked('a fetch of nfl.com/injuries returns bytes', Cause.NETWORK,
            'this executor is refused at the egress proxy (CONNECT '
            'www.nfl.com:443 -> 403). A mock would prove only that the mock '
            'returns what it was told to. Filed as OUT-012.')


def test_M2_that_a_cron_actually_fired_cannot_be_proven_here():
    blocked('a scheduled run of NFL T-90 anchored capture started on GitHub',
            Cause.NETWORK,
            'GitHub Actions run history is outside this checkout and absence '
            'of a commit is not proof a run did not start. Needs the Actions '
            'API. Filed as OUT-011.')


def test_N_every_blocked_proof_has_a_filed_request():
    """A blocked proof that nobody was asked for is a shrug."""
    print('\nN. the blocked proofs are assigned, not abandoned')
    text = OUTBOX.read_text()
    for ident in ('OUT-011', 'OUT-012'):
        check(f'{ident} is filed in the outbox', ident in text)
    check('OUT-011 names the workflow files the networked agent must query',
          'nfl-t90.yml' in text and 'nfl-capture.yml' in text)
    check('OUT-011 names the exact stop time',
          '2026-09-11T03:38' in text or '2026-09-11T00:44' in text)
    check('and the outbox states these are assigned, not blocked for both',
          'ASSIGNED' in text)


if __name__ == '__main__':
    for fn in sorted(n for n in dir() if n.startswith('test_')):
        globals()[fn]()
    print(f'\n{PASSED} passed, {FAILED} failed, {BLOCKED} blocked')
    sys.exit(1 if FAILED else 0)
