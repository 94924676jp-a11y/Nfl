#!/usr/bin/env python3.12
"""Rebuild the research projection when, and only when, a verified input it consumes has changed.

    python3.12 nfl/integrations/rebuild.py 2026W5 --raw-dir RAW --reference-state STATE.json      # plan only
    python3.12 nfl/integrations/rebuild.py 2026W5 --raw-dir RAW --reference-state STATE.json \
        --execute --out NEW_EMPTY_DIR [--sims 2000]

PLAN compares what a build made NOW would consume against what the reference build consumed, one
component at a time, using identities both sides can state from committed records:

  depth_charts       the sha of the newest PASS depth-chart capture lawful at the as-of, against the sha of
                     the capture the reference state names (state.depth.qb_chart[*].capture_id)
  injuries           the injury captures the point-in-time selector treats as lawful now, against those lawful
                     at the newest block retrieval the reference state records. The feed is walked as a
                     series, so any new capture can change a club's block
  official_inactives the same, for captured official inactives pages
  raw_dir            the bytes of the slate's raw files (schedule and roster slices) against the hashes the
                     reference universe recorded
  dk_pool            whether a DK salary file for this slate has arrived in the inbox since a reference
                     that was built on the research universe

A content-unchanged recapture is NOT a change: it has the same sha. A component that cannot be compared
is reported UNCOMPARABLE with the reason, never as unchanged.

EXECUTE runs universe -> state -> simulation into a NEW, EMPTY directory (it refuses a non-empty one, so
a frozen board is never overwritten) and appends the build's components to REBUILD_LEDGER.jsonl, which
becomes the reference for the next plan. It never edits a board, an entry, or anything on a platform.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'rebuild-1'
MANIFEST = _REPO / 'nfl' / 'vintage_manifest.jsonl'
LEDGER = _REPO / 'nfl' / 'integrations' / 'REBUILD_LEDGER.jsonl'


def _cut(as_of: str) -> str:
    """'2026-10-09T17:03:33Z' -> '20261009T170333Z', the capture-id order the state builder uses."""
    return as_of.replace('-', '').replace(':', '')[:15] + 'Z'


def manifest_rows(path=None):
    out = []
    for ln in open(path or MANIFEST):
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


def _pass(rows, source, cut, repo=_REPO):
    """[(capture_id, sha256, blob)] for PASS rows of `source` lawful at `cut` whose blob exists."""
    got = []
    for r in rows:
        if r.get('source') != source or r.get('state') != 'PASS':
            continue
        v = r.get('value') or {}
        cid, b, sha = str(r.get('capture_id') or ''), v.get('blob'), v.get('sha256')
        if cid <= cut and b and sha and (repo / b).exists():
            got.append((cid, sha, b))
    return sorted(got)


def _injury_blobs(as_of):
    """Blob names of the injury captures the point-in-time selector treats as lawful at `as_of`."""
    from nfl.production.nonqb import vintage_selector as VS
    t = as_of if isinstance(as_of, dt.datetime) else dt.datetime.fromisoformat(str(as_of).replace('Z', '+00:00'))
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return sorted({p.name for _, p in VS.lawful_paths('injuries', as_of=t)})


def current_components(slate_id, as_of, raw_dir, rows, inbox_rows, repo=_REPO):
    cut = _cut(as_of)
    dc = _pass(rows, 'depth_charts', cut, repo)
    comp = {
        'depth_charts': {'capture_id': dc[-1][0], 'sha256': dc[-1][1]} if dc else None,
        'injuries': _injury_blobs(as_of),
        'official_inactives': sorted({s for _, s, _ in _pass(rows, 'official_inactives', cut, repo)}),
        'raw_dir': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(pathlib.Path(raw_dir).glob('*')) if p.is_file()} if raw_dir else None,
        'dk_pool': dk_pool_for_slate(slate_id, inbox_rows),
    }
    return comp


def dk_pool_for_slate(slate_id, inbox_rows):
    """The newest ingested CLASSIC DK salary file whose kickoffs include the slate's kickoff, or None."""
    from nfl.dfs.salaries import early_only as EO
    kick = EO.SLATES.get(slate_id, {}).get('kickoff')
    best = None
    for r in inbox_rows:
        s = r.get('summary') or {}
        if (r.get('kind') == 'DK_SALARIES' and r.get('state') == 'PASS' and s.get('game_type') == 'CLASSIC'
                and kick in (s.get('kickoffs') or [])):
            if best is None or r['ingested_at'] > best['ingested_at']:
                best = r
    return {'sha256': best['sha256'], 'blob': best['blob'], 'original_name': best['original_name']} if best else None


