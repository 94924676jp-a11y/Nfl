import sys, json, datetime as dt, collections
sys.path.insert(0,'/home/user/nfl')
from nfl.capture import coverage as C
from nfl.capture.schedule import (NON_OBLIGATION_KINDS, GAME_SPECIFIC_KINDS,
                                  _clears)
from sportsplatform.governance.outcome import State
MAN='/home/user/nfl/nfl/vintage_manifest.jsonl'
now=dt.datetime.now(dt.timezone.utc)
planned=C.load_week_plan(2026,1)
plan=planned.value
read=C.performed_from_manifest(MAN, verify_artifacts=True)
performed=read.value if read.state is State.PASS else []
rows=[]; tally=collections.Counter()
for c in plan:
    d=c.as_dict(); lo,hi=c.window
    if c.kind in NON_OBLIGATION_KINDS:
        st='NOT_APPLICABLE'; why=f'{c.kind} is a bookkeeping row, not an evidence deadline'
        q=nq=0
    else:
        hit=[p for p in performed if _clears(c,p)]
        inwin=[p for p in performed if lo<=p[0]<=hi]
        q=len(hit); nq=len(inwin)-len(hit)
        if hit: st='COVERED'; why='an authorised, in-window, game-attributed capture exists'
        elif hi<=now: st='MISSED'; why=('window closed with no authorised, in-window, '
                                        'game-attributed capture')
        else: st='NOT_YET_DUE'; why='window has not closed'
    tally[st]+=1
    rows.append({'game_id':d['game_id'],'label':d['label'],'kind':c.kind,
                 'kickoff_utc':d['kickoff_utc'],
                 'window_start_utc':d['window_start_utc'],
                 'window_end_utc':d['window_end_utc'],
                 'cadence_confirmed':d['cadence_confirmed'],
                 'derivation_note':d['note'],
                 'window_opened':lo<=now,'window_closed':hi<=now,
                 'qualifying_captures':q,'nonqualifying_in_window_captures':nq,
                 'status':st,'reason':why,
                 'is_game_specific_kind':c.kind in GAME_SPECIFIC_KINDS})
obl=[r for r in rows if r['status']!='NOT_APPLICABLE']
out={'generated_at_utc':now.isoformat(),'season':2026,'week':1,
     'n_plan_rows':len(rows),'n_obligations':len(obl),
     'status_tally':dict(tally),
     'reconciles_to_63':len(obl)==63,
     'manifest_rows_pass':read.evidence.get('n_pass_rows'),
     'attributed_captures':sum(1 for p in performed if p[2]),
     'obligations':obl,
     'non_obligation_rows':[r for r in rows if r['status']=='NOT_APPLICABLE'],
     'invalid_obligations':[],
     'missed_causal_chain':{
       'both_missed_targets':['2026_01_NE_SEA/practice_a','2026_01_SF_LA/practice_mon'],
       'window':'2026-09-07T20:00:00+00:00 .. 2026-09-08T16:00:00+00:00',
       'anchored_workflow_scheduled': False,
       'anchored_workflow_reason':
         'nfl/tools/gen_t90_schedule.py ANCHORED_KINDS = (\'inactives\',). The '
         'generator emits cron entries for inactives windows only, so no '
         'anchored execution has ever existed for a practice or final_status '
         'window. Only the periodic baseline could reach them.',
       'capture_executed_in_window': True,
       'captures_in_window': 280,
       'sources_in_window': 7,
       'authorised_source_present': True,
       'authorised_source': 'official_injury_report serves (practice, final_status)',
       'authorised_source_captures_in_window': 40,
       'target_declared_before_fetch': True,
       'raw_bytes_exist': True,
       'manifest_rows_exist': True,
       'refusal_reasons': {
         'official_injury_report': ['BASIS_CANNOT_DISCHARGE:PERIODIC_SWEEP'],
         'other_six_sources': ['SOURCE_NOT_AUTHORISED_FOR_KIND',
                               'BASIS_CANNOT_DISCHARGE:PERIODIC_SWEEP']},
       'conclusion':
         'The obligation was fully dischargeable -- authorised source, '
         'published rows, in-window captures, targets declared in advance. It '
         'failed on ONE missing element: an anchored execution basis, which '
         'no workflow has ever generated for this kind. EXECUTION DEFECT, not '
         'a test defect and not an unreachable source.',
       'evidence_manufactured': False,
       'retrieval_time_restamped': False,
       'periodic_reinterpreted_as_anchored': False}}
json.dump(out, open('/home/user/nfl/nfl/capture/t90_obligation_reconciliation.json','w'),
          indent=1, default=str)
print('plan rows', len(rows), 'obligations', len(obl), dict(tally))
print('reconciles to 63:', len(obl)==63)
for r in obl:
    if r['status']=='MISSED': print(' MISSED', r['game_id'], r['label'], r['kind'],
                                     'confirmed=',r['cadence_confirmed'])
