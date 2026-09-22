"""The DFS eligibility boundary proves its own handoff.

Owner of `INACTIVE_PLAYER_IN_SIMULATION_OR_OPTIMIZER_POOL`. The gate does not
perform this comparison: the boundary that builds the populations is the one
that can say whether a player who will not play survived into them.

PREVENTION AND DETECTION ARE DIFFERENT MECHANISMS, and this file is the
second one. `pool.build_pool` PREVENTS a will-not-play player from entering
and records the removal in its exclusion ledger. This producer DETECTS one
who got in anyway -- by a bug, a bypass, a hand-built pool, a future caller
that forgot. A prevention nobody verifies is a prevention nobody can trust.

TWO POPULATIONS, AND THEY ARE NOT THE SAME CLAIM

  OPTIMIZER POOL    a will-not-play player here is a VIOLATION. He can be
                    put in a lineup.
  SIMULATION        a will-not-play player here is EXPECTED. `inactives
                    .apply_to_appearance` zeroes his appearance draws IN
                    PLACE and says so: "Nothing else is touched." The row
                    stays. What would be a violation is a row that was NOT
                    zeroed -- a player who will not play still carrying
                    draws -- and that is reported separately, naming the
                    population.

The blocking form of "he still owns opportunity" on the PROJECTION side is
the audit's `INACTIVE_PLAYER_OWNS_OPPORTUNITY`. This producer does not repeat
it; it checks membership and the zeroing, which the audit does not see.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any, Dict, List, Optional, Sequence

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from nfl.production.integrity import contract as IC                   # noqa: E402
from nfl.production.state import availability as AV                   # noqa: E402

SPEC_VERSION = 'nfl-dfs-eligibility-integrity-0'
PRODUCER = 'dfs.eligibility_integrity.will_not_play_in_dfs_populations'
C_INACTIVE_IN_POOL = 'INACTIVE_PLAYER_IN_SIMULATION_OR_OPTIMIZER_POOL'

POP_OPTIMIZER = 'optimizer_pool'
POP_SIMULATION = 'simulation'


def _availability_by_id(availability_by_id=None, board_rows=None
                        ) -> Dict[str, Dict[str, Any]]:
    """Canonical availability per player, from state or from a board row.

    A board row carries the dossier's SERIALISED spelling, and
    `AV.will_not_play` knows the one alias, so both sources answer the same
    question the same way.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for pid, v in (availability_by_id or {}).items():
        out[pid] = dict(v) if isinstance(v, dict) else {'availability': v}
    for r in board_rows or ():
        pid = r.get('gsis_id')
        if pid and pid not in out:
            out[pid] = {'availability': r.get('availability'),
                        'name': r.get('player'), 'team': r.get('team'),
                        'evidence_grade': r.get('evidence_grade')}
    return out


def _rows_not_zeroed(pid: str, layers: Dict[str, Any],
                     arrays: Dict[str, Any]) -> List[str]:
    """Layers where this player's draws are NOT all zero."""
    hot = []
    for layer, spec in (layers or {}).items():
        ids = list((spec or {}).get('row_ids') or ())
        if pid not in ids:
            continue
        i = ids.index(pid)
        for key, a in (arrays or {}).items():
            base = key.split('/', 1)[0] if '/' in key else key.split(
                '__', 1)[0]
            if base != layer or getattr(a, 'shape', None) is None:
                continue
            if a.shape[0] <= i:
                continue
            try:
                if float(abs(a[i]).max()) > 0.0:
                    hot.append(f'{layer}:{key}')
            except (TypeError, ValueError):       # pragma: no cover
                continue
    return sorted(set(hot))


