"""Run one forecast TWICE from frozen inputs and prove the two runs are one run.

    python3.12 nfl/tools/determinism_proof.py \
        --game-id 2026_01_DEN_KC --season 2026 --week 1 \
        --cutoff 2026-09-14T23:00:00Z \
        --out-root-a /tmp/dp/A --out-root-b /tmp/dp/B \
        --draws 1000 --proof-out nfl/research/remediation/l5/PROOF.json

WHAT IS BEING PROVEN, IN THE OWNER'S WORDS

    identical predictive arrays
    identical candidate identity
    identical execution identity
    identical model configuration
    identical input hashes

and, separately and additionally,

    generated forecast output does not alter the second run's identity.

The last one is not implied by the first five. Five equalities can all hold on a
single run compared with itself. The claim is that run B, executing in a world
that now CONTAINS run A's outputs, computes the same identity as run A did in a
world that did not. That is `dF/dD = 0` from `nfl.identity.code_identity`, and
it is the property the withdrawn `<sha>+dirty[N]` form did not have.

TWO TOP-LEVEL OUTPUT DIRECTORIES, DELIBERATELY

One directory would not prove it. `run_forecast` names each run's directory
after its own `run_id`, so two runs into one root land in two subdirectories
either way -- but under the old contract the whole-tree porcelain count moved
once, when the first subdirectory appeared, and then a THIRD run would have
counted the same. WS-E's finding is that a single shared root shows a false
green: the count is already elevated when the comparison is taken, so both runs
see the same elevated count and agree. Two separate TOP-LEVEL roots move the
count at a point where the old implementation would have disagreed and the new
one must not. `--out-root-a` and `--out-root-b` are therefore required to be
distinct and neither may contain the other; the tool refuses otherwise.

    B's identity is computed with A's entire output tree already on disk.

WHY THE COUNTERFACTUAL COUNT IS COMPUTED AND WHERE IT IS PUT

Proving that the new digest did not move is weak on its own: it is also what a
tool that reads nothing at all would report. So the harness computes, at each
observation point, the WITHDRAWN string `<HEAD>+dirty[N]` as a counterfactual,
and reports whether it WOULD have moved across the two runs. A green with a
moved counterfactual is a positive result; a green with a static counterfactual
is a weaker one and says so (`counterfactual_discriminating: false`).

What is computed is the COUNT, never the withdrawn STRING. Assembling
`<sha>+dirty[N]` here would put a third implementation of the withdrawn form
inside `nfl/tools`, which is in the identity's own SOURCE scope; the sweep in
`nfl/tests/test_determinism_proof.py` flagged exactly that on the first draft of
this module and it was removed rather than exempted. The count comes from
`code_identity()`'s Outcome evidence, so this tool makes no git call of its own.

That counterfactual reads generated artifact state (D) -- it is a count of the
working tree, which now contains run A's outputs if the roots are inside the
repo. Per the identity contract, NOTHING THAT READS D MAY ENTER A SEALED BODY,
hashed or not, because the body is hashed into an identity of its own. That
defect was found once already inside the repair itself: a "recorded, not hashed"
count sat outside `source_scope_sha256` and still reached `seal_payload_sha256`,
because the artifact minus two keys IS the payload. So this proof artifact has
the same two-part shape as `q9shadow/seal.py`: `PROOF_BODY_EXCLUDED` names every
key that reads D, the clock, or the machine, and `proof_body_sha256` is computed
over the artifact WITHOUT them. Re-running this tool on an unchanged repository
reproduces `proof_body_sha256` exactly; `diagnostics` moves freely underneath.

ROWS ARE ADDRESSED BY ID, NEVER BY POSITION

`manifest['layers'][layer]['row_ids']` with `row_axis` 'gsis_id' (or 'team' for
`team_volume`) is the row axis. Comparing matrices positionally would call two
runs equal whose row ORDER differed, and would call two runs unequal whose rows
were the same set in a different order. Both are wrong answers, and the second
is the one that would raise a false alarm on a night when a roster read
reordered. Each array is compared cell-by-cell over the INTERSECTION of the two
row-id sets, and rows present in only one run are reported as a row-set defect
in their own right rather than folded into an array mismatch.

Comparison is on raw bytes of the float64 values, not `==`. `np.array_equal`
calls two NaNs unequal and two differently-signed zeros equal; neither is what
"bit-for-bit" means, and a draw set is allowed to contain neither, so the
byte test is the one that cannot be argued with.

CLASSIFICATION, AND WHY IT COMES BEFORE THE VERDICT

A determinism harness that can only say PASS or FAIL is unusable on a night when
other agents are editing the tree, because its most likely failure is not a
determinism failure at all. Every failure is classified against the three rows of
the identity contract, in this order, first match winning, because an earlier
cause explains every later symptom:

  CAUSE_0_INPUTS_NOT_FROZEN          the information set moved between the two
                                     runs. The premise "identical frozen inputs"
                                     failed; nothing downstream is evidence.
  CAUSE_1_IN_SCOPE_SOURCE_CHANGED    a file inside the identity's declared
                                     SOURCE scope changed between the runs.
                                     THE EXPECTED CAUSE ON A LIVE NIGHT. Named
                                     files are reported, so the answer is
                                     "pipeline.py changed at 16:41", not "the
                                     model is nondeterministic".
  CAUSE_2_SEALED_BODY_READS_D        the arrays are identical and an identity
                                     moved anyway, with source and inputs
                                     constant. Something in the identity read
                                     the clock, a path, a count, or the machine.
  CAUSE_3_PREDICTIVE_NONDETERMINISM  source constant, inputs constant, every
                                     identity constant, and the DRAWS differ.
                                     This has never been observed in this
                                     repository and is the only one of the four
                                     that is a defect in the model rather than
                                     in the measurement of it.

CAUSE_3 is last on purpose. It is the conclusion a naive harness reaches first
and the one least likely to be true.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import pathlib
import platform
import sys
import time

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.identity import code_identity as CI                          # noqa: E402
from nfl.production import draws_artifact as DA                       # noqa: E402

PROOF_VERSION = 'nfl-determinism-proof-1'

# Everything here reads generated artifact state (D), the wall clock, or the
# machine. It is recorded because a reader needs it; it is outside
# `proof_body_sha256` because a proof whose own hash moves when an unrelated
# file appears is the defect this tool exists to detect, one level up.
PROOF_BODY_EXCLUDED = ('diagnostics', 'proof_body_sha256', 'proof_signature',
                       'proof_body_excludes', 'proof_body_excludes_why')

DEFAULT_SEED = 20260908
DEFAULT_MODEL_CONFIGURATION = 'V1_CANDIDATE'

CAUSES = {
    'CAUSE_0_INPUTS_NOT_FROZEN':
        'the frozen input manifest was not held constant across the two runs, '
        'so the premise of the comparison failed and nothing downstream of it '
        'is evidence about determinism.',
    'CAUSE_1_IN_SCOPE_SOURCE_CHANGED':
        'a file inside the declared SOURCE scope of identity B changed between '
        'the two runs. The two runs did not execute the same code, so a '
        'difference in their outputs or identities is expected and is not a '
        'determinism defect.',
    'CAUSE_2_SEALED_BODY_READS_D':
        'the predictive arrays are identical and an identity moved anyway, '
        'with in-scope source and input hashes constant. Some field inside an '
        'identity read state outside the declared inputs -- a path, a count, a '
        'clock, or the machine. This is the dF/dD != 0 defect class.',
    'CAUSE_3_PREDICTIVE_NONDETERMINISM':
        'in-scope source constant, input hashes constant, every identity '
        'constant, and the draws differ. Genuine nondeterminism in the '
        'predictive path. NEVER OBSERVED IN THIS REPOSITORY -- if this is '
        'reported, exhaust the other three before believing it.',
}


# ---------------------------------------------------------------- utilities
def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(
        timespec='seconds').replace('+00:00', 'Z')


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                      default=str).encode()


def _sha(obj) -> str:
    return hashlib.sha256(_canon(obj)).hexdigest()


def _bits(a: np.ndarray) -> bytes:
    """The bytes of the float64 values, in C order.

    Not `==` and not `np.array_equal`. `==` and `array_equal` call NaN != NaN
    and call -0.0 == 0.0; the first would report a false difference and the
    second would hide a real one. Bit-for-bit means these bytes.
    """
    return np.ascontiguousarray(np.asarray(a, dtype=np.float64)).tobytes()


def _legacy_counterfactual(o: Outcome) -> dict:
    """The working-tree COUNT the withdrawn form keyed on, read and reported.

    THE COUNT, AND DELIBERATELY NOT THE STRING. An earlier draft of this
    function shelled out to `git status --porcelain` itself and assembled
    `f'{head}+dirty[{n}]'` so the proof could print the withdrawn identity
    verbatim. This module's own sweep test flagged it, correctly, as a THIRD
    implementation of the thing L5 was sent to prove does not exist -- sitting
    in `nfl/tools`, which is inside the identity's SOURCE scope, where the next
    person needing a code version would find it and copy it.

    The evidence wanted here is "the count moved while the digest did not".
    That is the COUNT. Assembling the string adds no evidence and adds a
    construction, so the construction is gone and the count is taken from
    `code_identity()`'s own evidence -- the one declared implementation --
    rather than from a second git call. Nothing in this repository outside
    `nfl/identity/` asks git about the working tree, this tool included.
    """
    n = dict(o.evidence).get('n_dirty_tree_entries_observed')
    if n is None:
        return {'available': False,
                'why': 'code_identity() did not report a tree-entry count'}
    return {'available': True, 'n_dirty_tree_entries': int(n),
            'is_not_a_code_version': (
                'this is the quantity the WITHDRAWN form keyed on. It is a '
                'diagnostic and is never assembled into an identity string.')}


def _observe_code_identity(label: str) -> dict:
    """Identity A+B+C at one instant, plus the counterfactual, kept apart."""
    o = CI.code_identity()
    if o.state is not State.PASS:
        return {'label': label, 'resolved': False,
                'state': o.state.value, 'code': o.code,
                'detail': o.detail[:400],
                'legacy': _legacy_counterfactual(o)}
    v = o.value
    return {
        'label': label,
        'resolved': True,
        'commit': v['commit'],
        'code_version': v['code_version'],
        'source_scope_sha256': v['source_scope_sha256'],
        'source_scope_clean': v['source_scope_clean'],
        'runtime_token': v['runtime_token'],
        'dirty_source_files': [
            {'path': e['path'], 'state': e['state'], 'sha256': e['sha256']}
            for e in v['dirty_source_files']],
        'legacy': _legacy_counterfactual(o),
    }


def tool_source_sha256() -> str:
    """This module's own bytes. A proof should name the code that produced it.

    `nfl/tools/` is a SOURCE_ROOT, so an edit to this file already moves
    identity B; this is the direct statement of the same fact, so a reader
    holding only the proof can check it without a checkout.
    """
    return hashlib.sha256(
        pathlib.Path(__file__).resolve().read_bytes()).hexdigest()


# ------------------------------------------------------- the frozen manifest
def resolve_input_manifest(kickoff_utc: str, cutoff: str) -> Outcome:
    """The information set at the cutoff, frozen into a comparable record.

    This is the `--input-manifest` object. It is resolved ONCE, before run A,
    and then asserted against what each run actually reports consuming. The
    alternative -- letting each run resolve its own and comparing afterwards --
    cannot distinguish "the two runs consumed different bytes" from "a capture
    landed between them", and those need different answers.
    """
    from nfl.research.shadow import information_set as IS
    try:
        info = IS.build(kickoff_utc, observed_before=cutoff)
    except Exception as exc:                                     # noqa: BLE001
        return Outcome.blocked(
            'DP_INFORMATION_SET_UNAVAILABLE',
            f'the information set for cutoff {cutoff} could not be built: '
            f'{type(exc).__name__}: {exc}. A determinism proof cannot freeze '
            f'inputs it cannot name.', cause=Cause.DATA)
    srcs = info.get('sources') or {}
    if not srcs:
        return Outcome.blocked(
            'DP_INFORMATION_SET_EMPTY',
            f'the information set at cutoff {cutoff} names no sources. An '
            f'empty input manifest would make every run agree trivially, '
            f'which is the absence-read-as-success defect inside the proof.',
            cause=Cause.DATA, absent=sorted(info.get('absent') or []))
    frozen = {
        'manifest_version': 'nfl-frozen-input-manifest-1',
        'kickoff_utc': kickoff_utc,
        'cutoff_utc': cutoff,
        'absent_sources': sorted(info.get('absent') or []),
        'sources': {k: {'sha256': v.get('sha256'),
                        'blob_sha256': v.get('blob_sha256'),
                        'observed_at': v.get('observed_at'),
                        'capture_id': v.get('capture_id'),
                        'blob': v.get('blob')}
                    for k, v in sorted(srcs.items())},
    }
    frozen['manifest_sha256'] = _sha(
        {k: v for k, v in frozen.items() if k != 'manifest_sha256'})
    return Outcome.ok('DP_INPUT_MANIFEST_FROZEN', value=frozen,
                      detail=f'{len(srcs)} source(s) frozen at {cutoff}',
                      n_sources=len(srcs),
                      manifest_sha256=frozen['manifest_sha256'])


def _observed_manifest(run: dict) -> dict:
    """What a completed run says it consumed, in the frozen manifest's shape."""
    caps = (run.get('artifact') or {}).get('source_captures') or []
    out = {}
    for c in caps:
        name = c.get('source') or c.get('name')
        if name:
            out[name] = {'sha256': c.get('sha256'),
                         'retrieved_at': c.get('retrieved_at')}
    return out


