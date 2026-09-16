"""Rushing mass with a resolvable owner gets one; the rest stays unnamed.

TWO HALVES AND THEY ARE DIFFERENT CLAIMS. The allocation must conserve
exactly -- every kneel, wr and te carry the category held goes to a named
player in the SAME draw, never a share of a mean. And what is left unnamed
must be left unnamed ON PURPOSE: fringe and the unmodelled-back pool are not
allocated because their owners are punters, defensive backs, and players with
no position in any source held. A test that only checked "unnamed mass went
down" would be satisfied by inventing a name, which is the worse failure.

THE FROZEN ARM MUST NOT MOVE. This is a closure change with its own candidate
identity, so R9_W1P carries no gadget layer and this asserts that too.

ROW IDENTITY COMES FROM THE MANIFEST AND THE ARTIFACT, never from board.json:
the allocation deals to the complete lawful participant universe, which is
wider than the displayed board. Three DET-BUF receivers took gadget carries
while appearing on no display row -- reading their team from board.json
returned None and made conservation look broken when it was exact.
"""
import glob
import json
import os
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

_P, _F = [], []
CATS = ('kneel', 'te', 'wr')


def ck(name, cond, detail=''):
    (_P if cond else _F).append(name)
    print(('PASS ' if cond else 'FAIL ') + name
          + ((' :: ' + detail) if detail else ''))


def structural():
    from nfl.production import candidate_mode as CM
    from nfl.production.nonqb import gadget_rush as G

    o = CM.resolve(CM.V1_CANDIDATE_R9_W1P_G)
    ck('new_candidate_resolves', o.state.name == 'PASS', o.code)
    ck('new_candidate_sets_the_flag',
       bool(o.value['flags'].get('allocate_gadget_rush')))
    base = CM.resolve(CM.V1_CANDIDATE_R9_W1P)
    ck('the_arm_it_descends_from_is_untouched',
       not base.value['flags'].get('allocate_gadget_rush'),
       'a closure change may never be an edit to a frozen arm')
    ck('new_candidate_carries_its_own_component',
       any(c.get('component') == 'R9_W1P_G'
           for c in o.value['components']))
    ck('not_promoted', not o.value.get('promoted'))

    ck('fringe_is_declared_unallocated', 'fringe' in G.NOT_ALLOCATED)
    ck('unmodelled_pool_is_declared_unallocated',
       'unmodelled_back_pool' in G.NOT_ALLOCATED)
    ck('alpha_is_recorded_per_category',
       set(G.ALPHA) == set(G.CATEGORIES), str(G.ALPHA))

    fit = json.loads((REPO / 'nfl' / 'production' / 'nonqb'
                      / 'GADGET_RUSH_FIT.json').read_text())
    ck('fit_artifact_records_the_withdrawn_criterion',
       'withdrawn_criterion' in fit,
       'the moment-match that returned the grid boundary')
    for c in G.CATEGORIES:
        a = fit['alpha_fit'][c]
        ck(f'{c}_alpha_optimum_is_interior', a['interior_optimum'],
           f"alpha={a['alpha']} on grid {a['grid'][0]}..{a['grid'][-1]}")
        ck(f'{c}_alpha_in_code_matches_the_fit', G.ALPHA[c] == a['alpha'],
           f"code {G.ALPHA[c]} fit {a['alpha']}")
        ck(f'{c}_no_carry_went_to_an_owner_outside_the_pool',
           a['owner_not_in_pool'] == 0, str(a['owner_not_in_pool']))
    ck('residual_concentration_gap_is_reported_not_closed',
       'residual_under_the_fitted_alpha' in fit)


def _newest(layer, candidate_dir_fragment):
    best = None
    for man in glob.glob(str(REPO / 'nfl/research/live/*/*/*/'
                             'player_draws_manifest.json')):
        if candidate_dir_fragment not in man:
            continue
        try:
            m = json.load(open(man))
        except (OSError, ValueError):
            continue
        if layer and layer not in (m.get('layers') or {}):
            continue
        t = os.path.getmtime(man)
        if best is None or t > best[0]:
            best = (t, os.path.dirname(man))
    return best[1] if best else None


