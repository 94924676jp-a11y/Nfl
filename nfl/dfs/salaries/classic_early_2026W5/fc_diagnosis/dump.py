from load import *
import json
big=[r for r in ev if r.get('ours_minus_benchmark') is not None and abs(r['ours_minus_benchmark'])>=5]
extra=[r for r in ev if r['player'] in ('Breece Hall','Caleb Williams','Michael Pittman','Adonai Mitchell')]
targets=big+extra
I=idx(inc['rows']); T=idx(tie['rows']); S=idx(scn['rows'])
rbx={(norm(r['player']),r['team']):r for r in rb}
def g(d,*ks):
    for k in ks:
        if d is None: return None
        d=d.get(k) if isinstance(d,dict) else None
    return d
for e in targets:
    key=(norm(e['player']),e['team'])
    pid=I.get(key)
    if pid is None:
        # try loose
        c=[k for (n,t),k in I.items() if t==e['team'] and norm(e['player']).split()[-1] in n]
        pid=c[0] if c else None
    p=inc['rows'].get(pid,{}); s=st['players'].get(pid,{}); r=rs['states'].get(pid,{})
    tp=tie['rows'].get(pid,{}); sp=scn['rows'].get(pid)
    rr=rbx.get(key) or next((x for x in rb if x['team']==e['team'] and norm(e['player']).split()[-1] in norm(x['player'])),None)
    print('='*100)
    print(e['player'],e['team'],e['pos'],'pid',pid,'proj name',p.get('name'),'ours',e['our_dk_points'],'fc',e.get('benchmark_fc'),'diff',e.get('ours_minus_benchmark'))
    print(' EB: elig',e['eligibility'],'avail',e['availability_state'],'desig',e['designation'],'prac',e['practice_status'],'| engine prac',e['practice_status_in_engine_state'],'inj',e['injury'],'chart',e['depth_chart_captured'],'supplied_rank',e['supplied_depth_rank'],'qb',e['club_qb_listed_by_schedule'],e['club_qb_engine_starter'],e['club_qb_flags'])
    print(' EB workload',e['workload_2026'],'vol',e['our_volume'],'p_plays',e['our_p_plays'],'if_plays',e['our_dk_if_plays'],'sim',e.get('our_sim'),'alt',e.get('alt_arm_dk_points'))
    print(' EB flags',e.get('research_flags')); 
    for x in e.get('STORED_NOT_CONSUMED') or []: print('   SNC',x)
    if rr:
        print(' RB est',rr['estimates']); print(' RB usage', {w:(u.get('targets'),u.get('carries'),u.get('pass_attempts'),u.get('target_share'),u.get('carry_share'),u.get('snap_pct'),u.get('dk_points'),u.get('played')) for w,u in rr['facts'].get('usage_by_week',{}).items()})
        print(' RB facts', {k:v for k,v in rr['facts'].items() if k!='usage_by_week'}, rr.get('fc_injury_flag'))
    print(' PROJ dk',p.get('dk_points'),'ifp',p.get('dk_points_if_plays'),'p_plays',p.get('p_plays'),'band',p.get('role_band'),'ceil',p.get('askable_ceiling'),'chart_rank',p.get('_chart_rank'),'capped',p.get('capped'),'conflict',bool(p.get('role_evidence_conflict')),'prior',p.get('prior_tier'),p.get('prior_confidence'),p.get('prior_effective_obs'),'weeks',p.get('current_season_weeks'))
    print('   vol T/C/PA',round(p.get('targets') or 0,2),round(p.get('carries') or 0,2),round(p.get('pass_attempts') or 0,2),'cond',{k:round(v,2) for k,v in (p.get('conditional_volume') or {}).items() if v is not None})
    print('   claims',p.get('claims'),'final_share',{f:g(p,'allocation',f,'final_share') for f in ('targets','carries','pass_attempts')})
    print('   eff',p.get('efficiency'))
    li=p.get('dk_points_if_plays_line_items') or {}
    print('   line_items_ifplays',li)
    print('   td: rec_rz_opps',p.get('rec_rz_opps'),'rush_rz_opps',p.get('rush_rz_opps'),'pass_td?',[ (k,p.get(k)) for k in p if 'td' in k.lower()])
    print('   explain',g(p,'explanation','contributions'))
    print(' STATE depth_rank',s.get('depth_rank'),'usage_rank',s.get('depth_usage_rank'),'src',s.get('depth_source'),'avail',g(s,'current_availability','status'),g(s,'current_availability','practice_status'),'plc',s.get('predicted_lineup_context'),'obs',s.get('observed_2026'))
    print(' ROLE ev',r.get('evidence'),'band',r.get('role_band'),'ceil',r.get('askable_ceiling'),'hist',r.get('historical_band'),'obs',r.get('observed_band'),r.get('observed_share'),'rank_pos',r.get('depth_rank_within_position'),'capped',r.get('capped'),'cap_reason',(r.get('cap_reason') or '')[:120],'conflict',r.get('role_evidence_conflict') and {k:r['role_evidence_conflict'][k] for k in ('history_band','assigned_band','evidence','ceiling')})
    rt=rs_t['states'].get(pid,{})
    print(' TIE1 dk',tp.get('dk_points'),'band',tp.get('role_band'),'ceil',tp.get('askable_ceiling'),'ev',rt.get('evidence'),'| SCN dk',(sp or {}).get('dk_points') if sp else 'ABSENT_FROM_SCENARIO','band',(sp or {}).get('role_band'))
    # room
    room=[(k,x) for k,x in st['players'].items() if x['team']==e['team'] and x['position']==e['pos']]
    print(' ROOM:')
    for k,x in sorted(room,key=lambda kx:(kx[1].get('depth_rank') or 99,kx[0])):
        pr=inc['rows'].get(k,{}); rr2=rs['states'].get(k,{})
        print('   ',k,x['name'],'rank',x.get('depth_rank'),'usage',x.get('depth_usage_rank'),'posrank',rr2.get('depth_rank_within_position'),'ev',rr2.get('evidence'),'band',rr2.get('role_band'),'ceil',rr2.get('askable_ceiling'),'hist',rr2.get('historical_band'),'dk',pr.get('dk_points'),'tie1',tie['rows'].get(k,{}).get('dk_points'),'scn',(scn['rows'].get(k) or {}).get('dk_points'),'obs',g(x,'observed_2026','combined'),'avail',g(x,'current_availability','status'),g(x,'current_availability','practice_status'))
