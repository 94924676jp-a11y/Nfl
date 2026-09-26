"""One end-to-end Showdown research fixture, with the three checks kept apart.

THREE CHECKS, AND THEY ARE NOT THE SAME CHECK

  LEGALITY      does the lineup satisfy DraftKings Showdown rules -- six
                players, one captain, the salary cap, both teams represented,
                no duplicate player? Decidable from the salary file alone.
                A legal lineup can be a terrible lineup.

  FORECAST      is the football underneath it supported -- role established,
                participation resolved, opportunity conserved, draws sealed?
                Decidable from the chain. A supported forecast is not a
                profitable one.

  PROFITABILITY does the portfolio beat the field after entry fees? Needs
                ownership, duplication, a field model and a payout table.
                NONE of those exist here, so this check returns UNKNOWN and
                says why. It is never inferred from the other two.

Collapsing them is how a legal lineup full of unsupported players gets
presented as an edge. Each is computed separately and reported separately.

WHAT THIS FIXTURE MAY NOT DO. It invents no projection, no ownership, no
duplication estimate and no passing gate. A player the football layers cannot
place is reported as unplaceable and is not given a number so a lineup can be
built around him.
"""
from __future__ import annotations

import csv
import itertools
import json
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

SPEC_VERSION = "showdown-research-fixture-1"

# --- DraftKings Showdown rules, from the captured rules file --------------
ROSTER_SIZE = 6
N_CAPTAIN = 1
SALARY_CAP = 50000
CAPTAIN_MULTIPLIER = 1.5
MIN_TEAMS = 2

UNKNOWN = "UNKNOWN"


@dataclass
class SalaryRow:
    dk_id: str
    name: str
    position: str
    roster_position: str          # CPT or FLEX
    salary: int
    team: str
    game_info: str


@dataclass
class Candidate:
    dk_id_flex: Optional[str]
    dk_id_cpt: Optional[str]
    name: str
    team: str
    position: str
    salary_flex: Optional[int]
    salary_cpt: Optional[int]
    gsis_id: Optional[str] = None
    identity_state: str = "SALARY_IDENTITY_UNRESOLVED"
    role: Optional[str] = None
    role_support: Optional[str] = None
    participation_state: Optional[str] = None
    expected_snap_share: Optional[float] = None
    support_state: Optional[str] = None
    p_zero_opportunity: Optional[float] = None
    p_zero_source: str = UNKNOWN
    dk_points_p10: Optional[float] = None
    dk_points_median: Optional[float] = None
    dk_points_source: str = UNKNOWN
    credible_workload: bool = False
    why: List[str] = field(default_factory=list)


def read_salaries(path) -> Tuple[List[SalaryRow], Dict]:
    """The salary table embedded in a DK entry file, plus the entry block.

    The file carries both: entry rows in the first columns and the player
    table from column 11 on. Both are read; neither is guessed at.
    """
    rows = list(csv.reader(pathlib.Path(path).open(newline="")))
    sal: List[SalaryRow] = []
    entries: List[Dict] = []
    contest = {}
    for r in rows:
        if len(r) > 9 and r[0] and r[0].isdigit():
            entries.append({"entry_id": r[0], "contest": r[1],
                            "contest_id": r[2], "fee": r[3],
                            "cpt": r[4], "flex": [x for x in r[5:10] if x]})
            contest = {"name": r[1], "contest_id": r[2], "entry_fee": r[3]}
        if len(r) >= 20 and r[15] in ("CPT", "FLEX") and r[16].isdigit():
            sal.append(SalaryRow(dk_id=r[14], name=r[13].strip(),
                                 position=r[11].strip(),
                                 roster_position=r[15],
                                 salary=int(r[16]), team=r[18].strip(),
                                 game_info=r[17].strip()))
    return sal, {"contest": contest, "n_entries": len(entries),
                 "entries": entries}


def build_candidates(sal: Sequence[SalaryRow]) -> List[Candidate]:
    """One candidate per player, carrying both his CPT and FLEX prices."""
    by_name: Dict[Tuple[str, str], Candidate] = {}
    for s in sal:
        key = (s.name, s.team)
        c = by_name.get(key)
        if c is None:
            c = Candidate(None, None, s.name, s.team, s.position, None, None)
            by_name[key] = c
        if s.roster_position == "CPT":
            c.dk_id_cpt, c.salary_cpt = s.dk_id, s.salary
        else:
            c.dk_id_flex, c.salary_flex = s.dk_id, s.salary
    return sorted(by_name.values(), key=lambda c: -(c.salary_flex or 0))


