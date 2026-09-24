"""The pre-kickoff forecast-cut registry, and the refusals that give it value.

WHAT THIS MODULE ASSERTS
========================
1. A CUT CANNOT BE REGISTERED AFTER KICKOFF. This is the property the whole
   artifact rests on. A grading row written after a game can never establish
   that the forecast existed before it; this ledger can, but only because it
   refuses to be written afterwards. A row claiming to be prospective and
   written after the event is worse than no row, because it looks like
   evidence.
2. A CUT CANNOT BE REGISTERED TWICE. Later outcomes may GRADE a cut keyed by
   cut_id; they may never mutate it. Re-registration would let a later belief
   overwrite what was actually believed at prediction time.
3. THE EVIDENCE DIGEST IS A FUNCTION OF CONTENT, NOT OF ORDER OR PATH. Two
   contracts listing the same families and hashes in different dictionary
   order give the same digest; moving a blob does not move it; changing one
   source's sha256 does.
4. UNHASHED OR ABSENT EVIDENCE REFUSES rather than registering a row with
   empty fields. A registration that records nothing is not a record.
5. A FAILED RUN IS STILL REGISTERED. Registration is not conditional on
   sealing: an unsealed research output is a forecast that existed at a time,
   and its refusal state is part of what is registered. If only passing runs
   entered the scientific record, the record would carry exactly the sampling
   bias this project exists to avoid.
6. TONIGHT'S REAL CUT IS IN THE LEDGER, registered before kickoff.
"""
import datetime as dt
import json
import os
import sys
import tempfile

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from nfl.prospective.cut_ledger import (  # noqa: E402
    LEDGER,
    CutLedgerError,
    build_row,
    evidence_bundle_hash,
    existing_cut_ids,
    register,
)

PASSED = FAILED = BLOCKED = 0

RUN = os.path.join(_ROOT, 'nfl', 'research', 'unsealed',
                   '2026_03_ATL_GB', '2fc4e9599f0889f1')
KICKOFF = '2026-09-25T00:15:00Z'
BEFORE = dt.datetime(2026, 9, 24, 19, 0, tzinfo=dt.timezone.utc)
AFTER = dt.datetime(2026, 9, 25, 3, 0, tzinfo=dt.timezone.utc)


def chk(label, ok, detail=''):
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


def raises(fn, needle=''):
    try:
        fn()
    except CutLedgerError as e:
        return needle in str(e)
    return False


def test_a_cut_cannot_be_registered_after_kickoff():
    if not os.path.isdir(RUN):
        return blocked('post-kickoff refusal', f'{RUN} absent')
    chk('registering before kickoff builds a row',
        build_row(RUN, KICKOFF, now=BEFORE)['cut_id'].startswith('CUT-'))
    chk('registering AFTER kickoff refuses',
        raises(lambda: build_row(RUN, KICKOFF, now=AFTER),
               'has already passed'))
    chk('and says why in those words',
        raises(lambda: build_row(RUN, KICKOFF, now=AFTER),
               'looks like evidence'))


def test_a_cutoff_at_or_after_kickoff_is_not_a_pregame_forecast():
    if not os.path.isdir(RUN):
        return blocked('cutoff ordering', f'{RUN} absent')
    # The clock must sit before BOTH, or the post-kickoff refusal fires
    # first and this branch is never reached. The run's cutoff is 15:30Z, so
    # a 15:20Z kickoff read at 15:00Z is future-dated AND before the cutoff.
    chk('a kickoff at or before the declared cutoff refuses',
        raises(lambda: build_row(
            RUN, '2026-09-24T15:20:00Z',
            now=dt.datetime(2026, 9, 24, 15, 0, tzinfo=dt.timezone.utc)),
            'not a pregame forecast'))
    chk('and the post-kickoff refusal takes precedence when both apply',
        raises(lambda: build_row(RUN, '2026-09-24T15:00:00Z', now=BEFORE),
               'has already passed'))


def test_a_cut_cannot_be_registered_twice():
    if not os.path.isdir(RUN):
        return blocked('append-only', f'{RUN} absent')
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'ledger.jsonl')
        first = register(RUN, KICKOFF, path=path, now=BEFORE)
        chk('the first registration writes', os.path.exists(path))
        chk('a second registration of the same cut REFUSES',
            raises(lambda: register(RUN, KICKOFF, path=path, now=BEFORE),
                   'already registered'))
        chk('and explains that grading happens elsewhere',
            raises(lambda: register(RUN, KICKOFF, path=path, now=BEFORE),
                   'graded elsewhere'))
        chk('the file still holds exactly one row',
            len([x for x in open(path).read().splitlines() if x.strip()]) == 1)
        chk('and that row is the one we wrote',
            existing_cut_ids(path) == {first['cut_id']})