# --------------------------------------------------------------- run a game
def run_once(*, season, week, game_id, cutoff, out_root, draws, seed,
             model_configuration, label) -> Outcome:
    """One forecast into its own top-level root. Never two into one."""
    from nfl.tools import make_board as MB
    root = pathlib.Path(out_root)
    root.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    try:
        ko = MB.kickoff_for(season, week, game_id)
        summary, board, run_dir = MB.build_one(
            season, week, game_id, cutoff, str(root),
            draws=draws, seed=seed,
            model_configuration=model_configuration)
    except SystemExit as exc:
        return Outcome.blocked(
            'DP_RUN_REFUSED',
            f'{label}: the forecast refused before sealing: {exc}',
            cause=Cause.DATA, label=label)
    except Exception as exc:                                     # noqa: BLE001
        return Outcome.fail(
            'DP_RUN_RAISED',
            f'{label}: {type(exc).__name__}: {exc}', label=label)
    elapsed = round(time.time() - t0, 3)
    run_dir = pathlib.Path(run_dir)
    if summary.get('status') != 'SEALED':
        return Outcome.blocked(
            'DP_RUN_NOT_SEALED',
            f'{label}: the run finished with status '
            f'{summary.get("status")!r} rather than SEALED, so there is no '
            f'forecast to compare. First failure: '
            f'{summary.get("first_failure")}',
            cause=Cause.DATA, label=label, status=summary.get('status'))

    man_p = run_dir / 'player_draws_manifest.json'
    npz_p = run_dir / 'player_draws.npz'
    for p in (man_p, npz_p):
        if not p.exists():
            return Outcome.fail(
                'DP_RUN_WITHOUT_DRAWS',
                f'{label}: {p.name} is absent from a run that reported '
                f'SEALED. A sealed forecast with no draw set is the '
                f'absence-read-as-success defect, not a determinism result.',
                label=label, path=str(p))
    manifest = json.loads(man_p.read_text())
    arrays = DA.read(npz_p)
    if arrays.state is not State.PASS:
        return arrays
    art_p = run_dir / 'forecast_artifact.json'
    board_p = run_dir / 'board.json'
    return Outcome.ok(
        'DP_RUN_SEALED',
        value={
            'label': label,
            'run_dir': str(run_dir),
            'out_root': str(root),
            'summary': summary,
            'manifest': manifest,
            'arrays': arrays.value,
            'artifact': (json.loads(art_p.read_text())
                         if art_p.exists() else {}),
            'board': (json.loads(board_p.read_text())
                      if board_p.exists() else {}),
            'kickoff_utc': ko,
            'elapsed_s': elapsed,
        },
        detail=f'{label}: sealed {summary["run_id"]} in {elapsed}s',
        run_id=summary['run_id'], label=label, elapsed_s=elapsed)