def join_football(cands: Sequence[Candidate], universe_rows,
                  role_rows, part_rows) -> Dict[str, int]:
    """Exact-name join only. NO EDIT-DISTANCE MATCHING IS PERMITTED.

    A DK row that does not match a football row exactly keeps
    SALARY_IDENTITY_UNRESOLVED and is excluded from lineups. Guessing which
    player a near-miss refers to is how a lineup acquires a player nobody
    modelled.
    """
    by_name: Dict[str, dict] = {}
    for r in universe_rows:
        for k in ("display_name", "football_name"):
            n = (r.get(k) or "").strip()
            if n:
                by_name.setdefault((n, r["team"]), r)
    roles = {r["gsis_id"]: r for r in role_rows}
    parts = {r["gsis_id"]: r for r in part_rows}
    stats = {"resolved": 0, "unresolved": 0}
    for c in cands:
        u = by_name.get((c.name, c.team))
        if u is None:
            c.why.append(
                f"no football row matches {c.name!r} on {c.team} by exact "
                f"name; edit-distance matching is not permitted")
            stats["unresolved"] += 1
            continue
        c.gsis_id = u["gsis_id"]
        c.identity_state = "SALARY_IDENTITY_RESOLVED"
        c.support_state = u.get("support_state")
        stats["resolved"] += 1
        r = roles.get(c.gsis_id)
        if r:
            c.role, c.role_support = r["role"], r["role_support"]
        p = parts.get(c.gsis_id)
        if p:
            c.participation_state = p["participation_state"]
            c.expected_snap_share = p["expected_snap_share"]
    return stats


def attach_draw_risk(cands: Sequence[Candidate], manifest_path) -> Dict:
    """P(zero opportunity) and DK-point quantiles, from the sealed draws only.

    A player with no row in the draw artifact gets UNKNOWN, not zero. "The
    model emitted nothing for him" and "the model says he scores nothing" are
    different statements and only one of them is evidence.
    """
    import numpy as np
    man = pathlib.Path(manifest_path)
    m = json.loads(man.read_text())
    npz = man.parent / "player_draws.npz"
    if not npz.exists():
        return {"state": "NO_DRAW_ARTIFACT", "why": str(npz)}
    arr = np.load(npz)
    layers = m.get("layers") or {}

    def matrix(layer, metric):
        key = f"{layer}__{metric}"
        return arr[key] if key in arr.files else None

    dk = layers.get("dk_scoring") or {}
    kick = layers.get("kicking") or {}
    ev = {"state": "OK", "dk_layer_present": bool(dk),
          "metrics_used": [], "n_draws": m.get("n_draws")}

    def rows_for(layer):
        return {pid: i for i, pid in
                enumerate((layers.get(layer) or {}).get("row_ids") or [])}

    dk_rows = rows_for("dk_scoring")
    kick_rows = rows_for("kicking")
    rec_rows = rows_for("receiving")
    rush_rows = rows_for("rushing")
    qb_rows = rows_for("qb")

    dk_pts = matrix("dk_scoring", "dk_points")
    kick_pts = matrix("kicking", "dk_points")
    if dk_pts is not None:
        ev["metrics_used"].append("dk_scoring/dk_points")
    if kick_pts is not None:
        ev["metrics_used"].append("kicking/dk_points")
    tgt = matrix("receiving", "targets")
    car = matrix("rushing", "carries")
    att = matrix("qb", "attempts")

    for c in cands:
        if not c.gsis_id:
            continue
        pts = None
        if dk_pts is not None and c.gsis_id in dk_rows:
            pts = dk_pts[dk_rows[c.gsis_id]]
            c.dk_points_source = "dk_scoring/dk_points"
        elif kick_pts is not None and c.gsis_id in kick_rows:
            pts = kick_pts[kick_rows[c.gsis_id]]
            c.dk_points_source = "kicking/dk_points"
        if pts is not None:
            c.dk_points_median = float(np.median(pts))
            c.dk_points_p10 = float(np.percentile(pts, 10))

        opp = None
        if tgt is not None and c.gsis_id in rec_rows:
            opp = tgt[rec_rows[c.gsis_id]].astype(float)
        if car is not None and c.gsis_id in rush_rows:
            r = car[rush_rows[c.gsis_id]].astype(float)
            opp = r if opp is None else opp + r
        if att is not None and c.gsis_id in qb_rows:
            a = att[qb_rows[c.gsis_id]].astype(float)
            opp = a if opp is None else opp + a
        if opp is not None:
            c.p_zero_opportunity = float((opp <= 0).mean())
            c.p_zero_source = "receiving/targets + rushing/carries + qb/attempts"
    return ev


