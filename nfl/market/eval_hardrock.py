import sys, json, csv, pathlib
import numpy as np
sys.path.insert(0,'/home/user/nfl')
sys.path.insert(0,'/home/user/nfl/external-research/engine-full-product-research-mandate-2026-09-21')
from nfl.production.universe import player_universe as PU
import offer_edge as OE
POST='nfl/research/showdown_fixture/run_post/d90d80c0b4a7f95e'
m=json.loads((pathlib.Path(POST)/'player_draws_manifest.json').read_text())
a=np.load(pathlib.Path(POST)/'player_draws.npz'); L=m['layers']
def rows(l): return {p:i for i,p in enumerate((L.get(l) or {}).get('row_ids') or [])}
MAP={'player_receiving_yards':('receiving','receiving_yards'),
     'player_receptions':('receiving','receptions'),
     'player_rushing_yards':('rushing','rushing_yards'),
     'player_rushing_attempts':('rushing','carries'),
     'player_passing_yards':('qb','pyds'),
     'player_passing_touchdowns':('qb','ptd')}
uni=PU.build(2026,2,'2026_02_NYG_LA','2026-09-21T23:20:00Z').value
NM={}
for r in uni:
    for k in ('display_name','football_name'):
        n=(r.get(k) or '').strip()
        if n: NM.setdefault(n.lower(), r['gsis_id'])
INACT=set(json.load(open('nfl/research/showdown_fixture/INACTIVE_IDENTITY_RESOLUTION.json'))['resolved'])
board=list(csv.DictReader(open('nfl/market/raw/HR_NYG_LAR_BOARD_2026-09-21T2320Z.csv')))
out=[]; unmatched=set(); skipped_inactive=set()
for r in board:
    mk=r['market']
    if mk not in MAP or r.get('is_main')!='True': continue
    ly,me=MAP[mk]; M=a.get(f'{ly}__{me}') if f'{ly}__{me}' in a.files else None
    if M is None: continue
    idx=rows(ly); sel=(r['selection'] or '').strip()
    gid=NM.get(sel.lower())
    if gid is None: unmatched.add(sel); continue
    if gid in INACT: skipped_inactive.add(sel); continue
    if gid not in idx: unmatched.add(sel+' [no draw row]'); continue
    try: line=float(r['points'])
    except: continue
    v=M[idx[gid]].astype(float)
    p_over=float((v>line).mean()); p_push=float((v==line).mean())
    try: o=int(float(r['over'])); u=int(float(r['under']))
    except: continue
    io,iu=OE.implied_probability(o), OE.implied_probability(u)
    hold=io+iu-1.0; nv=io/(io+iu)
    out.append({'market':mk,'player':sel,'line':line,'over':o,'under':u,
      'model_p_over':round(p_over,4),'p_push':round(p_push,4),
      'market_novig_p_over':round(nv,4),'hold':round(hold,4),
      'diff':round(p_over-nv,4),'price_id':r.get('price_id'),'ts':r.get('ts_utc'),
      'mc_se':round(float(np.sqrt(p_over*(1-p_over)/len(v))),4)})
out.sort(key=lambda x:-abs(x['diff']))
json.dump({'source':'nfl/market/raw/HR_NYG_LAR_BOARD_2026-09-21T2320Z.csv',
  'simulation':m.get('run_id'),'digest':m.get('content_digest'),'n_evaluated':len(out),
  'unmatched':sorted(unmatched),'skipped_inactive':sorted(skipped_inactive),
  'calibration_status':'UNVALIDATED — no prop family has passed G-XVIII-2 or G-XX-2. '
    'These differences are NOT edges and no wager is recommended.',
  'rows':out}, open('nfl/research/showdown_fixture/HR_MODEL_COMPARISON.json','w'), indent=1)
print('evaluated %d main lines | unmatched %d | inactive skipped %d'%(len(out),len(unmatched),len(skipped_inactive)))
print('skipped (inactive, correctly no line evaluated):', sorted(skipped_inactive))
print()
print('%-26s %-22s %6s %5s/%5s  %6s %6s %7s' % ('MARKET','PLAYER','LINE','OVER','UNDER','MODEL','MKT_NV','DIFF'))
for x in out[:22]:
    print('%-26s %-22s %6.1f %5d/%5d  %6.3f %6.3f %+7.3f' % (x['market'][7:], x['player'][:22], x['line'], x['over'], x['under'], x['model_p_over'], x['market_novig_p_over'], x['diff']))