# ------------------------------------------------------------- comparisons
def compare_arrays(a: dict, b: dict) -> dict:
    """Every array, cell by cell, rows addressed by id. Never positionally."""
    man_a, man_b = a['manifest'], b['manifest']
    lay_a = man_a.get('layers') or {}
    lay_b = man_b.get('layers') or {}

    rep = {'layers_only_in_a': sorted(set(lay_a) - set(lay_b)),
           'layers_only_in_b': sorted(set(lay_b) - set(lay_a)),
           'arrays_only_in_a': sorted(set(a['arrays']) - set(b['arrays'])),
           'arrays_only_in_b': sorted(set(b['arrays']) - set(a['arrays'])),
           'row_axis_disagreements': [], 'row_set_differences': [],
           'array_differences': [], 'compared': []}

    idx_a, idx_b = {}, {}
    for layer in sorted(set(lay_a) & set(lay_b)):
        ax_a = lay_a[layer].get('row_axis')
        ax_b = lay_b[layer].get('row_axis')
        if ax_a != ax_b:
            rep['row_axis_disagreements'].append(
                {'layer': layer, 'a': ax_a, 'b': ax_b})
            continue
        ids_a = [str(r) for r in (lay_a[layer].get('row_ids') or [])]
        ids_b = [str(r) for r in (lay_b[layer].get('row_ids') or [])]
        idx_a[layer] = {r: i for i, r in enumerate(ids_a)}
        idx_b[layer] = {r: i for i, r in enumerate(ids_b)}
        only_a = sorted(set(ids_a) - set(ids_b))
        only_b = sorted(set(ids_b) - set(ids_a))
        if only_a or only_b:
            rep['row_set_differences'].append(
                {'layer': layer, 'row_axis': ax_a,
                 'only_in_a': only_a[:40], 'n_only_in_a': len(only_a),
                 'only_in_b': only_b[:40], 'n_only_in_b': len(only_b)})
        if ids_a != ids_b and not (only_a or only_b):
            # Same set, different order. Not a draw difference -- and the
            # reason rows are addressed by id is that a positional compare
            # would have called this a draw difference.
            rep['row_set_differences'].append(
                {'layer': layer, 'row_axis': ax_a, 'only_in_a': [],
                 'n_only_in_a': 0, 'only_in_b': [], 'n_only_in_b': 0,
                 'note': 'same row-id set, different row ORDER. Addressed by '
                         'id, so this is not an array difference.'})

    n_cells = 0
    for key in sorted(set(a['arrays']) & set(b['arrays'])):
        layer = key.split('/', 1)[0]
        if layer not in idx_a or layer not in idx_b:
            rep['array_differences'].append(
                {'array': key, 'kind': 'LAYER_NOT_IN_BOTH_MANIFESTS'})
            continue
        ma, mb = a['arrays'][key], b['arrays'][key]
        shared = sorted(set(idx_a[layer]) & set(idx_b[layer]))
        if not shared:
            rep['array_differences'].append(
                {'array': key, 'kind': 'NO_SHARED_ROWS'})
            continue
        if ma.shape[1] != mb.shape[1]:
            rep['array_differences'].append(
                {'array': key, 'kind': 'DRAW_COUNT_DIFFERS',
                 'a_n_draws': int(ma.shape[1]), 'b_n_draws': int(mb.shape[1])})
            continue
        bad = []
        for rid in shared:
            va = ma[idx_a[layer][rid]]
            vb = mb[idx_b[layer][rid]]
            ba = np.frombuffer(_bits(va), dtype=np.uint64)
            bb = np.frombuffer(_bits(vb), dtype=np.uint64)
            if ba.tobytes() != bb.tobytes():
                # The bit pattern is the comparison; the delta is only there
                # so a reader can see whether a difference is a last-bit
                # rounding or a different number. A non-finite delta is
                # reported as None rather than as the token `NaN`, which is
                # not valid JSON and would make the proof unreadable.
                d = float(np.max(np.abs(va - vb)))
                bad.append({'row_id': rid,
                            'n_cells_differing': int(np.sum(ba != bb)),
                            'max_abs_delta': d if np.isfinite(d) else None})
        n_cells += len(shared) * int(ma.shape[1])
        if bad:
            rep['array_differences'].append(
                {'array': key, 'kind': 'CELLS_DIFFER',
                 'n_rows_differing': len(bad), 'rows': bad[:20]})
        rep['compared'].append({'array': key, 'n_rows': len(shared),
                                'n_draws': int(ma.shape[1])})

    rep['n_arrays_compared'] = len(rep['compared'])
    rep['n_cells_compared'] = n_cells
    rep['content_digest_a'] = man_a.get('content_digest')
    rep['content_digest_b'] = man_b.get('content_digest')
    rep['content_digest_equal'] = (man_a.get('content_digest')
                                   == man_b.get('content_digest'))
    rep['identical'] = not (rep['layers_only_in_a'] or rep['layers_only_in_b']
                            or rep['arrays_only_in_a']
                            or rep['arrays_only_in_b']
                            or rep['row_axis_disagreements']
                            or rep['row_set_differences']
                            or rep['array_differences'])
    # A comparison that compared nothing is not a pass. This is the same rule
    # `run_suite` applies to a test function that ran zero checks.
    if rep['n_cells_compared'] == 0:
        rep['identical'] = False
        rep['array_differences'].append(
            {'array': None, 'kind': 'NOTHING_WAS_COMPARED',
             'why': 'zero draw cells were compared, so "identical" would be '
                    'a statement about an empty set.'})
    return rep


