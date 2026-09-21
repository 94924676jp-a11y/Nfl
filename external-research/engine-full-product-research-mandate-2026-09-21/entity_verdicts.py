"""Verdicts per affected game, player and product, with declared rollup rules.

QUESTION Q-1, CLOSED. Revision 3 blocked a whole scope when one entity was
affected: `WEATHER_PROXY:game1` on a thirteen-game slate lost all thirteen.
The conservative direction was the right one to take while the machinery did
not exist. This is the machinery.

THE RULE IS THE SAME ONE, APPLIED AT THE RIGHT GRAIN

A blocker names something. `WEATHER_PROXY:game1` names a game;
`ROUTES_PROXY:player1` names a player; `IDENTITY_UNRESOLVED:draftkings:J. Smith`
names a salary row. Those block the entities they name and leave the rest
usable. A blocker that names nothing, or that names a thing every consumer
shares -- an unproven release, a stale input, a weight vector that could not be
made feasible -- blocks everything in a sensitive scope, because there is no
subset of entities it spares.

So the two failure modes are opposite and this module has to avoid both: a
per-entity blocker must not take down unrelated entities, and a shared blocker
must not be narrowed into one.

ROLLUP IS DECLARED PER SCOPE, NOT DECIDED AT THE CALL SITE

Three rules, and which one applies is a property of what the scope IS:

  PER_ENTITY   the scope is usable for the entities that are usable. Player
               projections and prop families work this way: one unresolved
               player does not invalidate the other fifty.

  ANY_AFFECTED the scope is a property of the whole slate and cannot be
               evaluated per entity. Ownership, field composition and
               duplication are slate-level: a field model fit with a player
               missing is not a field model that is correct for everyone else,
               because the missing player's ownership went somewhere.

  PORTFOLIO    the scope is usable only if every entity the declared portfolio
               actually uses is usable. A portfolio is a commitment to a
               specific set of players; it is not made safer by the existence
               of other players it did not pick.

A scope-level failure -- a gate that did not clear, a shared code -- blocks
every entity whatever the rollup. Rollup decides how ENTITY-level blocks add
up, not whether scope-level ones apply.

Unaccepted specification. No gate evaluated, nothing promoted.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import verdict_engine as ve                                      # noqa: E402

SPEC_VERSION = "entity-verdicts-1"

# --- entity kinds ----------------------------------------------------------
GAME = "GAME"
PLAYER = "PLAYER"
MARKET = "MARKET"
SLATE = "SLATE"
ENTITY_KINDS = (GAME, PLAYER, MARKET, SLATE)


@dataclass(frozen=True)
class Entity:
    kind: str
    entity_id: str
    game_id: Optional[str] = None
    player_id: Optional[str] = None
    family: Optional[str] = None
    market_id: Optional[str] = None
    salary_name: Optional[str] = None

    def axis(self, name: str) -> Optional[str]:
        return getattr(self, name, None)


# --- which axis a reason code selects on -----------------------------------
#: A code listed here names ONE entity on that axis and blocks only entities
#: matching it. Everything not listed is SHARED and blocks every entity of a
#: sensitive scope -- which is the safe default, because a code nobody
#: classified must not be quietly narrowed.
CODE_SELECTS_ON: Dict[str, str] = {
    "WEATHER_PROXY": "game_id",
    "NO_OUTPUT": "game_id",
    "ROUTES_PROXY": "player_id",
    "GAMEDAY_STATUS_UNKNOWN": "player_id",
    "NO_ANALOGUE": "player_id",
    "CONFLICT_UNRESOLVED": "player_id",
    "IDENTITY_UNRESOLVED": "salary_name",
}

#: Named explicitly so the list is auditable rather than implied by absence.
SHARED_CODES = frozenset({
    "RELEASE_UNPROVEN", "STALE_INPUT", "CALIBRATION_INFEASIBLE",
    "MARKET_INTERVAL_INCLUDES_ZERO", "SGP_LEGS_NOT_DECLARED",
})

# --- rollup ----------------------------------------------------------------
PER_ENTITY = "PER_ENTITY"
ANY_AFFECTED = "ANY_AFFECTED_BLOCKS_THE_SCOPE"
PORTFOLIO = "PORTFOLIO_REQUIRES_EVERY_ENTITY_IT_USES"
ROLLUPS = (PER_ENTITY, ANY_AFFECTED, PORTFOLIO)

SCOPE_ROLLUP: Dict[str, str] = {
    "D3": ANY_AFFECTED, "D4": ANY_AFFECTED,
    "D3.showdown": ANY_AFFECTED, "D4.showdown": ANY_AFFECTED,
    "D5": PORTFOLIO, "D5.showdown": PORTFOLIO,
}
DEFAULT_ROLLUP = PER_ENTITY

ROLLUP_WHY: Dict[str, str] = {
    PER_ENTITY: ("usable for the entities that are usable; one unresolved "
                 "player does not invalidate the others"),
    ANY_AFFECTED: ("a slate-level property that cannot be evaluated per "
                   "entity: a field model fit with a player missing is not "
                   "correct for the rest, because his ownership went "
                   "somewhere"),
    PORTFOLIO: ("a commitment to a specific set of entities; it is not made "
                "safer by players it did not pick"),
}


def rollup_for(scope_id: str) -> str:
    return SCOPE_ROLLUP.get(scope_id, DEFAULT_ROLLUP)


@dataclass
class EntityBlock:
    entity_id: str
    codes: List[str] = field(default_factory=list)


@dataclass
class ScopeEntityVerdict:
    scope_id: str
    verdict: str
    rollup: str
    rollup_why: str = ""
    usable_entities: List[str] = field(default_factory=list)
    blocked_entities: List[EntityBlock] = field(default_factory=list)
    scope_level_reasons: List[str] = field(default_factory=list)
    display_codes: List[str] = field(default_factory=list)
    upstream_blockers: List[str] = field(default_factory=list)
    portfolio_entities: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def _entity_blocked_by(code: str, scope: "ve.Scope", ent: Entity
                       ) -> bool:
    """Whether one entity is blocked by one code, given the scope is sensitive."""
    prefix = ve._code_prefix(code)
    axis = CODE_SELECTS_ON.get(prefix)
    if axis is None:
        return True                       # shared: no entity is spared
    named = ve._code_entity(code)
    if named is None:
        return True                       # unqualified: bites everything
    if axis == "salary_name":
        named = named.split(":")[-1]      # platform:name -> name
    mine = ent.axis(axis)
    if mine is None:
        # The entity has no value on the axis the code selects on, so the
        # code cannot be shown to name it. Blocking would be over-reach and
        # clearing would be under-reach; the scope-level answer already
        # carries the code, so leave the entity usable and say so.
        return False
    return mine == named


def evaluate_entities(
    gate_results,
    release_codes: Iterable[str],
    entities: Sequence[Entity],
    *,
    portfolio: Optional[Dict[str, Sequence[str]]] = None,
    sgp_legs: Optional[Sequence[str]] = None,
    strict_scoping: bool = False,
    gates=None,
    scopes=None,
) -> Dict[str, ScopeEntityVerdict]:
    """Per-scope verdicts carrying which entities survive and which do not.

    UPSTREAM PROPAGATION IS ITSELF PER ENTITY, which is the whole point. A
    first version took the scope-level engine's `UPSTREAM_NOT_DEPLOYABLE`
    markers as scope-level reasons, so one blocked player upstream collapsed
    every entity downstream -- reintroducing Q-1 one layer down. A dependent
    scope now inherits the upstream's BLOCKED ENTITY SET, and inherits a
    scope-level block only when the upstream was blocked at scope level.

    `portfolio` maps a PORTFOLIO-rollup scope id to the entity ids its
    declared portfolio uses. Portfolio findings are computed whether or not
    the scope is already blocked, because "this portfolio also uses a player
    who is out" is worth knowing alongside "the field model is unusable".
    """
    gates = gates or ve.load_gates()
    scopes = scopes or ve.load_scopes()
    codes = list(release_codes)
    portfolio = portfolio or {}
    all_ids = [e.entity_id for e in entities]
    known = set(all_ids)

    base = ve.evaluate_release(gate_results, codes, sgp_legs=sgp_legs,
                               strict_scoping=strict_scoping,
                               gates=gates, scopes=scopes)

    # --- phase A: each scope on its own evidence --------------------------
    own_scope_reasons: Dict[str, List[str]] = {}
    own_blocks: Dict[str, Dict[str, List[str]]] = {}
    for sid, scope in scopes.items():
        b = base[sid]
        applicable = [c for c in codes
                      if ve._code_applies(c, scope, ve.Context(sid))]
        entity_codes = [c for c in applicable
                        if ve._code_prefix(c) in CODE_SELECTS_ON]
        own_scope_reasons[sid] = [
            c for c in b.reason_codes
            if c not in entity_codes
            and not c.startswith("UPSTREAM_NOT_DEPLOYABLE:")]
        blocks: Dict[str, List[str]] = {}
        for e in entities:
            hits = [c for c in entity_codes if _entity_blocked_by(c, scope, e)]
            if hits:
                blocks[e.entity_id] = hits
        own_blocks[sid] = blocks

    # --- phase B: inherit downward, to a fixpoint -------------------------
    scope_reasons = {sid: list(v) for sid, v in own_scope_reasons.items()}
    blocks = {sid: {k: list(v) for k, v in own_blocks[sid].items()}
              for sid in scopes}
    for _ in range(len(scopes) + 1):
        changed = False
        for sid, scope in scopes.items():
            for dep in ve.dependency_closure(sid, scopes, sgp_legs):
                if dep not in scopes:
                    continue
                # A scope-level failure upstream is a scope-level failure here.
                for r in scope_reasons[dep]:
                    marker = f"UPSTREAM_NOT_DEPLOYABLE:{dep}:{r}"
                    if marker not in scope_reasons[sid]:
                        scope_reasons[sid].append(marker)
                        changed = True
                # A slate-level upstream leaves nothing usable downstream.
                if rollup_for(dep) == ANY_AFFECTED and blocks[dep]:
                    marker = (f"UPSTREAM_SLATE_LEVEL_BLOCK:{dep}:"
                              f"{len(blocks[dep])}_entity(ies)")
                    if marker not in scope_reasons[sid]:
                        scope_reasons[sid].append(marker)
                        changed = True
                # Otherwise the blocked ENTITIES flow down, and only those.
                for eid, cs in blocks[dep].items():
                    cur = blocks[sid].setdefault(eid, [])
                    for c in cs:
                        tag = f"{c}@{dep}" if dep != sid else c
                        if c not in cur and tag not in cur:
                            cur.append(c if dep == sid else tag)
                            changed = True
        if not changed:
            break

    # --- assemble ---------------------------------------------------------
    out: Dict[str, ScopeEntityVerdict] = {}
    for sid, scope in scopes.items():
        b = base[sid]
        rl = rollup_for(sid)
        v = ScopeEntityVerdict(scope_id=sid, verdict=b.verdict, rollup=rl,
                               rollup_why=ROLLUP_WHY[rl],
                               display_codes=list(b.display_codes),
                               upstream_blockers=list(b.upstream_blockers))
        v.scope_level_reasons = list(scope_reasons[sid])
        blocked = blocks[sid]

        # Portfolio findings are computed unconditionally.
        if rl == PORTFOLIO:
            declared = portfolio.get(sid)
            v.portfolio_entities = list(declared or ())
            if declared is None:
                v.scope_level_reasons.append(f"PORTFOLIO_NOT_DECLARED:{sid}")
                v.notes.append(
                    "a portfolio scope with no declared portfolio cannot be "
                    "evaluated; assuming the whole usable pool would certify "
                    "lineups nobody named")
            else:
                used_blocked = sorted(set(declared) & set(blocked))
                unknown = sorted(set(declared) - known)
                if used_blocked:
                    v.scope_level_reasons.append(
                        "PORTFOLIO_USES_BLOCKED_ENTITY:"
                        + ",".join(used_blocked))
                    v.notes.append(ROLLUP_WHY[PORTFOLIO])
                if unknown:
                    v.scope_level_reasons.append(
                        "PORTFOLIO_USES_UNKNOWN_ENTITY:" + ",".join(unknown))

        if v.scope_level_reasons:
            v.blocked_entities = [
                EntityBlock(eid, sorted(set(blocked.get(eid, []))
                                        | set(v.scope_level_reasons)))
                for eid in all_ids]
            v.usable_entities = []
            v.verdict = ("NO_SUPPORTED_EDGE"
                         if b.verdict == "NO_SUPPORTED_EDGE"
                         else "RESEARCH_ONLY")
            v.notes.append(
                "blocked at scope level; rollup decides how ENTITY blocks "
                "add up, not whether scope-level ones apply")
            out[sid] = v
            continue

        v.blocked_entities = [EntityBlock(eid, blocked[eid])
                              for eid in all_ids if eid in blocked]
        v.usable_entities = [eid for eid in all_ids if eid not in blocked]

        if rl == PER_ENTITY:
            v.verdict = b.verdict if v.usable_entities else "RESEARCH_ONLY"
            if v.blocked_entities and v.usable_entities:
                v.notes.append(
                    f"{len(v.usable_entities)} entity(ies) remain usable; "
                    f"{len(v.blocked_entities)} are withheld by name")
        elif rl == ANY_AFFECTED:
            if v.blocked_entities:
                v.verdict = "RESEARCH_ONLY"
                v.usable_entities = []
                v.notes.append(ROLLUP_WHY[ANY_AFFECTED])
        else:
            v.verdict = b.verdict if v.usable_entities else "RESEARCH_ONLY"
        out[sid] = v

    return out


def usable_pool(verdicts: Dict[str, ScopeEntityVerdict],
                scope_id: str) -> Set[str]:
    v = verdicts.get(scope_id)
    return set(v.usable_entities) if v else set()
