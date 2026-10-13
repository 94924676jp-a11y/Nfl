import sys; p=sys.argv[1] if len(sys.argv) > 1 else 'nfl/tools/proj_v1.py'; s=open(p).read()
old1="""        dvals, claims = [0.0] * len(crows), []
        for i, r in enumerate(crows):
            claims.append(max(0.0, (r.get('_claims') or {}).get(field) or 0.0))"""
new1="""        dvals, claims = [0.0] * len(crows), []
        # PROJ-FIX-1 (PREREG_PROJFIX1_ZERO_CLAIM.md), opt-in NFL_PROJ_ZERO_CLAIM_IS_EVIDENCE=1: remember which claims were
        # MEASURED as zero (not None). A measured zero is evidence and takes weight 0 below; only a MISSING claim keeps the
        # half-depth fallback. Unset leaves the allocation byte-identical.
        zero_is_evidence = os.environ.get('NFL_PROJ_ZERO_CLAIM_IS_EVIDENCE') == '1'
        measured_zero = []
        for i, r in enumerate(crows):
            raw = (r.get('_claims') or {}).get(field)
            measured_zero.append(raw is not None and raw <= 0)
            claims.append(max(0.0, raw or 0.0))"""
assert old1 in s; s=s.replace(old1,new1)
old2="""            elif pn <= 0 or dn <= 0:
                # one side has no evidence at all; take half the other rather than zero, so a
                # player is never silently removed from a club's offence by a missing measure
                w.append(max(pn, dn) * 0.5)"""
new2="""            elif zero_is_evidence and measured_zero[i]:
                w.append(0.0)                       # a MEASURED zero claim: no volume in this field (PROJ-FIX-1)
            elif pn <= 0 or dn <= 0:
                # one side has no evidence at all; take half the other rather than zero, so a
                # player is never silently removed from a club's offence by a missing measure
                w.append(max(pn, dn) * 0.5)"""
assert old2 in s; s=s.replace(old2,new2)
if '\nimport os\n' not in s:
    s=s.replace('\nimport json\n','\nimport json\nimport os\n',1)
assert '\nimport os\n' in s
open(p,'w').write(s); print('patched')
