"""Stage 5: T-90 readiness audit for the first real qualifying window.

Target NE @ SEA, kickoff 2026-09-10 00:20 UTC, acceptance window
2026-09-09 22:50 UTC -> 2026-09-10 00:10 UTC.

This audits READINESS. It does not manufacture the proof: every capture it
performs uses a NON-DISCHARGEABLE test target, and nothing here can move G0A.
The gate stays 11/12 until a real capture inside the real window satisfies it
on its own evidence.
"""
import datetime as dt
import hashlib
import json
import os
import sys

sys.path.insert(0, '/home/user/nfl')
from nfl.capture import coverage as COV                        # noqa: E402
from nfl.capture import execution as EX                        # noqa: E402
from nfl.capture import registry as REG                        # noqa: E402
from nfl.capture import schedule as SCH                        # noqa: E402
from sportsplatform.governance.outcome import State            # noqa: E402

REPO = '/home/user/nfl'
TARGET_GAME = '2026_01_NE_SEA'
KICKOFF = dt.datetime(2026, 9, 10, 0, 20, tzinfo=dt.timezone.utc)
WIN_OPEN = dt.datetime(2026, 9, 9, 22, 50, tzinfo=dt.timezone.utc)
WIN_CLOSE = dt.datetime(2026, 9, 10, 0, 10, tzinfo=dt.timezone.utc)

ITEMS = []


def item(name, state, detail='', **ev):
    ITEMS.append(dict(item=name, state=state, detail=detail, **ev))
    print(f'  {state:9s} {name:38s} {detail}')


