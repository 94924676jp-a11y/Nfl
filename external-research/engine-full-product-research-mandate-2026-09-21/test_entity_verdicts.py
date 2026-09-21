"""Unrelated entities stay usable; shared failures reach every affected consumer.

The two halves are opposite failure modes and a test suite that only checks
one of them will pass a system that has the other. Q-1 is closed only if both
hold at once.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import entity_verdicts as evd                                    # noqa: E402
import verdict_engine as ve                                      # noqa: E402

GATES = ve.load_gates()
SCOPES = ve.load_scopes()
LEGS = ["P1.receiving_yards", "P1.anytime_td"]

PASSED = FAILED = 0


def ok(cond, what):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"  ok     {what}")
    else:
        FAILED += 1
        print(f"  FAIL   {what}")


def all_pass():
    g = {gid: "PASS" for gid in GATES}
    g["G-XX-2"] = "PASS_FAVORABLE"
    g["G-XXIX-2"] = "PASS_FAVORABLE"
    return g


# A two-game slate: four players, two per game.
ENTS = [
    evd.Entity(evd.PLAYER, "p1", game_id="game1", player_id="p1",
               salary_name="A. One"),
    evd.Entity(evd.PLAYER, "p2", game_id="game1", player_id="p2",
               salary_name="B. Two"),
    evd.Entity(evd.PLAYER, "p3", game_id="game2", player_id="p3",
               salary_name="C. Three"),
    evd.Entity(evd.PLAYER, "p4", game_id="game2", player_id="p4",
               salary_name="D. Four"),
]
ALL_IDS = {e.entity_id for e in ENTS}


def run(codes=(), gr=None, portfolio=None, **kw):
    kw.setdefault("sgp_legs", LEGS)
    return evd.evaluate_entities(gr if gr is not None else all_pass(),
                                 list(codes), ENTS, portfolio=portfolio, **kw)


def test_a_game_blocker_spares_the_other_game():
    out = run(["WEATHER_PROXY:game1"])
    f1 = out["F1"]
    ok(f1.rollup == evd.PER_ENTITY, f"F1 rolls up per entity: {f1.rollup}")
    ok(set(f1.usable_entities) == {"p3", "p4"},
       f"the other game's players remain usable: {f1.usable_entities}")
    ok({b.entity_id for b in f1.blocked_entities} == {"p1", "p2"},
       f"and only the named game's are withheld: "
       f"{[b.entity_id for b in f1.blocked_entities]}")
    ok(f1.verdict != "RESEARCH_ONLY" or f1.usable_entities,
       "the scope is not written off wholesale for one game")
    ok(all("WEATHER_PROXY:game1" in b.codes for b in f1.blocked_entities),
       "each withheld entity carries the code that withheld it")

    # And it reaches downstream products for the SAME entities only.
    d1 = out["D1"]
    ok(set(d1.usable_entities) == {"p3", "p4"},
       f"DFS projections inherit the block per entity: {d1.usable_entities}")
    ok(out["F4"].usable_entities == [e.entity_id for e in ENTS]
       or set(out["F4"].usable_entities) == {"p3", "p4"},
       f"and the kicker scope, which also descends from F1, is consistent: "
       f"{out['F4'].usable_entities}")


def test_a_player_blocker_spares_every_other_player():
    out = run(["ROUTES_PROXY:p2"])
    f2 = out["F2"]
    ok(set(f2.usable_entities) == {"p1", "p3", "p4"},
       f"three of four players remain usable: {f2.usable_entities}")
    ok([b.entity_id for b in f2.blocked_entities] == ["p2"],
       f"exactly the named player is withheld: "
       f"{[b.entity_id for b in f2.blocked_entities]}")
    ok(set(out["F1"].usable_entities) == ALL_IDS,
       f"F1 is upstream of F2 and loses nothing: "
       f"{out['F1'].usable_entities}")
    ok(set(out["P1.receiving_yards"].usable_entities) == {"p1", "p3", "p4"},
       "and the prop family inherits the single-player block")


def test_a_salary_blocker_touches_dfs_only_and_only_that_row():
    out = run(["IDENTITY_UNRESOLVED:draftkings:C. Three"])
    ok(set(out["F3"].usable_entities) == ALL_IDS,
       f"no football entity is touched by a salary failure: "
       f"{out['F3'].usable_entities}")
    d1 = out["D1"]
    ok([b.entity_id for b in d1.blocked_entities] == ["p3"],
       f"exactly the unresolved salary row is withheld from DFS: "
       f"{[b.entity_id for b in d1.blocked_entities]}")
    ok(set(d1.usable_entities) == {"p1", "p2", "p4"},
       f"and the rest of the slate is usable: {d1.usable_entities}")


def test_a_shared_failure_reaches_every_affected_consumer():
    out = run(["CALIBRATION_INFEASIBLE:receiving_yards"])
    for sid in ("P1.receiving_yards", "D1", "D2", "D3", "D4", "D5",
                "D3.showdown", "D5.showdown"):
        v = out[sid]
        ok(v.usable_entities == [],
           f"{sid} consumes the shared weights and keeps no usable entity: "
           f"{v.usable_entities}")
        ok(len(v.blocked_entities) == len(ENTS),
           f"{sid} withholds every entity, not a subset")
    ok(set(out["P1.rushing_yards"].usable_entities) == ALL_IDS,
       "a different prop family is untouched")
    for sid in ("F1", "F2", "F3"):
        ok(set(out[sid].usable_entities) == ALL_IDS,
           f"{sid} is upstream football and is untouched: "
           f"{out[sid].usable_entities}")
    ok("CALIBRATION_INFEASIBLE" in evd.SHARED_CODES,
       "the code is classified shared explicitly, not by absence")


def test_release_unproven_spares_nothing():
    out = run(["RELEASE_UNPROVEN"])
    for sid in ("F1", "F2", "F3", "D1", "D5", "P1.receiving_yards"):
        ok(out[sid].usable_entities == [],
           f"{sid} keeps no usable entity under an unproven release")
    ok(set(out["N2"].usable_entities) == ALL_IDS,
       "the evidence viewer, which does not list the code as blocking, is "
       "unaffected")


def test_a_gate_failure_blocks_every_entity_whatever_the_rollup():
    g = all_pass()
    g["G-VII-2"] = "FAIL"
    out = run(gr=g)
    for sid in ("F2", "F3", "D1"):
        v = out[sid]
        ok(v.usable_entities == [],
           f"{sid}: a gate that did not clear is not attributable to one "
           f"entity, so none survives: {v.usable_entities}")
        ok(any("G-VII-2" in c for c in v.scope_level_reasons),
           f"{sid} records it as a scope-level reason: "
           f"{v.scope_level_reasons[:1]}")
    ok(set(out["F1"].usable_entities) == ALL_IDS,
       "and F1, upstream of the failing gate, keeps everything")


def test_slate_level_scopes_cannot_be_evaluated_per_entity():
    out = run(["ROUTES_PROXY:p2"])
    for sid in ("D3", "D4", "D3.showdown", "D4.showdown"):
        v = out[sid]
        ok(v.rollup == evd.ANY_AFFECTED,
           f"{sid} is slate-level: {v.rollup}")
        ok(v.usable_entities == [],
           f"{sid} keeps nothing when any entity is affected, because the "
           f"missing player's ownership went somewhere: {v.usable_entities}")
    ok(set(out["D1"].usable_entities) == {"p1", "p3", "p4"},
       "while the projection scope beneath them stays per entity")


def test_a_portfolio_is_judged_on_what_it_actually_uses():
    codes = ["ROUTES_PROXY:p2"]
    clean = run(codes, portfolio={"D5": ["p1", "p3"],
                                  "D5.showdown": ["p1", "p3"]})
    ok(clean["D5"].rollup == evd.PORTFOLIO,
       f"D5 rolls up as a portfolio: {clean['D5'].rollup}")
    ok(clean["D5"].portfolio_entities == ["p1", "p3"],
       "and records the entities it was judged on")

    dirty = run(codes, portfolio={"D5": ["p1", "p2"],
                                  "D5.showdown": ["p1", "p3"]})
    ok(dirty["D5"].verdict == "RESEARCH_ONLY",
       f"a portfolio that uses a blocked player is refused: "
       f"{dirty['D5'].verdict}")
    ok(any("PORTFOLIO_USES_BLOCKED_ENTITY" in c
           for c in dirty["D5"].scope_level_reasons),
       f"naming the entity: {dirty['D5'].scope_level_reasons}")

    undeclared = run(codes)
    ok(undeclared["D5"].verdict == "RESEARCH_ONLY"
       and any("PORTFOLIO_NOT_DECLARED" in c
               for c in undeclared["D5"].scope_level_reasons),
       f"and a portfolio scope with nothing declared is refused rather than "
       f"assuming the pool: {undeclared['D5'].scope_level_reasons}")

    ghost = run(codes, portfolio={"D5": ["p1", "p99"]})
    ok(any("PORTFOLIO_USES_UNKNOWN_ENTITY" in c
           for c in ghost["D5"].scope_level_reasons),
       f"a lineup referencing an entity not in the universe is refused: "
       f"{ghost['D5'].scope_level_reasons}")


def test_an_unclassified_code_is_shared_by_default():
    out = run(["SOME_NEW_CODE_NOBODY_CLASSIFIED"])
    ok("SOME_NEW_CODE" not in evd.CODE_SELECTS_ON,
       "the code selects on no axis")
    # It is not in any scope's blocking list, so it does not bite at all --
    # which is the correct behaviour for an undeclared code, and different
    # from being narrowed to one entity.
    ok(set(out["F1"].usable_entities) == ALL_IDS,
       "an undeclared code does not block, rather than blocking a subset")
    # But a DECLARED code with no axis blocks everything.
    out2 = run(["STALE_INPUT:nflverse_depth_charts"])
    ok(out2["F1"].usable_entities == [],
       "a declared code with no selecting axis spares no entity")
    ok("STALE_INPUT" in evd.SHARED_CODES,
       "and is listed as shared explicitly")


def test_rollup_rules_are_declared_not_decided_at_the_call_site():
    for sid in SCOPES:
        ok(evd.rollup_for(sid) in evd.ROLLUPS,
           f"{sid} has a declared rollup: {evd.rollup_for(sid)}")
    ok(evd.rollup_for("D5") == evd.PORTFOLIO
       and evd.rollup_for("D3") == evd.ANY_AFFECTED
       and evd.rollup_for("F3") == evd.PER_ENTITY,
       "the three rules are assigned by what the scope is")
    for r in evd.ROLLUPS:
        ok(bool(evd.ROLLUP_WHY.get(r)), f"{r} carries its justification")


def test_zz_every_check_passed():
    if FAILED:
        raise AssertionError(f"{FAILED} check(s) failed in this module")


def main():
    for t in (test_a_game_blocker_spares_the_other_game,
              test_a_player_blocker_spares_every_other_player,
              test_a_salary_blocker_touches_dfs_only_and_only_that_row,
              test_a_shared_failure_reaches_every_affected_consumer,
              test_release_unproven_spares_nothing,
              test_a_gate_failure_blocks_every_entity_whatever_the_rollup,
              test_slate_level_scopes_cannot_be_evaluated_per_entity,
              test_a_portfolio_is_judged_on_what_it_actually_uses,
              test_an_unclassified_code_is_shared_by_default,
              test_rollup_rules_are_declared_not_decided_at_the_call_site):
        print(f"== {t.__name__}")
        t()
    print(f"\nPASSED {PASSED} FAILED {FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
