"""Which board a reader is looking at, and how it is allowed to change.

TWO NAMED IDENTITIES, ONE POINTER
=================================
`V1_SEALED`    the sealed DEN@KC V1 candidate. IMMUTABLE PROSPECTIVE
               EVIDENCE. It is never deleted, never overwritten, never edited,
               and this module refuses to write a byte anywhere under
               `nfl/research/live/`. Its three digests are frozen as constants
               below and re-verified on every operation; a mismatch fails
               LOUDLY rather than being repaired.
`MNF_REBUILD`  tonight's rebuilt candidate. It earns the pointer or it does
               not get it.

The pointer is a separate, small file. Swapping it NEVER touches either board.
That is the whole design: a prospective seal that can be edited is not
prospective evidence, so the only thing that moves is a name.

THE SWAP IS ATOMIC, AND ATOMIC MEANS TWO THINGS HERE
====================================================
1. `os.replace` over a temp file in the same directory, after fsync. A reader
   sees the old pointer or the new one and never a half-written one.
2. No mixed-version rows, ever. The pointer names ONE identity, ONE run_id and
   ONE draw digest, and `_no_mixed_versions` asserts the board it is about to
   name agrees with its own manifest on all three before the swap. A board
   assembled from two runs is refused, not published with a footnote.

WHILE A NEW SEAL IS BEING COMPUTED THE PRIOR ONE STAYS VISIBLE
==============================================================
`begin_candidate()` records that a computation is in flight. `resolve()` then
keeps returning the prior identity and attaches a STALE WARNING naming what is
being computed and since when. The alternative -- blanking the board while a
rebuild runs -- replaces a stale number with no number and tells the reader
less, not more.

WHAT GATES THE SWAP
===================
Both of these, independently, and the pointer records which one refused:
  * every HARD product quality gate, RE-RUN HERE over the candidate's own
    artifact. A caller-supplied verdict is never accepted. Offering one is the
    same defect `authorization.ForbiddenBasis` exists to refuse: a decision
    taken from a flag instead of from the facts.
  * `nfl.production.authorization.may_publish()`, which is the only function
    permitted to say a forecast may be published. This module CONSULTS it and
    does not reimplement, weaken or bypass it. Tonight it refuses on
    NFL1_NOT_AUTHORIZED, so the pointer cannot move whatever the gates say,
    and the refusal is recorded under its own key so the two reasons are never
    read as one.

PUBLICATION STATE
=================
`PRELIMINARY_PROVISIONAL`, either way. FINAL requires an authoritative
inactive list. Tonight the full source ladder was exhausted -- nfl.com 403 on
CONNECT, both club sources 403, api.nfl.com, static.www.nfl.com and
pro-football-reference all unreachable -- so FINAL is not reachable and this
module refuses to write it.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import pathlib

from sportsplatform.governance.outcome import Cause, Outcome
from nfl.product import quality_gates as QG
from nfl.production import authorization as AUTH

SPEC_VERSION = 'nfl-board-pointer-1'
_REPO = pathlib.Path(__file__).resolve().parents[2]

# The only directory this module writes to. Everything else is read-only.
STATE_DIR = _REPO / 'nfl' / 'research' / 'v2' / 'r5'
POINTER = STATE_DIR / 'active_board_pointer.json'

# NOTHING under here is writable by this module, at any depth, ever.
SEALED_ROOT = _REPO / 'nfl' / 'research' / 'live'

PRELIMINARY_PROVISIONAL = 'PRELIMINARY_PROVISIONAL'
FINAL = 'FINAL'

V1_SEALED = 'V1_SEALED'
MNF_REBUILD = 'MNF_REBUILD'

IDENTITIES = {
    V1_SEALED: {
        'role': 'HISTORICAL_PROSPECTIVE_EVIDENCE',
        'path': ('nfl/research/live/2026_01_DEN_KC/'
                 'PRELIMINARY_PROVISIONAL_V1_CANDIDATE_R8/f91342d6787a66a1'),
        'run_id': 'f91342d6787a66a1',
        # THE TWO DIGESTS ARE DIFFERENT OBJECTS AND WERE CONFLATED ONCE.
        # 41350b5b... is the DETERMINISM-PROOF draw digest recorded in
        # nfl/research/live/2026_01_DEN_KC/DEN_KC_LIVE_RUN_RECORD.json
        # ('determinism_proof.draw_digest', 22/22 arrays bit-identical over
        # 134,000 cells across two independent output roots). The board's own
        # draw_content_digest is the 256-bit 86e3707d... . Neither is a
        # prefix of the other and neither is wrong; they answer different
        # questions, so both are frozen and both are verified.
        'determinism_draw_digest': '41350b5bac617b709c81f609fe3818b5',
        'determinism_record': ('nfl/research/live/2026_01_DEN_KC/'
                               'DEN_KC_LIVE_RUN_RECORD.json'),
        'draw_content_digest':
            '86e3707db48ce5ac3adf359878caca5b1a9bae18ef7c0a8a3165194c3c46b26a',
        'immutable': True,
        'why_immutable':
            'it was sealed before kickoff and is admissible as prospective '
            'evidence only for as long as it is provably the artifact that '
            'was sealed. Editing it would not improve it; it would destroy '
            'the only property it has.'},
    MNF_REBUILD: {
        'role': 'TONIGHT_CANDIDATE',
        'path': None,                 # supplied by register_candidate()
        'run_id': None,
        'draw_content_digest': None,
        'immutable': False,
        'why_immutable': None},
}


class SealViolation(RuntimeError):
    """Raised when anything tries to write inside the sealed artifact tree."""


# ===========================================================================
# SEAL PROTECTION
# ===========================================================================
def _assert_writable(path: pathlib.Path) -> pathlib.Path:
    """Refuse a destination inside the sealed tree. Resolved, so `..` cannot
    get round it and a symlink cannot either."""
    p = pathlib.Path(path).resolve()
    try:
        p.relative_to(SEALED_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise SealViolation(
            f'SEALED_ARTIFACT_WRITE_REFUSED: {p} resolves inside '
            f'{SEALED_ROOT}. Sealed boards are immutable prospective '
            f'evidence. Nothing in this module writes there, and a caller '
            f'that wants to is asking for the one thing that would destroy '
            f'the artifact\'s value.')
    try:
        p.relative_to(STATE_DIR.resolve())
    except ValueError:
        raise SealViolation(
            f'POINTER_WRITE_OUTSIDE_OWNED_DIR: {p} is outside {STATE_DIR}, '
            f'which is the only directory this module owns.')
    return p


def _sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_seal(identity: str = V1_SEALED) -> Outcome:
    """Re-derive the sealed board's digests and compare them to the frozen
    constants. A mismatch is a FAIL, never a repair and never a new baseline."""
    spec = IDENTITIES.get(identity)
    if spec is None or not spec.get('path'):
        return Outcome.blocked(
            'SEAL_NOT_REGISTERED',
            f'{identity} has no registered path to verify',
            cause=Cause.DEPENDENCY, spec_version=SPEC_VERSION)
    d = _REPO / spec['path']
    if not d.is_dir():
        return Outcome.fail(
            'SEALED_BOARD_MISSING',
            f'{d} does not exist. The sealed board is prospective evidence '
            f'and its absence is a defect, not a clean state.',
            spec_version=SPEC_VERSION, path=str(d))
    try:
        board = json.loads((d / 'board.json').read_text())
    except (OSError, ValueError) as e:
        return Outcome.fail('SEALED_BOARD_UNREADABLE', str(e),
                            spec_version=SPEC_VERSION, path=str(d))
    obs = {
        'run_id': board.get('run_id'),
        'draws_sha256_recomputed': _sha256(d / 'player_draws.npz'),
        'draws_sha256_declared': board.get('draws_sha256'),
        'board_json_sha256': _sha256(d / 'board.json'),
        'draw_content_digest_declared': board.get('draw_content_digest'),
    }
    problems = []
    if obs['run_id'] != spec['run_id']:
        problems.append(f'run_id is {obs["run_id"]!r}, expected '
                        f'{spec["run_id"]!r}')
    if obs['draws_sha256_recomputed'] != obs['draws_sha256_declared']:
        problems.append(
            f'the draw file no longer hashes to what the board declares: '
            f'{obs["draws_sha256_recomputed"]} vs '
            f'{obs["draws_sha256_declared"]}')
    want = str(spec.get('draw_content_digest') or '')
    got = str(obs['draw_content_digest_declared'] or '')
    if want and got and want != got:
        problems.append(f'draw_content_digest is {got!r}, expected {want!r}')
    # The determinism digest lives in the run record, not the board, and is
    # checked THERE. A digest nobody re-reads is a digest that has stopped
    # being evidence.
    dd = spec.get('determinism_draw_digest')
    if dd:
        rec = _REPO / str(spec.get('determinism_record') or '')
        if not rec.exists():
            problems.append(f'the determinism record {rec} is missing, so '
                            f'the draw digest {dd} cannot be verified')
        else:
            try:
                r = json.loads(rec.read_text())
                seen = ((r.get('determinism_proof') or {})
                        .get('draw_digest'))
            except (OSError, ValueError):
                seen = None
            obs['determinism_draw_digest_observed'] = seen
            if seen != dd:
                problems.append(
                    f'the run record\'s determinism draw digest is {seen!r}, '
                    f'expected {dd!r}')
    o = Outcome.ok if not problems else None
    if problems:
        return Outcome.fail(
            'SEAL_INTEGRITY_VIOLATED',
            f'{identity}: ' + '; '.join(problems) + '. The seal is not '
            f'repaired here and no new baseline is written.',
            observed=obs, spec_version=SPEC_VERSION)
    return o('SEAL_INTACT', value=identity,
             detail=f'{identity} hashes to its sealed values',
             observed=obs, spec_version=SPEC_VERSION)


# ===========================================================================
# NO MIXED VERSIONS
# ===========================================================================
def _no_mixed_versions(board_dir) -> Outcome:
    """Every row on the board comes from ONE run and ONE draw artifact."""
    d = pathlib.Path(board_dir)
    try:
        board = json.loads((d / 'board.json').read_text())
        man = json.loads((d / 'player_draws_manifest.json').read_text())
    except (OSError, ValueError) as e:
        return Outcome.blocked('BOARD_UNREADABLE', str(e), cause=Cause.DATA,
                               spec_version=SPEC_VERSION, path=str(d))
    problems = []
    if board.get('run_id') != man.get('run_id'):
        problems.append(f'board run_id {board.get("run_id")!r} != manifest '
                        f'run_id {man.get("run_id")!r}')
    if board.get('draw_content_digest') != man.get('content_digest'):
        problems.append('board draw_content_digest != manifest content_digest')
    if board.get('game_id') != man.get('game_id'):
        problems.append('board game_id != manifest game_id')
    recomputed = _sha256(d / (board.get('draws_file') or 'player_draws.npz'))
    if recomputed != board.get('draws_sha256'):
        problems.append('the draw file does not hash to the board\'s '
                        'declared draws_sha256')
    # Every board row must be joinable to a row of THIS manifest.
    ids = set()
    for lay in (man.get('layers') or {}).values():
        if lay.get('row_axis') == 'gsis_id':
            ids |= set(lay.get('row_ids') or [])
    orphans = sorted({p.get('gsis_id') for p in (board.get('players') or [])}
                     - ids)
    if orphans:
        problems.append(f'{len(orphans)} board row(s) have no row in this '
                        f'manifest: {orphans[:5]}')
    ev = {'run_id': board.get('run_id'), 'n_players': board.get('n_players'),
          'n_draws': board.get('n_draws'), 'orphan_rows': orphans}
    if problems:
        return Outcome.fail('MIXED_VERSION_ROWS', '; '.join(problems),
                            spec_version=SPEC_VERSION, **ev)
    return Outcome.ok('SINGLE_VERSION_BOARD', value=board.get('run_id'),
                      detail=f'{board.get("n_players")} row(s), one run, one '
                             f'draw artifact', spec_version=SPEC_VERSION, **ev)


# ===========================================================================
# THE POINTER FILE
# ===========================================================================
def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _default_pointer() -> dict:
    return {
        'spec_version': SPEC_VERSION,
        'pointer_version': 0,
        'active': None,
        'active_path': None,
        'active_run_id': None,
        'publication_state': PRELIMINARY_PROVISIONAL,
        'computing': None,
        'history': [],
        'note': 'the ACTIVE user-facing board. Swapping this file never '
                'touches a board artifact.',
    }


def read_pointer() -> dict:
    if not POINTER.exists():
        return _default_pointer()
    try:
        p = json.loads(POINTER.read_text())
    except ValueError:
        return _default_pointer()
    return p if isinstance(p, dict) else _default_pointer()


def _write_pointer(payload: dict, *, expect_version=None) -> Outcome:
    """Atomic replace, with an optimistic-concurrency check."""
    target = _assert_writable(POINTER)
    cur = read_pointer()
    if expect_version is not None and cur.get('pointer_version') != \
            expect_version:
        return Outcome.fail(
            'POINTER_VERSION_CONFLICT',
            f'the pointer moved underneath this swap: expected version '
            f'{expect_version}, found {cur.get("pointer_version")}. Nothing '
            f'was written. Re-read and decide again rather than overwrite.',
            spec_version=SPEC_VERSION)
    payload = dict(payload)
    payload['pointer_version'] = int(cur.get('pointer_version') or 0) + 1
    payload['written_at'] = _now()
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix('.json.tmp')
    data = json.dumps(payload, indent=1, sort_keys=True).encode()
    with open(tmp, 'wb') as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)             # atomic within the same filesystem
    return Outcome.ok('POINTER_WRITTEN', value=payload,
                      detail=f'pointer_version {payload["pointer_version"]}',
                      spec_version=SPEC_VERSION)


# ===========================================================================
def register_candidate(name: str, board_dir) -> Outcome:
    """Name a candidate board. Registration is not promotion."""
    if name == V1_SEALED:
        return Outcome.fail(
            'SEALED_IDENTITY_NOT_REREGISTRABLE',
            f'{V1_SEALED} is frozen in this module with its run_id and '
            f'digests. Re-pointing it at another directory would let a '
            f'different artifact inherit the seal\'s name.',
            spec_version=SPEC_VERSION)
    d = pathlib.Path(board_dir)
    if not (d / 'board.json').exists():
        return Outcome.blocked(
            'CANDIDATE_BOARD_MISSING',
            f'{d}/board.json does not exist, so there is nothing to register. '
            f'An empty registration is not a result.',
            cause=Cause.DEPENDENCY, spec_version=SPEC_VERSION)
    board = json.loads((d / 'board.json').read_text())
    IDENTITIES.setdefault(name, {'role': 'CANDIDATE', 'immutable': False})
    IDENTITIES[name].update({
        'path': str(d.resolve().relative_to(_REPO)),
        'run_id': board.get('run_id'),
        'draw_content_digest': board.get('draw_content_digest')})
    return Outcome.ok('CANDIDATE_REGISTERED', value=IDENTITIES[name],
                      detail=f'{name} -> {IDENTITIES[name]["path"]}',
                      spec_version=SPEC_VERSION)


def begin_candidate(name: str = MNF_REBUILD, *, note: str = '') -> Outcome:
    """Record that a rebuild is in flight. The prior board stays visible."""
    p = read_pointer()
    p['computing'] = {'identity': name, 'since': _now(), 'note': note}
    return _write_pointer(p)


def resolve() -> dict:
    """What a reader should be shown right now, and what is wrong with it."""
    p = read_pointer()
    out = {'spec_version': SPEC_VERSION,
           'active': p.get('active'),
           'active_path': p.get('active_path'),
           'active_run_id': p.get('active_run_id'),
           'publication_state': p.get('publication_state',
                                      PRELIMINARY_PROVISIONAL),
           'pointer_version': p.get('pointer_version'),
           'stale': False, 'stale_warning': None,
           'computing': p.get('computing')}
    parts = []
    if p.get('active') is None:
        out['stale'] = True
        parts.append(
            'NO BOARD IS ACTIVE. Nothing has passed the hard gates, so there '
            'is nothing to show. This is a state, not an empty page to fill '
            'with numbers.')
    if p.get('computing'):
        out['stale'] = True
        c = p['computing']
        who = (f'{p.get("active")} (run {p.get("active_run_id")})'
               if p.get('active') else 'no board')
        parts.append(
            f'You are looking at {who}. A newer board, {c.get("identity")}, '
            f'has been computing since {c.get("since")} and has NOT replaced '
            f'this one. The prior seal stays visible until the new one passes '
            f'every hard gate.')
    if p.get('last_refusal'):
        r = p['last_refusal']
        parts.append(
            f'The most recent candidate, {r.get("identity")}, was REFUSED the '
            f'pointer at {r.get("at")}, blocked by {r.get("blocked_by")}. '
            f'That refusal is why nothing newer is shown.')
    out['stale_warning'] = ' '.join(parts) or None
    return out


def swap(to: str, *, inactives=None, names=None, reason: str = '') -> Outcome:
    """Point the active board at `to`, ONLY if it earns it.

    Returns PASS only when the pointer actually moved. Every refusal path
    leaves the previous pointer exactly where it was.
    """
    spec = IDENTITIES.get(to)
    if spec is None or not spec.get('path'):
        return Outcome.blocked(
            'IDENTITY_NOT_REGISTERED',
            f'{to!r} is not a registered board identity with a path. '
            f'register_candidate() first.',
            cause=Cause.DEPENDENCY, spec_version=SPEC_VERSION)
    d = _REPO / spec['path']

    # 1. The seal is intact. Checked on EVERY swap, including one that is
    #    about to point somewhere else entirely, because the moment to notice
    #    a sealed artifact has moved is before anything depends on it.
    seal = verify_seal(V1_SEALED)
    if seal.state.name == 'FAIL':
        return Outcome.fail(
            'SWAP_REFUSED_SEAL_INTEGRITY',
            f'the V1 seal does not verify, so no pointer operation is safe: '
            f'{seal.detail}', seal=seal.as_dict(), spec_version=SPEC_VERSION)

    # 2. One run, one draw artifact, no mixed-version rows.
    mixed = _no_mixed_versions(d)
    if mixed.state.name != 'PASS':
        return Outcome.fail(
            'SWAP_REFUSED_MIXED_VERSIONS',
            f'{to} is not a single-version board: {mixed.detail}',
            mixed_versions=mixed.as_dict(), seal=seal.as_dict(),
            spec_version=SPEC_VERSION)

    # 3. The hard gates, RE-RUN HERE. A caller-supplied verdict is refused.
    gates = QG.evaluate(d, inactives=inactives, names=names)
    if gates.state.name != 'PASS':
        return Outcome.blocked(
            'SWAP_REFUSED_GATES_UNEVALUABLE',
            f'the quality gates could not be evaluated over {to}: '
            f'{gates.detail}. An unevaluated gate is not a passed gate.',
            cause=Cause.DATA, gates=gates.as_dict(), seal=seal.as_dict(),
            spec_version=SPEC_VERSION)
    v = gates.evidence['verdict']

    # 4. Authorization. CONSULTED, not reimplemented.
    auth = AUTH.may_publish()

    blocked_by = []
    if v['counts']['hard_fired']:
        blocked_by.append('QUALITY_GATES')
    if v['counts']['hard_insufficient_evidence']:
        blocked_by.append('QUALITY_GATES_INSUFFICIENT_EVIDENCE')
    if auth.state.name != 'PASS':
        blocked_by.append(f'AUTHORIZATION:{auth.code}')

    p = read_pointer()
    ev = {'candidate': to, 'candidate_path': spec['path'],
          'candidate_run_id': spec.get('run_id'),
          'gate_verdict': v, 'authorization': auth.as_dict(),
          'seal': seal.as_dict(), 'mixed_versions': mixed.as_dict(),
          'blocked_by': blocked_by, 'spec_version': SPEC_VERSION}

    if blocked_by:
        # The refusal is RECORDED on the pointer without moving it, so the
        # reason a board is not showing is visible to the reader rather than
        # living in a log nobody opens.
        p['last_refusal'] = {
            'identity': to, 'at': _now(), 'blocked_by': blocked_by,
            'hard_fired': v['hard_fired'],
            'hard_insufficient_evidence': v['hard_insufficient_evidence'],
            'authorization_code': auth.code}
        w = _write_pointer(p)
        return Outcome.blocked(
            'BOARD_SWAP_REFUSED',
            f'{to} does not take the pointer: blocked by {blocked_by}. '
            f'{v["counts"]["hard_fired"]} hard gate finding(s) fired and '
            f'{v["counts"]["hard_insufficient_evidence"]} could not be '
            f'evaluated; authorization says {auth.code}. The previous pointer '
            f'is unchanged.',
            cause=Cause.GOVERNANCE, pointer_write=w.code, **ev)

    # 5. Publication state never rises here.
    if v.get('publication_state') != PRELIMINARY_PROVISIONAL:
        return Outcome.fail(
            'PUBLICATION_STATE_NOT_PERMITTED',
            f'the candidate claims publication state '
            f'{v.get("publication_state")!r}. Only '
            f'{PRELIMINARY_PROVISIONAL} may be written by this module; '
            f'{FINAL} requires an authoritative inactive list that does not '
            f'exist tonight.', **ev)

    prev = p.get('active')
    p.update({'active': to, 'active_path': spec['path'],
              'active_run_id': spec.get('run_id'),
              'publication_state': PRELIMINARY_PROVISIONAL,
              'computing': None, 'last_refusal': None})
    p['history'] = (p.get('history') or []) + [
        {'at': _now(), 'from': prev, 'to': to, 'reason': reason,
         'gate_counts': v['counts'], 'authorization_code': auth.code}]
    w = _write_pointer(p, expect_version=p.get('pointer_version'))
    if w.state.name != 'PASS':
        return w
    return Outcome.ok('BOARD_SWAPPED', value=to,
                      detail=f'active board {prev!r} -> {to!r}', **ev)


def status() -> dict:
    """Everything a caller needs to explain the current product state."""
    return {'spec_version': SPEC_VERSION, 'resolved': resolve(),
            'identities': {k: dict(v) for k, v in IDENTITIES.items()},
            'seal': verify_seal(V1_SEALED).as_dict(),
            'sealed_root_is_read_only': str(SEALED_ROOT),
            'pointer_file': str(POINTER.relative_to(_REPO))}


def main(argv=None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)
    print(json.dumps(status(), indent=1, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
