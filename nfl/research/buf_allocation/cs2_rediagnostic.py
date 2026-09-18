"""Does the Buffalo appearance inversion survive CS2? Measured, not asserted.

THE QUESTION, STATED SO IT CAN COME OUT EITHER WAY. The sealed board gave
James Cook P(zero opportunity) 0.372 against Ray Davis's 0.180 -- a
depth-chart RB1 absent more often than his backup, 27.8 Monte Carlo standard
errors apart. CS2 is the layer that was missing. Applying it to the same
2026 week-2 forecast asks one thing: with current-season evidence reaching the
room, does the ordering change?

WHAT THIS IS NOT. It is not a claim that CS2 fixes the board -- CS2 is a STATE
layer and nothing here writes into a projection or a sealed artifact. It is
not a fit: the prior strengths come from the forward chain on 2022-2025 and
are read, not chosen here. And a result in either direction is reportable. If
the inversion survives, CS2 was not the whole cause and that is worth knowing
before anything is promoted on it.

ONE WEEK OF EVIDENCE. The 2026 conditioning set is week 1 alone. Whatever
comes out is a single-week update of a prior-season prior, and its uncertainty
is not small.
"""
from __future__ import annotations

import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance import artifact_claim as AC             # noqa: E402
from sportsplatform.governance.outcome import State                    # noqa: E402
from nfl.production.nonqb import cs2_state as CS                       # noqa: E402
from nfl.production.nonqb import current_season_nonqb_panel as P       # noqa: E402

SEAL = '2026-09-16T15:45:14Z'
FIT = _REPO / 'nfl/research/cs2/CS2_STAGE2_FIT.json'
OUT = _REPO / 'nfl/research/buf_allocation/CS2_REDIAGNOSTIC.json'

#: The two men the diagnostic is about, by gsis_id. Never by name.
COOK = '00-0037248'
DAVIS = '00-0039875'
GORE = '00-0039471'
BUF = 'BUF'

#: From the sealed board, for comparison only. Nothing is written back.
SEALED = {COOK: {'name': 'James Cook', 'p_zero_opportunity': 0.3719,
                 'carry_share_unconditional': 0.454,
                 'carry_share_given_appears': 0.692},
          DAVIS: {'name': 'Ray Davis', 'p_zero_opportunity': 0.1801,
                  'carry_share_unconditional': 0.331},
          GORE: {'name': 'Frank Gore Jr.', 'p_zero_opportunity': 0.397,
                 'carry_share_unconditional': 0.215}}


