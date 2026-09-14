"""Reuse may preserve a predictive payload. It may never preserve admissibility.

    python3.12 -m nfl.prospective.q9shadow.reuse --season 2026 --date 2026-09-13

THE RULE, STATED ONCE AND THEN MADE EXECUTABLE

    A cache hit on unchanged governed inputs may skip RECOMPUTING the
    numbers. It may not skip RE-EVALUATING whether those numbers are
    currently admissible as prospective evidence.

Those are two independent questions and this module keeps them independent:
`payload_identity` answers the first, `assert_currently_admissible` answers the
second, and neither calls the other. A slate can therefore report "12 boards
reused, 0 admissible" without contradiction -- which is exactly what the
2026-09-13 slate is.

WHY THIS EXISTS, MEASURED RATHER THAN IMAGINED

The 2026-09-13 slate reused 12 sealed R8 boards (`UNCHANGED_REUSED`) while the
Q9 arm refused all 24 team-games at the per-team readiness gate. Auditing the
two paths against each other found that `nfl.research.postgame.score_game`
gates on FINALITY ALONE. It does not read `seal_path`, `readiness_gate`,
`completeness` or even the artifact's own `prospective_eligible` flag. On disk
already: 3,230 scoring rows across 2 games, every source artifact carrying
`prospective_eligible: false`, and `postgame.accounting` reporting
`prospective_sample_size = 2 GAME`.

So the bypass was live, not hypothetical. A forecast that the artifact itself
declared ineligible was being counted in the unit the section-4 floors are
measured in.

FAIL CLOSED, AND NEVER BY REWRITING HISTORY. A legacy artifact is not edited,
re-stamped or deleted. Its ORIGINAL classification stands as the historical
record; what this module produces is a SEPARATE current-run disposition saying
whether it is admissible TODAY, under TODAY's contract.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State     # noqa: E402
from nfl.prospective.q9shadow import timebasis as TB                    # noqa: E402

SPEC_VERSION = 'q9-reuse-admissibility-1'
HERE = _REPO / 'nfl' / 'prospective' / 'q9shadow'
DISPOSITION = HERE / 'Q9_REUSE_DISPOSITION.json'

GOVERNED_APPEARANCE_INTERFACE = 'nfl.production.nonqb.layers.appearance'
PER_TEAM_READINESS_GATE = 'PER_TEAM'

# The dispositions a reused artifact can receive TODAY. `LEGACY_UNVERIFIED` is
# deliberately NOT a synonym for REFUSED: it says the artifact predates a
# mandatory control and therefore carries no evidence either way. Collapsing
# the two would claim we checked something we could not check.
ADMISSIBLE = 'ADMISSIBLE'
LEGACY_UNVERIFIED = 'LEGACY_UNVERIFIED'
REFUSED = 'REFUSED'
DISPOSITIONS = (ADMISSIBLE, LEGACY_UNVERIFIED, REFUSED)

# Every control a reused artifact must satisfy to be surfaced as CURRENT
# prospective evidence. Named here so a future control cannot be added to the
# seal path and silently forgotten on the reuse path.
MANDATORY_CONTROLS = (
    'governed_appearance_interface',
    'per_team_readiness_gate',
    'time_basis',
    'completeness_evidence_class',
    'current_blocker_state',
    'candidate_freeze_identity',
    'prospective_evidence_eligibility',
)

# Fields introduced by controls that postdate the historical boards. An
# artifact missing one of these cannot be judged on it -- it is LEGACY, not
# compliant and not in breach.
CONTROL_FIELDS_BY_INTRODUCTION = {
    'seal_path': 'the structural appearance-interface control',
    'time_basis': 'the canonical UTC time-basis control',
}


def payload_identity(art) -> dict:
    """What a cache hit legitimately preserves: the predictive payload.

    Deliberately carries NO admissibility field. If this dict and the
    admissibility verdict ever merged, "the numbers did not change" would
    start implying "the governance answer did not change", which is the
    defect this module exists to prevent.
    """
    return {
        'draw_artifact_sha256': art.get('draw_artifact_sha256'),
        'draw_content_sha256': art.get('draw_content_sha256'),
        'spec_hash': art.get('spec_hash'),
        'feature_set_hash': art.get('feature_set_hash'),
        'n_players': len(art.get('player_ids') or []),
        'written_at': art.get('written_at'),
        'is_predictive_payload_only': True,
        'note': 'unchanged here means the NUMBERS are unchanged. It says '
                'nothing about whether they may be counted.',
    }


def _control_governed_interface(art):
    sp = art.get('seal_path')
    if sp is None:
        return LEGACY_UNVERIFIED, 'SEAL_PATH_UNRECORDED', (
            'the artifact records no seal_path, so which appearance '
            'interface produced it cannot be established')
    got = sp.get('appearance_interface')
    if got != GOVERNED_APPEARANCE_INTERFACE:
        return REFUSED, 'SEAL_PATH_NOT_GOVERNED', (
            f'built through {got!r}, not {GOVERNED_APPEARANCE_INTERFACE!r}')
    if sp.get('upstream_test_only'):
        return REFUSED, 'SEAL_PATH_TEST_ONLY_UPSTREAM', (
            'built on a TEST_ONLY appearance fixture')
    return ADMISSIBLE, 'SEAL_PATH_GOVERNED', got


def _control_readiness_gate(art):
    sp = art.get('seal_path') or {}
    got = sp.get('readiness_gate')
    if not art.get('seal_path'):
        return LEGACY_UNVERIFIED, 'READINESS_GATE_UNRECORDED', (
            'no seal_path, so no readiness-gate provenance exists')
    if got is None:
        return LEGACY_UNVERIFIED, 'READINESS_GATE_UNRECORDED', (
            'seal_path records no readiness_gate')
    if got != PER_TEAM_READINESS_GATE:
        return REFUSED, 'READINESS_GATE_NOT_PER_TEAM', (
            f'readiness_gate={got!r}; only {PER_TEAM_READINESS_GATE} refuses '
            f'INJURY_REPORT_INCOMPLETE')
    return ADMISSIBLE, 'READINESS_GATE_PER_TEAM', got


def _control_time_basis(art):
    caps = art.get('source_captures') or []
    if not caps:
        return REFUSED, 'TIME_BASIS_NO_SOURCE_CAPTURES', 'no input capture'
    o = TB.assert_prospective_order([c.get('retrieved_at') for c in caps],
                                    art.get('written_at'),
                                    art.get('kickoff_utc'))
    if o.state is not State.PASS:
        return REFUSED, o.code, (o.detail or '')[:200]
    return ADMISSIBLE, o.code, o.detail


def _control_completeness(art):
    c = art.get('completeness')
    if c is None:
        return LEGACY_UNVERIFIED, 'COMPLETENESS_UNRECORDED', 'no completeness'
    if c != 'COMPLETE':
        return REFUSED, 'COMPLETENESS_NOT_COMPLETE', (
            f'completeness={c}; protocol section 2 admits only COMPLETE as an '
            f'eligible forecast')
    return ADMISSIBLE, 'COMPLETENESS_COMPLETE', c


def _control_blockers(_art):
    from nfl.prospective.q9shadow import ledger as LED
    st = LED.blocker_states()
    bad = {n: v['state'] for n, v in st.items()
           if v['state'] in LED.NON_CLEARED_BLOCKER_STATES}
    if bad:
        return REFUSED, 'BLOCKERS_NOT_CLEARED', json.dumps(bad, sort_keys=True)
    return ADMISSIBLE, 'BLOCKERS_CLEARED', ''


def _control_candidate_identity(art):
    cand = art.get('candidate')
    if not cand:
        # An R8 production board carries no Q9 candidate block. That is not a
        # breach -- it is not a Q9 artifact -- and it is recorded as such
        # rather than passed silently.
        return LEGACY_UNVERIFIED, 'NOT_A_CANDIDATE_ARTIFACT', (
            'carries no candidate identity block; the freeze comparison does '
            'not apply to it')
    from nfl.prospective.q9shadow import candidate as CAND
    want = CAND.identity_sha256(CAND.identity(art.get('season') or 2026))
    got = cand.get('identity_sha256')
    if got != want:
        return REFUSED, 'CANDIDATE_IDENTITY_DRIFT', f'{got} != {want}'
    return ADMISSIBLE, 'CANDIDATE_MATCHES_FREEZE', got


def _control_evidence_flag(art):
    v = art.get('prospective_evidence')
    if v is None:
        if art.get('prospective_eligible') is False:
            return REFUSED, 'ARTIFACT_DECLARES_ITSELF_INELIGIBLE', (
                'prospective_eligible is false on the artifact itself')
        return LEGACY_UNVERIFIED, 'EVIDENCE_FLAG_UNRECORDED', (
            'no prospective_evidence field')
    if v is not True:
        return REFUSED, 'ARTIFACT_DECLARES_ITSELF_NOT_EVIDENCE', str(v)
    return ADMISSIBLE, 'ARTIFACT_DECLARES_ITSELF_EVIDENCE', 'true'


CONTROL_EVALUATORS = {
    'governed_appearance_interface': _control_governed_interface,
    'per_team_readiness_gate': _control_readiness_gate,
    'time_basis': _control_time_basis,
    'completeness_evidence_class': _control_completeness,
    'current_blocker_state': _control_blockers,
    'candidate_freeze_identity': _control_candidate_identity,
    'prospective_evidence_eligibility': _control_evidence_flag,
}


def assert_currently_admissible(art) -> Outcome:
    """Is this artifact admissible as CURRENT prospective evidence?

    Every mandatory control is evaluated -- none short-circuits -- so the
    disposition record names every reason rather than the first one. A single
    REFUSED makes the artifact inadmissible; absent a REFUSED, a single
    LEGACY_UNVERIFIED makes it legacy.
    """
    missing = sorted(set(MANDATORY_CONTROLS) - set(CONTROL_EVALUATORS))
    if missing:
        return Outcome.fail(
            'REUSE_CONTROL_NOT_EVALUATED',
            f'{missing} are mandatory controls with no evaluator. A control '
            f'that is declared and not run has not been satisfied.',
            missing=missing)
    per = {}
    for name in MANDATORY_CONTROLS:
        try:
            disp, code, detail = CONTROL_EVALUATORS[name](art)
        except Exception as exc:                              # noqa: BLE001
            disp, code, detail = (REFUSED, 'CONTROL_EVALUATOR_ERROR',
                                  f'{type(exc).__name__}: {exc}'[:200])
        per[name] = {'disposition': disp, 'code': code,
                     'detail': str(detail)[:300]}
    refused = [n for n, v in per.items() if v['disposition'] == REFUSED]
    legacy = [n for n, v in per.items()
              if v['disposition'] == LEGACY_UNVERIFIED]
    if refused:
        return Outcome.fail(
            'REUSE_INADMISSIBLE',
            f'{len(refused)} mandatory control(s) refuse this artifact for '
            f'current reuse: {refused}. Its predictive payload may be '
            f'unchanged; its admissibility is not.',
            disposition=REFUSED, controls=per, refused=refused,
            legacy=legacy)
    if legacy:
        return Outcome.blocked(
            'REUSE_LEGACY_UNVERIFIED',
            f'{len(legacy)} mandatory control(s) cannot be evaluated on this '
            f'artifact because it predates them: {legacy}. That is not '
            f'compliance and not a breach -- it is an absence of evidence, '
            f'and absence of evidence is not admissibility.',
            cause=Cause.GOVERNANCE, disposition=LEGACY_UNVERIFIED,
            controls=per, legacy=legacy,
            control_fields_introduced_later=CONTROL_FIELDS_BY_INTRODUCTION)
    return Outcome.ok(
        'REUSE_ADMISSIBLE', value=ADMISSIBLE,
        detail=f'all {len(MANDATORY_CONTROLS)} mandatory control(s) pass on '
               f'the current contract',
        disposition=ADMISSIBLE, controls=per)


def disposition_record(sealed_records) -> dict:
    """A CURRENT-RUN disposition for each reused artifact. Mutates nothing.

    The historical artifact keeps its own fields and its own original
    classification. This is a separate document saying what today's contract
    makes of it.
    """
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    out, tally = [], {d: 0 for d in DISPOSITIONS}
    for rec in sealed_records:
        d = pathlib.Path(rec['dir'])
        p = d / 'forecast_artifact.json'
        if not p.exists():
            out.append({'game_id': rec.get('game_id'),
                        'rel_dir': rec.get('rel_dir'),
                        'disposition': LEGACY_UNVERIFIED,
                        'code': 'NO_FORECAST_ARTIFACT',
                        'controls': {}})
            tally[LEGACY_UNVERIFIED] += 1
            continue
        art = json.loads(p.read_text())
        o = assert_currently_admissible(art)
        disp = o.evidence.get('disposition', REFUSED)
        tally[disp] = tally.get(disp, 0) + 1
        sp = art.get('seal_path') or {}
        out.append({
            'game_id': rec.get('game_id'),
            'team_ids': art.get('team_ids'),
            'rel_dir': rec.get('rel_dir'),
            # ---- ORIGINAL, read and never inferred -----------------------
            'original_run_id': rec.get('run_id'),
            'original_seal_timestamp': art.get('written_at'),
            'original_information_timestamp': (
                max((c.get('retrieved_at') for c in
                     (art.get('source_captures') or [])), default=None)),
            'original_seal_path': art.get('seal_path'),
            'original_readiness_gate': sp.get('readiness_gate'),
            'original_completeness': art.get('completeness'),
            'original_prospective_eligible': art.get('prospective_eligible'),
            'original_model_configuration': art.get('model_configuration'),
            'original_candidate': rec.get('candidate'),
            # ---- CURRENT contract --------------------------------------
            'satisfies_governed_appearance_interface':
                sp.get('appearance_interface')
                == GOVERNED_APPEARANCE_INTERFACE,
            'readiness_gate_is_per_team':
                sp.get('readiness_gate') == PER_TEAM_READINESS_GATE,
            'predates_mandatory_seal_controls': sorted(
                f for f in CONTROL_FIELDS_BY_INTRODUCTION if f not in art),
            'disposition': disp,
            'code': o.code,
            'detail': (o.detail or '')[:300],
            'controls': o.evidence.get('controls'),
            'payload_identity': payload_identity(art),
        })
    return {
        'artifact': 'NFL_Q9_REUSE_DISPOSITION',
        'spec_version': SPEC_VERSION,
        'evaluated_at': now,
        'rule': ('reuse may preserve model output when governed inputs are '
                 'unchanged, but admissibility must be re-evaluated under the '
                 'current seal/governance contract'),
        'mandatory_controls': list(MANDATORY_CONTROLS),
        'n_evaluated': len(out),
        'tally': tally,
        'n_admissible': tally.get(ADMISSIBLE, 0),
        'history_mutated': False,
        'history_note': ('the historical artifacts are untouched. Their '
                         'original fields and original classification stand; '
                         'this is a separate current-run disposition.'),
        'records': out,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--date', default='2026-09-13')
    ap.add_argument('--candidate', default='V1_CANDIDATE_R8')
    a = ap.parse_args(argv)
    from nfl.research import sealed_index as SI
    recs, seen = [], {}
    for r in SI.discover_all():
        if not (r.get('kickoff_utc') or '').startswith(a.date):
            continue
        if a.candidate and r.get('candidate') != a.candidate:
            continue
        prev = seen.get(r['game_id'])
        if prev is None or str(r.get('written_at')) > str(prev.get('written_at')):
            seen[r['game_id']] = r
    recs = [seen[k] for k in sorted(seen)]
    doc = disposition_record(recs)
    DISPOSITION.write_text(json.dumps(doc, indent=1, default=str) + '\n')
    print(f"evaluated  : {doc['n_evaluated']}")
    print(f"tally      : {doc['tally']}")
    print(f"admissible : {doc['n_admissible']}")
    for r in doc['records'][:3]:
        print(f"  {r['game_id']:20s} {r['disposition']:18s} {r['code']}")
    print(f"written    : {DISPOSITION}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
