"""Classify every STORED_NOT_CONSUMED flag on the Week 5 evidence board (research, read-only).

Categories (owner directive 2026-10-09):
  C1_CONFIRMED_SHOULD_CONSUME   confirmed evidence the engine should consume but ignores (or consumes wrongly)
  C2_REPRESENTED_INDIRECTLY     the information already reaches the projection by another path
  C3_RESEARCH_REQUIRED          the predictive effect is unmeasured; no validated mechanism exists
  C4_UNVERIFIED_SPECULATIVE     not confirmed at a tier that may move a projection
  C5_SHOULD_NOT_INFLUENCE       must never move the proprietary projection
Each assignment carries its reason and, where a scenario or replay measured it, the measured DK impact."""
import json, sys, collections, pathlib
board, qbv, out = sys.argv[1], sys.argv[2], sys.argv[3]
B = json.loads(pathlib.Path(board).read_text()); Q = json.loads(pathlib.Path(qbv).read_text())
qclubs = Q.get('clubs') or Q
RULES = {
 'DEPTH_TIE_BROKEN_BY_ID': ('C1_CONFIRMED_SHOULD_CONSUME',
    'the chart and usage ranks are stored; the engine consumed them wrongly (id tie-break, W5-G13). Repaired by the evidence order (role_state); invariance test on the W4 state'),
 'ROLE_HISTORY_ABOVE_CEILING': ('C3_RESEARCH_REQUIRED',
    'the engine names the conflict; for WR rank 2/3 it is the position-blind ceiling (50% of 1,890 WR2-weeks realise above SECONDARY). The formation-ceiling candidate (A2) improved 25 oracle replay games but not the real W4 pool: research, preregister'),
 'PRACTICE_STATUS_NOT_CONSUMED': ('C3_RESEARCH_REQUIRED',
    'practice participation has no validated mapping to P(plays) or workload; the OFFICIAL designation it precedes IS consumed (OUT moves volume) once captured Friday (W5-G14 capture lag)'),
 'TEAMMATE_PRACTICE_NOT_CONSUMED': ('C2_REPRESENTED_INDIRECTLY',
    'a teammate designated OUT or inactive is redistributed pro rata club-wide by the allocator; before a designation nothing should move'),
 'QB_REGIME_NOT_CONSUMED': ('C3_RESEARCH_REQUIRED',
    'QB identity sets the QB himself (chart) but not team volume/shares; the QB-conditioned candidate FAILED its bar (1 of 3); dropbacks preregistered prospectively (QBCTX-DB1)'),
 'LISTED_STARTER_NOT_CONSUMED': ('C4_UNVERIFIED_SPECULATIVE',
    'the nflverse schedule QB field is a listing, not an announcement, and was contradicted by play-by-play in week 4 (Keenum listed, Bagent threw every pass); the starter itself is resolved by the QB verification board, not by this field'),
 'SECONDARY_NEWS_NOT_CONSUMED': ('C4_UNVERIFIED_SPECULATIVE',
    'web supplement: a discovery signal by rule; it moves nothing until an official designation or captured document confirms it'),
 'APPEARANCE_HISTORY_NOT_CONSUMED': ('C1_CONFIRMED_SHOULD_CONSUME',
    'his own appearance record is stored (observed_2026.weeks_played) but P(plays) comes from a club-slot table by allocation rank: a WR5 who played the prior three weeks appears again 67% of the time (2021-2025) against the table 7.7% (W5-G16). Candidate AP-1 measured on the real W4 pool (-0.116 [-0.274, +0.046]); preregistered, not promoted'),
 'OPPONENT_QB_NOT_CONSUMED': ('C3_RESEARCH_REQUIRED',
    'the DST model does not condition on the opposing QB (D-02); no validated effect size'),
}
NEVER = [{'item': 'Fantasy Cruncher projections, floors, ceilings, ownership', 'category': 'C5_SHOULD_NOT_INFLUENCE', 'reason': 'benchmark only'},
         {'item': 'sportsbook props, spreads, totals (incl. nflverse schedule market columns)', 'category': 'C5_SHOULD_NOT_INFLUENCE', 'reason': 'owner production contract: football-only arm'},
         {'item': 'third-party simulation outputs (Stokastic sims, ownership, leverage)', 'category': 'C5_SHOULD_NOT_INFLUENCE', 'reason': 'external model output'},
         {'item': 'realised ownership of a contest before it locks', 'category': 'C5_SHOULD_NOT_INFLUENCE', 'reason': 'not available prelock'}]
rows, by_cat, by_kind = [], collections.Counter(), collections.Counter()
for r in B['rows']:
    for f in r['STORED_NOT_CONSUMED']:
        kind = f.split(':')[0]
        cat, why = RULES.get(kind, ('C3_RESEARCH_REQUIRED', 'unclassified kind'))
        # CHI starter: the starter question is confirmed at secondary-consistent tier for Bagent; it is the most
        # consequential single item and is handled by scenario forecasts until the official designation.
        if kind == 'QB_REGIME_NOT_CONSUMED' and r['team'] == 'CHI':
            cat, why = 'C1_CONFIRMED_SHOULD_CONSUME', ('starter identity: every secondary source and the official practice report point to Bagent; '
                       'the engine starts Williams from a stale chart capture. Consumed through the starter path once official (designation) or owner-relayed; scenario forecast until then')
        rows.append({'player': r['player'], 'team': r['team'], 'pos': r['pos'], 'flag': kind, 'detail': f, 'category': cat, 'reason': why})
        by_cat[cat] += 1; by_kind[(kind, cat)] += 1
doc = {'ARTIFACT': 'WEEK5_EVIDENCE_CONSUMPTION_CLASSIFICATION', 'board': board, 'qb_verification': qbv,
       'n_board_rows': len(B['rows']), 'n_rows_with_flags': sum(1 for r in B['rows'] if r['STORED_NOT_CONSUMED']),
       'n_flags': len(rows), 'by_category': dict(by_cat),
       'by_kind': [{'flag': k, 'category': c, 'n': n} for (k, c), n in sorted(by_kind.items(), key=lambda x: -x[1])],
       'never_inputs': NEVER, 'rows': rows}
pathlib.Path(out).write_text(json.dumps(doc, indent=1))
print(json.dumps({k: doc[k] for k in ('n_board_rows', 'n_rows_with_flags', 'n_flags', 'by_category', 'by_kind')}, indent=1))
