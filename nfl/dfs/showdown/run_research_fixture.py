import sys, json, pathlib, datetime as dt
sys.path.insert(0,'/home/user/nfl')
sys.path.insert(0,'/home/user/nfl/external-research/engine-full-product-research-mandate-2026-09-21')
from nfl.dfs.showdown import research_fixture as RF
from nfl.production.universe import (player_universe as PU, role_state as RS,
    participation as PA, allocation as AL, usage_vintage as UV, chronology as CH)
import entity_verdicts as EVD, verdict_engine as VE

CUT = sys.argv[1]; RAN = dt.datetime.now(dt.timezone.utc).isoformat()
GAME='2026_02_NYG_LA'; KICK='2026-09-22T00:15:00Z'
SAL='nfl/dfs/salaries/raw/DKEntries_NYG_LAR_SHOWDOWN_2026W2.csv'
DRAWS='nfl/research/mnf/run_nyg_la/9f2e3d1ae24fc05b/player_draws_manifest.json'
# DK writes LAR; the football corpus writes LA. A declared deterministic team
# alias, NOT a name similarity match.
TEAM_ALIAS={'LAR':'LA','LA':'LA','NYG':'NYG'}

out={'spec_version':RF.SPEC_VERSION,'game_id':GAME,'information_cut':CUT,
     'run_started_at':RAN,'kickoff_utc':KICK,
     'status':'RESEARCH FIXTURE. CANDIDATE_NOT_ACCEPTED_BASELINE. No gate promoted.'}

sal, entry = RF.read_salaries(SAL)
out['contest']=entry['contest']; out['n_entry_rows']=entry['n_entries']
cands = RF.build_candidates(sal)
for c in cands: c.team = TEAM_ALIAS.get(c.team, c.team)
out['n_dk_players']=len(cands)

uni = PU.build(2026,2,GAME,CUT)
usage = UV.usage_season(2026, CUT, before_week=2).value
ro = RS.assign(uni.value, season=2026, week=2, usage_rows=usage)
snaps = RS.load_snaps(2026,2); bud = PA.measure_budget(snaps.value)
po = PA.assess(ro.value, budget=bud.value)
prows = po.value or (po.evidence or {}).get('value') or []

chron = CH.certify(CUT, RAN, sources=uni.evidence['sources'])
fresh = CH.check_freshness(CUT, uni.evidence['sources'])
out['chronology']={'code':chron.code,'state':chron.state.name,
   'cut_before_run_s': (chron.value or {}).get('cut_is_before_run_by_seconds'),
   'cut_before_kickoff': CUT < KICK}
out['freshness']={'code':fresh.code,'families':[
   {k:f[k] for k in ('family','age_hours','max_age_hours','requirement_certification','state')}
   for f in (fresh.evidence or {}).get('families',[])]}

stats = RF.join_football(cands, uni.value, ro.value, prows)
out['identity']=stats
drawev = RF.attach_draw_risk(cands, DRAWS)
out['draws']=drawev
RF.mark_credible(cands)

def row(c):
    return {'name':c.name,'team':c.team,'pos':c.position,
            'salary_flex':c.salary_flex,'salary_cpt':c.salary_cpt,
            'identity':c.identity_state,'support_state':c.support_state,
            'role':c.role,'role_support':c.role_support,
            'participation':c.participation_state,
            'expected_snap_share':c.expected_snap_share,
            'p_zero_opportunity':c.p_zero_opportunity,
            'p_zero_source':c.p_zero_source,
            'dk_points_median':c.dk_points_median,'dk_points_p10':c.dk_points_p10,
            'dk_points_source':c.dk_points_source,
            'credible_workload':c.credible_workload,'why':c.why}
out['players']=[row(c) for c in cands]
out['n_credible']=sum(1 for c in cands if c.credible_workload)

lineups = RF.build_candidate_lineups(cands, limit=12, seed_pool=12)
out['candidate_lineups']=lineups

# entity verdicts over the real DK player pool
ents=[EVD.Entity(EVD.PLAYER, c.name, game_id=GAME, player_id=c.gsis_id,
                 salary_name=c.name) for c in cands]
codes=[]
for c in cands:
    if c.identity_state!='SALARY_IDENTITY_RESOLVED':
        codes.append(f'IDENTITY_UNRESOLVED:draftkings:{c.name}')
    elif c.role_support=='ROLE_UNSUPPORTED':
        codes.append(f'CONFLICT_UNRESOLVED:{c.gsis_id}')
gr={}   # NOTHING is asserted as passing: no gate has been evaluated
ev = EVD.evaluate_entities(gr, codes, ents,
      portfolio={'D5.showdown':[l['captain'] for l in lineups[:1]]+lineups[0]['flex']} if lineups else None,
      sgp_legs=[])
out['entity_verdicts']={k:{'verdict':v.verdict,'rollup':v.rollup,
    'n_usable':len(v.usable_entities),'n_blocked':len(v.blocked_entities),
    'scope_level_reasons':v.scope_level_reasons[:3]}
    for k,v in ev.items() if k in ('F1','F2','F3','F4','F5','D2','D3.showdown','D4.showdown','D5.showdown')}
p=pathlib.Path('nfl/research/showdown_fixture/NYG_LAR_SHOWDOWN_FIXTURE.json')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(out, indent=1, default=str))
print('WROTE', p)
print('identity', stats, '| credible', out['n_credible'], 'of', len(cands))
print('chronology', out['chronology'])
print('lineups', len(lineups))
