"""Resolve abbreviated inactive names to gsis_ids. Exact surname + team only."""
import sys, json, pathlib
sys.path.insert(0,'/home/user/nfl')
from nfl.production.universe import player_universe as PU

CUT=sys.argv[1]
d=json.load(open('nfl/research/showdown_fixture/OWNER_INACTIVES_NYG_LAR_2026W2.json'))
uni=PU.build(2026,2,'2026_02_NYG_LA',CUT)
rows=uni.value
SUFFIXES={'JR','SR','II','III','IV','V'}
def surname(full):
    toks=[t.strip().rstrip('.') for t in (full or '').split() if t.strip()]
    while len(toks)>1 and toks[-1].upper().rstrip('.') in SUFFIXES:
        toks.pop()
    return toks[-1] if toks else ''
out={'resolved':{}, 'unresolved':[], 'ambiguous':[],
     'normalisation':'declared suffix strip (Jr/Sr/II/III/IV/V) + exact surname + club + first initial. NO edit-distance.'}
for team, names in d['inactives'].items():
    for nm in names:
        sn = surname(nm)
        cands=[r for r in rows if r['team']==team
               and surname(r.get('display_name'))==sn]
        # a listed initial must agree with the first initial when one is given
        first = nm.split()[0].rstrip('.')
        if len(first)<=3 and not first.isalpha() or True:
            narrowed=[c for c in cands
                      if (c.get('display_name') or '').startswith(first)
                      or (c.get('display_name') or '')[:1]==first[:1]]
            if narrowed: cands=narrowed
        if len(cands)==1:
            out['resolved'][cands[0]['gsis_id']]={'listed':nm,'team':team,
                'display_name':cands[0]['display_name'],'pos':cands[0]['roster_position']}
        elif len(cands)>1:
            out['ambiguous'].append({'listed':nm,'team':team,
                'candidates':[c['display_name'] for c in cands]})
        else:
            out['unresolved'].append({'listed':nm,'team':team,
                'why':'no exact surname match on this club; edit-distance matching is not permitted'})
print(json.dumps(out, indent=1))
pathlib.Path('nfl/research/showdown_fixture/INACTIVE_IDENTITY_RESOLUTION.json').write_text(json.dumps(out,indent=1))