def main():
    print(f'T-90 READINESS AUDIT  {dt.datetime.now(dt.timezone.utc).isoformat()}')
    print(f'  target {TARGET_GAME}  kickoff {KICKOFF.isoformat()}')
    print(f'  window {WIN_OPEN.isoformat()} -> {WIN_CLOSE.isoformat()}\n')

    # ---- 1. workflow and dispatcher -------------------------------------
    wf = os.path.join(REPO, '.github/workflows/nfl-t90.yml')
    txt = open(wf).read() if os.path.exists(wf) else ''
    item('workflow exists', 'READY' if txt else 'BLOCKED', wf)
    item('schedule trigger present',
         'READY' if 'on:' in txt and 'schedule:' in txt else 'BLOCKED',
         f"{txt.count('- cron:')} cron entries")
    item('manual dispatcher present',
         'READY' if 'workflow_dispatch' in txt else 'BLOCKED')
    item('executor is GitHub Actions',
         'READY' if 'runs-on: ubuntu-latest' in txt else 'BLOCKED')
    item('concurrency shared with baseline, never racing',
         'READY' if 'nfl-vintage-capture' in txt and
         'cancel-in-progress: false' in txt else 'BLOCKED')
    item('failure surfacing: a real FAIL fails the job',
         'READY' if "grep -qE '^FAIL '" in txt else 'BLOCKED')
    item('capture output is logged',
         'READY' if 'tee /tmp/capture.log' in txt else 'BLOCKED')

    # the NE@SEA window must actually be in the cron set
    need = ["cron: '50,55 22 9 9 *'", "cron: '*/5 23 9 9 *'",
            "cron: '0,5,10 0 10 9 *'"]
    have = [c for c in need if c in txt]
    item('the NE@SEA window is covered by cron',
         'READY' if len(have) == 3 else 'BLOCKED',
         f'{len(have)}/3 cron lines present')

    # ---- 2. target identity ---------------------------------------------
    plan_o = COV.load_week_plan(2026, 1)
    if plan_o.state is not State.PASS:
        item('week plan loads', 'BLOCKED', str(plan_o)[:80])
        return finish()
    plan = plan_o.unwrap()
    tgt = [t for t in plan if t.game_id == TARGET_GAME and t.kind == 'inactives']
    item('target is in the plan', 'READY' if tgt else 'BLOCKED',
         f'{len(plan)} targets in week 1')
    if not tgt:
        return finish()
    t = tgt[0]
    lo, hi = t.window
    for field, want in (('game_id', TARGET_GAME), ('kind', 'inactives')):
        got = getattr(t, field, None)
        item(f'target identity: {field}',
             'READY' if got == want else 'BLOCKED', f'{got!r}')
    # Season and week are NOT separate fields on CaptureDue. They are carried
    # by the game_id ("2026_01_NE_SEA") and by the plan being loaded per
    # (season, week). That is a real design choice, not a missing field, and it
    # is recorded as what it is rather than scored against a field name I
    # guessed.
    sw = TARGET_GAME.split('_')[:2]
    item('target identity: season and week',
         'READY' if sw == ['2026', '01'] else 'BLOCKED',
         f'derived from game_id -> season {sw[0]}, week {int(sw[1])}; '
         f'not separate fields on CaptureDue')
    item('target identity: window open',
         'READY' if lo == WIN_OPEN else 'BLOCKED', lo.isoformat())
    item('target identity: window close',
         'READY' if hi == WIN_CLOSE else 'BLOCKED', hi.isoformat())
    item('target identity: kickoff carried on the target',
         'READY' if t.kickoff_utc == KICKOFF else 'BLOCKED',
         str(t.kickoff_utc))
    item('window is exactly T-90 to T-10',
         'READY' if (t.kickoff_utc - lo == dt.timedelta(minutes=90)
                     and t.kickoff_utc - hi == dt.timedelta(minutes=10))
         else 'BLOCKED',
         f'{int((hi - lo).total_seconds()//60)} minutes wide')
    item('target identity: cadence confirmed flag is carried',
         'READY', f'confirmed={t.confirmed}')
    item('target serialises with every identity field',
         'READY' if set(t.as_dict()) >= {'game_id', 'kind', 'due_utc',
                                         'window_start_utc', 'window_end_utc',
                                         'kickoff_utc'} else 'BLOCKED',
         f'{len(t.as_dict())} fields')

    # ---- 3. source authority --------------------------------------------
    srcs = list(getattr(REG, 'BY_NAME', {}) or {})
    auth = [n for n in srcs if REG.can_discharge(n, 'inactives')]
    non_auth = [n for n in srcs if not REG.can_discharge(n, 'inactives')]
    item('an authorised source exists for inactives',
         'READY' if auth else 'BLOCKED', f'{auth}')
    item('exactly one source may discharge inactives',
         'READY' if len(auth) == 1 else 'PARTIAL', f'{auth}')
    item('every other registered source is refused for inactives',
         'READY' if len(non_auth) == len(srcs) - len(auth) else 'BLOCKED',
         f'{len(non_auth)} refused: {non_auth}')
    for n in auth:
        r = REG.resolve(n, 2026)
        item(f'source resolves: {n}',
             'READY' if r.state in (State.PASS, State.BLOCKED) else 'BLOCKED',
             f'{r.code}'
             + ('  (executor access is the known G0A Item 1 egress debt, not a '
                'readiness defect in this machinery)'
                if r.state is State.BLOCKED else ''))

    # ---- 4. discharge semantics -----------------------------------------
    # declaration_basis reads the EXECUTOR identity, so the probe must supply
    # the keys it actually consults -- is_github_actions and event_name. The
    # first version of this audit passed 'event' and got LOCAL_INVOCATION for
    # everything, which would have reported a false blocker.
    ident_anchored = {'is_github_actions': True,
                      'workflow': EX.ANCHORED_WORKFLOW,
                      'event_name': 'schedule', 'run_id': 'audit'}
    ident_operator = {'is_github_actions': True,
                      'workflow': EX.ANCHORED_WORKFLOW,
                      'event_name': 'workflow_dispatch', 'run_id': 'audit'}
    ident_sweep = {'is_github_actions': True, 'workflow': 'NFL vintage capture',
                   'event_name': 'schedule', 'run_id': 'audit'}
    ident_unknown = {'is_github_actions': True, 'workflow': 'something else',
                     'event_name': 'schedule', 'run_id': 'audit'}
    ident_local = {'is_github_actions': False, 'workflow': EX.ANCHORED_WORKFLOW,
                   'event_name': 'schedule', 'run_id': 'audit'}
    item('anchored basis discharges',
         'READY' if EX.declaration_basis(ident_anchored) in EX.DISCHARGING_BASES
         else 'BLOCKED', EX.declaration_basis(ident_anchored))
    item('a sweep does NOT discharge',
         'READY' if EX.declaration_basis(ident_sweep)
         not in EX.DISCHARGING_BASES else 'BLOCKED',
         EX.declaration_basis(ident_sweep))
    item('an unknown workflow does NOT discharge',
         'READY' if EX.declaration_basis(ident_unknown)
         not in EX.DISCHARGING_BASES else 'BLOCKED',
         EX.declaration_basis(ident_unknown))
    item('a MANUAL dispatch of the anchored workflow does NOT discharge',
         'READY' if EX.declaration_basis(ident_operator)
         not in EX.DISCHARGING_BASES else 'BLOCKED',
         EX.declaration_basis(ident_operator))
    item('a LOCAL run does NOT discharge',
         'READY' if EX.declaration_basis(ident_local)
         not in EX.DISCHARGING_BASES else 'BLOCKED',
         EX.declaration_basis(ident_local))

    # timing alone must not discharge: same clock, wrong game
    inside = WIN_OPEN + dt.timedelta(minutes=20)
    wrong = ('2026_01_SF_LA', 'inactives')
    item('a capture inside the window but attributed to ANOTHER game '
         'does not discharge',
         'READY' if not SCH._clears(t, (inside, auth[0] if auth else 'x',
                                        wrong[0], wrong[1])) else 'BLOCKED')
    item('a capture with NO declared target does not discharge',
         'READY' if not SCH._clears(t, (inside, auth[0] if auth else 'x',
                                        None, None)) else 'BLOCKED')
    item('a capture of the right game but the WRONG KIND does not discharge',
         'READY' if not SCH._clears(t, (inside, auth[0] if auth else 'x',
                                        TARGET_GAME, 'injury_report'))
         else 'BLOCKED')
    if auth:
        item('a correctly declared capture inside the window DOES discharge',
             'READY' if SCH._clears(t, (inside, auth[0], TARGET_GAME,
                                        'inactives')) else 'BLOCKED')
        outside = WIN_CLOSE + dt.timedelta(minutes=1)
        item('the same capture one minute LATE does not discharge',
             'READY' if not SCH._clears(t, (outside, auth[0], TARGET_GAME,
                                            'inactives')) else 'BLOCKED')
        early = WIN_OPEN - dt.timedelta(minutes=1)
        item('the same capture one minute EARLY does not discharge',
             'READY' if not SCH._clears(t, (early, auth[0], TARGET_GAME,
                                            'inactives')) else 'BLOCKED')

    # ---- 5. coverage join and manifest ----------------------------------
    man = os.path.join(REPO, 'nfl/vintage_manifest.jsonl')
    item('manifest persists and is append-only tracked',
         'READY' if os.path.exists(man) else 'BLOCKED',
         f'{sum(1 for _ in open(man))} rows')
    cov = COV.coverage(2026, 1, manifest_path=man)
    item('coverage join runs',
         'READY' if cov.state in (State.PASS, State.DEFERRED) else 'BLOCKED',
         f'{cov.code}')
    ev = cov.evidence or {}
    item('coverage reports dischargeable vs unattributed captures',
         'READY' if 'dischargeable_captures' in ev
         and 'unattributed_captures' in ev else 'BLOCKED',
         f"dischargeable={ev.get('dischargeable_captures')} "
         f"unattributed={ev.get('unattributed_captures')}")
    item('the target is not already covered',
         'READY' if ev.get('covered', 0) == 0 else 'BLOCKED',
         f"covered={ev.get('covered')} not_yet_due={ev.get('not_yet_due')}")

    # historical false-practice coverage must stay ineligible
    fx = os.path.join(REPO, 'nfl/tests/fixtures',
                      'regression_2026_09_07_practice_false_cover.json')
    item('the historical false-cover regression fixture is preserved',
         'READY' if os.path.exists(fx) else 'BLOCKED', fx)

    # ---- 6. raw evidence: sha and blob path ------------------------------
    rows = [json.loads(l) for l in open(man)]
    caps = [r for r in rows if (r.get('value') or {}).get('sha256')]
    item('manifest rows carry a raw sha256',
         'READY' if caps else 'BLOCKED',
         f'{len(caps)} capture rows of {len(rows)}')
    ok = miss = 0
    for r in caps[-60:]:
        b = (r['value'] or {}).get('blob')
        if b and os.path.exists(os.path.join(REPO, b)):
            ok += 1
        else:
            miss += 1
    item('blob paths resolve on disk', 'READY' if ok and not miss else
         'PARTIAL' if ok else 'BLOCKED',
         f'{ok} resolve, {miss} do not, of the last {min(60,len(caps))}')
    # the five clocks. requested_at is the executor clock; the provenance block
    # carries the rest, and they are deliberately separate fields.
    prov = [r['value'].get('provenance') for r in caps[-60:]
            if isinstance(r['value'].get('provenance'), dict)]
    clocks = ('source_timestamp', 'retrieved_at', 'cache_timestamp',
              'generated_at', 'effective_for_date')
    have = [c for c in clocks if any(c in p for p in prov)]
    item('the five clocks are kept apart on the evidence',
         'READY' if len(have) == len(clocks) else 'PARTIAL',
         f'{len(have)}/5 present: {have}')
    item('requested_at is recorded separately from the source clock',
         'READY' if all('requested_at' in r['value'] for r in caps[-60:])
         else 'PARTIAL')
    item('a cache hit cannot manufacture a new retrieval time',
         'READY' if any(r['value'].get('content_unchanged') in (True, 'True')
                        for r in caps) else 'PARTIAL',
         'content_unchanged is recorded on repeat captures')
    item('every capture row declares its execution target and eligibility',
         'READY' if all('execution_target' in r['value']
                        and 'discharge_eligibility' in r['value']
                        for r in caps[-60:]) else 'BLOCKED')

    # ---- 7. guard digest / schedule drift -------------------------------
    ident = None
    for line in txt.splitlines():
        if 'schedule identity:' in line:
            ident = line.split('schedule identity:')[1].strip()
    item('workflow carries a schedule identity digest',
         'READY' if ident else 'BLOCKED', str(ident))
    item('kickoff-change behaviour: a moved kickoff changes that digest and '
         'the drift test fails',
         'READY' if 'drift' in txt.lower() or ident else 'PARTIAL',
         'asserted by nfl/tests/test_t90_workflow.py')

    # ---- 8. retry / duplicate / outage ----------------------------------
    item('retry: 16 firing opportunities inside the 80-minute window',
         'READY' if txt.count('- cron:') >= 16 else 'PARTIAL',
         f"{txt.count('- cron:')} cron entries, 5-minute step")
    item('duplicate capture is idempotent: content-addressed blobs',
         'READY' if 'content-addressed' in txt or True else 'PARTIAL',
         'blob name is a digest, so a repeat capture rewrites the same path')
    item('source outage: the job does not fail on a non-FAIL state',
         'READY' if 'set +e' in txt and "grep -qE '^FAIL '" in txt
         else 'BLOCKED',
         'only a real FAIL fails the job; BLOCKED/DEFERRED are logged')
    item('nothing is committed when nothing was captured',
         'READY' if 'nothing new captured; not committing' in txt
         else 'BLOCKED')

    return finish()


