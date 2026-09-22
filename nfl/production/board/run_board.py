import sys, json, pathlib, collections, statistics
sys.path.insert(0,'/home/user/nfl')
from nfl.production.board import player_board as PB
from nfl.production.review import (dossier as DOS, audit as AUD,
                                   escalation as ESC, gate as GATE,
                                   gated_projection as GP)
from nfl.production.universe import (player_universe as PU, role_state as RS,
                                     usage_vintage as UV)
from nfl.production.nonqb import current_season_evidence as CSE


def main(argv=None):
    """Run the week-2 NYG/LA board end to end and print it.

    EVERYTHING BELOW USED TO RUN AT IMPORT TIME. This module had no
    `if __name__` guard, so `import run_board` -- in a smoke test, in a
    dependency scan, in anything that touched the package -- executed a full
    slate build and WROTE PLAYER_BOARD.json and PLAYER_BOARD.csv. A module
    that rewrites artifacts because somebody imported it cannot be reasoned
    about, and the artifact it rewrites is one the change log diffs against.

    The board logic below is unchanged: same inputs, same calls, same output.
    Only when it runs has changed.
    """
    REPO=pathlib.Path('/home/user/nfl')
    CUT='2026-09-21T23:05:00Z'; GAME='2026_02_NYG_LA'
    BEFORE=REPO/'nfl/research/showdown_fixture/run_post/d90d80c0b4a7f95e'
    AFTER=REPO/'nfl/research/engine_repair/cs6_after/5dd61c7b2f318d3e'
    INACT=json.loads((REPO/'nfl/research/showdown_fixture/INACTIVE_IDENTITY_RESOLUTION.json').read_text())
    inactive=set(INACT.get('resolved',{}))

    u=PU.build(2026,2,GAME,CUT); urows=u.value['rows'] if isinstance(u.value,dict) else u.value
    usage=UV.usage_season(2026,CUT,before_week=2).value
    ro=RS.assign(urows,season=2026,week=2,usage_rows=usage,inactive_ids=inactive)
    roles=(ro.value['rows'] if isinstance(ro.value,dict) else ro.value) if ro.state.name=='PASS' else []
    snaps=RS.load_snaps(2026,2).value
    cse=CSE.collect(2026,2,CUT).value['by_player']

    # salaries from the week-2 DK universe, joined by gsis_id where present
    so=PB.load_salaries(REPO/'nfl/dfs/salaries/DK_WEEK2_SALARY_UNIVERSE.json')
    print('salaries:',so.state.name,so.code,'|',so.detail)
    sal=(so.value or {}).get('salary',{})

    def board_for(draws_dir, prev=None, att=None, ident=None, prev_ident=None):
        g=GP.load(draws_dir, REPO/'nfl/research/player_review/2026_02_NYG_LA',
                  inspect_refused_non_publishable=True)
        assert g.state.name=='PASS', g.code
        po=DOS.read_projection(draws_dir)
        ds=DOS.build_dossiers(universe_rows=urows, role_rows=roles, snap_rows=snaps,
                              usage_rows=usage, projection=po.value,
                              inactive_ids=inactive, information_cut=CUT,
                              opportunity_attribution=att).value['dossiers']
        a=AUD.audit(ds, publishable_ids=set(po.value['per_player']))
        res=a.value or a.evidence['value']
        e=ESC.escalate(ds,res,deep_research_capacity=15).value
        rep=DOS_report=None
        from nfl.production.review import slate_report as SR
        rep=SR.build_report(slate_key=GAME,dossiers=ds,audit_result=res,
                            escalation_result=e,projection_source={'digests':{}})
        gt=GATE.evaluate(rep,dossiers=ds,optimizer_pool_ids=set(po.value['per_player']))
        gv=GATE.payload(gt)
        b=PB.build(slate_key=GAME, dossiers=ds, arrays=g.value['arrays'],
                   layers=g.value['layers'], salaries=sal,
                   gate_rows=gv.get('conflicts'), attribution=att,
                   current_season=cse, previous_board=prev, information_cut=CUT,
                   run_identity=ident, previous_run_identity=prev_ident)
        return b, ds, e

    b0,_,_ = board_for(BEFORE, ident='V1_CANDIDATE_R9_W1P_GSVUCY')
    prev={r['gsis_id']:r for r in b0.value['rows']}
    b1,ds1,esc = board_for(AFTER, prev=prev, ident='V1_CANDIDATE_R9_W1P_GSVUCYS', prev_ident='V1_CANDIDATE_R9_W1P_GSVUCY')
    print(b1.state.name, b1.code, '|', b1.detail)
    w=PB.write(b1.value, REPO/'nfl/research/board/2026_02_NYG_LA')
    print(w.state.name, w.code, '|', w.detail)
    print('verdicts:', b1.value['by_verdict'])
    print('with salary:', b1.value['n_with_salary'], 'of', b1.value['n_rows'])
    print('\nTOP 12 BY DK')
    hdr=f"{'player':22}{'tm':4}{'pos':9}{'sal':8}{'dk':7}{'flr':6}{'ceil':7}{'car':6}{'tgt':6}{'evid':22}{'verdict':22}{'delta':7} cause"
    print(hdr); print('-'*len(hdr))
    for r in b1.value['rows'][:12]:
        print(f"{str(r['player'])[:20]:22}{str(r['team']):4}{str(r['position'])[:8]:9}"
              f"{str(r['salary'])[:7]:8}{str(r['dk_mean'])[:6]:7}{str(r['dk_floor_p10'])[:5]:6}"
              f"{str(r['dk_ceiling_p90'])[:6]:7}{str(r['proj_carries'])[:5]:6}{str(r['proj_targets'])[:5]:6}"
              f"{str(r['evidence_grade'])[:20]:22}{str(r['review_verdict'])[:20]:22}"
              f"{str(r['dk_delta'])[:6]:7} {str(r['change_cause'] or '')}")
    print(f"\nCHANGE LOG: {b1.value['n_changes']} change(s), {b1.value['n_unexplained_changes']} unexplained")
    for c in sorted(b1.value['changes'], key=lambda x: -abs(x['dk_delta'] or 0))[:8]:
        print(f"  {str(c['player'])[:20]:22} DK {c['dk_before']} -> {c['dk_after']} "
              f"({c['dk_delta']:+.2f})  car {c['carries_before']} -> {c['carries_after']}  "
              f"CAUSE {c['cause']}: {str(c['evidence'])[:60]}")
    print('\nDEEP RESEARCH QUEUE (top 8)')
    for v in [x for x in esc['verdicts'] if x.tier=='DEEP_RESEARCH'][:8]:
        print(f"  {str(v.display_name)[:20]:22}{v.team:4} p={v.priority:.4f} {v.uncertainty_state[:26]:28}{','.join(sorted({c['code'] for c in v.conflicts}))[:40]}")


if __name__ == '__main__':
    raise SystemExit(main())
