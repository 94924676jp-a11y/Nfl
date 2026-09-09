"""The complete V1 football engine: one call, one game, one draw index.

WHAT THIS IS

R3 left the engine spread across a rehearsal script. R4 needs the same chain
run three ways -- on a TEST-ONLY injury stand-in, on the real feed, and by the
test suite -- so it lives here once and the rehearsals are thin callers. A
second copy of an engine is a second engine.

ONE DRAW INDEX. Every layer for a game shares draw column j: appearance,
participation, the targets allocation, the carries allocation, conversion, both
touchdown layers and the QB layer. Coupling is the point -- a receiver's
receptions and his team's target volume have to move together within a draw or
the joint distribution is a fiction assembled from marginals.

WHAT IS ABSENT AND WHY. `rushing_yards` has no governed control (see
rushing_inventory.json). It is emitted as an explicit ABSENT record naming the
three open decisions. It is never emitted as zero.
"""
from __future__ import annotations

import collections
import pathlib
import sys
import time

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
for _q in (str(_REPO), str(_REPO / 'nfl' / 'research' / 'p4c'),
           str(_REPO / 'nfl' / 'research' / 'qb2')):
    if _q not in sys.path:
        sys.path.insert(0, _q)

from sportsplatform.governance.outcome import Outcome, State      # noqa: E402
from nfl.production import team_volume_v1 as TV                   # noqa: E402
from nfl.production import qb_accounting as QBACC                 # noqa: E402
from nfl.production import qb_v1 as QBV1                          # noqa: E402
from nfl.production.nonqb import accounting as ACC                # noqa: E402
from nfl.production.nonqb import frozen_priors as FP              # noqa: E402
from nfl.production.nonqb import layers as LY                     # noqa: E402
from nfl.production.nonqb import p4c_params as P4                 # noqa: E402
from nfl.production.nonqb import shared_pass as SP                # noqa: E402
from nfl.production import seeds as SEEDS                         # noqa: E402
from nfl.production.nonqb import qb_allocation as QA               # noqa: E402
from nfl.production.nonqb import participation_prior as PP        # noqa: E402
from nfl.production.nonqb import player_record as PR              # noqa: E402

RECEIVING_POS = ('WR', 'TE', 'RB')
CARRY_POS = ('RB',)
ENGINE_VERSION = 'nfl-football-engine-v1-r4'


def slate_fits(season, week, players) -> Outcome:
    """Everything that depends only on history, computed once per slate."""
    fits, states = {}, {}
    for name, o in (
            ('p4c_params_targets', P4.params('targets', season)),
            ('p4c_params_carries', P4.params('carries', season)),
            ('C_targets', P4.class_point_forecast('targets', season, week,
                                                  players)),
            ('C_carries', P4.class_point_forecast('carries', season, week,
                                                  players)),
            ('participation_prior', PP.share_prior(season, week, players)),
            ('receiving_priors', FP.receiving_priors(season)),
            ('td_priors_rec', FP.td_priors(season, 'rec')),
            ('td_priors_rush', FP.td_priors(season, 'rush'))):
        states[name] = f'{o.state.value}[{o.code}]'
        if o.state is not State.PASS:
            return Outcome.blocked(
                'SLATE_FITS_UNAVAILABLE',
                f'{name} returned {o.state.value}[{o.code}]: {o.detail[:160]}',
                cause=o.evidence.get('cause') or None, states=states)
        fits[name] = o
    return Outcome.ok('SLATE_FITS_OK', value=fits, states=states,
                      evidence_by_fit={
                          k: {kk: vv for kk, vv in v.evidence.items()
                              if kk != 'value'} for k, v in fits.items()})


def qb_slate(season, week, qb_players, m=200, seed=20260908,
             include_cold_start=False) -> Outcome:
    """The QB layer for the whole slate, computed once.

    QB rushing yards ARE supported and RB rushing yards are not, which looks
    inconsistent until you read both mechanisms. QB V1 draws a per-game
    yards-per-rush from the quarterback's own history mixed with the positional
    pool and multiplies by his drawn rush opportunity -- a distribution, and
    the owner-accepted production baseline. P5A's rushing control is a
    per-CARRY compound and is unadjudicated. Whatever P5A eventually defines
    should be checked against the QB mechanism, because the same football
    quantity is currently produced two different ways.
    """
    # The QB layer reads the derived panel too, through p4c_build. Ensuring
    # the cache here is what stops it depending on a copy someone else
    # happened to leave in the research tree.
    from nfl.production import derived as _D
    a = _D.artifacts()
    if a.state is not State.PASS:
        return a
    fh = QBV1.artifact_hash()
    if fh.state is not State.PASS:
        return fh
    sl = QBV1.slate_prospective(season, week, qb_players,
                                include_cold_start=include_cold_start)
    if sl.state is not State.PASS:
        return sl
    rows, allrows = sl.value
    o = QBV1.forecast(rows, season, allrows, seed=seed, m=m)
    if o.state is not State.PASS:
        return o
    by_team = collections.defaultdict(list)
    for i, r in enumerate(rows):
        by_team[r.get('team')].append(i)
    return Outcome.ok('QB_SLATE_OK', value={'rows': rows, 'draws': o.value,
                                            'index_by_team': dict(by_team),
                                            # kept so R2 can re-run the layer
                                            # at the allocated level without
                                            # reloading the frame
                                            'allrows': allrows,
                                            'season': season, 'm': m,
                                            'seed': seed},
                      spec_version=QBV1.SPEC_VERSION, n_qb=len(rows),
                      cold_start_included=bool(include_cold_start),
                      n_cold_start_rows=sl.evidence.get('n_cold_start_rows', 0),
                      qb_frame_sha256=fh.value,
                      warnings=[f'known limitation: {k}'
                                for k in QBV1.KNOWN_LIMITATIONS])



