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


def qb_slate(season, week, qb_players, m=200, seed=20260908) -> Outcome:
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
    sl = QBV1.slate_prospective(season, week, qb_players)
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
                                            'index_by_team': dict(by_team)},
                      spec_version=QBV1.SPEC_VERSION, n_qb=len(rows),
                      qb_frame_sha256=fh.value,
                      warnings=[f'known limitation: {k}'
                                for k in QBV1.KNOWN_LIMITATIONS])


def run_game(season, week, game_id, players, fits, m=200, seed=20260908,
             injuries_rows=None, test_only=False, kickoff_utc=None,
             run_id='rehearsal', qb=None):
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

    tv = TV.forecast(season, week, list(teams), m=m, seed=seed)
    g['layers']['team_environment'] = f'{tv.state.value}[{tv.code}]'
    if tv.state is not State.PASS:
        g['halted_at'] = 'team_environment'
        return g, None

    fixture = None
    if injuries_rows is not None:
        fixture = {'_test_only': True, 'practice_progression': {},
                   'teammate_availability': {},
                   'injuries_rows': injuries_rows}
    ap = LY.appearance(season, week, recv, fixture=fixture, m=m, seed=seed,
                       teams=teams, kickoff_utc=kickoff_utc)
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
                            fits['p4c_params_targets'].value, m=m, seed=seed)
    g['layers']['targets_carries'] = f'{tc.state.value}[{tc.code}]'
    if tc.state is not State.PASS:
        g['halted_at'] = 'targets_carries'
        return g, None
    S, other = tc.value['share'], tc.value['other']
    tgt_vol = np.stack([tv.value[('team_targets', t)] for t in teams])
    T = S * np.repeat(tgt_vol, counts, axis=0)

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
        fits['p4c_params_carries'].value, m=m, seed=seed)
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
        receiving_yards=cv.value['receiving_yards'])
    g['accounting']['receiving'] = f'{rec_acc.state.value}[{rec_acc.code}]'
    qb_rush, qb_records = None, []
    if qb is not None and qb.get('allocation'):
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
                target = tdb * a['shares'][j]
                drawn = np.asarray(D['db'][i], float)
                with np.errstate(divide='ignore', invalid='ignore'):
                    fac = np.where(drawn > 0, target / np.maximum(drawn, 1e-9),
                                   0.0)
                for f in QBV1.FIELDS:
                    scaled[f][i] = np.asarray(D[f][i], float) * fac
                applied += 1
        qb = dict(qb, draws=scaled)
        g['qb_allocation_applied'] = applied
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
                tv.value[('team_carries', t)], float) for t in teams})
        g['accounting']['qb_team_volume'] = f'{qv.state.value}[{qv.code}]'
        # FEED THE THIRD DORMANT GUARD. reconcile_cross_layer has been written,
        # correct and DEFERRED since R3 because no caller ever supplied the
        # receiving draws. They are in this run. Measured on the panel, team
        # passing yards and team receiving yards are the SAME quantity:
        # r = 0.9996, mean |difference| 0.26 yards, exact in 3,154 of 3,230
        # team-games, the residue being the named lateral exception.
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