def test_the_evidence_digest_follows_content_not_order_or_path():
    a = {'entries': {'schedules': {'sha256': 'aa', 'blob': 'x/one.gz'},
                     'injuries': {'sha256': 'bb', 'blob': 'x/two.gz'}}}
    b = {'entries': {'injuries': {'sha256': 'bb', 'blob': 'MOVED/two.gz'},
                     'schedules': {'sha256': 'aa', 'blob': 'MOVED/one.gz'}}}
    c = {'entries': {'schedules': {'sha256': 'aa', 'blob': 'x/one.gz'},
                     'injuries': {'sha256': 'CHANGED', 'blob': 'x/two.gz'}}}
    ha, _ = evidence_bundle_hash(a)
    hb, _ = evidence_bundle_hash(b)
    hc, _ = evidence_bundle_hash(c)
    chk('dictionary order and blob path do not move the digest', ha == hb)
    chk('changing one source sha256 DOES move it', ha != hc)
    chk('an empty bundle refuses',
        raises(lambda: evidence_bundle_hash({'entries': {}}), 'not a bundle'))
    chk('a source with no sha256 refuses',
        raises(lambda: evidence_bundle_hash(
            {'entries': {'schedules': {'blob': 'x'}}}), 'carries no sha256'))


def test_a_run_whose_artifacts_are_missing_refuses():
    with tempfile.TemporaryDirectory() as tmp:
        chk('an empty run directory refuses rather than writing empty fields',
            raises(lambda: build_row(tmp, KICKOFF, now=BEFORE), 'is missing'))


def test_a_failed_run_is_still_registered():
    """Registration is not conditional on sealing."""
    if not os.path.isdir(RUN):
        return blocked('failed-run registration', f'{RUN} absent')
    row = build_row(RUN, KICKOFF, now=BEFORE)
    pub = row.get('publication') or {}
    chk('this run did NOT publish',
        pub.get('state') == 'BLOCKED', json.dumps(pub)[:80])
    chk('and it is registered anyway, with the refusal recorded',
        row['cut_id'].startswith('CUT-')
        and (row.get('first_failure') or {}).get('stage') == 'artifact_sealing',
        json.dumps(row.get('first_failure'))[:90])
    chk('the row carries the evidence bundle digest',
        len(row['evidence_bundle_sha256']) == 64)
    chk('and every frozen source, hashed',
        len(row['sources']) == 7
        and all(s['sha256'] for s in row['sources']),
        str(len(row['sources'])))
    chk('and the draw artifact identity',
        row['n_draws'] == 8000 and len(row['draw_content_digest']) == 64)
    chk('it stores no outcome of any kind',
        not any(k in row for k in ('actual', 'crps', 'result', 'graded')))


def test_tonights_real_cut_is_registered_before_kickoff():
    if not LEDGER.exists():
        return blocked('live ledger', f'{LEDGER} not written yet')
    rows = [json.loads(x) for x in LEDGER.read_text().splitlines() if x.strip()]
    ours = [r for r in rows if r.get('game_id') == '2026_03_ATL_GB']
    if not ours:
        return blocked('live ledger', 'no ATL/GB cut registered')
    r = ours[-1]
    chk('the cut is registered', r['cut_id'].startswith('CUT-'))
    chk('registered strictly before kickoff',
        r['registered_at_utc'] < r['kickoff_utc'],
        f"{r['registered_at_utc']} vs {r['kickoff_utc']}")
    chk('with a cutoff strictly before kickoff',
        r['cutoff_utc'] < r['kickoff_utc'])
    chk('naming the candidate and the code commit',
        bool(r['code_commit']) and bool(r['candidate_identity']))
    chk('cut ids are unique across the ledger',
        len({x['cut_id'] for x in rows}) == len(rows))
    print(f"       {r['cut_id']}  registered {r['registered_at_utc']}  "
          f"kickoff {r['kickoff_utc']}")


if __name__ == '__main__':
    for _n, _f in sorted((n, f) for n, f in list(globals().items())
                         if n.startswith('test_') and callable(f)):
        print(f'\n== {_n}')
        _f()
    print(f'\nPASSED {PASSED}  FAILED {FAILED}  BLOCKED {BLOCKED}')
    raise SystemExit(1 if FAILED else 0)