def apply_r2_level(qb, alloc, tv, teams) -> Outcome:
    """R2: re-run QB V1 at the level D1 x QB3 already own.

    Pre-registered in nfl/research/r2/predeclaration_qb_level_ownership_r2.md,
    sha256 3d7beeb39f32da11623ac2be178ca4b764ecf314a5a55515b0d45c0e3d4f323c.

    THE DEFECT R2 REMOVES. QB V1 drew its own level, `DB = rint(V x S)`, from
    the same two pools D1 and QB3 own. `run_game` reconciled the duplicate by
    dividing one level by the other, and dividing by a small draw is what
    produced composition factors to 59.85 and a 49.14 passing-touchdown tail
    off a one-dropback donor. R2 deletes the duplicate instead of bounding the
    ratio: the level is apportioned from the team budget by largest remainder,
    and QB V1 supplies conditional rates at that level.

    After this, team dropback closure is INTEGER-exact by construction rather
    than float-exact through a division, which the pre-registration declares in
    advance as the invariant R2 replaces rather than preserves. There is no
    denominator, so the OWN-4 donor mechanism has nothing to repair.
    """
    if not qb or 'rows' not in qb:
        return Outcome.fail('R2_NO_QB_SLATE',
                            'R2 needs the QB slate it is re-levelling')
    rows = qb['rows']
    idx_by_team = qb['index_by_team']
    ext = np.zeros((len(rows), int(qb['m'])), np.int64)
    named = set()
    ev = {}
    for t in teams:
        a = alloc.get(t)
        if a is None:
            continue
        tdb = np.asarray(tv.value[('team_dropbacks_part', t)], float)
        pids = list(a['pids'])
        rows_for = {rows[i]['gsis_id']: i for i in idx_by_team.get(t, [])}
        keep = [(j, p) for j, p in enumerate(pids) if p in rows_for]
        if not keep:
            # Allocated mass with no modelled quarterback to receive it. This
            # is OWN-1's leak, and it is refused by name rather than shared out
            # among the survivors.
            return Outcome.fail(
                'R2_ALLOCATED_MASS_HAS_NO_MODELLED_QB',
                f'{t}: the allocation names {len(pids)} quarterback(s), none '
                f'of whom QB V1 forecast. No survivor renormalisation.',
                team=t, pids=pids)
        sub = np.stack([np.asarray(a['shares'][j], float) for j, _ in keep])
        ap = QBACC.apportion_dropbacks(tdb, sub, [p for _, p in keep])
        if ap.state is not State.PASS:
            return ap
        for k, (_, p) in enumerate(keep):
            ext[rows_for[p]] = ap.value[k]
            named.add(p)
        ev[t] = {'n_qb_levelled': len(keep),
                 'team_budget_mean': ap.evidence['team_budget_mean'],
                 'closes_exactly': True}
    o = QBV1.forecast(rows, qb['season'], qb['allrows'],
                      seed=qb['seed'], m=qb['m'], db_external=ext)
    if o.state is not State.PASS:
        return o
    out = dict(qb)
    out['draws'] = o.value
    out['r2'] = {'applied': True, 'per_team': ev,
                 'level_owner': 'D1 x QB3, apportioned by largest remainder',
                 'qb_v1_draws_no_level': True,
                 'donor_mechanism_reachable': False,
                 'closure': 'integer-exact by construction'}
    return Outcome.ok('QB_LEVEL_R2_APPLIED', value=out,
                      n_qb_levelled=len(named), **{'teams': list(ev)})

