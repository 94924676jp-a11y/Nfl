#!/usr/bin/env python3.12
"""Reconcile one week's T-90 obligations against the manifest, and MEASURE the causal chain.

OWNER RULE 1 (2026-10-02). The previous version of this script wrote a `missed_causal_chain`
block whose values were literals typed into the source -- `captures_in_window: 280`,
`sources_in_window: 7`, `authorised_source_captures_in_window: 40`,
`evidence_manufactured: False`, `retrieval_time_restamped: False` -- next to counts it had
actually computed, in the same artifact, with nothing to tell a reader which was which. It also
treated a refused manifest read as an empty capture set and then reported every obligation
MISSED, which is a finding manufactured from an absence.

Every value in the block is now computed from the artifact it describes, or is None with an
entry in `measurement_errors` naming what was not measured and why. A manifest that cannot be
read, a plan that cannot be built or a week with no obligations is `T90_RECONCILIATION_NOT_EXECUTED`
with its cause, never a reconciliation.

Usage:
    python3.12 nfl/tools/reconcile_t90_obligations.py [--season 2026] [--week 1]
        [--manifest nfl/vintage_manifest.jsonl] [--out nfl/capture/t90_obligation_reconciliation.json]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.capture import coverage as C                                # noqa: E402
from nfl.capture.schedule import (NON_OBLIGATION_KINDS,              # noqa: E402
                                  GAME_SPECIFIC_KINDS, _clears)
from sportsplatform.governance.outcome import State                  # noqa: E402

MANIFEST = _REPO / 'nfl' / 'vintage_manifest.jsonl'
OUT = _REPO / 'nfl' / 'capture' / 't90_obligation_reconciliation.json'

STATE_MEASURED = 'T90_RECONCILIATION_MEASURED'
STATE_NOT_EXECUTED = 'T90_RECONCILIATION_NOT_EXECUTED'


def _not_executed(cause: str, detail: str, **ev) -> dict:
    return {'state': STATE_NOT_EXECUTED, 'cause': cause, 'detail': detail,
            'n_obligations': 0, 'n_plan_rows': 0, 'obligations': [],
            'missed_causal_chain': None, 'measurement_errors': [detail], **ev}


def _rows(manifest_path) -> list:
    out = []
    for ln in pathlib.Path(manifest_path).read_text().splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if isinstance(r, dict):
            out.append(r)
    return out


def _ts(val: dict):
    prov = val.get('provenance') or {}
    return C._parse_ts(val.get('retrieved_at') or prov.get('retrieved_at'))


def _blob_present(val: dict) -> bool:
    b = val.get('blob')
    if not b:
        return False
    p = pathlib.Path(b)
    if not p.is_absolute():
        p = _REPO / p
    return p.exists() or (_REPO / 'nfl' / 'vintage' / p.name).exists()


def measure(season: int, week: int, *, manifest_path=MANIFEST, plan=None,
            vintage_dir=None, now=None, verify_artifacts: bool = True) -> dict:
    """The reconciliation, as a dict whose `state` says whether it ran on evidence.

    `plan` may be supplied (a list of CaptureDue, e.g. from schedule.season_plan) so the
    reconciliation can be measured against a plan that is itself an input rather than one read
    from the vintage store; when None the week's plan is read from the captured schedule.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    manifest_path = pathlib.Path(manifest_path)
    errors: list = []

    if plan is None:
        planned = C.load_week_plan(season, week, vintage_dir=vintage_dir)
        if planned.state is not State.PASS:
            return _not_executed(
                'EMPTY_INPUT' if planned.code in ('NO_SCHEDULE_SNAPSHOT', 'NO_GAMES_IN_SNAPSHOT')
                else 'NOT_EXECUTED',
                f'no plan: {planned}', blocked_on=planned.as_dict())
    if not plan:
        return _not_executed('EMPTY_INPUT', 'the week plan holds no targets; there are no '
                             'obligations to reconcile')

    if not manifest_path.exists():
        return _not_executed('EMPTY_INPUT', f'no manifest at {manifest_path}; no capture has '
                             f'been recorded, so nothing can be reconciled against')
    read = C.performed_from_manifest(manifest_path, verify_artifacts=verify_artifacts)
    if read.state is not State.PASS:
        # The old script set performed=[] here and reported every obligation MISSED.
        return _not_executed(
            'EMPTY_INPUT' if read.state is State.NOT_APPLICABLE else 'NOT_EXECUTED',
            f'the manifest could not be read as performed captures: {read}',
            blocked_on=read.as_dict())
    n_pass = read.evidence.get('n_pass_rows') or 0
    if n_pass == 0:
        return _not_executed('EMPTY_INPUT', f'{manifest_path.name} carries zero PASS rows; an '
                             f'empty capture set is not evidence that obligations were missed',
                             n_pass_rows=0)
    performed = read.value

    rows, tally = [], collections.Counter()
    for c in plan:
        d = c.as_dict()
        lo, hi = c.window
        if c.kind in NON_OBLIGATION_KINDS:
            st = 'NOT_APPLICABLE'
            why = f'{c.kind} is a bookkeeping row, not an evidence deadline'
            q = nq = 0
        else:
            hit = [p for p in performed if _clears(c, p)]
            inwin = [p for p in performed if lo <= p[0] <= hi]
            q, nq = len(hit), len(inwin) - len(hit)
            if hit:
                st, why = 'COVERED', 'an authorised, in-window, game-attributed capture exists'
            elif hi <= now:
                st, why = 'MISSED', ('window closed with no authorised, in-window, '
                                     'game-attributed capture')
            else:
                st, why = 'NOT_YET_DUE', 'window has not closed'
        tally[st] += 1
        rows.append({'game_id': d['game_id'], 'label': d['label'], 'kind': c.kind,
                     'kickoff_utc': d['kickoff_utc'],
                     'window_start_utc': d['window_start_utc'],
                     'window_end_utc': d['window_end_utc'],
                     'cadence_confirmed': d['cadence_confirmed'],
                     'derivation_note': d['note'],
                     'window_opened': lo <= now, 'window_closed': hi <= now,
                     'qualifying_captures': q, 'nonqualifying_in_window_captures': nq,
                     'status': st, 'reason': why,
                     'is_game_specific_kind': c.kind in GAME_SPECIFIC_KINDS})
    obl = [r for r in rows if r['status'] != 'NOT_APPLICABLE']
    if not obl:
        return _not_executed('EMPTY_INPUT', 'the plan carries only non-obligation rows; there '
                             'is nothing to reconcile', n_plan_rows=len(rows))

    # ---- the causal chain, MEASURED ----------------------------------------
    missed = [(c, r) for c, r in zip(plan, rows) if r['status'] == 'MISSED']
    chain: dict = {'n_missed': len(missed),
                   'missed_targets': [f"{r['game_id']}/{r['label']}" for _, r in missed],
                   'missed_kinds': sorted({r['kind'] for _, r in missed})}
    if missed:
        chain['windows'] = {f"{r['game_id']}/{r['label']}":
                            f"{r['window_start_utc']} .. {r['window_end_utc']}"
                            for _, r in missed}
        chain['window_span'] = (min(r['window_start_utc'] for _, r in missed) + ' .. '
                                + max(r['window_end_utc'] for _, r in missed))
    else:
        chain['windows'], chain['window_span'] = {}, None

    # anchored workflow: read from the generator, not asserted
    try:
        from nfl.tools import gen_t90_schedule as G
        anchored = tuple(G.ANCHORED_KINDS)
        chain['anchored_kinds'] = list(anchored)
        chain['missed_kinds_without_anchored_workflow'] = sorted(
            k for k in chain['missed_kinds'] if k not in anchored)
        chain['anchored_workflow_scheduled_for_missed_kinds'] = (
            None if not missed else not chain['missed_kinds_without_anchored_workflow'])
    except Exception as exc:  # noqa: BLE001
        chain['anchored_kinds'] = None
        chain['missed_kinds_without_anchored_workflow'] = None
        chain['anchored_workflow_scheduled_for_missed_kinds'] = None
        errors.append(f'anchored_workflow: gen_t90_schedule.ANCHORED_KINDS unreadable ({exc})')

    # in-window captures: counted from the manifest rows themselves
    windows = [(c.window[0], c.window[1], c.game_id, c.kind) for c, _ in missed]
    all_rows = _rows(manifest_path)
    inwin = []
    for r in all_rows:
        if r.get('state') != 'PASS':
            continue
        val = r.get('value') or {}
        ts = _ts(val)
        if ts is None:
            continue
        if any(lo <= ts <= hi for lo, hi, _, _ in windows):
            inwin.append((r, val, ts))
    chain['captures_in_window'] = len(inwin) if missed else None
    chain['sources_in_window'] = sorted({r.get('source') for r, _, _ in inwin}) if missed else None
    chain['manifest_rows_exist'] = (len(inwin) > 0) if missed else None
    if not missed:
        errors.append('captures_in_window / sources_in_window / manifest_rows_exist: no missed '
                      'obligation, so there is no window to count captures in')

    # authorised sources: read from the registry
    try:
        from nfl.capture import registry as R
        auth = {k: sorted(s.name for s in R.REGISTRY if k in s.serves_kinds)
                for k in chain['missed_kinds']}
        chain['authorised_sources_by_missed_kind'] = auth
        auth_names = {n for ns in auth.values() for n in ns}
        chain['authorised_source_present'] = (bool(auth_names) if missed else None)
        chain['authorised_source_captures_in_window'] = (
            sum(1 for r, _, _ in inwin if r.get('source') in auth_names) if missed else None)
    except Exception as exc:  # noqa: BLE001
        chain['authorised_sources_by_missed_kind'] = None
        chain['authorised_source_present'] = None
        chain['authorised_source_captures_in_window'] = None
        errors.append(f'authorised_source: registry unreadable ({exc})')

    # declarations, bytes and refusal reasons: read off the in-window rows
    if inwin:
        declared = sum(1 for _, v, _ in inwin if v.get('discharge_eligibility') is not None)
        before = sum(1 for _, v, _ in inwin
                     if (v.get('execution_target') or {}).get('declared_before_fetch') is True)
        chain['n_in_window_rows_with_declaration'] = declared
        chain['n_in_window_rows_declared_before_fetch'] = before
        chain['target_declared_before_fetch'] = before > 0
        present = sum(1 for _, v, _ in inwin if _blob_present(v))
        chain['n_in_window_rows_with_raw_bytes_on_disk'] = present
        chain['raw_bytes_exist'] = present > 0
        missed_pairs = {(g, k) for _, _, g, k in windows}
        reasons: dict = collections.defaultdict(collections.Counter)
        for r, v, _ in inwin:
            for t in ((v.get('discharge_eligibility') or {}).get('targets') or []):
                if (t.get('game_id'), t.get('kind')) in missed_pairs:
                    for why in (t.get('refusals') or []):
                        reasons[r.get('source')][why] += 1
        chain['refusal_reasons_by_source'] = {s: dict(c) for s, c in sorted(reasons.items())}
        basis = collections.Counter(
            str((v.get('execution_target') or {}).get('basis')) for _, v, _ in inwin)
        chain['execution_basis_in_window'] = dict(basis)
        credited_periodic = sum(
            1 for _, v, _ in inwin
            if (v.get('execution_target') or {}).get('basis') == 'PERIODIC_SWEEP'
            and any(t.get('eligible') for t in
                    ((v.get('discharge_eligibility') or {}).get('targets') or [])))
        chain['n_periodic_sweep_rows_credited_with_an_eligible_target'] = credited_periodic
        chain['periodic_reinterpreted_as_anchored'] = credited_periodic > 0
    else:
        for k in ('n_in_window_rows_with_declaration', 'n_in_window_rows_declared_before_fetch',
                  'target_declared_before_fetch', 'n_in_window_rows_with_raw_bytes_on_disk',
                  'raw_bytes_exist', 'refusal_reasons_by_source', 'execution_basis_in_window',
                  'n_periodic_sweep_rows_credited_with_an_eligible_target',
                  'periodic_reinterpreted_as_anchored'):
            chain[k] = None
        errors.append('declaration / raw bytes / refusal reasons / basis: no in-window PASS '
                      'row to read them from')

    # retrieval clock: restamping is measurable only where a row carries two clocks
    both = [(v.get('retrieved_at'), (v.get('provenance') or {}).get('retrieved_at'))
            for r in all_rows if r.get('state') == 'PASS'
            for v in [r.get('value') or {}]
            if v.get('retrieved_at') and (v.get('provenance') or {}).get('retrieved_at')]
    if both:
        differ = sum(1 for a, b in both if C._parse_ts(a) != C._parse_ts(b))
        chain['n_rows_with_two_retrieval_clocks'] = len(both)
        chain['n_rows_whose_two_clocks_differ'] = differ
        chain['retrieval_time_restamped'] = differ > 0
    else:
        chain['n_rows_with_two_retrieval_clocks'] = 0
        chain['n_rows_whose_two_clocks_differ'] = None
        chain['retrieval_time_restamped'] = None
        errors.append('retrieval_time_restamped: no PASS row carries both value.retrieved_at '
                      'and value.provenance.retrieved_at, so no restamping can be detected')

    # evidence_manufactured: not a manifest measurement. What IS measured is artifact verification.
    chain['evidence_manufactured'] = None
    chain['artifact_verification'] = {
        'verify_artifacts': bool(verify_artifacts),
        'n_excluded_on_artifact_verification': len(read.evidence.get('artifact_excluded') or []),
        'disposition_counts': read.evidence.get('disposition_counts')}
    errors.append('evidence_manufactured: not measurable from the manifest alone -- it needs an '
                  'independent upstream record to compare stored bytes against. The stored-bytes '
                  'verification that IS measured is in artifact_verification')
    chain['conclusion'] = None
    errors.append('conclusion: interpretation, not a measurement; read the measured fields')

    return {'state': STATE_MEASURED, 'generated_at_utc': now.isoformat(),
            'season': season, 'week': week,
            'n_plan_rows': len(rows), 'n_obligations': len(obl),
            'status_tally': dict(tally),
            'reconciles_to_63': len(obl) == 63,
            'manifest_rows_pass': n_pass,
            'attributed_captures': sum(1 for p in performed if p[2]),
            'obligations': obl,
            'non_obligation_rows': [r for r in rows if r['status'] == 'NOT_APPLICABLE'],
            'invalid_obligations': [],
            'missed_causal_chain': chain,
            'measurement_errors': errors,
            'MEANING': ('every value in missed_causal_chain is computed from the manifest, the '
                        'registry or the schedule generator, or is None with its reason in '
                        'measurement_errors. None of them is typed in.')}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--week', type=int, default=1)
    ap.add_argument('--manifest', default=str(MANIFEST))
    ap.add_argument('--out', default=str(OUT))
    a = ap.parse_args(argv)
    out = measure(a.season, a.week, manifest_path=a.manifest)
    pathlib.Path(a.out).write_text(json.dumps(out, indent=1, default=str) + '\n')
    print(out['state'], out.get('cause', ''), out.get('detail', ''))
    if out['state'] != STATE_MEASURED:
        return 3
    print('plan rows', out['n_plan_rows'], 'obligations', out['n_obligations'], out['status_tally'])
    print('reconciles to 63:', out['reconciles_to_63'])
    for r in out['obligations']:
        if r['status'] == 'MISSED':
            print(' MISSED', r['game_id'], r['label'], r['kind'], 'confirmed=', r['cadence_confirmed'])
    for e in out['measurement_errors']:
        print(' NOT MEASURED:', e)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