def _candidate_identity(run: dict) -> dict:
    art, board = run['artifact'], run['board']
    return {
        'spec_hash': art.get('spec_hash'),
        'feature_set_hash': art.get('feature_set_hash'),
        'model_arm': art.get('model_arm'),
        'seed_protocol': art.get('seed_protocol'),
        'candidate_components': art.get('candidate_components'),
        'candidate_components_applied': art.get('candidate_components_applied'),
        'cold_start_freeze_identity': art.get('cold_start_freeze_identity'),
        'component_manifest': board.get('component_manifest'),
    }


def _execution_identity(run: dict) -> dict:
    s, art = run['summary'], run['artifact']
    ci = s.get('code_identity') or {}
    return {
        'execution_identity': s.get('execution_identity'),
        'run_id': s.get('run_id'),
        'code_commit': s.get('code_commit'),
        'artifact_code_commit': art.get('code_commit'),
        'code_identity_commit': ci.get('commit'),
        'code_identity_source_scope_sha256': ci.get('source_scope_sha256'),
        'code_identity_code_version': ci.get('code_version'),
        'runtime_token': ci.get('runtime_token'),
        'written_at': s.get('written_at'),
        'arm': s.get('arm'),
        'pipeline_version': s.get('pipeline_version'),
    }


def _model_configuration(run: dict) -> dict:
    art, board = run['artifact'], run['board']
    return {
        'model_configuration': art.get('model_configuration')
                               or board.get('model_configuration'),
        'n_draws': board.get('n_draws') or run['manifest'].get('n_draws'),
        'rng': run['manifest'].get('rng'),
        'eligibility_verdict': art.get('eligibility_verdict'),
        'completeness': art.get('completeness'),
    }


