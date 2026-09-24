#!/usr/bin/env python3.12
"""A pinned, immutable evidence set for one forecast run.

    python3.12 -m nfl.truth.run_input --game-id 2026_03_ATL_GB \
        --cutoff 2026-09-24T15:30:00Z --capture-commit <sha> \
        --manifest <capture-prod vintage_manifest.jsonl> \
        --materialize <dir> --out <sealed.json>

WHY THIS EXISTS, MEASURED RATHER THAN ASSERTED

`availability_feed.newest_lawful()` selects the newest artifact **that exists
in the working tree**. On 2026-09-24 that silently selected an ESPN capture
stamped 2026-09-20T04:37:43Z -- four days stale -- because the fresh captures
live on `capture-prod` and the automation branch's manifest stopped at
20260921T175256Z. It did not warn, degrade or refuse. It returned PASS.

The damage was not hypothetical. On that stale vintage, Aaron Banks read
PROBABILISTIC against a declared OUT, Javon Hargrave read UNAVAILABLE against
a declared QUESTIONABLE, and Samson Ebukam had no item at all -- three
apparent source disagreements that were entirely an artefact of the two halves
of the run being on different clocks. On the SAME vintage all eight declared
players agreed exactly. A plausible stale answer had been one step from
reaching a board.

THE RULE THIS ENCODES

A forecast consumes a **named, hashed, immutable** evidence set chosen once,
before the run, and verified at the point of use. It never consumes "whatever
happens to be newest locally". A required family that is stale or missing is
a named refusal, never a fallback to an older artifact.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import shutil
import sys

SPEC_VERSION = 'run-input-contract/1.0.0'

# Families a pregame availability/identity run requires. A family absent from
# the pinned set is a refusal; it is never filled from the checkout.
REQUIRED_FAMILIES = ('schedules', 'weekly_rosters', 'depth_charts', 'injuries')
OPTIONAL_FAMILIES = ('espn_injuries_json', 'official_injury_report',
                     'official_inactives')

FRESH = 'FRESH'
STALE = 'STALE'
#: No max age is DECLARED for this family, so its age was not checked.
#:
#: This verdict exists because the old code returned FRESH in exactly this
#: case. `required_max_age_h` defaulted to None, the staleness test was
#: `required_max_age_h is not None and ...`, and so a family with no bound
#: could never be STALE. Measured 2026-09-24 on the live ATL @ GB contract:
#: `official_inactives` was pinned to a capture 214.41 hours old -- nine days
#: -- and verified FRESH with ok=True. A verdict named FRESH that means "the
#: file exists and hashes" is the exact collapse this layer is supposed to
#: prevent, and it failed permissive.
AGE_NOT_BOUNDED = 'AGE_NOT_BOUNDED'
MISSING = 'MISSING'
HASH_MISMATCH = 'HASH_MISMATCH'
AFTER_CUTOFF = 'AFTER_CUTOFF'


class RunInputRefusal(RuntimeError):
    def __init__(self, code, detail):
        super().__init__(f'{code}: {detail}')
        self.code, self.detail = code, detail


def _iso(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except ValueError:
        return None


def select(manifest_rows, *, cutoff, families) -> dict:
    """The newest PASS row per family whose retrieval clock is <= cutoff.

    RETRIEVAL, NOT PUBLICATION. Retrieval is never earlier than publication,
    so selecting on the retrieval clock is the conservative direction: it can
    exclude an artifact that was already public, and cannot include one that
    was not.
    """
    cut = _iso(cutoff)
    if cut is None:
        raise RunInputRefusal('CUTOFF_UNPARSEABLE',
                              f'{cutoff!r} is not a timestamp, and evidence '
                              f'chosen without a clock may contain its own '
                              f'answer.')
    best = {}
    for r in manifest_rows:
        fam = r.get('source')
        if fam not in families or r.get('state') != 'PASS':
            continue
        v = r.get('value') or {}
        prov = v.get('provenance') or {}
        got = _iso(prov.get('retrieved_at')) or _iso(v.get('requested_at'))
        if got is None or got > cut:
            continue
        cur = best.get(fam)
        if cur is None or got > cur['_clock']:
            best[fam] = {
                '_clock': got,
                'family': fam,
                'capture_id': r.get('capture_id'),
                'blob': v.get('blob'),
                'raw_blob': v.get('raw_blob'),
                'sha256': v.get('sha256'),
                'blob_file_sha256': v.get('blob_file_sha256'),
                'raw_blob_file_sha256': v.get('raw_blob_file_sha256'),
                'content_kind': v.get('content_kind'),
                'n_bytes': v.get('n_bytes'),
                'url': v.get('url'),
                'retrieved_at': prov.get('retrieved_at'),
                'source_timestamp': prov.get('source_timestamp'),
                'effective_scope': v.get('effective_scope'),
            }
    for e in best.values():
        e.pop('_clock', None)
    return best


def freeze(game_id, *, cutoff, capture_commit, manifest_rows,
           manifest_sha256=None) -> dict:
    """Pin one evidence set. Refuses if a REQUIRED family has no lawful row."""
    chosen = select(manifest_rows, cutoff=cutoff,
                    families=REQUIRED_FAMILIES + OPTIONAL_FAMILIES)
    missing = [f for f in REQUIRED_FAMILIES if f not in chosen]
    if missing:
        raise RunInputRefusal(
            'REQUIRED_FAMILY_UNAVAILABLE_AT_CUTOFF',
            f'{missing} have no PASS capture at or before {cutoff}. The run '
            f'does not fall back to a later or an older artifact; a family '
            f'that cannot be pinned is a refusal.')
    return {
        'schema': 'nfl_run_input_contract',
        'schema_version': SPEC_VERSION,
        'game_id': game_id,
        'cutoff_utc': cutoff,
        'capture_commit': capture_commit,
        'capture_manifest_sha256': manifest_sha256,
        'frozen_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'required_families': list(REQUIRED_FAMILIES),
        'optional_families': list(OPTIONAL_FAMILIES),
        'entries': {k: chosen[k] for k in sorted(chosen)},
        'immutability_note':
            'These entries are the evidence set for this run. Selection is '
            'done once, here. Nothing downstream may rediscover a file from '
            'the checkout, and a stale or missing family is a named refusal '
            'rather than a substitution.',
    }


def _governed_max_age_h(family: str):
    """The declared max age for `family`, or None when none is declared.

    Imported lazily so this module keeps working if the production package is
    not importable; a missing threshold table means UNBOUNDED, never a
    silently permissive default dressed as a bound.
    """
    try:
        from nfl.production.universe import governed_thresholds as GT
    except Exception:                                        # noqa: BLE001
        return None
    try:
        return (GT.freshness_requirement(family) or {}).get('max_age_hours')
    except Exception:                                        # noqa: BLE001
        return None


def verify(pinned: dict, *, root: pathlib.Path, required_max_age_h=None) -> dict:
    """Check every pinned entry against the bytes actually present.

    Four things, in order, because they fail differently: the file exists, its
    hash matches what was pinned, its clock is at or before the cutoff, and it
    is inside any required freshness window. A family that fails any of them
    is reported by name -- NOT replaced.
    """
    cut = _iso(pinned['cutoff_utc'])
    out, verdicts = {}, {}
    for fam, e in pinned['entries'].items():
        rel = e.get('blob') or e.get('raw_blob')
        p = root / rel if rel else None
        if p is None or not p.exists():
            verdicts[fam] = MISSING
            out[fam] = {'verdict': MISSING, 'expected': rel}
            continue
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        expect = e.get('blob_file_sha256')
        if expect and actual != expect:
            verdicts[fam] = HASH_MISMATCH
            out[fam] = {'verdict': HASH_MISMATCH, 'expected_sha256': expect,
                        'actual_sha256': actual, 'path': str(p)}
            continue
        got = _iso(e.get('retrieved_at'))
        if got and cut and got > cut:
            verdicts[fam] = AFTER_CUTOFF
            out[fam] = {'verdict': AFTER_CUTOFF, 'retrieved_at':
                        e.get('retrieved_at'), 'cutoff': pinned['cutoff_utc']}
            continue
        age_h = None
        if got and cut:
            age_h = (cut - got).total_seconds() / 3600.0
        # THE BOUND COMES FROM THE GOVERNED TABLE, NOT FROM THE CALLER'S
        # DEFAULT. `governed_thresholds.FRESHNESS_HOURS` already declares a
        # per-family max age with its reasoning -- injuries 6h because
        # designations move on a daily cycle, depth_charts and weekly_rosters
        # 24h, schedules 168h. This function used to ignore all of it and
        # apply one scalar that defaulted to None. An explicit
        # `required_max_age_h` still overrides, and the STRICTER of the two
        # wins, so a caller can tighten but never loosen a governed bound.
        bound = _governed_max_age_h(fam)
        if required_max_age_h is not None:
            bound = (required_max_age_h if bound is None
                     else min(bound, required_max_age_h))
        if age_h is None:
            verdicts[fam] = AGE_NOT_BOUNDED
        elif bound is None:
            # NOT FRESH. Nobody declared how old is too old for this family,
            # so its age has not been checked and saying FRESH would assert
            # something no one established.
            verdicts[fam] = AGE_NOT_BOUNDED
        else:
            verdicts[fam] = STALE if age_h > bound else FRESH
        out[fam] = {'verdict': verdicts[fam], 'age_hours': None if age_h is
                    None else round(age_h, 2), 'max_age_hours': bound,
                    'sha256': actual,
                    'retrieved_at': e.get('retrieved_at'), 'path': str(p)}
    bad = {f: v for f, v in verdicts.items()
           if f in pinned['required_families'] and v != FRESH}
    return {'per_family': out, 'verdicts': verdicts, 'required_failures': bad,
            'ok': not bad}


def assert_consumable(pinned: dict, report: dict) -> None:
    """Raise unless every REQUIRED family verified FRESH. No partial runs."""
    if report['ok']:
        return
    raise RunInputRefusal(
        'PINNED_EVIDENCE_NOT_CONSUMABLE',
        f'required families failed verification: {report["required_failures"]}'
        f'. The run stops here. Substituting an older local artifact is the '
        f'exact failure this contract exists to prevent -- on 2026-09-24 that '
        f'substitution returned PASS on evidence four days stale.')


def materialize(pinned: dict, *, src_root: pathlib.Path,
                dest: pathlib.Path) -> dict:
    """Copy the pinned blobs into an isolated directory. Nothing else lands."""
    dest.mkdir(parents=True, exist_ok=True)
    placed = {}
    for fam, e in pinned['entries'].items():
        rel = e.get('blob') or e.get('raw_blob')
        if not rel:
            continue
        s = src_root / rel
        if not s.exists():
            continue
        d = dest / pathlib.Path(rel).name
        shutil.copy2(s, d)
        placed[fam] = str(d)
    return placed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--game-id', required=True)
    ap.add_argument('--cutoff', required=True)
    ap.add_argument('--capture-commit', required=True)
    ap.add_argument('--manifest', required=True)
    ap.add_argument('--root', default='.')
    ap.add_argument('--materialize', default='')
    ap.add_argument('--max-age-hours', type=float, default=None)
    ap.add_argument('--out', default='')
    a = ap.parse_args(argv)

    mp = pathlib.Path(a.manifest)
    raw = mp.read_bytes()
    rows = [json.loads(l) for l in raw.decode().splitlines() if l.strip()]
    try:
        pinned = freeze(a.game_id, cutoff=a.cutoff,
                        capture_commit=a.capture_commit, manifest_rows=rows,
                        manifest_sha256=hashlib.sha256(raw).hexdigest())
    except RunInputRefusal as r:
        print(f'RUN_INPUT_REFUSED {r.code}\n\n  {r.detail}')
        return 1

    root = pathlib.Path(a.root).resolve()
    if a.materialize:
        placed = materialize(pinned, src_root=root,
                             dest=pathlib.Path(a.materialize))
        pinned['materialized'] = placed
        root = pathlib.Path(a.materialize)
        for fam, e in pinned['entries'].items():
            rel = e.get('blob') or e.get('raw_blob')
            if rel:
                e['materialized_name'] = pathlib.Path(rel).name

    rep = verify(pinned, root=root if not a.materialize else root,
                 required_max_age_h=a.max_age_hours)
    pinned['freshness_report'] = rep
    for fam in sorted(rep['verdicts']):
        print(f"  {fam:24s} {rep['verdicts'][fam]}")
    if a.out:
        pathlib.Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(a.out).write_text(json.dumps(pinned, indent=1) + '\n')
        print(f'wrote {a.out}')
    try:
        assert_consumable(pinned, rep)
    except RunInputRefusal as r:
        print(f'\nRUN_INPUT_REFUSED {r.code}\n\n  {r.detail}')
        return 1
    print('\nPINNED_EVIDENCE_CONSUMABLE')
    return 0


if __name__ == '__main__':
    sys.exit(main())