def reference_components(state_path, rows, repo=_REPO):
    """What the reference build consumed, read from its STATE.json and its universe record."""
    sp = pathlib.Path(state_path)
    st = json.loads(sp.read_text())
    ref_cut = _cut(st['as_of'])
    sha_of = {(r.get('source'), str(r.get('capture_id'))): (r.get('value') or {}).get('sha256')
              for r in rows if r.get('state') == 'PASS'}
    used = {v.get('capture_id') for v in ((st.get('depth') or {}).get('qb_chart') or {}).values()}
    used.discard(None)
    if len(used) == 1:
        cid = used.pop()
        depth = {'capture_id': cid, 'sha256': sha_of.get(('depth_charts', cid))}
    else:
        depth = {'UNCOMPARABLE': f'reference names {len(used)} depth capture ids'}
    # The injury blocks the reference ACTUALLY consumed: its state records the retrieval instant of each club's
    # newest block. Reconstructing "lawful at its as-of" from today's manifest would wrongly credit it with
    # captures synced in after it was built.
    got = [t for t in ((st.get('injury_report') or {}).get('retrieved_at') or []) if t]
    if got:
        inj_cut, inj_basis = max(got), 'newest block retrieval recorded in the reference state'
    else:
        inj_cut, inj_basis = st['as_of'], 'RECONSTRUCTED: lawful at the reference as-of in today\'s manifest'
    uni = None
    # The build's OWN universe record first: a parent directory can hold an older build's record (found
    # 2026-10-10, when the planner compared the roster rebuild against Friday's universe and reported a false change).
    for cand in (sp.parent / f"RESEARCH_UNIVERSE_{st['slate_id']}.json",
                 sp.parent.parent / f"RESEARCH_UNIVERSE_{st['slate_id']}.json",
                 sp.parent.parent.parent / f"RESEARCH_UNIVERSE_{st['slate_id']}.json"):
        if cand.exists():
            uni = json.loads(cand.read_text()).get('evidence', {}).get('sources')
            break
    return {
        'as_of': st['as_of'], 'export': st.get('export'), 'export_sha256': st.get('export_sha256'),
        'depth_charts': depth,
        'injuries': _injury_blobs(inj_cut),
        'injuries_basis': inj_basis,
        'official_inactives': sorted({s for _, s, _ in _pass(rows, 'official_inactives', ref_cut, repo)}),
        'raw_dir_sources': uni,
    }


def compare(ref, cur):
    changes, same, uncomparable = [], [], []
    rd, cd = ref.get('depth_charts') or {}, cur.get('depth_charts') or {}
    if 'UNCOMPARABLE' in rd or not rd.get('sha256'):
        uncomparable.append({'component': 'depth_charts', 'why': rd.get('UNCOMPARABLE') or
                             'the reference depth capture has no sha in the manifest'})
    elif not cd:
        uncomparable.append({'component': 'depth_charts', 'why': 'no lawful depth capture now'})
    elif rd['sha256'] != cd['sha256']:
        changes.append({'component': 'depth_charts', 'reference': rd, 'current': cd})
    else:
        same.append('depth_charts')
    for k in ('injuries', 'official_inactives'):
        new = sorted(set(cur[k]) - set(ref[k]))
        if new:
            changes.append({'component': k, 'new_since_reference': [x[:40] for x in new]})
        else:
            same.append(k)
    src = ref.get('raw_dir_sources')
    if cur.get('raw_dir') is None:
        uncomparable.append({'component': 'raw_dir', 'why': 'no raw dir given'})
    elif not src:
        uncomparable.append({'component': 'raw_dir', 'why': 'the reference universe record was not found'})
    else:
        have = set(cur['raw_dir'].values())
        moved = {k: v['sha256'][:16] for k, v in src.items() if v.get('sha256') not in have}
        (changes.append({'component': 'raw_dir', 'reference_files_no_longer_present': moved})
         if moved else same.append('raw_dir'))
    if cur.get('dk_pool') and ref.get('export') == 'RESEARCH_UNIVERSE':
        changes.append({'component': 'dk_pool', 'current': cur['dk_pool'],
                        'why': 'a DK salary export for this slate has arrived; the reference used the research '
                               'universe'})
    else:
        same.append('dk_pool')
    return changes, same, uncomparable