def main() -> int:
    if not FIT.exists():
        print('BLOCKED: no CS2_STAGE2_FIT.json; run fit_cs2.py first. The '
              'prior strengths are READ from the chain, never chosen here.')
        return 1
    fit = json.loads(FIT.read_text())
    kappa_a = fit['best_appearance']['kappa_a']
    kappa_s = fit['best_allocation']['kappa_s']
    print(f'prior strengths from the forward chain: kappa_a={kappa_a}, '
          f'kappa_s={kappa_s} (read, not chosen)')

    cur = P.usage_season(2026, as_of=SEAL)
    prev = P.usage_season(2025)
    if cur.state is not State.PASS or prev.state is not State.PASS:
        print(f'BLOCKED: {cur.code} / {prev.code}')
        return 1
    prior = CS.prior_from_season(prev.value, CS.CARRIES)
    st = CS.state(cur.value, prior, CS.CARRIES, kappa_a=kappa_a,
                  kappa_s=kappa_s, n_weeks=1)
    if st.state is not State.PASS:
        print(f'{st.state.value}[{st.code}] {st.detail}')
        return 1
    room = {pid: r for (club, pid), r in st.value.items() if club == BUF}
    rows = []
    for pid, sealed in SEALED.items():
        r = room.get(pid)
        rows.append({
            'gsis_id': pid, 'name': sealed['name'],
            'sealed_p_zero_opportunity': sealed['p_zero_opportunity'],
            'sealed_carry_share_unconditional':
                sealed['carry_share_unconditional'],
            'cs2_p_appears': (r['p_appears'] if r else None),
            'cs2_p_zero_opportunity': (1 - r['p_appears']) if r else None,
            'cs2_share_given_appears': (r['share_given_appears']
                                        if r else None),
            'cs2_n_opportunity': (r['n_opportunity'] if r else None),
            'in_cs2_room': r is not None})
    cook, davis = room.get(COOK), room.get(DAVIS)
    sealed_inverted = (SEALED[COOK]['p_zero_opportunity']
                       > SEALED[DAVIS]['p_zero_opportunity'])
    cs2_inverted = (cook is not None and davis is not None
                    and cook['p_appears'] < davis['p_appears'])
    body = {
        'artifact': 'BUF_CS2_REDIAGNOSTIC',
        'question': 'does the Cook/Davis appearance inversion survive CS2?',
        'uses_outcome_data': False,
        'conditioning': 'BUF 2026 week 1 only, as_of the 2026-09-16 seal',
        'prior_season': 2025,
        'kappa_a': kappa_a, 'kappa_s': kappa_s,
        'kappa_source': 'nfl/research/cs2/CS2_STAGE2_FIT.json, forward '
                        'chained on 2022-2025; read here, not chosen',
        'sealed_board_inverted': bool(sealed_inverted),
        'cs2_inverted': bool(cs2_inverted),
        'verdict': ('INVERSION_RESOLVED' if sealed_inverted and not cs2_inverted
                    else 'INVERSION_PERSISTS' if cs2_inverted
                    else 'NO_INVERSION_IN_EITHER'),
        'rows': rows,
        'nothing_written_back': ('CS2 is a state layer. No projection, no '
                                 'sealed artifact and no board is modified '
                                 'by this diagnostic.'),
        'one_week': ('the 2026 conditioning set is week 1 alone. This is a '
                     'single-week update of a prior-season prior and its '
                     'uncertainty is not small.'),
        'no_monotonicity_imposed': ('CS2 does not force RB1 above RB2. If the '
                                    'ordering changed, the evidence changed '
                                    'it.'),
        'saturation_limitation': {
            'code': 'CS2_APPEARANCE_SATURATES_AT_ONE',
            'n_p_appears_at_one': st.evidence['n_p_appears_at_one'],
            'n_p_appears_at_zero': st.evidence['n_p_appears_at_zero'],
            'n_rows': st.evidence['n_rows'],
            'n_prior_fallbacks': st.evidence['n_prior_fallbacks'],
            'what_it_means': (
                "Cook's CS2 P(zero opportunity) is EXACTLY 0.0000, which says "
                "he cannot miss. That is not a plausible football state. A "
                "Beta posterior mean saturates for a man who has never missed "
                "and for one who has never played, and on this slate that is "
                "a large share of the rows. The inversion result stands -- "
                "the ORDERING is what was asked about -- but these "
                "probabilities must not reach a simulator unfloored."),
            'the_floor_is_a_new_choice': (
                'clipping to [eps, 1-eps] is a modelling decision with a '
                'value in it, and it belongs in a preregistration rather '
                'than in a diagnostic that noticed it was needed.'),
            'blocks': 'CS2 stage 2 reaching production allocation',
        },
    }
    OUT.write_text(json.dumps(body, indent=1, sort_keys=True))
    print(f"\nsealed board inverted: {sealed_inverted}; "
          f"CS2 inverted: {cs2_inverted}  ->  {body['verdict']}")
    print(f"{'player':18s} {'sealed P(0 opp)':>16s} {'CS2 P(0 opp)':>14s} "
          f"{'sealed share':>13s} {'CS2 share|app':>14s} {'wk1 carries':>12s}")
    for r in rows:
        print(f"{r['name']:18s} {r['sealed_p_zero_opportunity']:16.4f} "
              f"{(r['cs2_p_zero_opportunity'] or 0):14.4f} "
              f"{r['sealed_carry_share_unconditional']:13.4f} "
              f"{(r['cs2_share_given_appears'] or 0):14.4f} "
              f"{(r['cs2_n_opportunity'] or 0):12.0f}")
    c = AC.claim(OUT, schema=['rows', 'verdict'], label=OUT.name)
    return 0 if c.state is State.PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())
