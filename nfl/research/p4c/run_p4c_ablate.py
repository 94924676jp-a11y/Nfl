"""P4C ablations: WHERE does the calibration failure come from, and what is
each piece of oracle information worth?

P4B failed the randomised PIT in 18 of 20 target-seasons and P4C has to say why
rather than guess. Each variant replaces exactly ONE component of the chosen
eligible system with its oracle value and re-measures. Everything here is
DIAGNOSTIC: no variant is eligible, none is offered to selection, and the
module never writes a system into p4c_results.json.
"""
import collections, json, os, sys, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p4c_lib as L                                            # noqa: E402
import p4c_build as B                                          # noqa: E402
from run_p4c import groups_of                                  # noqa: E402

BASE = {'simplex': 'C', 'occupancy': 'C'}


def main():
    t0 = time.time()
    rows = B.load_panel()
    vol = B.load_volume()
    pa = B.appearance(rows)
    OUT = {}
    for cls, c in L.CLASSES.items():
        mode = c['mode']
        skey, ykey = c['share'], c['y']
        sub = B.prepare_class(rows, cls)
        res = {}
        for ev in L.EVAL:
            store = vol.get((c['den'], ev))
            if store is None:
                continue
            par = B.fit_params(sub, cls, ev, rows)
            te = [r for r in sub if r['season'] == ev and r.get(skey) is not None
                  and id(r) in pa and (r.get('f_n_prior') or 0) >= 1
                  and r['_C'] is not None
                  and (r['team'], r['ord']) in store['index']]
            te.sort(key=lambda r: (r['ord'], r['team'], r['gsis_id']))
            if len(te) < 200:
                continue
            n = len(te)
            starts, counts, gkeys = groups_of(te)
            G = len(starts)
            y = np.array([r[ykey] for r in te], float)
            C = np.array([r['_C'] for r in te], np.float32)
            positions = [r['position'] for r in te]
            p_app = np.array([pa[id(r)] for r in te], np.float32)
            S_real = np.array([r[skey] for r in te], np.float32)
            A_real = np.array([1.0 if r['appeared'] else 0.0 for r in te], np.float32)
            ti = np.array([store['index'][(r['team'], r['ord'])] for r in te])
            Tb = store['B'][ti]
            Tr = np.repeat(store['realized'][ti][:, None], L.M_DRAWS, axis=1)
            rng = np.random.default_rng(L.SEED + 1009)
            Ad = (rng.random((n, L.M_DRAWS), np.float32) < p_app[:, None])
            Ar = np.repeat(A_real[:, None], L.M_DRAWS, axis=1).astype(bool)
            mass = B.mass_draws('C', par, G, L.M_DRAWS,
                                np.random.default_rng(L.SEED + 5002))
            avail = (1.0 - mass) if mode == 'simplex' else mass
            Wp = B.gen_weights('C', C, positions, par, cls, n, L.M_DRAWS,
                               np.random.default_rng(L.SEED + 3034))
            Wr = np.repeat(S_real[:, None], L.M_DRAWS, axis=1)

            def run(W, A, T):
                S, _o, _b = L.allocate(W, A, starts, counts, 'occupancy', avail)
                return (T * S).astype(np.float32)

            variants = {}
            variants['base'] = run(Wp, Ad, Tb)
            variants['oracle_team_total'] = run(Wp, Ad, Tr)
            variants['oracle_appearance'] = run(Wp, Ar, Tb)
            variants['oracle_all_shares'] = run(Wr, Ad, Tb)
            # ---- own share only: NO renormalisation, the P4B PR arm ---------
            variants['oracle_own_share_unallocated'] = (
                Tb * (Wr * Ad)).astype(np.float32)
            # ---- teammate vector only: teammates realised, focal projected --
            # denom_i = sum_j W_j A_j - S_real_i A_i + C_i A_i, computed in O(n)
            WrA = Wr * Ad
            tot = L.gexp(L.gsum(WrA, starts), counts)
            den = tot - WrA + C[:, None] * Ad
            Sti = np.divide(avail.repeat(counts, axis=0) * (C[:, None] * Ad),
                            den, out=np.zeros((n, L.M_DRAWS), np.float32),
                            where=den > 1e-9)
            variants['oracle_teammate_vector'] = (Tb * Sti).astype(np.float32)
            del WrA, tot, den, Sti
            variants['oracle_everything'] = run(Wr, Ar, Tr)

            d = {}
            base_mean = variants['base'].mean(axis=1)
            # MULTIPLICATIVE, not additive. An additive shift with a clip at
            # zero destroys the point mass at zero -- which is 28-31% of the
            # rows -- and the randomised PIT then measures that destruction
            # rather than the bias. The first version of this variant did
            # exactly that and produced chi-squared values in the thousands.
            # A rescale leaves every exact zero exactly zero.
            shift = float(y.mean() / max(base_mean.mean(), 1e-9))
            variants['base_debiased_oracle_rescale'] = (
                variants['base'] * shift).astype(np.float32)
            for k, Y in variants.items():
                sc = L.score(Y, y, np.random.default_rng(L.SEED + 31))
                d[k] = {'crps': sc['crps'], 'mae': sc['mae'], 'bias': sc['bias'],
                        'rpit_chi2': sc['randomised_pit']['chi2'],
                        'cov90': sc['coverage']['90']['coverage'],
                        'log_score': sc['log_score'],
                        'floor_rate': sc['floor_rate']}
            d['_debias_shift_applied'] = shift

            # ---- subgroups on the base system -------------------------------
            crps_base = L.crps_samples(variants['base'], y)
            Ya = (Tb * (B.gen_weights('A', C, positions, par, cls, n,
                                      L.M_DRAWS,
                                      np.random.default_rng(L.SEED + 3000))
                        * Ad)).astype(np.float32)
            crps_A = L.crps_samples(Ya, y)
            def pb(p):
                return ('p<0.50' if p < .5 else 'p 0.50-0.80' if p < .8
                        else 'p 0.80-0.95' if p < .95 else 'p>=0.95')
            iq = [r.get('info_quality') or 'UNKNOWN' for r in te]
            rc = ['role_change' if r.get('role_change') == 1 else 'stable'
                  for r in te]
            splits = {
                'appearance_uncertainty': [pb(p) for p in p_app],
                'role_stability': rc,
                'information_quality': iq,
                'role_change_x_info': [f'{a}|{b}' for a, b in zip(rc, iq)],
                'position': positions,
            }
            sg = {}
            for sname, lab in splits.items():
                lab = np.array(lab)
                dd = {}
                for u in sorted(set(lab.tolist())):
                    m = lab == u
                    if m.sum() < 60:
                        continue
                    Ysub = variants['base'][m]
                    dd[u] = {
                        'n': int(m.sum()),
                        'crps_A': float(crps_A[m].mean()),
                        'crps_base': float(crps_base[m].mean()),
                        'rpit_chi2': L.pit_stats(L.rpit(
                            Ysub, y[m], np.random.default_rng(L.SEED + 31)))['chi2'],
                        'mae': float(np.abs(y[m] - Ysub.mean(axis=1)).mean()),
                        'appearance_rate': float(A_real[m].mean()),
                    }
                sg[sname] = dd
            res[ev] = {'n': n, 'variants': d, 'subgroups': sg,
                       'base_system': BASE[mode]}
            v = d
            print(f'  {cls:11s} {ev} rPIT chi2  base={v["base"]["rpit_chi2"]:8.1f} '
                  f'+T={v["oracle_team_total"]["rpit_chi2"]:8.1f} '
                  f'+App={v["oracle_appearance"]["rpit_chi2"]:8.1f} '
                  f'+Teammates={v["oracle_teammate_vector"]["rpit_chi2"]:8.1f} '
                  f'+Shares={v["oracle_all_shares"]["rpit_chi2"]:8.1f} '
                  f'+Debias={v["base_debiased_oracle_rescale"]["rpit_chi2"]:8.1f} '
                  f'+All={v["oracle_everything"]["rpit_chi2"]:8.1f}')
            OUT[cls] = res
            json.dump(OUT, open(f'{HERE}/p4c_ablation.json', 'w'), indent=1)
        OUT[cls] = res
        json.dump(OUT, open(f'{HERE}/p4c_ablation.json', 'w'), indent=1)
    print(f'done in {time.time()-t0:.0f}s -> p4c_ablation.json')


if __name__ == '__main__':
    main()
