"""Build a run's `source_hashes` from the vintage manifest. DK-4.

WHAT THIS REPLACES, AND WHY IT IS A DEFECT AND NOT A SHORTCUT

The only slate driver in this repository satisfied `capture_validation` with

    'source_hashes': {'schedules': {'sha256': 'b' * 64,
                                    'retrieved_at': '2026-09-08T12:00:00Z'}}

Sixty-four `b` characters for one source. That is why `run_slate.py` is
declared REHEARSAL ONLY and sets `dry_run=True` in the call itself: the run
cannot honestly claim its inputs were validated, so the whole thing is
quarantined. The quarantine was the right response to the placeholder. It was
never a substitute for removing it.

THE ASSEMBLER USES THE SAME SELECTOR THE LAYERS USE, AND THAT IS THE POINT

`vintage_selector.select(family, as_of=written_at)` is what the football layers
call to choose which capture they read. Building the fixture from the same call
at the same cut makes the VALIDATED set and the CONSUMED set the same set. They
were previously disjoint: the stage validated `{schedules}` while the layers
read injuries, depth charts and rosters through the selector without passing
through validation at all. Two sets that never meet cannot disagree, which is
why nothing ever complained.

EVERY HASH HERE IS MEASURED, NOT COPIED

The manifest records a `blob_file_sha256` for each capture. This module does
not repeat it. It opens the blob and hashes the bytes on disk, then compares
its own measurement against the manifest's record and refuses
`VINTAGE_BLOB_HASH_DISAGREES` when they differ. Copying a recorded hash into a
field called `sha256` would produce a fixture that passes validation while
proving nothing about the bytes -- a smaller version of the placeholder, and
harder to see.

WHAT A REFUSAL HERE MEANS

A missing lawful vintage is NOT an error to route around. It means no capture
of that source exists at or before the cut, and the honest consequence is that
the run has no inputs and must refuse. This module never widens the cut, never
falls back to a later capture, and never substitutes a different source.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.capture import registry as REG                          # noqa: E402
from nfl.production.nonqb import vintage_selector as VS          # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'fixture-assembler-1'

MANIFEST = _REPO / 'nfl' / 'vintage_manifest.jsonl'


def _parse(ts: str) -> _dt.datetime:
    t = (ts or '').replace('Z', '+00:00')
    d = _dt.datetime.fromisoformat(t)
    return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)


def _sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def _manifest_record(source: str, blob: str, manifest=None) -> dict:
    """The manifest row that produced this blob, or {}.

    Matched on (source, blob) rather than on capture_id, because the same blob
    is referenced by every recapture that found the content unchanged and any
    of those rows is the same evidence about the same bytes.
    """
    path = MANIFEST if manifest is None else pathlib.Path(manifest)
    if not path.exists():
        return {}
    hit = {}
    with open(path) as f:
        for ln in f:
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if r.get('source') != source or r.get('state') != 'PASS':
                continue
            v = r.get('value') or {}
            if v.get('blob') == blob:
                hit = r
    return hit


def assemble(written_at: str, sources=None, manifest=None) -> Outcome:
    """`source_hashes` for a run written at `written_at`, or a named refusal.

    PASS carries the mapping `capture_validation` consumes. Every entry is
    backed by a blob this function opened and hashed.
    """
    cut = _parse(written_at)
    want = sorted(set(sources) if sources is not None
                  else (set(VS.FAMILIES) & set(REG.BY_NAME)))
    out, detail, refusals = {}, {}, []
    for name in want:
        if name not in VS.FAMILIES:
            refusals.append({'source': name, 'code': 'VINTAGE_FAMILY_UNDECLARED',
                             'why': f'{name} is not a declared vintage family, '
                                    f'so this module has no selection rule for '
                                    f'it and will not invent one'})
            continue
        sel = VS.select(name, as_of=cut, manifest_lines=(
            pathlib.Path(manifest).read_text().splitlines()
            if manifest else None))
        if sel.state is not State.PASS:
            refusals.append({'source': name, 'code': sel.code,
                             'why': (sel.detail or '')[:300]})
            continue
        v = sel.value
        if not v.blob:
            refusals.append({'source': name, 'code': 'VINTAGE_HAS_NO_BLOB',
                             'why': 'the selected capture names no blob, so '
                                    'there are no bytes to hash'})
            continue
        p = _REPO / v.blob
        if not p.exists():
            refusals.append({'source': name, 'code': 'VINTAGE_BLOB_ABSENT',
                             'why': f'{v.blob} is named by the manifest and is '
                                    f'not on disk. A recorded hash for bytes '
                                    f'nobody can open is not evidence.'})
            continue
        # MEASURED HERE. Not read out of the manifest and passed along.
        got = _sha256_file(p)
        rec = _manifest_record(name, v.blob, manifest=manifest)
        recorded = ((rec.get('value') or {}).get('blob_file_sha256'))
        if recorded and recorded != got:
            refusals.append({
                'source': name, 'code': 'VINTAGE_BLOB_HASH_DISAGREES',
                'why': f'{v.blob} hashes to {got} and the manifest records '
                       f'{recorded}. One of the two is wrong and this module '
                       f'will not pick a winner.'})
            continue
        if v.retrieved_at and _parse(v.retrieved_at) > cut:
            # The selector should never return one, so this is a guard against
            # the selector rather than against the data. A guard that can only
            # fire on a bug upstream is still worth having when the failure it
            # prevents is a forecast reading the future.
            refusals.append({
                'source': name, 'code': 'VINTAGE_LATER_THAN_CUT',
                'why': f'{name} was retrieved {v.retrieved_at}, after the cut '
                       f'{written_at}. The selector returned it anyway, which '
                       f'is a selector defect, not a licence to use it.'})
            continue
        out[name] = {
            'sha256': got,
            'retrieved_at': v.retrieved_at,
            'schema_ok': True,
        }
        detail[name] = {
            'blob': v.blob,
            'blob_bytes': p.stat().st_size,
            'capture_id': v.capture_id,
            'content_address': v.content_sha256,
            'manifest_blob_file_sha256': recorded,
            'hash_measured_here': True,
            'manifest_agrees': (recorded == got) if recorded else None,
            'published_at': v.published_at,
            'published_authority': v.published_authority,
            'chronology': v.chronology,
            'fallback_reason': v.fallback_reason,
        }
    if refusals:
        return Outcome.blocked(
            'FIXTURE_SOURCES_UNAVAILABLE', cause=Cause.DATA,
            detail='; '.join(f'{r["source"]}: {r["code"]}' for r in refusals)
                   + '. A run cannot declare a capture it does not have, and '
                     'substituting one would be the defect this module '
                     'exists to remove.',
            spec_version=SPEC_VERSION, written_at=written_at,
            refusals=refusals, assembled=sorted(out))
    return Outcome.ok('FIXTURE_ASSEMBLED', value=out,
                      spec_version=SPEC_VERSION, written_at=written_at,
                      sources=want, detail_by_source=detail,
                      basis='nfl/production/nonqb/vintage_selector.select at '
                            'the run cut -- the same call the football layers '
                            'make, so the validated set IS the consumed set',
                      hashes_are='sha256 of the blob bytes on disk, measured '
                                 'by this module and cross-checked against '
                                 'the manifest record')


def verify_declared(src: dict, manifest=None) -> Outcome:
    """Do the declared hashes belong to captures this repository holds?

    This is what makes a fabricated hash fail. `capture_validation` calls it
    for any run that is not a declared dry run: a declared sha256 must be the
    measured hash of a blob the manifest names for that source.
    """
    bad, seen = [], {}
    for name, meta in sorted((src or {}).items()):
        want = (meta or {}).get('sha256')
        if not want:
            bad.append({'source': name, 'code': 'NO_SHA256',
                        'why': 'the declaration carries no hash at all'})
            continue
        found = None
        path = MANIFEST if manifest is None else pathlib.Path(manifest)
        if path.exists():
            with open(path) as f:
                for ln in f:
                    try:
                        r = json.loads(ln)
                    except ValueError:
                        continue
                    if r.get('source') != name or r.get('state') != 'PASS':
                        continue
                    v = r.get('value') or {}
                    if v.get('blob_file_sha256') == want:
                        found = v.get('blob')
                        break
        if found is None:
            bad.append({
                'source': name, 'code': 'NOT_IN_VINTAGE_MANIFEST',
                'declared_sha256': want,
                'why': f'no PASS capture of {name} in the vintage manifest '
                       f'has blob_file_sha256 {want}. A hash that names no '
                       f'capture this repository holds is a claim, not an '
                       f'input.'})
            continue
        p = _REPO / found
        if not p.exists():
            bad.append({'source': name, 'code': 'BLOB_ABSENT',
                        'blob': found,
                        'why': 'the manifest names this blob and it is not on '
                               'disk'})
            continue
        got = _sha256_file(p)
        if got != want:
            bad.append({'source': name, 'code': 'BLOB_HASH_MISMATCH',
                        'blob': found, 'declared_sha256': want,
                        'measured_sha256': got,
                        'why': 'the bytes on disk do not hash to the declared '
                               'value'})
            continue
        seen[name] = {'blob': found, 'sha256': got}
    if bad:
        return Outcome.blocked(
            'DECLARED_CAPTURES_UNVERIFIED', cause=Cause.DATA,
            detail='; '.join(f'{b["source"]}: {b["code"]}' for b in bad),
            spec_version=SPEC_VERSION, unverified=bad, verified=sorted(seen))
    return Outcome.ok('DECLARED_CAPTURES_VERIFIED', value=seen,
                      spec_version=SPEC_VERSION,
                      n_verified=len(seen),
                      method='each declared sha256 matched a PASS capture in '
                             'the vintage manifest AND the blob was reopened '
                             'and rehashed')


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--written-at', required=True)
    ap.add_argument('--out', default=None,
                    help='write a fixtures JSON here; otherwise print')
    ap.add_argument('--kickoff-utc', default=None)
    a = ap.parse_args(argv)
    o = assemble(a.written_at)
    if o.state is not State.PASS:
        print(f'{o.state.name}[{o.code}] {o.detail}')
        for r in (o.evidence or {}).get('refusals', []):
            print(f'  {r["source"]}: {r["code"]} -- {r["why"][:160]}')
        return 1
    fx = {'source_hashes': o.value}
    if a.kickoff_utc:
        fx['kickoff_utc'] = a.kickoff_utc
    txt = json.dumps(fx, indent=1, sort_keys=True)
    if a.out:
        pathlib.Path(a.out).write_text(txt + '\n')
        print(f'wrote {a.out}')
    else:
        print(txt)
    for name, d in sorted((o.evidence or {})['detail_by_source'].items()):
        print(f'  {name:16} {d["blob"]}  {d["blob_bytes"]} bytes  '
              f'manifest_agrees={d["manifest_agrees"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