def run_game(season, week, game_id, players, fits, m=200, seed=20260908,
             injuries_rows=None, test_only=False, kickoff_utc=None,
             run_id='rehearsal', qb=None, shared_pass='off',
             game_coupling='none'):
    """One game, every implemented layer, one draw index."""
    away, home = game_id.split('_')[2:4]
    teams = (away, home)
    g = {'game_id': game_id, 'teams': list(teams), 'layers': {},
         'accounting': {}, 'engine_version': ENGINE_VERSION}

    recv = [q for q in players if q.get('position') in RECEIVING_POS]
    ids = [q['gsis_id'] for q in recv]
    pos = [q['position'] for q in recv]
    starts, counts, i = [], [], 0
    by_team = collections.defaultdict(list)
    for q in recv:
        by_team[q['team']].append(q)
    order = []
    for t in teams:
        order.extend(by_team.get(t, []))
        starts.append(i)
        counts.append(len(by_team.get(t, [])))
        i += len(by_team.get(t, []))
    recv, ids, pos = order, [q['gsis_id'] for q in order], \
        [q['position'] for q in order]
    g['n_players'] = len(recv)

    # A3G in the V1 candidate mode: the two teams in a game share one coupled
    # draw index, so the game total stops being the sum of two independent
    # marginals. Measured: SD(total plays) 12.271 -> 9.269 against a historical
    # 9.265, and the fraction of drawn games outside the entire 2020-2025
    # observed range 1.520% -> 0.188%. The rank copula moves no marginal by
    # construction -- it changes WHICH residual each side receives, not the
    # pool it is drawn from. Opt-in; no production default is changed here.
    tv = (TV.forecast(season, week, list(teams), m=m, seed=seed,
                      joint_residuals=True, game_pairs=[(teams[0], teams[1])],
                      game_coupling=game_coupling)
          if game_coupling and game_coupling != 'none'
          else TV.forecast(season, week, list(teams), m=m, seed=seed))
    g['layers']['game_coupling'] = (f'PASS[A3G_{game_coupling.upper()}]'
                                    if game_coupling
                                    and game_coupling != 'none'
                                    else 'NOT_APPLICABLE[GAME_COUPLING_NONE]')
    g['layers']['team_environment'] = f'{tv.state.value}[{tv.code}]'
    if tv.state is not State.PASS:
        g['halted_at'] = 'team_environment'
        return g, None

    fixture = None
    if injuries_rows is not None:
        fixture = {'_test_only': True, 'practice_progression': {},
                   'teammate_availability': {},
                   'injuries_rows': injuries_rows}
    # game_id separates this game's streams from every other game on the
    # slate. Without it a sixteen-game slate is not sixteen games.
    ap = LY.appearance(season, week, recv, fixture=fixture, m=m, seed=seed,
                       teams=teams, kickoff_utc=kickoff_utc,
                       game_id=game_id)
    g['layers']['appearance'] = f'{ap.state.value}[{ap.code}]'
    if ap.state is not State.PASS:
        g['halted_at'] = 'appearance'
        g['halt_reason'] = ap.detail[:200]
        for k in ('participation', 'targets_carries', 'carries',
                  'receiving_conversion', 'receiving_td', 'rushing_td'):
            g['layers'][k] = 'NOT_APPLICABLE[UPSTREAM_NOT_EXECUTED]'
        g['layers']['rushing_conversion'] = \
            'DEFERRED[RUSHING_CONVERSION_CONTROL_UNDEFINED]'
        return g, None

    pa = LY.participation(ap, fits['participation_prior'].value, m=m)
    g['layers']['participation'] = f'{pa.state.value}[{pa.code}]'

    # ---- targets (WR/TE/RB, simplex) ------------------------------------
    Ct = [fits['C_targets'].value.get(p, 0.0) for p in ids]
    tc = LY.targets_carries(pa, 'targets', Ct, pos, (starts, counts), ids,
                            fits['p4c_params_targets'].value, m=m, seed=seed,
                            game_id=game_id, ordinal=season * 100 + week)
    g['layers']['targets_carries'] = f'{tc.state.value}[{tc.code}]'
    if tc.state is not State.PASS:
        g['halted_at'] = 'targets_carries'
        return g, None
    S, other = tc.value['share'], tc.value['other']
    c3 = None
    c3_other = None
    if shared_pass == 'c3' and qb is not None and qb.get('draws'):
        # C3: THE TARGET BUDGET COMES FROM THE THROW PROCESS, NOT FROM D1.
        #
        # `T = share x D1.team_targets` multiplied a share by a SEPARATELY
        # DRAWN count of the same football quantity -- two owners of one
        # number -- and then treated a continuous product as a count. The
        # audit measured the consequence: corr(team passing yards, team
        # receiving yards) = +0.001 under the production default, with the
        # yard identity violated in 12,800 of 12,800 draws.
        #
        # Under C3 the quarterbacks' attempts ARE the throw budget, a named
        # untargeted pool is drawn from it, and every remaining throw is dealt
        # to exactly one receiver by the SAME simplex. Receiver competition is
        # untouched; only the denominator changes, and it changes to the one
        # the football event actually has.
        ur = SP.untargeted_rate()
        if ur.state is not State.PASS:
            g['halted_at'] = 'shared_pass'
            g['halt_reason'] = f'{ur.code}: {ur.detail[:180]}'
            return g, None
        att_by_team = [np.stack([np.asarray(qb['draws']['att'][i], float)
                                 for i in qb['index_by_team'].get(t, [])])
                       if qb['index_by_team'].get(t) else None for t in teams]
        if any(a is None for a in att_by_team):
            g['halted_at'] = 'shared_pass'
            g['halt_reason'] = ('C3_TEAM_HAS_NO_QUARTERBACK_ROW: the throw '
                                'budget is the quarterbacks\' attempts, so a '
                                'team with no modelled passer has no budget')
            return g, None
        rng_c3 = np.random.default_rng(
            [seed, season * 100 + week,
             int(SEEDS.game_component(game_id).value), 0xC3])
        tgt = []
        for a in att_by_team:
            t_o = SP.targeted_throws(a, ur.value, rng_c3)
            if t_o.state is not State.PASS:
                g['halted_at'] = 'shared_pass'
                g['halt_reason'] = f'{t_o.code}: {t_o.detail[:180]}'
                return g, None
            tgt.append(t_o.value)
        dealt = SP.deal_targets(S, other, [x['targeted'] for x in tgt],
                                starts, counts, rng_c3)
        if dealt.state is not State.PASS:
            g['halted_at'] = 'shared_pass'
            g['halt_reason'] = f'{dealt.code}: {dealt.detail[:180]}'
            return g, None
        T = dealt.value['targets'].astype(float)
        tgt_vol = np.stack([np.asarray(x['targeted'], float) for x in tgt])
        # CLOSURE UNDER C3 IS A COUNT IDENTITY, AND IT IS CHECKED AS ONE.
        # `deal_targets` partitions an integer targeted-throw budget by a
        # multinomial, so `sum_i T_i + other == targeted` holds EXACTLY in
        # every draw by construction. The share-form identity the accounting
        # layer checks -- sum(T) + other_share x V == V -- is a property of
        # the `share x volume` architecture C3 replaces, and neither passing
        # the allocator's share (a different quantity) nor re-expressing the
        # dealt count as a share (which then breaks simplex closure) makes it
        # hold. Both were tried and both moved the failure rather than
        # removing it.
        #
        # So the count identity is asserted HERE, exactly, and reported under
        # its own name. The allocator's own `other` is left untouched so that
        # `share_simplex_closure` still checks the allocator.
        c3_other = dealt.value['other'].astype(float)
        _per_team = np.stack([T[a:a + cc].sum(0)
                              for a, cc in zip(starts, counts)])
        c3_closure = int((np.abs(_per_team + dealt.value['other']
                                 - tgt_vol) > 1e-9).sum())
        c3 = {'untargeted_rate': float(ur.value),
              'count_closure_violating_cells': c3_closure,
              'count_closure_identity': 'sum_i targets_i + other == targeted, '
                                        'per team per draw, exact',
              'mean_throws': [round(float(np.mean(x['throws'])), 4)
                              for x in tgt],
              'mean_targeted': [round(float(np.mean(x['targeted'])), 4)
                                for x in tgt],
              'targets_dealt_mean': dealt.evidence['mean_targets_per_draw'],
              'other_pool_mean': dealt.evidence['mean_other_per_draw'],
              'target_budget_owner': 'the throw process (QB attempts), not D1',
              'd1_team_targets_unused': True}
        if c3_closure:
            g['halted_at'] = 'shared_pass'
            g['halt_reason'] = (
                f'C3_TARGET_COUNT_DOES_NOT_CLOSE: {c3_closure} cell(s) where '
                f'the dealt targets plus the other pool do not equal the '
                f'targeted budget. This is a construction, so a failure here '
                f'is a defect, never a tolerance to widen.')
            g['layers']['shared_pass'] = 'FAIL[C3_TARGET_COUNT_DOES_NOT_CLOSE]'
            return g, None
        g['layers']['shared_pass'] = 'PASS[C3_TARGET_BUDGET_FROM_THROWS]'
    else:
        tgt_vol = np.stack([tv.value[('team_targets', t)] for t in teams])
        T = S * np.repeat(tgt_vol, counts, axis=0)
        g['layers']['shared_pass'] = f'NOT_APPLICABLE[SHARED_PASS_{shared_pass.upper()}]'

    # ---- carries (RB only, simplex, its own group layout) ----------------
    rb = [q for q in recv if q['position'] in CARRY_POS]
    rb_ids = [q['gsis_id'] for q in rb]
    rb_pos = [q['position'] for q in rb]
    rb_starts, rb_counts, j = [], [], 0
    for t in teams:
        n = sum(1 for q in rb if q['team'] == t)
        rb_starts.append(j); rb_counts.append(n); j += n
    car = LY.targets_carries(
        pa, 'carries', [fits['C_carries'].value.get(p, 0.0) for p in rb_ids],
        rb_pos, (rb_starts, rb_counts), rb_ids,
        fits['p4c_params_carries'].value, m=m, seed=seed,
        game_id=game_id, ordinal=season * 100 + week)
    g['layers']['carries'] = f'{car.state.value}[{car.code}]'
    if car.state is not State.PASS:
        g['halted_at'] = 'carries'
        g['halt_reason'] = car.detail[:200]
        return g, None
    Sc, other_c = car.value['share'], car.value['other']
    car_vol = np.stack([tv.value[('team_carries', t)] for t in teams])
    C = Sc * np.repeat(car_vol, rb_counts, axis=0)

    ordinal = season * 100 + week
    cv = LY.receiving_conversion(tc, T, fits['receiving_priors'].value, ids,
                                 pos, ordinal, m=m, seed=seed)
    g['layers']['receiving_conversion'] = f'{cv.state.value}[{cv.code}]'
    tdp = dict(fits['td_priors_rec'].value)
    tdp['pos_catch_rate'] = fits['receiving_priors'].value['pos_catch_rate']
    td = LY.td_layer(cv, T, tdp, ids, pos, ordinal, m=m, seed=seed)
    g['layers']['receiving_td'] = f'{td.state.value}[{td.code}]'
    rtd = LY.rushing_td(car, C, fits['td_priors_rush'].value, rb_ids, rb_pos,
                        ordinal, m=m, seed=seed)
    g['layers']['rushing_td'] = f'{rtd.state.value}[{rtd.code}]'
    ry = LY.rushing_conversion(car)
    g['layers']['rushing_conversion'] = f'{ry.state.value}[{ry.code}]'

    for o in (cv, td, rtd):
        if o.state is not State.PASS:
            g['halted_at'] = 'conversion_or_td'
            g['halt_reason'] = o.detail[:200]
            return g, None

    # ---- accounting, on the same draw index -----------------------------
    A = np.stack([np.asarray(pa.value[p], np.float32).reshape(-1)
                  for p in ids])
    rec_acc = ACC.reconcile_nonqb(
        S, other, tgt_vol, T, (A > 0).astype(np.float32), starts, counts,
        receptions=cv.value['receptions'], receiving_td=td.value['td'],
        receiving_yards=cv.value['receiving_yards'],
        # Under C3 the opportunity identity is checked as exact integer
        # counts, which is stricter than the share form it replaces.
        opportunity_other_counts=(c3_other if c3 is not None else None))
    g['accounting']['receiving'] = f'{rec_acc.state.value}[{rec_acc.code}]'
    qb_rush, qb_records = None, []
    if qb is not None and qb.get('r2'):
        # R2: THERE IS NOTHING TO COMPOSE. The level was apportioned from
        # D1 x QB3 before QB V1 ran, so the draws already sit at the allocated
        # level. The division that produced factors to 59.85 does not execute,
        # and the OWN-4 donor mechanism has no denominator to repair -- both
        # are unreachable rather than merely unused.
        g['accounting']['qb_composition'] = 'PASS[QB_LEVEL_OWNED_BY_D1_X_QB3]'
        g['accounting']['qb_composition_mass'] = \
            'PASS[QB_COMPOSITION_NO_DIVISION_PERFORMED]'
        g['accounting']['qb_composition_amplification'] = {
            'rows_failing_rate_fidelity': 0, 'cells_stretched': 0,
            'cells_live': 0, 'frac_stretched': 0.0, 'factor_max': 0.0,
            'condition': 'R2 -- no ratio is formed, so none can be extreme',
            'repair': 'R2 applied'}
        g['r2'] = qb['r2']
        share_ok = QBACC.reconcile_allocation_share(
            {t: qb['allocation'][t] for t in teams if t in qb['allocation']},
            {t: [qb['rows'][i]['gsis_id'] for i in
                 qb['index_by_team'].get(t, [])] for t in teams})
        g['accounting']['qb_allocation_share'] = \
            f'{share_ok.state.value}[{share_ok.code}]'
        g['accounting']['qb_allocation_share_evidence'] = {
            k: v for k, v in share_ok.evidence.items() if k != 'value'}
    elif qb is not None and qb.get('allocation'):
        # THE COMPOSITION W2 SECTION 7.1 ALREADY SPECIFIES:
        #     QB dropbacks = team dropbacks x QB dropback share
        # QB V1 forecasts a passer's line CONDITIONAL ON BEING THE PRIMARY
        # PASSER. The allocation supplies the conditioning it was always
        # missing. This is composition, not a replacement of a frozen model,
        # and the rate-type outputs are untouched because every count scales by
        # the same factor.
        D = qb['draws']
        alloc = qb['allocation']
        scaled = {k: np.array(v, float) for k, v in D.items()}
        applied = 0
        repaired_cells = repaired_rows = 0
        at_risk = 0.0
        amp_worst = 0.0
        amp_stretched = amp_cells = amp_fail = 0
        for t in teams:
            a = alloc.get(t)
            if a is None:
                continue
            tdb = np.asarray(tv.value[('team_dropbacks_part', t)], float)
            pos_in_alloc = {pid: i for i, pid in enumerate(a['pids'])}
            for i in qb['index_by_team'].get(t, []):
                pid = qb['rows'][i]['gsis_id']
                j = pos_in_alloc.get(pid)
                if j is None:
                    scaled['db'][i] = 0.0
                    for f in QBV1.FIELDS:
                        scaled[f][i] = 0.0
                    continue
                target = np.asarray(tdb * a['shares'][j], float)
                drawn = np.asarray(D['db'][i], float)
                # OWN-4. A STOCHASTIC ZERO MUST NOT ERASE ALLOCATED OPPORTUNITY.
                #
                # QB V1 draws its OWN level -- V from the team-dropback pool and
                # S from the share pool, DB = rint(V*S) -- which is the very
                # quantity D1 and QB3 already own. This composition then
                # reconciles the duplicate by division, and where QB V1's
                # independent level happens to be zero the ratio is undefined
                # and the allocated dropbacks were being dropped: measured at
                # 20 cells of 47,600, but up to 37.7 dropbacks in a single draw
                # -- an entire team's passing game for that draw.
                #
                # The repair borrows a donor draw FROM THE SAME ROW. Every rate
                # in qb2_lib.simulate is a row-level scalar, so any non-zero
                # draw of this row carries the same rates; scaling it to the
                # allocated target reproduces exactly what the composition
                # would have done had the level draw not been zero. Nothing is
                # fitted, nothing is clipped, no survivor is renormalised, and
                # the terminal-state identity survives because every field of
                # the donor scales by one factor.
                cons = QBACC.conserve_allocated_mass(
                    target, drawn,
                    [seed, int(season) * 100 + int(week),
                     int.from_bytes(str(pid).encode()[-8:], 'little'), 0x04])
                if cons.state is not State.PASS:
                    g['halted_at'] = 'qb_composition'
                    g['halt_reason'] = f'{pid} on {t}: {cons.detail[:220]}'
                    g['accounting']['qb_composition'] = \
                        f'{cons.state.value}[{cons.code}]'
                    return g, None
                src = cons.value
                repaired_cells += cons.evidence['cells_needing_repair']
                repaired_rows += int(bool(cons.evidence['cells_needing_repair']))
                at_risk = max(at_risk,
                              cons.evidence.get('max_single_draw_at_risk', 0.0))
                amp = QBACC.measure_composition_amplification(target,
                                                              drawn[src])
                amp_worst = max(amp_worst,
                                float(amp.evidence.get('factor_max') or 0.0))
                amp_stretched += int(amp.evidence.get('n_stretched') or 0)
                amp_cells += int(amp.evidence.get('n_cells') or 0)
                if amp.state is State.FAIL:
                    amp_fail += 1
                den = drawn[src]
                with np.errstate(divide='ignore', invalid='ignore'):
                    fac = np.where((target > 0) & (den > 0),
                                   target / np.maximum(den, 1e-9), 0.0)
                for f in QBV1.FIELDS:
                    scaled[f][i] = np.asarray(D[f][i], float)[src] * fac
                applied += 1
        qb = dict(qb, draws=scaled)
        g['qb_allocation_applied'] = applied
        # MASS CONSERVATION WAS NEVER THE PROPERTY IN DOUBT. This reported
        # PASS[QB_COMPOSITION_MASS_CONSERVED] while composing quarterbacks by
        # stretching a one-dropback donor draw up to the allocated level --
        # measured factor 59.85, producing a 49.14 passing-touchdown tail for a
        # passer whose raw draws max at 5. The verdict now names what actually
        # failed, and the mass statement is kept beside it rather than standing
        # in for it. The repair is R2 and is not authorised here.
        _mass = ('QB_COMPOSITION_MASS_CONSERVED' if not repaired_cells
                 else 'QB_COMPOSITION_ZERO_DRAW_REPAIRED')
        g['accounting']['qb_composition'] = (
            f'PASS[{_mass}]' if not amp_fail
            else f'FAIL[QB_COMPOSITION_RATE_FIDELITY_UNVERIFIED]')
        g['accounting']['qb_composition_mass'] = f'PASS[{_mass}]'
        g['accounting']['qb_composition_amplification'] = {
            'rows_failing_rate_fidelity': amp_fail,
            'cells_stretched': amp_stretched, 'cells_live': amp_cells,
            'frac_stretched': (round(amp_stretched / amp_cells, 6)
                               if amp_cells else None),
            'factor_max': round(amp_worst, 4),
            'condition': 'drawn < target -- parameter-free, nothing fitted',
            'repair': 'R2, pre-registered, not authorised in this task'}
        g['qb_composition_repair'] = {
            'cells_repaired': repaired_cells, 'rows_repaired': repaired_rows,
            'max_single_draw_dropbacks_at_risk': round(at_risk, 6),
            'mechanism': 'donor draw borrowed from the same row and scaled to '
                         'the allocated target; row-level rates are identical '
                         'across a row so the donor carries them',
            'no_survivor_renormalisation': True, 'nothing_fitted': True}
        # FEED THE GUARD ITS INPUT, at the one place that has both sides.
        # The scaling above zeroes a forecast row that the allocation does not
        # name. The REVERSE -- an allocation entry naming a quarterback QB V1
        # never forecast -- had no counterpart at all, and his share left the
        # system without a refusal. Measured on the real 2026 week-1 slate:
        # 35 quarterbacks, 5.13% of every team's dropbacks, MIA 33.8%.
        share_ok = QBACC.reconcile_allocation_share(
            {t: alloc[t] for t in teams if t in alloc},
            {t: [qb['rows'][i]['gsis_id'] for i in qb['index_by_team'].get(t, [])]
             for t in teams})
        g['accounting']['qb_allocation_share'] = \
            f'{share_ok.state.value}[{share_ok.code}]'
        g['accounting']['qb_allocation_share_evidence'] = {
            k: v for k, v in share_ok.evidence.items() if k != 'value'}
    if qb is not None:
        idx = qb['index_by_team']
        D = qb['draws']
        rows_by_team = {t: idx.get(t, []) for t in teams}
        # The team's QB rush opportunity in draw j is the SUM over that team's
        # quarterbacks, because the containment question is about the team's
        # carry budget, not about any one passer.
        qb_rush = np.stack([
            (D['rush_opp'][rows_by_team[t]].sum(0) if rows_by_team[t]
             else np.zeros(m)) for t in teams])
        for t in teams:
            for i in rows_by_team[t]:
                pid = qb['rows'][i]['gsis_id']
                mets = {}
                for fld, name in (('db', 'dropbacks'), ('att', 'attempts'),
                                  ('cmp', 'completions'),
                                  ('pyds', 'passing_yards'),
                                  ('ptd', 'passing_td'),
                                  ('int', 'interceptions'),
                                  ('sacks', 'sacks'),
                                  ('rush_opp', 'rush_opportunity'),
                                  ('ryds', 'rushing_yards'),
                                  ('rtd', 'rushing_td')):
                    mets[name] = PR.summarise(D[fld][i], QBV1.SPEC_VERSION,
                                              name, run_id)
                qb_records.append(PR.record(pid, 'QB', game_id, run_id, mets))
    rush_acc = ACC.reconcile_rushing(
        Sc, other_c, car_vol, C, rb_starts, rb_counts,
        rushing_td=rtd.value['rush_td'], rushing_yards=None,
        qb_rush_opportunity=qb_rush)
    g['accounting']['rushing'] = f'{rush_acc.state.value}[{rush_acc.code}]'
    g['accounting']['detail'] = {
        'receiving': {k: v for k, v in rec_acc.evidence.items()
                      if k not in ('value', 'other_mass_interpretation')},
        'rushing': {k: v for k, v in rush_acc.evidence.items()
                    if k not in ('value', 'qb_carry_measurement')}}
    chain = ACC.reconcile_chain(tv, ap, pa, tc, cv, td)
    g['accounting']['chain'] = f'{chain.state.value}[{chain.code}]'
    if qb is not None:
        # FEED THE DORMANT GUARD. reconcile_team's hard rush check has never
        # refused anything because no caller ever passed it a budget.
        rows_here = [qb['rows'][i] for t in teams
                     for i in qb['index_by_team'].get(t, [])]
        sel = [i for t in teams for i in qb['index_by_team'].get(t, [])]
        Dsub = {k: np.asarray(v)[sel] for k, v in qb['draws'].items()}
        qv = QBACC.reconcile_team_volume(
            Dsub, rows_here,
            team_dropback_draws={t: np.asarray(
                tv.value[('team_dropbacks_part', t)], float) for t in teams},
            team_carry_draws={t: np.asarray(
                tv.value[('team_carries', t)], float) for t in teams},
            # Under R2 the level is an integer apportionment, so the dropback
            # identity is checked as exact EQUALITY against rint(budget)
            # instead of the incumbent's <= against the float budget. Stricter,
            # and declared in the R2 pre-registration before it was measured.
            integer_level=bool(qb.get('r2')))
        g['accounting']['qb_team_volume'] = f'{qv.state.value}[{qv.code}]'
        # FEED THE THIRD DORMANT GUARD. reconcile_cross_layer has been written,
        # correct and DEFERRED since R3 because no caller ever supplied the
        # receiving draws. They are in this run. Measured on the panel, team
        # passing yards and team receiving yards are the SAME quantity:
        # r = 0.9996, mean |difference| 0.26 yards, exact in 3,154 of 3,230
        # team-games, the residue being the named lateral exception.
        if c3 is not None:
            # C3, SECOND HALF: THE PASSER'S LINE IS A CREDIT FROM THE EVENT.
            # Completions, passing yards and passing touchdowns are no longer
            # drawn independently by QB V1 -- they ARE the receiving totals,
            # attributed back to the quarterbacks on the targeted-throw share.
            # One event, generated once, credited to both sides.
            rngc = np.random.default_rng(
                [seed, season * 100 + week,
                 int(SEEDS.game_component(game_id).value), 0xC301])
            cred_ok = True
            for k, t in enumerate(teams):
                sel = list(qb['index_by_team'].get(t, []))
                ri = [i for i, q in enumerate(recv) if q['team'] == t]
                if not sel or not ri:
                    continue
                A = np.stack([np.asarray(qb['draws']['att'][i], float)
                              for i in sel])
                # These layers return ROW-INDEXED arrays, not player-keyed
                # dicts; `ri` already holds the row indices for this team.
                R = np.asarray(cv.value['receptions'], float)[ri].sum(0)
                Y = np.asarray(cv.value['receiving_yards'], float)[ri].sum(0)
                TD = np.asarray(td.value['td'], float)[ri].sum(0)
                cr = SP.credit_to_passers(A, R, Y, TD, rngc)
                if cr.state is not State.PASS:
                    g['accounting']['shared_pass_credit'] = \
                        f'{cr.state.value}[{cr.code}]'
                    cred_ok = False
                    break
                for n, i in enumerate(sel):
                    qb['draws']['cmp'][i] = cr.value['cmp'][n]
                    qb['draws']['pyds'][i] = cr.value['pyds'][n]
                    qb['draws']['ptd'][i] = cr.value['ptd'][n]
            if cred_ok:
                g['accounting']['shared_pass_credit'] = \
                    'PASS[PASSING_LINE_CREDITED_FROM_THE_RECEIVING_EVENT]'
                c3['passer_line_owner'] = ('the receiving event; QB V1 no '
                                           'longer draws cmp/pyds/ptd')
            g['c3'] = c3

        xl = {}
        for t in teams:
            qi = [n for n, tt in enumerate(
                [qb['rows'][i]['team'] for tt2 in teams
                 for i in qb['index_by_team'].get(tt2, [])]) if tt == t]
            sel_t = [i for i in qb['index_by_team'].get(t, [])]
            ri = [i for i, tt in enumerate(
                [q['team'] for q in recv]) if tt == t]
            if not sel_t or not ri:
                continue
            # The guard compares TEAM TOTALS -- it forms py.sum(0) - ry.sum(0)
            # -- but enforces row alignment, and a QB room and a receiver room
            # have different row counts. Summing to (1, m) first is
            # mathematically identical to what the guard computes and satisfies
            # its shape contract honestly. The guard is NOT loosened.
            Dt = {'pyds': np.stack([np.asarray(qb['draws']['pyds'][i], float)
                                    for i in sel_t]).sum(0)[None, :],
                  'ptd': np.stack([np.asarray(qb['draws']['ptd'][i], float)
                                   for i in sel_t]).sum(0)[None, :]}
            RY = np.stack([cv.value['receiving_yards'][i]
                           for i in ri]).sum(0)[None, :]
            RT = np.stack([td.value['td'][i] for i in ri]).sum(0)[None, :]
            o = QBACC.reconcile_cross_layer(Dt, receiving=RY, receiving_td=RT)
            xl[t] = {'state': f'{o.state.value}[{o.code}]',
                     **{k: v for k, v in o.evidence.items()
                        if k in ('violating_draws', 'td_violating_draws',
                                 'worst_abs_residual', 'n_draws')}}
            xl[t]['mean_abs_yard_residual'] = float(
                np.abs(Dt['pyds'].sum(0) - RY.sum(0)).mean())
            xl[t]['mean_team_passing_yards'] = float(Dt['pyds'].sum(0).mean())
            xl[t]['corr_passing_receiving'] = (
                float(np.corrcoef(Dt['pyds'].sum(0), RY.sum(0))[0, 1])
                if Dt['pyds'].sum(0).std() > 0 and RY.sum(0).std() > 0
                else None)
        g['accounting']['cross_layer'] = xl
        g['accounting']['detail']['qb_team_volume'] = {
            k: v for k, v in qv.evidence.items() if k != 'value'}

    # ---- player records --------------------------------------------------
    rb_index = {p: k for k, p in enumerate(rb_ids)}
    records = []
    for k, q in enumerate(recv):
        pid = q['gsis_id']
        mets = {
            'appearance': PR.summarise(ap.value[pid], LY.SPEC['appearance'],
                                       'appearance', run_id),
            'participation': PR.summarise(pa.value[pid],
                                          LY.SPEC['participation'],
                                          'participation', run_id),
            'targets': PR.summarise(T[k], LY.SPEC['targets_carries'],
                                    'targets', run_id),
            'receptions': PR.summarise(cv.value['receptions'][k],
                                       LY.SPEC['receiving_conversion'],
                                       'receptions', run_id),
            'receiving_yards': PR.summarise(cv.value['receiving_yards'][k],
                                            LY.SPEC['receiving_conversion'],
                                            'receiving_yards', run_id),
            'receiving_td': PR.summarise(td.value['td'][k],
                                         LY.SPEC['td_layer'],
                                         'receiving_td', run_id),
        }
        if q['position'] in CARRY_POS:
            r = rb_index[pid]
            mets['carries'] = PR.summarise(C[r], LY.SPEC['targets_carries'],
                                           'carries', run_id)
            mets['rushing_td'] = PR.summarise(rtd.value['rush_td'][r],
                                              LY.SPEC['rushing_td'],
                                              'rushing_td', run_id)
            mets['rushing_yards'] = PR.absent(
                'rushing_yards',
                'RUSHING_CONVERSION_CONTROL_UNDEFINED: no governed frozen '
                'control exists for carry -> rushing yards. Three scientific '
                'decisions are open; see '
                'nfl/production/nonqb/rushing_inventory.json.',
                run_id, open_decisions=list(LY.RUSHING_CONVERSION_DECISIONS))
        records.append(PR.record(pid, q['position'], game_id, run_id, mets))
    records.extend(qb_records)
    g['n_records'] = len(records)
    g['n_qb_records'] = len(qb_records)
    v = PR.validate(records)
    g['player_contract'] = f'{v.state.value}[{v.code}]'
    g['player_contract_evidence'] = {k: x for k, x in v.evidence.items()
                                     if k != 'value'}
    pub = LY.assert_publishable(ap, pa, tc, car, cv, td, rtd)
    g['publication_gate'] = f'{pub.state.value}[{pub.code}]'
    g['test_only'] = bool(test_only or ap.evidence.get('test_only'))
    # The IDENTITY of every draw row travels with the draws. A covariance
    # diagnostic needs to know which player and which team a row is, and
    # reconstructing that from a parallel list is how a mismatch happens.
    return g, {'records': records, 'draws': {
        'targets': T, 'carries': C, 'receptions': cv.value['receptions'],
        'receiving_yards': cv.value['receiving_yards'],
        'receiving_td': td.value['td'], 'rush_td': rtd.value['rush_td']},
        'accounting': (rec_acc, rush_acc),
        'index': {'recv_ids': ids, 'recv_pos': pos,
                  'recv_team': [q['team'] for q in recv],
                  'rb_ids': rb_ids, 'rb_team': [q['team'] for q in rb],
                  'teams': list(teams)},
        # The ALLOCATION LAYER's own outputs, so a study can re-run the
        # conversion chain on a different opportunity budget without
        # reimplementing the layers that produced the competition. Additive:
        # nothing downstream reads these and B0 is unchanged by their presence.
        'allocation': {'share': S, 'other': other, 'starts': starts,
                       'counts': counts, 'tc': tc,
                       'team_target_volume': tgt_vol},
        'team_draws': {t: {k: np.asarray(tv.value[(k, t)], float)
                           for k in TV.METRICS} for t in teams},
        'qb': ({'ids': [qb['rows'][i]['gsis_id']
                        for t in teams for i in qb['index_by_team'].get(t, [])],
                'team': [t for t in teams
                         for i in qb['index_by_team'].get(t, [])],
                'draws': {f: np.stack([np.asarray(qb['draws'][f][i], float)
                                       for t in teams
                                       for i in qb['index_by_team'].get(t, [])])
                          for f in QBV1.FIELDS}}
               if qb is not None else None)}
