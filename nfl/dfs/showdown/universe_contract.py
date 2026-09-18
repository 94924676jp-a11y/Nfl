"""Which players are in which universe, declared once and compared explicitly.

THE DEFECT THIS CLOSES. The 2026-09-17 postmortem put a delivered exposure
next to a `P(optimal)` for Tyler Bass and Jake Bates. Those two numbers were
computed over DIFFERENT SETS OF PLAYERS: the delivered lineups could roster a
kicker, and the optimal-world solve could not, because the model has no named
kicker. "22.5% exposure against a P(optimal) of 0.0" reads as an indictment of
the portfolio and is actually an artefact of comparing two universes. The
kicker's `P(optimal)` was not low; it was UNDEFINED.

FOUR UNIVERSES, AND THEY ARE NOT THE SAME SET

  SITE                  every row the contest file offers. The outer bound.
  SIMULATED             the site rows the sealed board can name and score.
  OPTIMIZATION          the rows actually handed to the solver. A subset of
                        SIMULATED: a blocked confidence tag or a missing
                        captain row removes a player here without removing
                        him from the model.
  DELIVERED_PORTFOLIO   the rows that actually appear in lineups that went
                        out. THIS ONE IS NOT A SUBSET OF THE OTHERS, which is
                        the whole problem.

THE RULE. A metric defined over one universe may only be compared against a
metric defined over the same universe. `assert_comparable` refuses otherwise
with `DFS_METRIC_COMPARISON_UNIVERSE_MISMATCH`, naming the players that fall
outside, because a refusal that does not say who is not actionable.

WHAT THIS MODULE DOES NOT DO. It does not repair an identity, admit a kicker,
or decide what a portfolio should have done. It reports set membership and the
reason for each exclusion. Admitting kickers is
`KICKER_IDENTITY_MUST_BE_PLAYER_KEYED` work, upstream of here.
"""
from __future__ import annotations

import csv
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State    # noqa: E402
from nfl.dfs.showdown import universe as U                            # noqa: E402
from nfl.production.dfs import projection_confidence as PC            # noqa: E402

SPEC_VERSION = 'nfl-dfs-universe-contract-1'

SITE = 'SITE_UNIVERSE'
SIMULATED = 'SIMULATED_UNIVERSE'
OPTIMIZATION = 'OPTIMIZATION_UNIVERSE'
DELIVERED = 'DELIVERED_PORTFOLIO_UNIVERSE'
UNIVERSES = (SITE, SIMULATED, OPTIMIZATION, DELIVERED)

CODE_MISMATCH = 'DFS_METRIC_COMPARISON_UNIVERSE_MISMATCH'

#: Why a site row is not in the optimization universe. Every exclusion carries
#: one of these; an unexplained exclusion is a defect in this module.
REASONS = {
    'IDENTITY_UNRESOLVED': 'the sealed board carries no named row for him. '
                           'For kickers this is structural: the kicking layer '
                           'is team-keyed, and resolving him by (team, '
                           'position) would be an inference about a join.',
    'UNSUPPORTED_POSITION': 'DST is not modelled at all. Team defence points '
                            'are not inferable from a team score.',
    'CONFIDENCE_BLOCKED': 'his confidence tag blocks him from a lineup.',
    'NO_CAPTAIN_ROW': 'the contest file offers no CPT row for him, so he '
                      'cannot be priced in the captain slot.',
    'NOT_A_FLEX_ROW': 'a CPT row is the same man as his FLEX row, counted '
                      'once.',
}


def _lineup_players(path) -> set:
    """Distinct normalised names across a delivered portfolio CSV."""
    out = set()
    p = pathlib.Path(path)
    if not p.exists():
        return out
    for r in csv.reader(p.read_text().splitlines()):
        if not (r and r and r[0].isdigit()):
            continue
        for cell in r[4:10]:
            nm = cell.strip()
            if nm:
                out.add(U.norm(nm))
    return out