def manifest_drift(frozen: dict, obs_a: dict, obs_b: dict) -> list:
    """Where either run departed from the FROZEN manifest.

    Separate from the A-vs-B comparison on purpose. Two runs can agree with
    each other and both disagree with the manifest -- that is a cutoff that
    moved, not determinism -- and two runs can each match the manifest on the
    sources they report while one silently consumed fewer. Both need naming,
    and a single equality flag cannot say which happened.
    """
    drift = []
    for name, rec in (frozen.get('sources') or {}).items():
        for label, obs in (('a', obs_a), ('b', obs_b)):
            got = obs.get(name)
            if got is None:
                drift.append({'source': name, 'run': label,
                              'frozen_sha256': rec.get('sha256'),
                              'observed_sha256': None,
                              'why': 'the run did not report consuming it'})
            elif got.get('sha256') != rec.get('sha256'):
                drift.append({'source': name, 'run': label,
                              'frozen_sha256': rec.get('sha256'),
                              'observed_sha256': got.get('sha256')})
    return drift


def _diff(name: str, a, b) -> list:
    """Field-level differences between two flat dicts, as a readable list."""
    out = []
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k):
            out.append({'group': name, 'field': k,
                        'a': a.get(k), 'b': b.get(k)})
    return out


# --------------------------------------------------------------- classifier
def classify(*, before, between, after, frozen, obs_a, obs_b,
             arrays_rep, identity_diffs) -> dict:
    """Which of the contract's rows explains the failure. First match wins.

    Order is the whole value of this function. An in-scope source change makes
    every downstream difference expected, so reporting a draw difference as
    nondeterminism while `pipeline.py` changed underneath would be a false
    alarm with a confident name on it.
    """
    findings = []

    # --- CAUSE 0. Did the premise hold?
    drift = manifest_drift(frozen, obs_a, obs_b)
    cross = _diff('input_hashes',
                  {k: v.get('sha256') for k, v in obs_a.items()},
                  {k: v.get('sha256') for k, v in obs_b.items()})
    if drift or cross:
        findings.append({
            'cause': 'CAUSE_0_INPUTS_NOT_FROZEN',
            'meaning': CAUSES['CAUSE_0_INPUTS_NOT_FROZEN'],
            'evidence': {'manifest_drift': drift[:40],
                         'a_vs_b': cross[:40]}})

    # --- CAUSE 1. Did the code change under the runs?
    pts = [p for p in (before, between, after) if p.get('resolved')]
    scopes = {p['source_scope_sha256'] for p in pts}
    commits = {p['commit'] for p in pts}
    if len(pts) != 3:
        findings.append({
            'cause': 'CAUSE_1_IN_SCOPE_SOURCE_CHANGED',
            'meaning': 'identity B could not be resolved at one or more '
                       'observation points, so a source change cannot be '
                       'ruled out and must not be assumed away.',
            'evidence': {'unresolved': [p['label'] for p in
                                        (before, between, after)
                                        if not p.get('resolved')]}})
    elif len(scopes) > 1 or len(commits) > 1:
        moved = {}
        for p in pts:
            for e in p['dirty_source_files']:
                moved.setdefault(e['path'], set()).add(e['sha256'])
        changed = sorted(k for k, v in moved.items() if len(v) > 1)
        # A file dirty at one point and absent from another point's list also
        # changed: it was committed, reverted, or newly edited.
        present_at = {}
        for p in pts:
            for e in p['dirty_source_files']:
                present_at.setdefault(e['path'], []).append(p['label'])
        appeared = sorted(k for k, v in present_at.items() if len(v) < len(pts))
        findings.append({
            'cause': 'CAUSE_1_IN_SCOPE_SOURCE_CHANGED',
            'meaning': CAUSES['CAUSE_1_IN_SCOPE_SOURCE_CHANGED'],
            'evidence': {
                'source_scope_sha256_by_point': {
                    p['label']: p['source_scope_sha256'] for p in pts},
                'commit_by_point': {p['label']: p['commit'] for p in pts},
                'files_whose_content_changed': changed,
                'files_not_dirty_at_every_point': appeared,
                'read_this_as': 'another agent edited in-scope source while '
                                'this proof was running. Re-run when the tree '
                                'is quiescent; do not report a determinism '
                                'defect on this evidence.'}})

    # --- CAUSE 2. Arrays equal, identity moved anyway.
    if arrays_rep['identical'] and identity_diffs and not findings:
        findings.append({
            'cause': 'CAUSE_2_SEALED_BODY_READS_D',
            'meaning': CAUSES['CAUSE_2_SEALED_BODY_READS_D'],
            'evidence': {'identity_differences': identity_diffs[:40]}})

    # --- CAUSE 3. Everything constant and the draws moved.
    if (not arrays_rep['identical']) and not identity_diffs and not findings:
        findings.append({
            'cause': 'CAUSE_3_PREDICTIVE_NONDETERMINISM',
            'meaning': CAUSES['CAUSE_3_PREDICTIVE_NONDETERMINISM'],
            'evidence': {'arrays': arrays_rep['array_differences'][:20],
                         'rows': arrays_rep['row_set_differences'][:20]}})

    # Anything left over that no row above claims. Named rather than dropped:
    # an unclassified failure reported as "no cause found" would read as a
    # pass to a skim.
    if (identity_diffs or not arrays_rep['identical']) and not findings:
        findings.append({
            'cause': 'UNCLASSIFIED',
            'meaning': 'a difference exists that none of the contract rows '
                       'explains. This is a gap in the classifier, not a '
                       'clean result, and must be read as such.',
            'evidence': {'identity_differences': identity_diffs[:40],
                         'arrays': arrays_rep['array_differences'][:20]}})
    return {'findings': findings,
            'primary_cause': findings[0]['cause'] if findings else None}