def will_not_play_in_dfs_populations(
        *, availability_by_id: Dict[str, Any] = None,
        board_rows: Sequence[Dict[str, Any]] = None,
        pool_players: Optional[Sequence[Any]] = None,
        simulation_layers: Optional[Dict[str, Any]] = None,
        simulation_arrays: Optional[Dict[str, Any]] = None,
        slate_key: str = None, information_cut: str = None,
        source_artifacts: Dict[str, str] = None) -> IC.IntegrityReport:
    """No canonical WILL_NOT_PLAY player survives into a DFS population.

    `pool_players` is None when no DFS population exists at this point in the
    chain -- which is the case for a plain gated projection load. That is
    NOT_APPLICABLE with a reason, never a pass.
    """
    avail = _availability_by_id(availability_by_id, board_rows)
    if pool_players is None and simulation_layers is None:
        return IC.not_applicable(
            C_INACTIVE_IN_POOL, owner=IC.OWNER_ELIGIBILITY, producer=PRODUCER,
            version=SPEC_VERSION,
            why='no DFS population was supplied to this call -- neither an '
                'optimizer pool nor a simulation row axis -- so there is no '
                'membership to check. A gated projection load reaches this '
                'point before any pool exists, and reporting that as passing '
                'would claim a check nobody ran.')
    if not avail:
        return IC.not_applicable(
            C_INACTIVE_IN_POOL, owner=IC.OWNER_ELIGIBILITY, producer=PRODUCER,
            version=SPEC_VERSION,
            why='no canonical availability was supplied for any player, so '
                'membership cannot be judged against football truth. An '
                'unjudged population is not a clean one.')

    out_ids = {pid for pid, v in avail.items()
               if AV.will_not_play(v.get('availability'))}
    findings: List[IC.IntegrityFinding] = []

    pool_ids = ({getattr(p, 'gsis_id', None) for p in pool_players}
                if pool_players is not None else set())
    for pid in sorted(out_ids & pool_ids):
        v = avail[pid]
        findings.append(IC.IntegrityFinding(
            code=C_INACTIVE_IN_POOL, subject=pid, subject_kind='player',
            severity=IC.BLOCKING, owner=IC.OWNER_ELIGIBILITY,
            detail=f'canonical availability for {v.get("name") or pid} is '
                   f'{v.get("availability")}, which asserts he will not take '
                   f'the field, and he is in the OPTIMIZER POOL. He can be '
                   f'put in a lineup.',
            producer=PRODUCER, producer_version=SPEC_VERSION,
            evidence={'population': POP_OPTIMIZER,
                      'availability': v.get('availability'),
                      'canonical': AV.canonical(v.get('availability')),
                      'evidence_grade': v.get('evidence_grade'),
                      'team': v.get('team')},
            source_artifacts=dict(source_artifacts or {}),
            information_cut=information_cut))

    sim_checked = 0
    sim_members = 0
    if simulation_layers is not None:
        sim_checked = 1
        for pid in sorted(out_ids):
            in_sim = any(pid in ((spec or {}).get('row_ids') or ())
                         for spec in (simulation_layers or {}).values())
            if not in_sim:
                continue
            sim_members += 1
            hot = _rows_not_zeroed(pid, simulation_layers,
                                   simulation_arrays or {})
            if not hot:
                # EXPECTED. apply_to_appearance zeroes in place and leaves
                # the row. Membership alone is not the violation.
                continue
            v = avail[pid]
            findings.append(IC.IntegrityFinding(
                code=C_INACTIVE_IN_POOL, subject=pid, subject_kind='player',
                severity=IC.BLOCKING, owner=IC.OWNER_ELIGIBILITY,
                detail=f'canonical availability for {v.get("name") or pid} is '
                       f'{v.get("availability")}, and he still carries '
                       f'NON-ZERO draws in the SIMULATION population: '
                       f'{hot}. A player who will not play is expected to '
                       f'remain as a zeroed row; one that was never zeroed '
                       f'is a live projection for somebody who is not '
                       f'playing.',
                producer=PRODUCER, producer_version=SPEC_VERSION,
                evidence={'population': POP_SIMULATION,
                          'availability': v.get('availability'),
                          'layers_not_zeroed': hot,
                          'evidence_grade': v.get('evidence_grade'),
                          'team': v.get('team')},
                source_artifacts=dict(source_artifacts or {}),
                information_cut=information_cut))

    pops = []
    if pool_players is not None:
        pops.append(f'optimizer pool ({len(pool_ids)} player(s))')
    if sim_checked:
        pops.append(f'simulation ({sim_members} will-not-play row(s) '
                    f'present, checked for zeroing)')
    return IC.finding_report(
        C_INACTIVE_IN_POOL, owner=IC.OWNER_ELIGIBILITY, producer=PRODUCER,
        version=SPEC_VERSION, findings=findings, n_checked=len(out_ids),
        detail=f'{len(out_ids)} canonical will-not-play player(s) against '
               f'{" and ".join(pops) or "no population"}',
        source_artifacts=source_artifacts, information_cut=information_cut,
        slate_key=slate_key)