def build(portfolios=()) -> Outcome:
    """The contract: one row per site player, with every universe flagged."""
    uni = U.build()
    if uni.state is not State.PASS:
        return uni
    players = uni.value['players']
    playable = {p['key'] for p in uni.value['playable']}
    cpt_keys = {p['key'] for p in players if p['slot'] == 'CPT'}

    delivered = {}
    for label, path in portfolios:
        delivered[label] = _lineup_players(path)
    delivered_all = set().union(*delivered.values()) if delivered else set()

    rows, by_key = [], {}
    for p in players:
        if p['slot'] != 'FLEX':
            continue
        key = p['key']
        # A kicker is simulated through his OWN layer, which carries its own
        # array rather than a `dk_scoring` row index. Reading only
        # `draw_row` made the simulated set smaller than the optimization set
        # -- an impossible ordering, and the contract test caught it.
        simulated = p['draw_row'] is not None or p.get('kicking_layer', False)
        blocked = PC.POLICY[p['tag']]['blocked']
        if not simulated:
            reason = ('UNSUPPORTED_POSITION' if p['pos'] == 'DST'
                      else 'IDENTITY_UNRESOLVED')
        elif p.get('kicking_layer') and not p.get('gsis_id'):
            reason = 'IDENTITY_UNRESOLVED'
        elif blocked:
            reason = 'CONFIDENCE_BLOCKED'
        elif key not in cpt_keys:
            reason = 'NO_CAPTAIN_ROW'
        else:
            reason = None
        row = {
            'site_player_id': p['dk_id'],
            'canonical_key': key,
            'name': p['name'], 'team': p['team'], 'position': p['pos'],
            'salary': p['salary'],
            'scoring_support': True,          # DK scoring is mechanical
            'simulation_support': simulated,
            'optimization_eligible': key in playable,
            'excluded_because': reason,
            'excluded_detail': REASONS.get(reason),
            'confidence_state': p['tag'],
            SITE: True,
            SIMULATED: simulated,
            OPTIMIZATION: key in playable,
            DELIVERED: key in delivered_all,
            'delivered_in': sorted(k for k, v in delivered.items()
                                   if key in v),
        }
        rows.append(row)
        by_key[key] = row

    counts = {u: sum(1 for r in rows if r[u]) for u in UNIVERSES}
    # THE MISMATCHES, named. A count alone would let this pass unread.
    delivered_not_optimized = sorted(
        r['name'] for r in rows if r[DELIVERED] and not r[OPTIMIZATION])
    delivered_not_simulated = sorted(
        r['name'] for r in rows if r[DELIVERED] and not r[SIMULATED])
    optimized_not_delivered = sorted(
        r['name'] for r in rows if r[OPTIMIZATION] and not r[DELIVERED])
    unknown_delivered = sorted(delivered_all - set(by_key))

    ev = {
        'spec_version': SPEC_VERSION, 'counts': counts,
        'delivered_but_not_in_optimization': delivered_not_optimized,
        'delivered_but_not_simulated': delivered_not_simulated,
        'in_optimization_but_never_delivered': optimized_not_delivered,
        'delivered_names_not_on_the_site_board': unknown_delivered,
        'portfolios': {k: len(v) for k, v in delivered.items()},
        'exclusion_counts': {},
        'this_module_does_not_repair': (
            'it reports set membership. Admitting a kicker is '
            'KICKER_IDENTITY_MUST_BE_PLAYER_KEYED work, upstream of here.'),
    }
    for r in rows:
        if r['excluded_because']:
            ev['exclusion_counts'][r['excluded_because']] = (
                ev['exclusion_counts'].get(r['excluded_because'], 0) + 1)
    return Outcome.ok(
        'DFS_UNIVERSE_CONTRACT', value={'rows': rows, 'by_key': by_key},
        detail=f"site {counts[SITE]}, simulated {counts[SIMULATED]}, "
               f"optimization {counts[OPTIMIZATION]}, delivered "
               f"{counts[DELIVERED]}; "
               f"{len(delivered_not_optimized)} delivered player(s) outside "
               f"the optimization universe",
        **ev)


def assert_comparable(names, contract, *, metric='p_optimal',
                      universe=OPTIMIZATION) -> Outcome:
    """A P(optimal) may only be set beside another player in the same set."""
    by_key = contract.value['by_key'] if hasattr(contract, 'value') else contract
    outside, unknown = [], []
    for nm in names:
        r = by_key.get(U.norm(nm))
        if r is None:
            unknown.append(nm)
        elif not r[universe]:
            outside.append({'name': nm, 'reason': r['excluded_because'],
                            'detail': r['excluded_detail']})
    ev = {'spec_version': SPEC_VERSION, 'metric': metric,
          'universe': universe, 'n_names': len(list(names)),
          'outside_universe': outside, 'not_on_the_board': unknown}
    if outside or unknown:
        who = [x['name'] for x in outside] + unknown
        return Outcome.fail(
            CODE_MISMATCH,
            f'{metric} is defined over {universe} and {len(who)} of the '
            f'players compared are not in it: {who}. The metric is not low '
            f'for them, it is UNDEFINED, and printing a zero beside a '
            f'delivered exposure reads as a finding when it is an artefact.',
            cause=Cause.GOVERNANCE, **ev)
    return Outcome.ok(
        'DFS_METRIC_COMPARISON_LAWFUL', value=list(names),
        detail=f'{len(list(names))} player(s), all inside {universe}', **ev)


def main() -> int:
    HERE = _REPO / 'nfl/research/dfs/DET_BUF_2026W2'
    o = build(portfolios=(('CLAUDE', HERE / 'PORTFOLIO_CLAUDE_40.csv'),
                          ('ALTERNATE', HERE / 'PORTFOLIO_ALTERNATE_40.csv')))
    print(f'{o.state.value}[{o.code}] {o.detail}')
    if o.state is not State.PASS:
        return 1
    for k in ('delivered_but_not_in_optimization', 'delivered_but_not_simulated',
              'in_optimization_but_never_delivered',
              'delivered_names_not_on_the_site_board'):
        print(f'  {k}: {o.evidence[k]}')
    print(f'  exclusion_counts: {o.evidence["exclusion_counts"]}')
    out = HERE / 'DFS_UNIVERSE_CONTRACT.json'
    out.write_text(json.dumps(
        {'spec_version': SPEC_VERSION, 'detail': o.detail,
         'evidence': {k: v for k, v in o.evidence.items() if k != 'cause'},
         'rows': o.value['rows']}, indent=1, sort_keys=True))
    from sportsplatform.governance import artifact_claim as AC
    c = AC.claim(out, schema=['rows', 'evidence'], label=out.name)
    return 0 if c.state is State.PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())
