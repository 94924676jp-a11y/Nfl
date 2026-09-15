"""The replay runner. D23 closes here, not at the contract.

A contract nothing calls is a document. This is the thing that actually
reproduces a sealed forecast, and it is the reason ORIGINAL_REPLAY means
something.

WHAT IT PROVES, AND HOW

Every seal carries `input_bundle_sha256`, a digest over the content hash of
every source it consumed. That makes input identity CHECKABLE rather than
asserted. Measured on the committed 2024_01_ARI_BUF/ARI dry run:

    sealed                              6477fddd245bcc26...
    ORIGINAL_REPLAY from its partitions 6477fddd245bcc26...   identical
    re-running selection at same clock  6970cb9b6ea65fa8...   different

Both selections are lawful. The second is simply what the manifest says today,
and the manifest has grown. So an ORIGINAL_REPLAY that re-selects is not a
replay, and this runner refuses to be one: it is handed the recorded partition
ids, resolves exactly those, and then CHECKS the resulting bundle digest
against the seal. A replay that cannot reproduce the seal's own input digest is
refused rather than reported.

THE MODES ARE NOT INTERCHANGEABLE AND THERE IS NO DEFAULT.

  ORIGINAL_REPLAY              pinned to the recorded partitions, digest
                               checked against the seal
  RETROSPECTIVE_RECONSTRUCTION re-selects at the clock; MAY differ, and says so
  NEW_CANDIDATE_BACKTEST       a new candidate over a historical window;
                               nothing is being reproduced, so there is nothing
                               to check a digest against

WHAT IT NEVER DOES. It does not write, mutate or re-seal anything. It does not
substitute a nearest lawful blob for a missing one. It does not infer a mode.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Outcome, State        # noqa: E402
from nfl.prospective.q9shadow import inputs as IN                   # noqa: E402
from nfl.research.shadow import replay_contract as RC               # noqa: E402

SPEC_VERSION = 'replay_runner/1.0.0'

MODES = RC.MODES
ORIGINAL_REPLAY = RC.ORIGINAL_REPLAY
RETROSPECTIVE_RECONSTRUCTION = RC.RETROSPECTIVE_RECONSTRUCTION
NEW_CANDIDATE_BACKTEST = RC.NEW_CANDIDATE_BACKTEST


def load_sealed(path) -> Outcome:
    """Read a sealed forecast, refusing anything that is not one."""
    p = pathlib.Path(path)
    if not p.exists():
        return Outcome.fail('SEALED_FORECAST_ABSENT', f'{p} does not exist',
                            path=str(p))
    try:
        art = json.loads(p.read_text())
    except ValueError as exc:
        return Outcome.fail('SEALED_FORECAST_UNPARSEABLE', f'{p}: {exc}',
                            path=str(p))
    seal = art.get('seal') or {}
    missing = [k for k in ('consumed_partition_ids', 'payload_sha256')
               if not seal.get(k)]
    if missing or not art.get('kickoff_utc'):
        return Outcome.fail(
            'SEALED_FORECAST_INCOMPLETE',
            f'{p} lacks {missing or ["kickoff_utc"]}. A forecast that does not '
            f'record what it consumed cannot be replayed, only re-run.',
            path=str(p), missing=missing)
    return Outcome.ok('SEALED_FORECAST_LOADED', value=art, path=str(p))


def replay(sealed, mode, *, sources=None) -> Outcome:
    """Rebuild the input set a sealed forecast should consume, in `mode`.

    Returns the information set plus an INPUT IDENTITY VERDICT. For
    ORIGINAL_REPLAY the verdict is load-bearing: a bundle digest that does not
    match the seal is a refusal, because the only thing an original replay is
    for is being identical.
    """
    if mode not in MODES:
        return Outcome.fail('REPLAY_MODE_UNKNOWN',
                            f'{mode!r} is not one of {MODES}. There is no '
                            f'default mode and there must not be one.',
                            mode=mode, known=list(MODES))
    art = sealed
    if not isinstance(art, dict):
        got = load_sealed(art)
        if got.state is not State.PASS:
            return got
        art = got.value

    kickoff = art['kickoff_utc']
    written_at = art.get('written_at')
    sealed_bundle = art.get('input_bundle_sha256')
    recorded = list(art['seal']['consumed_partition_ids'])

    if mode == ORIGINAL_REPLAY:
        b = IN.bundle_from_partition_ids(recorded, kickoff)
        if b.state is not State.PASS:
            return b
        iset = b.value
        got = IN.bundle_sha256(iset)
        replayed_ids = RC.partition_ids_of(iset)
        if replayed_ids != sorted(recorded):
            return Outcome.fail(
                'REPLAY_PARTITIONS_DIFFER',
                f'resolved {replayed_ids} against recorded {sorted(recorded)}',
                recorded=sorted(recorded), resolved=replayed_ids)
        if sealed_bundle and got != sealed_bundle:
            # THE CHECK THAT MAKES THE MODE MEAN SOMETHING. If the seal carries
            # a bundle digest and the replay cannot reproduce it, something
            # about the inputs has moved and reporting the run as an original
            # replay would be a false claim of identity.
            return Outcome.fail(
                'REPLAY_INPUT_BUNDLE_MISMATCH',
                f'the replayed input bundle hashes to {got} where the seal '
                f'records {sealed_bundle}. An ORIGINAL_REPLAY that cannot '
                f'reproduce the seal\'s own input digest is not one.',
                sealed=sealed_bundle, replayed=got,
                partition_ids=replayed_ids)
        return Outcome.ok(
            'REPLAY_INPUTS_IDENTICAL', value=iset,
            detail=f'{len(replayed_ids)} partition(s) resolved from the seal; '
                   f'input bundle {got[:16]} matches the seal exactly',
            replay_mode=mode, spec_version=SPEC_VERSION, pinned=True,
            input_bundle_sha256=got, sealed_input_bundle_sha256=sealed_bundle,
            input_identity='IDENTICAL',
            partition_ids=replayed_ids, game_id=art.get('game_id'),
            team=art.get('team'), written_at=written_at)

    # ---- the unpinned modes ------------------------------------------------
    if written_at is None:
        return Outcome.fail(
            'UNPINNED_MODE_WITHOUT_CLOCK',
            f'{mode} re-runs selection and therefore needs written_at',
            mode=mode)
    b = IN.bundle(kickoff, written_at, sources=sources)
    if b.state is not State.PASS:
        return b
    iset = dict(b.value)
    iset['mode'] = mode
    iset['pinned'] = False
    got = IN.bundle_sha256(iset)
    ids = RC.partition_ids_of(iset)
    differs = bool(sealed_bundle) and got != sealed_bundle
    return Outcome.ok(
        'REPLAY_RECONSTRUCTED', value=iset,
        detail=f'{len(ids)} partition(s) selected at {written_at}; this is '
               f'{"NOT " if differs else ""}the input set the seal recorded',
        replay_mode=mode, spec_version=SPEC_VERSION, pinned=False,
        input_bundle_sha256=got, sealed_input_bundle_sha256=sealed_bundle,
        # NEVER "IDENTICAL" BY ACCIDENT. When a reconstruction happens to agree
        # with the seal it is reported as AGREES_TODAY, not IDENTICAL: it agrees
        # because the manifest has not grown yet, which is a fact about the
        # corpus rather than a property of the run.
        input_identity='DIFFERS' if differs else 'AGREES_TODAY',
        partition_ids=ids, game_id=art.get('game_id'), team=art.get('team'),
        written_at=written_at)


def ledger_row(out: Outcome, *, candidate_id=None, model_hash=None,
               data_build_hash=None, seed=None, n_draws=None,
               artifact_hash=None) -> dict:
    """One row of the historical replay ledger, from a replay Outcome.

    Fields the caller does not supply stay None. A ledger that invents a seed
    or a model hash to look complete is worse than one that admits a gap.
    """
    ev = out.evidence or {}
    return {
        'game_id': ev.get('game_id'),
        'team': ev.get('team'),
        'written_at': ev.get('written_at'),
        'replay_mode': ev.get('replay_mode'),
        'spec_version': SPEC_VERSION,
        'pinned': ev.get('pinned'),
        'input_identity': ev.get('input_identity'),
        'input_bundle_sha256': ev.get('input_bundle_sha256'),
        'sealed_input_bundle_sha256': ev.get('sealed_input_bundle_sha256'),
        'partition_ids': ev.get('partition_ids'),
        'candidate_id': candidate_id,
        'model_hash': model_hash,
        'data_build_hash': data_build_hash,
        'rng_seed': seed,
        'n_draws': n_draws,
        'artifact_hash': artifact_hash,
        'state': out.state.value,
        'code': out.code,
    }
