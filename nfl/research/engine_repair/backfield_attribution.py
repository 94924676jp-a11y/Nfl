"""Ten-stage numeric attribution + ablations for the NYG backfield.
PRE-KICKOFF EVIDENCE ONLY. No NYG@LAR result is read anywhere."""
import sys, json, collections, statistics
sys.path.insert(0,'/home/user/nfl')
import numpy as np
from nfl.production.nonqb import p4c_params as P4, role_prior as RP
from nfl.production.universe import player_universe as PU, role_state as RS, usage_vintage as UV
from nfl.production.review import dossier as DOS
from nfl.product import board as PBRD
from nfl.production.nonqb import vintage_selector as VS
from sportsplatform.governance.outcome import State

SEASON, WEEK = 2026, 2
CUT_ORD = SEASON*100+WEEK
CUT = '2026-09-21T23:05:00Z'
GAME = '2026_02_NYG_LA'
BACKS = {'00-0040715':'Cam Skattebo','00-0039384':'Tyrone Tracy Jr.',
         '00-0035250':'Devin Singletary','00-0036893':'Najee Harris'}

P4.ensure_artifacts()
import p4c_build as PB, p4c_lib as PL
PB.P4B=str(P4._DIR)
panel = PB.load_panel()

# --- stages 1-2: measured 2026 participation and usage ---------------------
u=PU.build(SEASON,WEEK,GAME,CUT); urows=u.value['rows'] if isinstance(u.value,dict) else u.value
us=UV.usage_season(SEASON,CUT,before_week=WEEK); usage=us.value if us.state.name=='PASS' else {}
ro=RS.assign(urows,season=SEASON,week=WEEK,usage_rows=usage)
roles={r['gsis_id']:r for r in (ro.value['rows'] if isinstance(ro.value,dict) else ro.value)}
uby={r['gsis_id']:r for r in urows}

# --- stage 3: valid offensive depth, production map ------------------------
dro = PBRD.depth_rank_outcome(SEASON, WEEK, ['NYG','LA'],
                              as_of=VS.as_of_cut('2026-09-22T00:15:00Z', CUT))
dr_full = dro.value if dro.state is State.PASS else {}
dr = {k: v[1] for k, v in dr_full.items()}     # production's `dr[k] = v[1]`

# --- stages 4-5: role prior and tier ---------------------------------------
rp_carries = RP.build(panel, 'carry_share', PL.CLASSES['carries']['pos'], CUT_ORD).value
players=[{'gsis_id':r['gsis_id'],'position':r['roster_position'],'team':r['team']}
         for r in urows if r.get('roster_position')]
at = RP.assign_tiers([q for q in players if q['position']!='QB'], rp_carries, depth_rank=dr)
tiers, basis, detail = at['tier'], at['basis'], at['detail']

# --- stage 6: C, the opportunity centre ------------------------------------
skey=PL.CLASSES['carries']['share']
hist=collections.defaultdict(list)
for r in sorted(panel,key=lambda x:(x['ord'],x['team'],x['gsis_id'])):
    if r['position'] not in PL.CLASSES['carries']['pos'] or r['ord']>=CUT_ORD: continue
    v=r.get(skey)
    if v is None or not r['appeared']: continue
    hist[r['gsis_id']].append(float(v))

def measured_share(pid):
    ev=(roles.get(pid,{}).get('evidence',{}).get('current_season_usage') or {})
    return ev.get('carry_share')

def C_of(pid,pos,tier,use_hist=True,use_tier=True,measured=None):
    """`measured` is the counterfactual only: None = as production runs it,
    'only' = the 2026 measured share standing alone at n=1,
    'append' = the 2026 measured share appended to the stale panel history."""
    h = list(hist.get(pid) or []) if use_hist else []
    if measured == 'only':
        m = measured_share(pid)
        h = [m] if m is not None else []
    elif measured == 'append':
        m = measured_share(pid)
        if m is not None: h = h + [m]
    t = tier if use_tier else RP.MAX_TIER
    return RP.weight(pid,pos,PB.ewma(h) if h else None,len(h) if h else 0,t,rp_carries)

# --- stage 10: final carries from the sealed draws -------------------------
po=DOS.read_projection('nfl/research/showdown_fixture/run_post/d90d80c0b4a7f95e')
proj=po.value['per_player']

