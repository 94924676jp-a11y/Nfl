#!/usr/bin/env python3.12
"""Probe which NFL data sources are reachable from this execution environment.

Writes a machine-readable availability audit. This exists because CLAUDE.md's
rule 7 ("zeros and empties are errors, not results") and the V8 failure taxonomy
Class A ("absence read as success") both require that a claim of availability be
produced by something that actually ran, with the response recorded.

It records what the probe SAW. It does not interpret. A 404 here means "this
exact path 404ed", never "this dataset does not exist" -- a name variant may.

Usage:  python3.12 nfl/tools/probe_nfl_sources.py [-o OUT.json]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys

NFLVERSE_RELEASE = "https://github.com/nflverse/nflverse-data/releases/download"

# (label, url). Kept explicit rather than generated so the audit says exactly
# which paths were tried.
TARGETS: list[tuple[str, str]] = [
    ("nflverse.pbp.2024", f"{NFLVERSE_RELEASE}/pbp/play_by_play_2024.csv"),
    ("nflverse.pbp.2025", f"{NFLVERSE_RELEASE}/pbp/play_by_play_2025.csv"),
    ("nflverse.participation.2024", f"{NFLVERSE_RELEASE}/pbp_participation/pbp_participation_2024.csv"),
    ("nflverse.participation.2025", f"{NFLVERSE_RELEASE}/pbp_participation/pbp_participation_2025.csv"),
    ("nflverse.participation.2016", f"{NFLVERSE_RELEASE}/pbp_participation/pbp_participation_2016.csv"),
    ("nflverse.ftn.2021", f"{NFLVERSE_RELEASE}/ftn_charting/ftn_charting_2021.csv"),
    ("nflverse.ftn.2022", f"{NFLVERSE_RELEASE}/ftn_charting/ftn_charting_2022.csv"),
    ("nflverse.ftn.2025", f"{NFLVERSE_RELEASE}/ftn_charting/ftn_charting_2025.csv"),
    ("nflverse.snap_counts.2024", f"{NFLVERSE_RELEASE}/snap_counts/snap_counts_2024.csv"),
    ("nflverse.snap_counts.2025", f"{NFLVERSE_RELEASE}/snap_counts/snap_counts_2025.csv"),
    ("nflverse.injuries.2024", f"{NFLVERSE_RELEASE}/injuries/injuries_2024.csv"),
    ("nflverse.injuries.2025", f"{NFLVERSE_RELEASE}/injuries/injuries_2025.csv"),
    ("nflverse.depth_charts.2024", f"{NFLVERSE_RELEASE}/depth_charts/depth_charts_2024.csv"),
    ("nflverse.player_stats.2024", f"{NFLVERSE_RELEASE}/player_stats/player_stats_2024.csv"),
    ("nflverse.weekly_rosters.2024", f"{NFLVERSE_RELEASE}/weekly_rosters/roster_weekly_2024.csv"),
    ("nflverse.rosters.2024", f"{NFLVERSE_RELEASE}/rosters/roster_2024.csv"),
    ("nflverse.players", f"{NFLVERSE_RELEASE}/players/players.csv"),
    ("nflverse.pfr_advstats.pass.2024", f"{NFLVERSE_RELEASE}/pfr_advstats/advstats_week_pass_2024.csv"),
    ("nflverse.espn_qbr.week", f"{NFLVERSE_RELEASE}/espn_data/qbr_week_level.csv"),
    ("nflverse.officials", f"{NFLVERSE_RELEASE}/officials/officials.csv"),
    ("nflverse.combine", f"{NFLVERSE_RELEASE}/combine/combine.csv"),
    # Correct extension. An earlier probe of ".csv" 404ed and was briefly
    # mis-read as "this dataset does not exist"; it is gzipped, not absent.
    ("nflverse.ngs_receiving.gz", f"{NFLVERSE_RELEASE}/nextgen_stats/ngs_receiving.csv.gz"),
    ("nflverse.stats_player_week.2025", f"{NFLVERSE_RELEASE}/stats_player/stats_player_week_2025.csv"),
    ("nflverse.schedules", f"{NFLVERSE_RELEASE}/schedules/games.csv"),
    ("nflverse.contracts.gz", f"{NFLVERSE_RELEASE}/contracts/historical_contracts.csv.gz"),
    # The official perishable sources. Externally measured HTTP 200 on
    # 2026-09-06 by a networked researcher; probed here to record what THIS
    # executor gets, which is a different question.
    ("official.nfl_injuries", "https://www.nfl.com/injuries/"),
    ("official.nfl_inactives", "https://www.nfl.com/inactives/"),
    ("fallback.espn_injuries_json",
     "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"),
    # Deliberate negative controls: these establish the egress boundary itself.
    ("control.raw_githubusercontent", "https://raw.githubusercontent.com/nflverse/nflverse-data/master/README.md"),
    ("control.github_api_other_owner", "https://api.github.com/repos/nflverse/nflverse-data"),
    ("control.pro_football_reference", "https://www.pro-football-reference.com/"),
    ("control.espn_api", "https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams"),
    ("control.sleeper_api", "https://api.sleeper.app/v1/players/nfl"),
]

TIMEOUT_S = 45


def probe(url: str) -> dict:
    """One HEAD-style probe, recording the FAILURE CLASS, not just a code.

    `-w %{http_code}` reports 000 for everything that never reached an origin --
    DNS failure, TCP refusal, TLS failure and a proxy CONNECT rejection all look
    identical. That is how this repository came to record nfl.com as "measured at
    000", which reads as "the site is down" when the truth is "our proxy refused
    to connect to a site that answers 200 elsewhere". Those have different owners
    and different fixes, so `-v` output is parsed for the distinguishing line.
    """
    cmd = [
        "curl", "-sS", "-L", "-I", "-o", "/dev/null", "-v",
        "-w", "%{http_code} %{size_download} %{content_type}",
        "--max-time", str(TIMEOUT_S), url,
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S + 15)
    except subprocess.TimeoutExpired:
        return {"state": "FAIL", "code": "PROBE_TIMEOUT", "detail": f"no response in {TIMEOUT_S}s"}

    out = (r.stdout or "").strip().split(" ", 2)
    status = out[0] if out and out[0] else "000"
    err = (r.stderr or "").strip() or None
    verbose = r.stderr or ""

    if status == "000":
        # Distinguish the classes that all report 000.
        low = verbose.lower()
        if "could not resolve host" in low:
            klass, code = "DNS_RESOLUTION_FAILED", "DNS_RESOLUTION_FAILED"
        elif "connect tunnel failed" in low or "received http code 403 from proxy" in low:
            klass, code = "LOCAL_PROXY_CONNECT_REJECTED", "LOCAL_PROXY_CONNECT_403"
        elif "connection refused" in low:
            klass, code = "TCP_CONNECTION_REFUSED", "TCP_CONNECTION_REFUSED"
        elif "timed out" in low or "operation timed out" in low:
            klass, code = "CONNECTION_TIMEOUT", "CONNECTION_TIMEOUT"
        elif "ssl" in low or "tls" in low:
            klass, code = "TLS_FAILURE", "TLS_FAILURE"
        else:
            klass, code = "UNCLASSIFIED_NO_RESPONSE", "NO_RESPONSE"
        evidence = [ln.strip() for ln in verbose.splitlines()
                    if any(k in ln.lower() for k in
                           ("connect tunnel", "could not resolve", "refused",
                            "timed out", "proxy", "< http/"))][:4]
        # A proxy refusal is a statement about THIS EXECUTOR, not about the
        # source, so it is BLOCKED (cause NETWORK), never FAIL.
        state = "BLOCKED" if klass == "LOCAL_PROXY_CONNECT_REJECTED" else "FAIL"
        return {"state": state, "code": code, "http_status": status,
                "failure_class": klass, "evidence_lines": evidence,
                "says_about": ("this executor's egress policy"
                               if state == "BLOCKED" else "the connection"),
                "detail": None}
    if status.startswith("2"):
        return {"state": "PASS", "code": "REACHABLE", "http_status": status, "detail": err}
    if status == "404":
        return {"state": "FAIL", "code": "PATH_NOT_FOUND",
                "http_status": status,
                "detail": "this exact path 404ed; a name variant may still exist"}
    if status in ("403", "407"):
        return {"state": "BLOCKED", "code": "EGRESS_DENIED", "http_status": status, "detail": err}
    return {"state": "FAIL", "code": "UNEXPECTED_STATUS", "http_status": status, "detail": err}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="nfl/NFL_DATA_AVAILABILITY.json")
    args = ap.parse_args()

    started = _dt.datetime.now(_dt.timezone.utc).isoformat()
    results = {}
    for label, url in TARGETS:
        res = probe(url)
        res["url"] = url
        results[label] = res
        print(f"{res['state']:<8} {res.get('http_status','---'):>4}  {label}", flush=True)

    counts: dict[str, int] = {}
    for r in results.values():
        counts[r["state"]] = counts.get(r["state"], 0) + 1

    if not results:
        raise SystemExit("PROBE_EMPTY: no targets probed; refusing to write an empty audit")

    audit = {
        "artifact": "NFL_DATA_AVAILABILITY",
        "probe_started_utc": started,
        "probe_finished_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "probe_tool": "nfl/tools/probe_nfl_sources.py",
        "n_targets": len(results),
        "state_counts": counts,
        "note": (
            "States use the V8 Rule 001 vocabulary. PASS=reachable. "
            "BLOCKED=egress policy denied. FAIL/PATH_NOT_FOUND=this exact path "
            "404ed and says nothing about a name variant. Controls at the end "
            "establish the egress boundary and are expected to fail."
        ),
        "results": results,
    }
    with open(args.out, "w") as fh:
        json.dump(audit, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print(f"\nwrote {args.out}: {len(results)} targets, {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