def mark_credible(cands: Sequence[Candidate]) -> None:
    """Credible workload = the football layers placed him, and said so.

    This is a GATE, not a projection. It asks whether the chain established a
    role and resolved participation. It assigns no number and orders nobody.
    """
    for c in cands:
        reasons = []
        if c.identity_state != "SALARY_IDENTITY_RESOLVED":
            reasons.append("salary identity unresolved")
        if c.role_support != "ROLE_SUPPORTED":
            reasons.append(f"role {c.role or 'absent'} ({c.role_support})")
        if c.participation_state != "PARTICIPATION_RESOLVED":
            reasons.append(f"participation {c.participation_state or 'absent'}")
        if c.dk_points_median is None:
            reasons.append("no DK-point draws emitted")
        c.credible_workload = not reasons
        if reasons:
            c.why.extend(reasons)


# --- LEGALITY, and nothing but legality ------------------------------------
def lineup_is_legal(cpt: Candidate, flex: Sequence[Candidate]) -> Tuple[bool, List[str]]:
    problems = []
    players = [cpt, *flex]
    if len(players) != ROSTER_SIZE:
        problems.append(f"roster size {len(players)} != {ROSTER_SIZE}")
    ids = [p.name for p in players]
    if len(set(ids)) != len(ids):
        problems.append("duplicate player")
    if cpt.salary_cpt is None:
        problems.append(f"{cpt.name} has no captain salary")
    if any(p.salary_flex is None for p in flex):
        problems.append("a flex player has no flex salary")
    if not problems:
        total = cpt.salary_cpt + sum(p.salary_flex for p in flex)
        if total > SALARY_CAP:
            problems.append(f"salary {total} over cap {SALARY_CAP}")
    if len({p.team for p in players}) < MIN_TEAMS:
        problems.append("only one team represented")
    return (not problems), problems


def lineup_salary(cpt: Candidate, flex: Sequence[Candidate]) -> int:
    return cpt.salary_cpt + sum(p.salary_flex for p in flex)


def build_candidate_lineups(cands: Sequence[Candidate], limit: int = 20,
                            seed_pool: int = 12) -> List[Dict]:
    """Legal lineups drawn ONLY from players with a credible workload.

    Ordering is by median simulated DK points, which is a FORECAST quantity
    and is reported as such. It is not a profitability ranking and no claim
    is made that these lineups beat a field.
    """
    pool = [c for c in cands if c.credible_workload]
    pool = sorted(pool, key=lambda c: -(c.dk_points_median or 0))[:seed_pool]
    out = []
    for cpt in pool:
        rest = [c for c in pool if c.name != cpt.name]
        for flex in itertools.combinations(rest, ROSTER_SIZE - 1):
            legal, problems = lineup_is_legal(cpt, flex)
            if not legal:
                continue
            med = (cpt.dk_points_median or 0) * CAPTAIN_MULTIPLIER + sum(
                (p.dk_points_median or 0) for p in flex)
            floor = (cpt.dk_points_p10 or 0) * CAPTAIN_MULTIPLIER + sum(
                (p.dk_points_p10 or 0) for p in flex)
            out.append({
                "captain": cpt.name, "flex": [p.name for p in flex],
                "salary": lineup_salary(cpt, flex),
                "teams": sorted({cpt.team, *(p.team for p in flex)}),
                "sum_median_dk_points": round(med, 2),
                "sum_p10_dk_points": round(floor, 2),
                "legality": "LEGAL",
                "forecast_basis": "median of sealed simulated DK points; "
                                  "captain at 1.5x",
                "profitability": UNKNOWN,
            })
    out.sort(key=lambda x: -x["sum_median_dk_points"])
    return out[:limit]