print('PANEL COVERAGE: ord', min(r["ord"] for r in panel), '->',
      max(r["ord"] for r in panel), '| 2026 rows:',
      sum(1 for r in panel if r['ord']>=202601))
print()
hdr=f'{"stage":<34}' + ''.join(f'{n.split()[-1][:11]:>13}' for n in BACKS.values())
print(hdr); print('-'*len(hdr))
def line(label, fn):
    print(f'{label:<34}' + ''.join(f'{fn(p):>13}' for p in BACKS))
line('1 measured snap share 2026',
     lambda p: f'{(roles.get(p,{}).get("evidence",{}).get("current_season_snaps",{}) or {}).get("mean_offense_pct")}')
line('2 measured carries 2026',
     lambda p: f'{(roles.get(p,{}).get("evidence",{}).get("current_season_usage",{}) or {}).get("carries")}')
line('2b measured carry share 2026',
     lambda p: f'{round((roles.get(p,{}).get("evidence",{}).get("current_season_usage",{}) or {}).get("carry_share") or 0,4)}')
line('3 offensive depth rank (prod)', lambda p: f'{dr_full.get(p)}')
line('4 tier', lambda p: f'{tiers.get(p)}')
line('4b tier basis', lambda p: f'{(basis.get(p) or "")[:12]}')
line('5 panel rows (pre-2026 only)', lambda p: f'{len(hist.get(p,[]))}')
line('5b own ewma (2025 and older)',
     lambda p: f'{round(PB.ewma(hist[p]),4) if hist.get(p) else "None"}')
line('5c tier mean anchor',
     lambda p: f'{round(rp_carries["tier_mean"].get(RP._tier_label("RB",tiers.get(p,RP.MAX_TIER)),float("nan")),4)}')
line('5d shrinkage w',
     lambda p: f'{round(len(hist.get(p,[]))/(len(hist.get(p,[]))+rp_carries["k"].get("RB",statistics.mean(rp_carries["k"].values()))),4)}')
line('6 C = opportunity centre',
     lambda p: f'{round(C_of(p,"RB",tiers.get(p,RP.MAX_TIER)),6)}')
line('10 final carries (sealed)',
     lambda p: f'{round(proj.get(p,{}).get("carries",{}).get("mean",float("nan")),4)}')

print('\nABLATIONS on C (stage 6). Same code path, one input removed.')
abl=[('as run                      ', dict(use_hist=True,use_tier=True)),
     ('remove historical prior     ', dict(use_hist=False,use_tier=True)),
     ('remove depth prior (tier)   ', dict(use_hist=True,use_tier=False)),
     ('prior-only (no tier)        ', dict(use_hist=True,use_tier=False)),
     ('tier-only (no history)      ', dict(use_hist=False,use_tier=True)),
     ('COUNTERFACTUAL measured-only', dict(measured='only')),
     ('COUNTERFACTUAL panel+measured', dict(measured='append'))]
print(f'{"ablation":<30}'+''.join(f'{n.split()[-1][:11]:>13}' for n in BACKS.values())+'   inversion?')
for name,kw in abl:
    vals={p:C_of(p,'RB',tiers.get(p,RP.MAX_TIER),**kw) for p in BACKS}
    inv = vals['00-0039384'] > vals['00-0040715']
    print(f'{name:<30}'+''.join(f'{round(vals[p],6):>13}' for p in BACKS)+
          f'   {"TRACY>SKATTEBO" if inv else "correct order"}')
json.dump({'artifact':'BACKFIELD_CARRY_ATTRIBUTION','pre_kickoff_only':True,'panel_max_ord':max(r['ord'] for r in panel),
           'panel_2026_rows':sum(1 for r in panel if r['ord']>=202601),
           'tiers':{BACKS[p]:tiers.get(p) for p in BACKS},
           'basis':{BACKS[p]:basis.get(p) for p in BACKS},
           'detail':{BACKS[p]:detail.get(p) for p in BACKS},
           'C':{BACKS[p]:C_of(p,'RB',tiers.get(p,RP.MAX_TIER)) for p in BACKS},
           'panel_rows':{BACKS[p]:len(hist.get(p,[])) for p in BACKS},
           'final_carries':{BACKS[p]:proj.get(p,{}).get('carries',{}).get('mean') for p in BACKS}},
          open('nfl/research/engine_repair/BACKFIELD_ATTRIBUTION.json','w'),indent=1,default=str)