def numeric(run_dir):
    m = json.load(open(os.path.join(run_dir, 'player_draws_manifest.json')))
    z = np.load(os.path.join(run_dir, 'player_draws.npz'), allow_pickle=True)
    art = json.load(open(os.path.join(run_dir, 'forecast_artifact.json')))
    rid = {k: v['row_ids'] for k, v in m['layers'].items()}
    gm = (art.get('gadget_rush') or {}).get('rows') or {}
    g = rid['gadget_rush']
    n = int(m['n_draws'])

    ck('every_gadget_row_is_named',
       all(gm.get(p, {}).get('name_resolved') for p in g),
       str([p for p in g if not gm.get(p, {}).get('name_resolved')]))
    ck('every_gadget_row_has_a_team',
       all(gm.get(p, {}).get('team') for p in g))
    ck('gadget_shares_the_draw_index',
       all(z[f'gadget_rush__{c}'].shape[1] == n
           for c in m['layers']['gadget_rush']['metrics']))

    cr = rid['rush_category']
    before = after = total = 0.0
    for t in cr:
        ti = cr.index(t)
        rows = [i for i, p in enumerate(g) if gm[p]['team'] == t]
        for c in CATS:
            cat = z[f'rush_category__{c}'][ti]
            al = (z[f'gadget_rush__{c}'][rows].sum(0) if rows
                  else np.zeros(n))
            ck(f'{t}/{c} every_carry_allocated_in_the_same_draw',
               int((al == cat).sum()) == n,
               f'{int((al == cat).sum())}/{n}; cat {cat.mean():.4f} '
               f'alloc {al.mean():.4f}')
            before += float(cat.mean())
        fr = z['rush_category__fringe'][ti]
        pool = z['rush_player_pool__unmodelled_back_pool'][
            rid['rush_player_pool'].index(t)]
        tc = z['team_volume__team_carries'][rid['team_volume'].index(t)]
        after += float((fr + pool).mean())
        before += float((fr + pool).mean())
        total += float(tc.mean())
        # A KNEEL IS A QUARTERBACK'S. Not a rule the allocator may bend.
        kn_rows = [i for i, p in enumerate(g)
                   if gm[p]['team'] == t and z['gadget_rush__kneel'][i].sum()]
        ck(f'{t} only_quarterbacks_kneel',
           all(gm[g[i]]['position'] == 'QB' for i in kn_rows),
           str([(gm[g[i]]['name'], gm[g[i]]['position']) for i in kn_rows]))
        ck(f'{t} only_receivers_take_wr_carries',
           all(gm[g[i]]['position'] == 'WR' for i in range(len(g))
               if gm[g[i]]['team'] == t and z['gadget_rush__wr'][i].sum()))
        ck(f'{t} only_tight_ends_take_te_carries',
           all(gm[g[i]]['position'] == 'TE' for i in range(len(g))
               if gm[g[i]]['team'] == t and z['gadget_rush__te'][i].sum()))
        ck(f'{t} nobody_gets_a_fractional_carry',
           all(bool(np.allclose(z[f'gadget_rush__{c}'][rows],
                                np.rint(z[f'gadget_rush__{c}'][rows])))
               for c in CATS for _ in (0,)) if rows else True)

    ck('unnamed_mass_fell', after < before,
       f'{100 * before / total:.2f}% -> {100 * after / total:.2f}% of carries')
    # AND IT DID NOT FALL TO ZERO, WHICH IS THE POINT.
    ck('fringe_and_the_pool_are_still_unnamed', after > 0,
       f'{100 * after / total:.2f}% remains, deliberately: punters, defensive '
       f'backs and rushers with no position in any source held')


def frozen_arm_unchanged():
    run = _newest(None, 'V1_CANDIDATE_R9_W1P/')
    if not run:
        print('NOT_EXECUTED frozen_arm_carries_no_gadget_layer :: no sealed '
              'R9_W1P run in the tree to compare against')
        return
    m = json.load(open(os.path.join(run, 'player_draws_manifest.json')))
    ck('frozen_arm_carries_no_gadget_layer',
       'gadget_rush' not in (m.get('layers') or {}),
       os.path.relpath(run, REPO))


def main():
    print('--- structural ---')
    structural()
    print('--- frozen arm ---')
    frozen_arm_unchanged()
    print('--- numeric ---')
    run = _newest('gadget_rush', 'R9_W1P_G')
    if not run:
        print('BLOCKED GADGET_NO_SEALED_RUN cause=DATA :: no sealed run '
              'carries a gadget_rush layer, so the allocation has nothing to '
              'be checked on. BLOCKED is not a pass.')
        print(f'\n{len(_P)} passed, {len(_F)} failed (structural only)')
        return 1 if _F else 0
    print(f'run: {os.path.relpath(run, REPO)}')
    numeric(run)
    print(f'\n{len(_P)} passed, {len(_F)} failed')
    if _F:
        print('FAILED: ' + ', '.join(_F))
    return 1 if _F else 0


if __name__ == '__main__':
    raise SystemExit(main())