def verdict_is_pass(equalities: dict, findings: list) -> bool:
    """PASS needs BOTH halves, and this is a function so it can be tested.

    Six green equalities with an open CAUSE_1 finding is not a proof. It says
    the two runs agreed while the code underneath them was moving -- a
    coincidence worth reporting, not a property worth certifying. It happens:
    measured on 2026-09-14, one execution on `2026_01_SF_LA` returned all five
    equalities green with `nfl/production/pool_audit.py` changing during the
    window. A verdict that read only the equalities would have handed that back
    as a PASS produced inside an edit window.

    An empty equalities dict is a FAIL for the same reason
    `compare_arrays` refuses to call an empty comparison identical.
    """
    if not equalities:
        return False
    return all(equalities.values()) and not findings


# ------------------------------------------------------------------- driver
def prove(*, season, week, game_id, cutoff, out_root_a, out_root_b,
          draws=1000, seed=DEFAULT_SEED,
          model_configuration=DEFAULT_MODEL_CONFIGURATION,
          input_manifest: dict = None) -> Outcome:
    """Two runs, five equalities, and dF/dD = 0. One Outcome, always named."""
    ra = pathlib.Path(out_root_a).resolve()
    rb = pathlib.Path(out_root_b).resolve()
    if ra == rb or str(rb).startswith(str(ra) + os.sep) \
            or str(ra).startswith(str(rb) + os.sep):
        return Outcome.blocked(
            'DP_OUTPUT_ROOTS_NOT_SEPARATE',
            f'--out-root-a {ra} and --out-root-b {rb} are the same directory '
            f'or one contains the other. WS-E established that a single '
            f'shared root shows a FALSE GREEN: the working-tree state is '
            f'already elevated by run A when run B observes it, so both runs '
            f'agree under an implementation that is in fact identity-'
            f'dependent on its own outputs. Two separate top-level roots are '
            f'the experiment, not a formatting preference.',
            cause=Cause.GOVERNANCE)

    from nfl.tools import make_board as MB
    try:
        kickoff = MB.kickoff_for(season, week, game_id)
    except SystemExit as exc:
        return Outcome.blocked(
            'DP_KICKOFF_UNKNOWN',
            f'{game_id}: {exc}. Without a kickoff the chronology cut cannot '
            f'be checked and neither run may be sealed.', cause=Cause.DATA)

    if input_manifest is None:
        fo = resolve_input_manifest(kickoff, cutoff)
        if fo.state is not State.PASS:
            return fo
        frozen = fo.value
    else:
        frozen = copy.deepcopy(input_manifest)
        restated = _sha({k: v for k, v in frozen.items()
                         if k != 'manifest_sha256'})
        if frozen.get('manifest_sha256') not in (None, restated):
            return Outcome.fail(
                'DP_INPUT_MANIFEST_SELF_INCONSISTENT',
                f'the supplied input manifest carries manifest_sha256 '
                f'{frozen.get("manifest_sha256")} but its own content hashes '
                f'to {restated}. A frozen manifest that does not hash to what '
                f'it says is not frozen.')
        frozen['manifest_sha256'] = restated

    before = _observe_code_identity('before_run_a')
    run_a = run_once(season=season, week=week, game_id=game_id, cutoff=cutoff,
                     out_root=ra, draws=draws, seed=seed,
                     model_configuration=model_configuration, label='A')
    between = _observe_code_identity('between_runs')
    if run_a.state is not State.PASS:
        return run_a
    run_b = run_once(season=season, week=week, game_id=game_id, cutoff=cutoff,
                     out_root=rb, draws=draws, seed=seed,
                     model_configuration=model_configuration, label='B')
    after = _observe_code_identity('after_run_b')
    if run_b.state is not State.PASS:
        return run_b
    A, B = run_a.value, run_b.value

    arrays_rep = compare_arrays(A, B)
    groups = {
        'candidate_identity': (_candidate_identity(A), _candidate_identity(B)),
        'execution_identity': (_execution_identity(A), _execution_identity(B)),
        'model_configuration': (_model_configuration(A),
                                _model_configuration(B)),
    }
    identity_diffs = []
    for name, (x, y) in groups.items():
        identity_diffs.extend(_diff(name, x, y))

    obs_a, obs_b = _observed_manifest(A), _observed_manifest(B)
    drift = manifest_drift(frozen, obs_a, obs_b)
    identity_diffs.extend(_diff(
        'input_hashes',
        {k: v.get('sha256') for k, v in obs_a.items()},
        {k: v.get('sha256') for k, v in obs_b.items()}))

    # THE dF/dD CLAIM, STATED AS A MEASUREMENT AND NOT AS A CONCLUSION.
    #
    # Run B computed its identity with run A's whole output tree on disk. If
    # `source_scope_sha256` is equal across all three observation points, the
    # identity did not read those outputs. The counterfactual says whether the
    # WITHDRAWN implementation would have disagreed at the same points -- if it
    # would not have, this run is a weak test and says so rather than claiming
    # a strength it did not demonstrate.
    pts = [before, between, after]
    resolved = [p for p in pts if p.get('resolved')]
    legacy_vals = [p['legacy'].get('n_dirty_tree_entries') for p in pts
                   if p.get('legacy', {}).get('available')]
    dfdd = {
        'claim': 'a run must not change its own identity by writing its own '
                 'outputs: F = f(A,B,C,E,inputs) and dF/dD = 0',
        'observation_points': ['before_run_a', 'between_runs', 'after_run_b'],
        'source_scope_sha256_by_point': {
            p['label']: p.get('source_scope_sha256') for p in pts},
        # TWO DIFFERENT STABILITY QUESTIONS, AND COLLAPSING THEM MISREPORTS.
        #
        # `run_forecast.build` resolves its code identity ONCE, before the run
        # writes anything, so both identities are fixed in the interval
        # before_run_a -> between_runs. That interval is what the dF/dD claim
        # needs: if the scope is constant across it and B's identity equals
        # A's, then B -- executing with A's whole output tree on disk --
        # computed the same identity, which is the property.
        #
        # A change landing WHILE run B executed is a different concern. B's
        # recorded identity cannot move (already resolved), but a module
        # imported late in the run could behave differently, so this is
        # reported and it does drive CAUSE_1 and the verdict. What it must not
        # do is turn the dF/dD LINE red, because a reader seeing "generated
        # output altered the second run's identity" would be reading a
        # sentence that is false. One observation, two questions, two fields.
        'source_scope_stable_at_identity_resolution': (
            before.get('resolved') and between.get('resolved')
            and before['source_scope_sha256'] == between['source_scope_sha256']),
        'source_scope_stable_through_run_b': (
            len(resolved) == 3
            and len({p['source_scope_sha256'] for p in resolved}) == 1),
        'run_b_identity_equals_run_a_identity': (
            _execution_identity(A)['execution_identity']
            == _execution_identity(B)['execution_identity']),
        'run_b_ran_with_run_a_outputs_on_disk': True,
        'out_root_a': str(ra),
        'out_root_b': str(rb),
        'roots_are_separate_top_level_directories': True,
        'counterfactual_discriminating': len(set(legacy_vals)) > 1,
        'counterfactual_counts_by_point': {
            p['label']: p.get('legacy', {}).get('n_dirty_tree_entries')
            for p in pts},
        'counterfactual_note': (
            'true means the WITHDRAWN <sha>+dirty[N] form WOULD have produced '
            'different identities across these observation points while the '
            'content digest did not -- the repair is doing work here. false '
            'means the tree happened not to move (for example both output '
            'roots are outside the repository), so this particular execution '
            'does not discriminate between the two implementations and is a '
            'weaker demonstration. It is never a reason to call the old form '
            'sound.'),
    }

    cls = classify(before=before, between=between, after=after,
                   frozen=frozen, obs_a=obs_a, obs_b=obs_b,
                   arrays_rep=arrays_rep, identity_diffs=identity_diffs)

    equalities = {
        'identical_predictive_arrays': arrays_rep['identical'],
        'identical_candidate_identity': not [d for d in identity_diffs
                                             if d['group']
                                             == 'candidate_identity'],
        'identical_execution_identity': not [d for d in identity_diffs
                                             if d['group']
                                             == 'execution_identity'],
        'identical_model_configuration': not [d for d in identity_diffs
                                              if d['group']
                                              == 'model_configuration'],
        # A vs B AND both against the frozen manifest. A pair of runs that
        # agree with each other and disagree with the manifest consumed the
        # same wrong bytes, which is not the property being claimed.
        'identical_input_hashes': not ([d for d in identity_diffs
                                        if d['group'] == 'input_hashes']
                                       or drift),
        'generated_output_did_not_alter_second_run_identity':
            bool(dfdd['source_scope_stable_at_identity_resolution']
                 and dfdd['run_b_identity_equals_run_a_identity']),
    }
    passed = verdict_is_pass(equalities, cls['findings'])

    proof = {
        'proof_version': PROOF_VERSION,
        'proof_tool': 'nfl/tools/determinism_proof.py',
        'proof_tool_sha256': tool_source_sha256(),
        'verdict': 'PASS' if passed else 'FAIL',
        'game_id': game_id, 'season': season, 'week': week,
        'kickoff_utc': kickoff, 'cutoff_utc': cutoff,
        'draws': draws, 'seed': seed,
        'model_configuration': model_configuration,
        'frozen_input_manifest': frozen,
        'equalities': equalities,
        'arrays': arrays_rep,
        'identity': {
            'a': {k: v[0] for k, v in groups.items()},
            'b': {k: v[1] for k, v in groups.items()},
            'differences': identity_diffs,
        },
        'consumed_inputs': {'a': obs_a, 'b': obs_b,
                            'drift_from_frozen_manifest': drift},
        'dF_dD': dfdd,
        'classification': cls,
        'cause_definitions': CAUSES,
        'code_identity_observations': [
            {k: v for k, v in p.items() if k != 'legacy'} for p in pts],
        'proof_body_excludes': list(PROOF_BODY_EXCLUDED),
        'proof_body_excludes_why': (
            'each excluded key reads generated artifact state (D), the wall '
            'clock, or the machine. The identity contract forbids a D-reader '
            'inside a sealed body whether or not it is hashed, because the '
            'body is itself hashed into an identity -- the artifact minus its '
            'hash keys IS the payload. Excluding them is what makes '
            'proof_body_sha256 reproducible across runs.'),
        'diagnostics': {
            'generated_at': _now(),
            'platform': platform.platform(),
            'python': platform.python_version(),
            'numpy': np.__version__,
            'run_dir_a': A['run_dir'], 'run_dir_b': B['run_dir'],
            'elapsed_s_a': A['elapsed_s'], 'elapsed_s_b': B['elapsed_s'],
            'legacy_counterfactual_by_point': {
                p['label']: p.get('legacy') for p in pts},
        },
    }
    body = {k: v for k, v in proof.items() if k not in PROOF_BODY_EXCLUDED}
    proof['proof_body_sha256'] = hashlib.sha256(_canon(body)).hexdigest()
    proof['proof_signature'] = hashlib.sha256(
        (proof['proof_body_sha256'] + ':'
         + proof['proof_tool_sha256']).encode()).hexdigest()

    detail = (f'{game_id}: ' + ('all six properties hold' if passed else
              f'FAILED -- primary cause '
              f'{cls["primary_cause"]}'))
    ev = dict(verdict=proof['verdict'],
              primary_cause=cls['primary_cause'],
              n_arrays_compared=arrays_rep['n_arrays_compared'],
              n_cells_compared=arrays_rep['n_cells_compared'],
              proof_body_sha256=proof['proof_body_sha256'],
              counterfactual_discriminating=dfdd['counterfactual_discriminating'])
    if passed:
        return Outcome.ok('DETERMINISM_PROVEN', value=proof, detail=detail, **ev)
    return Outcome.fail('DETERMINISM_NOT_PROVEN', detail, proof=proof, **ev)