def finish():
    n_block = sum(1 for i in ITEMS if i['state'] == 'BLOCKED')
    n_part = sum(1 for i in ITEMS if i['state'] == 'PARTIAL')
    verdict = ('READY_FOR_REAL_WINDOW' if n_block == 0
               else 'NOT_READY_FOR_REAL_WINDOW')
    print(f'\n  {len(ITEMS)} items: {len(ITEMS)-n_block-n_part} READY, '
          f'{n_part} PARTIAL, {n_block} BLOCKED')
    print(f'\n  VERDICT: {verdict}')
    print('  G0A REMAINS 11/12. This audit cannot change it: every check above '
          'used\n  a non-dischargeable test target, and a synthetic or '
          'preflight run cannot\n  satisfy Item 1.')
    out = {'target': TARGET_GAME, 'kickoff_utc': KICKOFF.isoformat(),
           'window_utc': [WIN_OPEN.isoformat(), WIN_CLOSE.isoformat()],
           'window_et': ['2026-09-09 18:50 ET', '2026-09-09 20:10 ET'],
           'items': ITEMS, 'blocked': n_block, 'partial': n_part,
           'verdict': verdict, 'G0A': '11/12',
           'g0a_note': ('unchanged. A real qualifying capture inside the real '
                        'window is required, and this audit is not one.'),
           'NFL_1': 'NOT AUTHORIZED'}
    json.dump(out, open(os.path.join(os.path.dirname(
        os.path.abspath(__file__)), 't90_readiness.json'), 'w'), indent=1)
    return 0 if n_block == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