def latest_ledger_build(slate_id, ledger=None):
    p = pathlib.Path(ledger or LEDGER)
    if not p.exists():
        return None
    rows = [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]
    rows = [r for r in rows if r.get('slate_id') == slate_id and r.get('state') == 'PASS']
    return rows[-1] if rows else None


def _packet_sha(path):
    import hashlib
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest() if path else None


def plan(slate_id, *, as_of, raw_dir, reference_state, rows=None, inbox_rows=None, repo=_REPO,
         evidence_packet=None) -> Outcome:
    rows = rows if rows is not None else manifest_rows()
    if inbox_rows is None:
        from nfl.integrations import inbox as IB
        inbox_rows = IB.ledger_rows()
    if not rows:
        return Outcome.blocked('REBUILD_NO_MANIFEST', 'the vintage manifest is empty', cause=Cause.EMPTY_INPUT)
    ref = reference_components(reference_state, rows, repo)
    cur = current_components(slate_id, as_of, raw_dir, rows, inbox_rows, repo)
    changes, same, unc = compare(ref, cur)
    ref_pk = (json.loads(pathlib.Path(reference_state).read_text()).get('official_inactives') or {}).get('packet_sha256')
    cur_pk = _packet_sha(evidence_packet)
    if ref_pk != cur_pk:
        changes.append({'component': 'evidence_packet', 'reference': ref_pk, 'current': cur_pk})
    else:
        same.append('evidence_packet')
    ev = dict(spec_version=SPEC_VERSION, as_of=as_of, reference_state=str(reference_state),
              reference=ref, current=cur, unchanged=same, uncomparable=unc, changes=changes)
    if changes:
        return Outcome.ok('REBUILD_REQUIRED', value=changes,
                          detail=f"{len(changes)} consumed input(s) changed: {[c['component'] for c in changes]}",
                          **ev)
    if unc:
        return Outcome.ok('NO_VERIFIED_CHANGE_SOME_UNCOMPARABLE', value=unc,
                          detail=f"no change in {same}; uncomparable: {[u['component'] for u in unc]}", **ev)
    return Outcome.ok('NO_CHANGE', value=same, detail=f'every consumed input matches the reference: {same}', **ev)


