"""Automatic Scientist v0: one assumption, identified through governance.

THE VERTICAL SLICE, IN ORDER

  1. IDENTIFY   A1 is in the registry with its falsifier written before any
                test ran.
  2. AUDIT      where does the live model actually assert certainty? The
                boundary audit runs over CS2's real output for 2026 week 2.
  3. MEASURE    does football support it? The historical cohort test runs on
                2022-2025 and returns a rate with an interval.
  4. FALSIFY    the falsifier is applied AS WRITTEN. No clause is added or
                softened after seeing the number.
  5. CLASSIFY   the status moves along a legal edge, with evidence attached.
  6. GOVERN     `assert_promotable` refuses to promote the consumers named in
                `downstream_dependencies`.

AND WHAT STEP 7 IS NOT. There is no step that changes a probability. The
audit reports, the measurement measures, the registry blocks. CS2's output on
disk is byte-identical before and after this runs, and `test_assumption_
governance` asserts exactly that.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import artifact_claim as AC             # noqa: E402
from sportsplatform.governance import assumption as AS                 # noqa: E402
from sportsplatform.governance.outcome import State                    # noqa: E402
from nfl.production.assumptions import audit_appearance as AA          # noqa: E402
from nfl.production.assumptions import registry as REG                 # noqa: E402
from nfl.production.nonqb import cs2_state as CS                       # noqa: E402
from nfl.production.nonqb import current_season_nonqb_panel as P       # noqa: E402
from nfl.research.assumptions import cohort_appearance_certainty as CO  # noqa: E402

SPEC_VERSION = 'automatic-scientist-v0'
OUT = _REPO / 'nfl/research/assumptions/ASSUMPTION_AUDIT.json'
SEAL = '2026-09-16T15:45:14Z'
N_DRAWS = 8000          # the sealed board's draw count; the band comes from it
FIT = _REPO / 'nfl/research/cs2/CS2_STAGE2_FIT.json'


def live_appearance() -> Outcome:
    """CS2's real appearance probabilities for the room the defect lives in."""
    fit = json.loads(FIT.read_text())
    ka = fit['best_appearance']['kappa_a']
    ks = fit['best_allocation']['kappa_s']
    cur = P.usage_season(2026, as_of=SEAL)
    prev = P.usage_season(2025)
    if cur.state is not State.PASS or prev.state is not State.PASS:
        return cur if cur.state is not State.PASS else prev
    prior = CS.prior_from_season(prev.value, CS.CARRIES)
    return CS.state(cur.value, prior, CS.CARRIES, kappa_a=ka, kappa_s=ks,
                    n_weeks=1)


def run() -> dict:
    body = {'artifact': 'ASSUMPTION_AUDIT', 'spec_version': SPEC_VERSION,
            'scope': 'v0: one assumption end to end, no source-code scanner',
            'nothing_is_repaired': (
                'no probability is clipped, floored or adjusted anywhere in '
                'this pipeline. A falsified assumption blocks a promotion and '
                'leaves the model output exactly as it was.')}

    reg = REG.audit()
    body['registry'] = {'state': reg.state.value, 'code': reg.code,
                        'detail': reg.detail,
                        'by_status': reg.evidence['by_status'],
                        'by_criticality': reg.evidence['by_criticality'],
                        'assumptions': [a.to_dict() for a in REG.REGISTRY]}
    if reg.state is not State.PASS:
        return body

    st = live_appearance()
    if st.state is State.PASS:
        p = {f'{k[0]}:{k[1]}': r['p_appears'] for k, r in st.value.items()}
        aud = AA.audit(p, n_draws=N_DRAWS, label='CS2 carries room, 2026 wk2')
        body['boundary_audit'] = {
            'state': aud.state.value, 'code': aud.code, 'detail': aud.detail,
            'evidence': {k: v for k, v in aud.evidence.items()
                         if k != 'cause'}}
    else:
        body['boundary_audit'] = {'state': st.state.value, 'code': st.code,
                                  'detail': st.detail}

    co = CO.measure(verbose=False)
    body['cohort_measurement'] = {
        'state': co.state.value, 'code': co.code, 'detail': co.detail,
        'evidence': ({k: v for k, v in co.evidence.items() if k != 'cause'}
                     if co.state is State.PASS else {})}

    a1 = REG.get('A1_APPEARANCE_CERTAINTY')
    if co.state is State.PASS:
        ev = co.evidence
        # THE FALSIFIER, APPLIED AS WRITTEN.
        falsified = ev['falsifies_a1']
        moved = AS.settle(
            a1, status=AS.FALSIFIED if falsified else AS.SUPPORTED,
            evidence={'rate': ev['rate'], 'ci95': ev['ci95'],
                      'n': ev['n_cohort_weeks'], 'failures': ev['n_failed'],
                      'seasons': ev['seasons'],
                      'test': a1.test,
                      'limb_upper_bound_below_one':
                          ev['falsifier_limb_upper_bound_below_one'],
                      'limb_any_observed_failure':
                          ev['falsifier_limb_any_observed_failure']},
            uncertainty=f"95% Wilson [{ev['ci95'][0]:.6f}, "
                        f"{ev['ci95'][1]:.6f}] on n={ev['n_cohort_weeks']}")
        body['settlement'] = {'state': moved.state.value, 'code': moved.code,
                              'detail': moved.detail,
                              'falsifier_unchanged':
                                  moved.evidence.get('falsifier_unchanged')}
        if moved.state is State.PASS:
            a1 = moved.value
            body['registry']['assumptions'] = [
                (a1.to_dict() if a.id == a1.id else a.to_dict())
                for a in REG.REGISTRY]

    settled = [a1 if a.id == a1.id else a for a in REG.REGISTRY]
    body['promotion'] = {}
    for consumer in sorted({d for a in settled
                            for d in a.downstream_dependencies}):
        g = AS.assert_promotable(settled, consumer=consumer,
                                 require_tested=False)
        body['promotion'][consumer] = {
            'state': g.state.value, 'code': g.code, 'detail': g.detail,
            'falsified_critical': g.evidence['falsified_critical'],
            'untested_critical': g.evidence['untested_critical']}
    return body


def main() -> int:
    body = run()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(body, indent=1, sort_keys=True, default=str))
    print(f"registry   : {body['registry']['code']} "
          f"{body['registry']['by_status']}")
    ba = body.get('boundary_audit', {})
    print(f"boundary   : {ba.get('code')} {ba.get('detail', '')[:120]}")
    cm = body.get('cohort_measurement', {})
    print(f"cohort     : {cm.get('code')} {cm.get('detail', '')}")
    st = body.get('settlement', {})
    print(f"settlement : {st.get('code')} {st.get('detail', '')}")
    print('promotion  :')
    for k, v in body['promotion'].items():
        print(f"    {k:48s} {v['code']}")
    c = AC.claim(OUT, schema=['registry', 'promotion'], label=OUT.name)
    return 0 if c.state is State.PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())
