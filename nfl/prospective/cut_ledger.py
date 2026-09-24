"""The immutable pre-kickoff registry of forecast cuts.

WHAT THIS IS, AND WHAT IT IS NOT

This is NOT a grading ledger. `nfl/research/postgame/PROSPECTIVE_LEDGER.jsonl`
already grades: its rows carry `actual`, `crps`, `coverage`, and they are
written once an outcome exists. This file is the other half and it runs in the
other direction -- one row per forecast CUT, written BEFORE kickoff, carrying
only what was true at prediction time.

The distinction is the whole point. A grading row written after the game can
never establish that the forecast existed before it. This one can, because it
refuses to be written afterwards.

WHY IT COMPOSES RATHER THAN RE-CAPTURES

Everything it needs already exists. `RUN_INPUT_CONTRACT.json` carries the
frozen evidence bundle -- every family, blob and sha256, the capture manifest
hash and the capture commit. `run_status.json` carries the run identity, the
code commit, the seed and arm, the draw artifact and the publication state.
This module reads those and registers them. It does not re-derive provenance,
because a second derivation of the same fact is a second thing that can
disagree.

THE THREE REFUSALS THAT MAKE IT WORTH ANYTHING

1. It refuses to register a cut whose kickoff has already passed. A row
   claiming to be prospective, written after the event, is worse than no row:
   it looks like evidence.
2. It refuses to overwrite an existing cut id. Later outcomes may GRADE a cut;
   they may never MUTATE it. Grading belongs in a separate file keyed by
   `cut_id`, never in this one.
3. It refuses a run whose artifacts it cannot read, rather than writing a row
   with empty fields. A registration that records nothing is not a record.

Nothing here is conditional on the run having SEALED. An unsealed research
output is still a forecast that existed at a time, and its refusal state is
part of what is registered rather than a reason to leave it unregistered --
otherwise the only runs in the scientific record would be the ones that
happened to pass, which is the sampling bias this project exists to avoid.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib

SPEC_VERSION = 'forecast-cut-ledger/1.0.0'

_REPO = pathlib.Path(__file__).resolve().parents[2]
LEDGER = _REPO / 'nfl' / 'prospective' / 'FORECAST_CUT_LEDGER.jsonl'

CONTRACT_FILE = 'RUN_INPUT_CONTRACT.json'
STATUS_FILE = 'run_status.json'
MANIFEST_FILE = 'player_draws_manifest.json'


class CutLedgerError(RuntimeError):
    """The cut cannot be registered. Never raised for a merely failed run."""


def _iso(value) -> str:
    if isinstance(value, dt.datetime):
        return value.astimezone(dt.timezone.utc).isoformat().replace(
            '+00:00', 'Z')
    return str(value)


def _parse(stamp: str) -> dt.datetime:
    s = str(stamp).replace('Z', '+00:00')
    out = dt.datetime.fromisoformat(s)
    if out.tzinfo is None:
        out = out.replace(tzinfo=dt.timezone.utc)
    return out


def evidence_bundle_hash(contract: dict) -> tuple[str, list[dict]]:
    """A stable digest over the frozen evidence, and the per-source rows.

    Sorted by family so the digest is a function of the CONTENT and not of
    dictionary order. Each source contributes its family and its sha256 only:
    a blob path can be moved without the evidence changing, and if it is moved
    the digest should not move either.
    """
    entries = contract.get('entries') or {}
    if not entries:
        raise CutLedgerError(
            'the run input contract carries no entries, so there is no '
            'evidence bundle to register. An empty bundle is not a bundle.')
    rows = []
    for family in sorted(entries):
        e = entries[family] or {}
        sha = e.get('sha256')
        if not sha:
            raise CutLedgerError(
                f'evidence family {family!r} carries no sha256, so the bundle '
                f'cannot be hashed. A registration with an unhashed source '
                f'proves nothing about what was consumed.')
        rows.append({'family': family, 'sha256': sha,
                     'capture_id': e.get('capture_id'),
                     'blob': e.get('blob')})
    payload = json.dumps([[r['family'], r['sha256']] for r in rows],
                         sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode()).hexdigest(), rows


def build_row(run_dir, kickoff_utc, *, now=None) -> dict:
    """Assemble the row for a run directory. Does not write."""
    d = pathlib.Path(run_dir)
    missing = [f for f in (CONTRACT_FILE, STATUS_FILE)
               if not (d / f).exists()]
    if missing:
        raise CutLedgerError(
            f'{d} is missing {missing}; refusing to register a cut whose own '
            f'artifacts cannot be read.')

    contract = json.loads((d / CONTRACT_FILE).read_text())
    status = json.loads((d / STATUS_FILE).read_text())

    kickoff = _parse(kickoff_utc)
    now = now or dt.datetime.now(dt.timezone.utc)
    if now >= kickoff:
        raise CutLedgerError(
            f'kickoff {_iso(kickoff)} has already passed at {_iso(now)}. A row '
            f'claiming to be prospective, written after the event, is worse '
            f'than no row because it looks like evidence.')

    cutoff = contract.get('cutoff_utc')
    if not cutoff:
        raise CutLedgerError('the contract declares no cutoff_utc')
    if _parse(cutoff) >= kickoff:
        raise CutLedgerError(
            f'the forecast cutoff {cutoff} is at or after kickoff '
            f'{_iso(kickoff)}; that is not a pregame forecast.')

    bundle_hash, sources = evidence_bundle_hash(contract)

    manifest = {}
    if (d / MANIFEST_FILE).exists():
        manifest = json.loads((d / MANIFEST_FILE).read_text())

    run_id = status.get('run_id') or ''
    game_id = contract.get('game_id') or ''
    cut_id = 'CUT-' + hashlib.sha256(
        f'{game_id}|{cutoff}|{run_id}|{bundle_hash}'.encode()).hexdigest()[:16]

    return {
        'spec_version': SPEC_VERSION,
        'cut_id': cut_id,
        'game_id': game_id,
        'kickoff_utc': _iso(kickoff),
        'cutoff_utc': cutoff,
        'registered_at_utc': _iso(now),
        'frozen_at_utc': contract.get('frozen_at_utc'),

        'run_id': run_id,
        'candidate_identity': status.get('code_identity') or status.get('arm'),
        'arm': status.get('arm'),
        'code_commit': status.get('code_commit'),
        'execution_identity': status.get('execution_identity'),
        'pipeline_version': status.get('pipeline_version'),

        'evidence_bundle_sha256': bundle_hash,
        'capture_manifest_sha256': contract.get('capture_manifest_sha256'),
        'capture_commit': contract.get('capture_commit'),
        'sources': sources,

        'n_draws': manifest.get('n_draws'),
        'n_layers': manifest.get('n_layers'),
        'draw_content_digest': manifest.get('content_digest'),
        'rng': manifest.get('rng'),

        'publication': status.get('publication'),
        'prospective_eligible': status.get('prospective_eligible'),
        'first_failure': status.get('first_failure'),
        'n_refusals': status.get('n_refusals'),

        'grading_note': (
            'Later outcomes may GRADE this cut in a separate artifact keyed '
            'by cut_id. They may never mutate this row.'),
    }


def existing_cut_ids(path=None) -> set[str]:
    p = pathlib.Path(path or LEDGER)
    if not p.exists():
        return set()
    out = set()
    for line in p.read_text().splitlines():
        if line.strip():
            out.add(json.loads(line).get('cut_id'))
    return out


def register(run_dir, kickoff_utc, *, path=None, now=None) -> dict:
    """Append one immutable row. Refuses to overwrite an existing cut."""
    row = build_row(run_dir, kickoff_utc, now=now)
    p = pathlib.Path(path or LEDGER)
    if row['cut_id'] in existing_cut_ids(p):
        raise CutLedgerError(
            f"{row['cut_id']} is already registered. This ledger is "
            f"append-only: a cut is registered once and graded elsewhere. "
            f"Re-registering would let a later belief overwrite what was "
            f"actually believed at prediction time.")
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'a') as fh:
        fh.write(json.dumps(row, sort_keys=True) + '\n')
    return row