def write_proof(proof: dict, path) -> Outcome:
    """Write the proof, refusing to overwrite a different one at the same path."""
    p = pathlib.Path(path)
    if not p.is_absolute():
        p = _REPO / p
    if p.exists():
        try:
            prior = json.loads(p.read_text())
        except (ValueError, OSError):
            prior = None
        if prior and prior.get('proof_body_sha256') \
                != proof.get('proof_body_sha256'):
            return Outcome.fail(
                'DP_PROOF_WOULD_OVERWRITE_DIFFERENT_PROOF',
                f'{p} already holds a proof whose body hashes to '
                f'{prior.get("proof_body_sha256")}, and this one hashes to '
                f'{proof.get("proof_body_sha256")}. A proof is evidence, not '
                f'a file that gets updated -- write the new one beside it.',
                prior=prior.get('proof_body_sha256'))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(proof, indent=1, sort_keys=True, default=str)
                 + '\n')
    return Outcome.ok('DP_PROOF_WRITTEN', value=str(p),
                      detail=f'{p.name}: {proof["verdict"]}')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description='Run one forecast twice from frozen inputs and prove the '
                    'two runs are one run.')
    ap.add_argument('--game-id', required=True)
    ap.add_argument('--season', type=int, default=2026)
    ap.add_argument('--week', type=int, default=1)
    ap.add_argument('--cutoff', required=True,
                    help='the forecast cutoff (written_at), e.g. '
                         '2026-09-14T23:00:00Z')
    ap.add_argument('--out-root-a', required=True)
    ap.add_argument('--out-root-b', required=True)
    ap.add_argument('--draws', type=int, default=1000)
    ap.add_argument('--seed', type=int, default=DEFAULT_SEED)
    ap.add_argument('--model-configuration',
                    default=DEFAULT_MODEL_CONFIGURATION)
    ap.add_argument('--input-manifest',
                    help='a frozen input manifest written by a previous run '
                         'with --write-manifest. Supplied, the two runs are '
                         'asserted against IT rather than against whatever '
                         'the information set resolves to now.')
    ap.add_argument('--write-manifest',
                    help='resolve the input manifest at the cutoff, write it '
                         'here, and exit without running anything.')
    ap.add_argument('--proof-out', help='where to write the proof artifact')
    a = ap.parse_args(argv)

    if a.write_manifest:
        from nfl.tools import make_board as MB
        ko = MB.kickoff_for(a.season, a.week, a.game_id)
        fo = resolve_input_manifest(ko, a.cutoff)
        print(f'{fo.state.value}[{fo.code}] {fo.detail}')
        if fo.state is not State.PASS:
            return 2
        p = pathlib.Path(a.write_manifest)
        if not p.is_absolute():
            p = _REPO / p
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(fo.value, indent=1, sort_keys=True) + '\n')
        print(f'MANIFEST_WRITTEN {p} sha256={fo.value["manifest_sha256"]}')
        return 0

    manifest = None
    if a.input_manifest:
        mp = pathlib.Path(a.input_manifest)
        if not mp.is_absolute():
            mp = _REPO / mp
        manifest = json.loads(mp.read_text())

    o = prove(season=a.season, week=a.week, game_id=a.game_id,
              cutoff=a.cutoff, out_root_a=a.out_root_a,
              out_root_b=a.out_root_b, draws=a.draws, seed=a.seed,
              model_configuration=a.model_configuration,
              input_manifest=manifest)

    print(f'{o.state.value}[{o.code}] {o.detail}')
    proof = o.value if o.state is State.PASS else dict(o.evidence).get('proof')
    if isinstance(proof, dict):
        for k, v in proof['equalities'].items():
            print(f'  {"PASS" if v else "FAIL"}  {k}')
        cf = proof['dF_dD']['counterfactual_discriminating']
        print(f'  counterfactual_discriminating: {cf}')
        for f in proof['classification']['findings']:
            print(f'  CAUSE {f["cause"]}')
            print(f'        {f["meaning"]}')
        print(f'  proof_body_sha256 {proof["proof_body_sha256"]}')
        if a.proof_out:
            w = write_proof(proof, a.proof_out)
            print(f'  {w.state.value}[{w.code}] {w.detail}')
    return 0 if o.state is State.PASS else 1


if __name__ == '__main__':
    sys.exit(main())
