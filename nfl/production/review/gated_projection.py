"""The only sanctioned way to load a projection set for publication or DFS.

WHY A CHOKEPOINT AND NOT A POLITE REMINDER

A gate that consumers may call is not a gate. Before this module every
selector opened `player_draws.npz` with `np.load` directly, which means the
review could BLOCK a slate and a lineup builder five lines later would never
know. So the arrays are no longer obtainable except through a call that has
already read the verdict.

`nfl/tests/test_review_enforcement.py` greps the tree for a direct load of a
draw artifact outside this module and FAILS on one. That is the enforcement:
not that consumers are asked to call the gate, but that the alternative route
is a test failure.

THREE REFUSALS, EACH BY NAME

    PLAYER_REVIEW_NOT_RUN     no review artifact for this slate
    PLAYER_REVIEW_STALE       the review audited a different draw artifact
    OPTIMIZATION_REFUSED_BY_PLAYER_REVIEW   the verdict was BLOCKED

None of them returns an empty pool. An empty pool read as success is the
defect class this project pays for most, and a refused load must look nothing
like a load that found nobody.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from typing import Any, Dict, Optional

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.review import gate as GATE                     # noqa: E402
from sportsplatform.governance.outcome import Cause, Outcome       # noqa: E402

SPEC_VERSION = 'gated-projection-load-1'

REVIEW_REPORT = 'slate_review_report.json'
GATE_RECORD = 'review_gate.json'


def _digest(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


#: A run that refused at any governing stage is not a forecast. These are the
#: statuses `run_status.json` can carry that mean "do not publish this".
REFUSED_RUN_STATUSES = ('REFUSED', 'BLOCKED', 'FAILED')

RUN_REFUSED = 'UPSTREAM_RUN_REFUSED'


def run_status(draws_dir) -> Outcome:
    """What the run itself said about whether it succeeded.

    A missing `run_status.json` is BLOCKED, not assumed fine: a draw artifact
    with no record of how its run ended is indistinguishable from one whose
    run refused.
    """
    p = pathlib.Path(draws_dir) / 'run_status.json'
    if not p.exists():
        return Outcome.blocked(
            'RUN_STATUS_ABSENT',
            f'{p} does not exist, so there is no record of whether this run '
            f'succeeded. An artifact without one is not a passing artifact.',
            cause=Cause.DATA)
    j = json.loads(p.read_text())
    st = str(j.get('status') or '').upper()
    first = j.get('first_failure') or {}
    if st in REFUSED_RUN_STATUSES:
        return Outcome.fail(
            RUN_REFUSED,
            f'the run ended {st} at stage {first.get("stage")!r} with '
            f'{first.get("code")!r}. A refused run is not a usable forecast '
            f'artifact and no downstream consumer may treat it as one.',
            value={'status': st, 'run_id': j.get('run_id'),
                   'stage': first.get('stage'), 'code': first.get('code'),
                   'detail': str(first.get('detail'))[:400],
                   'n_refusals': j.get('n_refusals')})
    return Outcome.ok('RUN_STATUS_OK', {'status': st, 'run_id': j.get('run_id')},
                      detail=f'run status {st}')


def load(draws_dir, review_dir, *, optimizer_pool_ids=None,
         allow_warnings: bool = True,
         resolved_conflict_codes=None,
         inspect_refused_non_publishable: bool = False) -> Outcome:
    """Draw arrays and layer index for a slate, or a named refusal.

    `review_dir` is the slate's review directory. The gate is re-evaluated
    here from the stored report rather than trusting the stored verdict: a
    verdict written yesterday against a projection replaced this morning is
    exactly the staleness this function exists to catch, and re-deriving it is
    cheap.
    """
    import numpy as np

    d = pathlib.Path(draws_dir)
    npz_p, man_p = d / 'player_draws.npz', d / 'player_draws_manifest.json'
    for p in (npz_p, man_p):
        if not p.exists():
            return Outcome.blocked(
                'DRAW_ARTIFACT_ABSENT',
                f'{p} does not exist. An absent artifact is not an empty '
                f'projection.', cause=Cause.DATA)

    consumed = _digest(npz_p)

    # REFUSAL PROPAGATES. The review gate and the run's own status are
    # INDEPENDENT reasons to refuse, and a run can fail its own sealing while
    # its review would have passed. Both are checked; neither substitutes.
    rs = run_status(d)
    if rs.state.name != 'PASS':
        if not inspect_refused_non_publishable:
            return Outcome.fail(
                RUN_REFUSED if rs.code == RUN_REFUSED else rs.code,
                rs.detail,
                value={**(rs.value or rs.evidence.get('value') or {}),
                       'verdict': 'BLOCKED',
                       'publishable': False,
                       'inspection_hint': 'a measurement or debugging path '
                                          'may pass '
                                          'inspect_refused_non_publishable='
                                          'True to READ this artifact; the '
                                          'result is marked non-publishable '
                                          'and carries no verdict'})
        # DEBUGGING PATH. Explicitly asked for, explicitly marked. A refused
        # run must be inspectable -- otherwise a blocked slate cannot be
        # diagnosed -- but what comes back may not be published.
        man = json.loads(man_p.read_text())
        arrays = {}
        with np.load(npz_p) as z:
            for k in z.files:
                arrays[k] = np.asarray(z[k])
                if '__' in k:
                    arrays[k.replace('__', '/', 1)] = arrays[k]
        return Outcome.ok(
            'REFUSED_ARTIFACT_OPENED_FOR_INSPECTION',
            {'arrays': arrays, 'manifest': man,
             'layers': man.get('layers', {}),
             'publishable': False, 'verdict': None,
             'run_status': rs.value or rs.evidence.get('value'),
             'draw_digest': consumed, 'spec_version': SPEC_VERSION},
            detail=f'NON-PUBLISHABLE inspection of a refused run: {rs.code}')

    rd = pathlib.Path(review_dir)
    rp = rd / REVIEW_REPORT
    if not rp.exists():
        return Outcome.blocked(
            GATE.PLAYER_REVIEW_NOT_RUN,
            f'no player review at {rp}. Every projection set reaching '
            f'publication or an optimizer must have been reviewed first, and '
            f'this one has not been.', cause=Cause.GOVERNANCE,
            value={'verdict': GATE.BLOCKED})
    report = json.loads(rp.read_text())
    # The dossiers are needed for materiality, and they are on disk beside
    # the report. Reading them back rather than accepting them as an argument
    # keeps the verdict a property of the saved artifact.
    from nfl.production.review import dossier as DOS
    from nfl.production.review import evidence as EV
    dossiers = []
    pdir = rd / 'player_dossiers'
    for f in sorted(pdir.glob('*.json')) if pdir.exists() else ():
        j = json.loads(f.read_text())
        dd = DOS.PlayerPregameDossier(
            gsis_id=j.get('gsis_id'), display_name=j.get('display_name'),
            team=j.get('team'), opponent=j.get('opponent'),
            game_id=j.get('game_id'), season=j.get('season'),
            week=j.get('week'), information_cut=j.get('information_cut'),
            support_state=j.get('support_state'),
            uncertainty_state=j.get('uncertainty_state',
                                    EV.EVIDENCE_SUFFICIENT),
            # The canonical facts the gate weighs, read back off the saved
            # artifact. Without them the verdict would depend on who is
            # holding objects in memory, which is the opposite of what
            # re-deriving from disk is for.
            canonical=DOS.CanonicalFacts.from_dict(j.get('canonical')),
            # The canonical grades behind each axis, needed by the
            # provenance integrity producer. Serialised since slice 2.
            evidence_provenance=j.get('evidence_provenance') or {},
            state_identity=j.get('state_identity') or {})
        for name, ax in (j.get('axes') or {}).items():
            dd.axes[name] = EV.Axis(name=name, value=ax.get('value'),
                                    grade=ax.get('grade', EV.UNAVAILABLE),
                                    note=ax.get('note'))
        for comp, c in (j.get('projection') or {}).items():
            dd.projection[comp] = EV.ProjectionComponent(
                component=comp, value=c.get('value'),
                grade=c.get('grade', EV.PRIOR))
        dossiers.append(dd)
    if not dossiers:
        return Outcome.blocked(
            GATE.PLAYER_REVIEW_NOT_RUN,
            f'the review at {rd} carries no player dossiers, so no verdict '
            f'about these projections can be re-derived. A report without '
            f'dossiers is not a review.', cause=Cause.DATA,
            value={'verdict': GATE.BLOCKED})

    # INTEGRITY, PRODUCED BY THE SUBSYSTEMS THAT OWN THE INVARIANTS.
    #
    # This is the production path an optimizer takes, so this is where the
    # producers must actually run. A code in a registry is not coverage and a
    # unit test calling a producer directly is not coverage either: the
    # governed chain has to invoke it, and it does, here.
    import numpy as _np
    from nfl.production.integrity import contract as IC
    from nfl.production.state import identity_integrity as II
    from nfl.production import simulation_integrity as SI
    from nfl.production.review import provenance_integrity as PI

    man = json.loads(man_p.read_text())
    _arrays = {}
    with _np.load(npz_p) as _z:
        for _k in _z.files:
            _arrays[_k] = _np.asarray(_z[_k])
    _arts = {'player_draws.npz': consumed,
             'player_draws_manifest.json': _digest(man_p)}
    _cut = report.get('information_cut')
    _slate = report.get('slate_key')
    integrity = IC.IntegrityReport.compose([
        II.duplicate_player_identity(
            dossiers, slate_key=_slate, information_cut=_cut,
            source_artifacts=_arts, what='dossier'),
        SI.missing_row_ids(man, slate_key=_slate, information_cut=_cut,
                           source_artifacts=_arts),
        SI.simulation_row_mismatch(man, _arrays, slate_key=_slate,
                                   information_cut=_cut,
                                   source_artifacts=_arts),
        PI.unavailable_claimed_as_measured(
            dossiers, slate_key=_slate, information_cut=_cut,
            source_artifacts=_arts),
    ], slate_key=_slate, information_cut=_cut)

    g = GATE.evaluate(report, dossiers=dossiers, projection_digest=consumed,
                      integrity_report=integrity,
                      require_integrity_coverage=True,
                      optimizer_pool_ids=optimizer_pool_ids,
                      resolved_conflict_codes=resolved_conflict_codes)
    # A REFUSAL TO ISSUE A VERDICT IS NOT A VERDICT. `PLAYER_REVIEW_STALE` and
    # `PLAYER_REVIEW_NOT_RUN` mean the review cannot speak about these
    # projections at all; `BLOCKED` means it looked and said no. Passing the
    # first two through `require_pass` turned both into
    # OPTIMIZATION_REFUSED_BY_PLAYER_REVIEW, which reads as "the review
    # blocked it" and sends a reader hunting for a conflict that does not
    # exist. They are returned by their own name instead.
    if g.code in (GATE.PLAYER_REVIEW_STALE, GATE.PLAYER_REVIEW_NOT_RUN):
        return g
    permitted = GATE.require_pass(g, allow_warnings=allow_warnings)
    if permitted.state.name != 'PASS':
        return Outcome.fail(
            permitted.code, permitted.detail,
            value={**(permitted.value or permitted.evidence.get('value') or {}),
                   'gate_code': g.code, 'gate_detail': g.detail,
                   # Carried on the REFUSAL too: a blocked slate is exactly
                   # when a reader needs to see which invariant fired.
                   'integrity': GATE.payload(g).get('integrity'),
                   'blocking_conflicts': [
                       r for r in GATE.payload(g).get('conflicts', [])
                       if r.get('disposition') == 'BLOCKING'],
                   'draws_dir': str(d), 'review_dir': str(rd)})

    man = json.loads(man_p.read_text())
    arrays: Dict[str, Any] = {}
    with np.load(npz_p) as z:
        for k in z.files:
            arrays[k] = np.asarray(z[k])
            if '__' in k:
                arrays[k.replace('__', '/', 1)] = arrays[k]
    gv = g.value or {}
    return Outcome.ok(
        'GATED_PROJECTION_LOADED',
        {'arrays': arrays, 'manifest': man, 'layers': man.get('layers', {}),
         'verdict': gv.get('verdict'),
         'integrity': gv.get('integrity'),
         'warning_count': gv.get('warning_count'),
         'warning_players': gv.get('warning_players'),
         'draw_digest': consumed,
         'run_id': man.get('run_id'), 'game_id': man.get('game_id'),
         'spec_version': SPEC_VERSION},
        detail=f'{man.get("n_matrices")} matrices at verdict '
               f'{gv.get("verdict")} '
               f'({gv.get("warning_count")} warning(s))')


def row_index(layers: Dict[str, Any], layer: str) -> Dict[str, int]:
    """{gsis_id: row} for one layer, refusing a layer with no row_ids.

    A missing row axis used to surface as an empty dict and then as a player
    silently absent from every lookup. It is a named absence here instead.
    """
    lay = layers.get(layer)
    if not lay or not lay.get('row_ids'):
        raise KeyError(
            f'{GATE.C_MISSING_ROW_IDS}: layer {layer!r} carries no row_ids, '
            f'so no player can be located in it. An empty index would make '
            f'every player silently missing.')
    return {p: i for i, p in enumerate(lay['row_ids'])}