def execute(slate_id, *, as_of, raw_dir, out, n_sims=2000, inbox_rows=None, ledger=None,
            evidence_packet=None) -> Outcome:
    out = pathlib.Path(out).resolve()          # the engine prints paths relative to the repository root
    t = dt.datetime.fromisoformat(str(as_of).replace('Z', '+00:00'))
    if t > dt.datetime.now(dt.timezone.utc):
        return Outcome.fail('REBUILD_AS_OF_IN_FUTURE', f'as-of {as_of} is later than the build clock; a build may not '
                                                       f'claim information it could not yet have')
    if out.exists() and any(out.iterdir()):
        return Outcome.fail('REBUILD_OUT_NOT_EMPTY', f'{out} is not empty; a rebuild never overwrites a build')
    out.mkdir(parents=True, exist_ok=True)
    from nfl.integrations import inbox as IB
    from nfl.dfs.salaries import early_only as EO
    from nfl.tools import research_universe as RU, classic_slate_state as CS, classic_slate_run as CR
    from nfl.tools import role_state as RS, proj_v1 as PV
    inbox_rows = inbox_rows if inbox_rows is not None else IB.ledger_rows()
    pool = dk_pool_for_slate(slate_id, inbox_rows)
    universe = None
    if pool:
        # Process-local: the slate's pool is the owner's DK file for this run only. The registry is not edited.
        EO.SLATES[slate_id] = dict(EO.SLATES[slate_id], pool_blob=_REPO / pool['blob'], pool_sha=pool['sha256'])
    else:
        universe = RU.build(slate_id, raw_dir)
        if universe.state.value != 'PASS':
            return universe
        (out / f'RESEARCH_UNIVERSE_{slate_id}.json').write_text(json.dumps(
            {'evidence': universe.evidence, 'rows': universe.value}, indent=1, default=str) + '\n')
    pk = None
    if evidence_packet:
        from nfl.tools import sunday_evidence as SE
        lo = SE.load(evidence_packet)
        if lo.state.value != 'PASS':
            return lo
        pk = lo.value
    st = (CS.build(slate_id, as_of=as_of, research_universe=universe, evidence_packet=pk) if universe is not None
          else CS.build(slate_id, as_of=as_of, evidence_packet=pk))
    if st.state.value != 'PASS':
        (out / 'STATE_REFUSAL.json').write_text(json.dumps({'code': st.code, 'detail': st.detail,
                                                            'evidence': st.evidence}, indent=1, default=str))
        return st
    (out / 'STATE.json').write_text(json.dumps(st.value, indent=1, default=str) + '\n')
    CR.paths = lambda s: {'state': out / 'STATE.json', 'proj': out / 'PROJ.json', 'draws': out / 'DRAWS.json',
                          'worlds': out / 'WORLDS.npz'}
    RS.OUT = PV.ROLE = out / 'ROLE_STATE.json'
    o = CR.run(slate_id, n_sims=n_sims)
    (out / 'RUN_OUTCOME.json').write_text(json.dumps({'state': o.state.value, 'code': o.code, 'detail': o.detail,
                                                      'evidence': o.evidence}, indent=1, default=str))
    rows = manifest_rows()
    comp = current_components(slate_id, as_of, raw_dir, rows, inbox_rows)
    try:
        out_rel = str(out.relative_to(_REPO))
    except ValueError:
        out_rel = str(out)
    rec = {'spec_version': SPEC_VERSION, 'slate_id': slate_id, 'as_of': as_of, 'state': o.state.value,
           'code': o.code, 'out': out_rel, 'n_sims': n_sims, 'pool': 'DK_SALARIES' if pool else 'RESEARCH_UNIVERSE',
           'components': dict(comp, evidence_packet=({'path': str(evidence_packet), 'sha256': pk['_sha256']}
                                                      if pk else None)),
           'built_at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    lp = pathlib.Path(ledger or LEDGER)
    with open(lp, 'a') as fh:
        fh.write(json.dumps(rec, sort_keys=True, default=str) + '\n')
    return o


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--raw-dir', required=True)
    ap.add_argument('--reference-state', required=True)
    ap.add_argument('--as-of', default=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    ap.add_argument('--execute', action='store_true')
    ap.add_argument('--out')
    ap.add_argument('--sims', type=int, default=2000)
    ap.add_argument('--json')
    ap.add_argument('--evidence-packet', help='a Sunday evidence packet (nfl/tools/sunday_evidence.py)')
    a = ap.parse_args(argv)
    p = plan(a.slate_id, as_of=a.as_of, raw_dir=a.raw_dir, reference_state=a.reference_state,
             evidence_packet=a.evidence_packet)
    print(f'{p.state.value}[{p.code}] {p.detail}')
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps({'code': p.code, 'detail': p.detail, 'evidence': p.evidence},
                                                   indent=1, default=str) + '\n')
    if not a.execute:
        return 0
    if p.code == 'NO_CHANGE':
        print('NOT_EXECUTED: nothing consumed has changed')
        return 0
    if not a.out:
        print('REFUSED: --execute needs --out NEW_EMPTY_DIR')
        return 2
    o = execute(a.slate_id, as_of=a.as_of, raw_dir=a.raw_dir, out=a.out, n_sims=a.sims,
                evidence_packet=a.evidence_packet)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 2


if __name__ == '__main__':
    raise SystemExit(main())
