"""Stage 3: the scaffold's own invariants.

Three things must be true of a diagnostic harness before anything it reports is
worth reading: it enforces physics, it cannot have its marginals swapped
without saying so, and it cannot be walked into a decision path.
"""
import ast, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import joint as J, build_joint as B                            # noqa: E402
sys.path.insert(0, os.path.join(HERE, '..', 'p4c'))
import p4c_lib as CL                                           # noqa: E402
import p4c_build as CB                                         # noqa: E402

P = F = 0


def check(l, c, d=''):
    global P, F
    if c:
        P += 1
        print(f'  ok   {l}')
    else:
        F += 1
        print(f'  FAIL {l}  {d}')


_CACHE = {}

# panel_enriched.pkl and volume_store.npy are deliberately NOT committed: Stage
# 1 established they are byte-for-byte regenerable, so the repository carries
# the leaves and the generator instead. Research code run from the repository
# therefore has to stage them first. An absent artifact is a NAMED BLOCKED
# state with the exact command to fix it -- never a crash, and never a silent
# pass.
_NEEDED = ('panel_enriched.pkl', 'volume_store.npy')
_P4B = os.path.abspath(os.path.join(HERE, '..', 'p4b'))


def _artifacts_present():
    return all(os.path.exists(os.path.join(_P4B, n)) for n in _NEEDED)


def _blocked_and_exit():
    missing = [n for n in _NEEDED
               if not os.path.exists(os.path.join(_P4B, n))]
    print('\nBLOCKED(cause=DEPENDENCY): the derived research artifacts are '
          'not staged.')
    print(f'  missing: {missing}')
    print('  They are not committed by design -- Stage 1 proved them '
          'byte-for-byte regenerable.')
    print('  Stage them with:')
    print('    python3.12 nfl/research/repro/regenerate.py --emit '
          'nfl/research/p4b')
    print('\n0 passed, 0 failed, BLOCKED')
    sys.exit(3)


def cell(cls='carries', ev=2024):
    if not _CACHE:
        _CACHE['rows'] = CB.load_panel()
        _CACHE['vol'] = CB.load_volume()
        _CACHE['pa'] = CB.appearance(_CACHE['rows'])
    k = (cls, ev)
    if k not in _CACHE:
        _CACHE[k] = B.build(_CACHE['rows'], _CACHE['vol'], _CACHE['pa'], cls, ev)
    return _CACHE[k]


def test_physical_invariants():
    print('\nA. physics the draws may never violate')
    for cls in ('carries', 'snaps'):
        j = cell(cls)
        for stage, S in (('pre', j.share_pre()), ('post', j.share_post())):
            check(f'{cls}/{stage}: no negative share',
                  float(S.min()) >= -1e-9, float(S.min()))
            check(f'{cls}/{stage}: no negative absolute outcome',
                  float((j.Y_pre() if stage == 'pre' else j.Y_post()).min())
                  >= -1e-6)
        # The group sum against the physical maximum is a MEASUREMENT, not an
        # assertion. The accepted occupancy marginal violates it -- 43% of
        # pre-reconciliation draws and 6.8% of post-reconciliation draws put
        # more than five skill players' worth of snap share on the field -- and
        # Stage 3 is forbidden to fix a marginal. So what is asserted here is
        # that the harness DETECTS and REPORTS it, which is the harness's job.
        ss = CL.gsum(j.share_post(), j.starts)
        acc = J.accounting(j, 'post')
        check(f'{cls}/post: the harness reports the group-sum maximum',
              abs(acc['team_group_sum_max'] - float(ss.max())) < 1e-6)
        check(f'{cls}/post: and the violation rate it reports is the real one',
              abs(acc['team_group_sum_gt_cap_rate']
                  - float((ss > j.group_cap + 1e-6).mean())) < 1e-9)
        check(f'{cls}/post: it also reports the realised maximum, so the model '
              f'can be compared against physics rather than against itself',
              acc['realised_group_sum_max'] > 0)
        check(f'{cls}: appearance draws are boolean',
              j.A.dtype == np.bool_, j.A.dtype)
        check(f'{cls}: team volume is SHARED within a team-game',
              all(np.array_equal(j.T[s], j.T[s + 1])
                  for s in j.starts[:50] if j.counts[list(j.starts).index(s)] > 1))
        check(f'{cls}: a non-appearing draw allocates nothing',
              float(j.share_post()[~j.A].max()) <= 1e-6,
              float(j.share_post()[~j.A].max()))


def test_pre_and_post_are_both_reported():
    print('\nB. the report cannot quietly become post-only')
    j = cell()
    d = J.diagnose(j)
    for block in ('accounting_coherence', 'marginal_calibration',
                  'joint_dependence'):
        check(f'{block} carries both stages',
              set(d[block]) == {'pre', 'post'}, sorted(d[block]))
    check('and they are genuinely different numbers, not a copy',
          d['accounting_coherence']['pre']['modelled_mass_mean']
          != d['accounting_coherence']['post']['modelled_mass_mean'])
    check('the three blocks are separate keys, never one score',
          'score' not in d and 'overall' not in d)
    src = open(os.path.join(HERE, 'joint.py')).read()
    check('and no function combines the three blocks into one number',
          'combined_score' not in src and 'overall_score' not in src)


def test_marginals_cannot_be_silently_replaced():
    print('\nC. a swapped marginal must announce itself')
    j = cell()
    ident = dict(j.marginal_id)
    check('the draws carry a marginal identity',
          set(ident) >= {'system', 'code_sha256', 'seed', 'M'}, sorted(ident))
    check('  which names the accepted system',
          ident['system'] == B.ACCEPTED_SYSTEM, ident['system'])
    check('  and hashes the code that produced it',
          len(ident['code_sha256']) == 64)
    j2 = J.JointDraws(j.cls, j.ev, j.rows, j.starts, j.counts, j.T, j.A,
                      j.W * 0.5, j.share_post(), j.y, j.S_star, j.A_star,
                      j.cap, j.group_cap,
                      {**ident, 'system': 'SOMETHING_ELSE'}, j.mode)
    d1, d2 = J.diagnose(j), J.diagnose(j2)
    check('a different marginal produces a different identity in the report',
          d1['marginal_id'] != d2['marginal_id'])
    check('  and the swap changes the pre-reconciliation numbers, so it '
          'cannot hide behind the normaliser',
          d1['accounting_coherence']['pre']['modelled_mass_mean']
          != d2['accounting_coherence']['pre']['modelled_mass_mean'])
    same = B.marginal_identity('carries', 2024)
    check('the identity is deterministic for the same inputs',
          same == B.marginal_identity('carries', 2024))


def test_cannot_enter_a_decision_path():
    print('\nD. the harness refuses to be used for a decision')
    for bad in ('wager sizing', 'DFS lineup', 'ownership projection',
                'salary optimisation', 'market price comparison',
                'find the edge', 'ROI estimate', 'bankroll', 'parlay',
                'prop pricing'):
        try:
            J.diagnose(cell(), purpose=bad)
            check(f'purpose {bad!r} is refused', False, 'no raise')
        except J.DiagnosticOnly as exc:
            check(f'purpose {bad!r} is refused', 'DIAGNOSTIC_ONLY' in str(exc))
    check('a diagnostic purpose is allowed',
          J.diagnose(cell(), purpose='diagnostic')['class'] == 'carries')
    # and the module must not import or reference a pricing surface at all
    tree = ast.parse(open(os.path.join(HERE, 'joint.py')).read())
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
            dd = ast.get_docstring(node, clean=False)
            if dd:
                docs.add(dd)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            names.add(node.attr.lower())
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.add((getattr(node, 'module', '') or '').lower())
    hits = [n for n in names
            if any(w in n for w in ('odds', 'price', 'salary', 'ownership',
                                    'lineup', 'wager', 'bankroll'))]
    check('no pricing or lineup identifier appears in the module',
          not hits, hits)


def test_guard_deletion():
    print('\nE. delete the guards')
    orig = J.FORBIDDEN_USES
    try:
        J.FORBIDDEN_USES = ()
        d = J.diagnose(cell(), purpose='DFS lineup optimisation for wagers')
        check('GD-1 with FORBIDDEN_USES emptied, a DFS purpose is accepted',
              d['class'] == 'carries')
    finally:
        J.FORBIDDEN_USES = orig
    try:
        J.diagnose(cell(), purpose='DFS lineup optimisation for wagers')
        check('  and with the guard restored it is refused again', False)
    except J.DiagnosticOnly:
        check('  and with the guard restored it is refused again', True)

    # GD-2: the pre/post pairing itself
    orig_acc = J.accounting
    try:
        J.accounting = lambda j, which: orig_acc(j, 'post')   # guard DELETED
        d = J.diagnose(cell())
        check('GD-2 with the stage argument ignored, pre and post become '
              'identical and the pre-reconciliation defect vanishes from the '
              'report',
              d['accounting_coherence']['pre']
              == d['accounting_coherence']['post'])
    finally:
        J.accounting = orig_acc
    d = J.diagnose(cell())
    check('  and with it restored they differ again',
          d['accounting_coherence']['pre']
          != d['accounting_coherence']['post'])


def test_the_scaffold_flags_but_does_not_decide():
    print('\nF. flagging is not deciding')
    res = os.path.join(HERE, 's3_results.json')
    if not os.path.exists(res):
        check('s3_results.json exists', False, 'run run_s3.py first')
        return
    o = json.load(open(res))
    check('flags were raised', len(o['flags']) > 0, len(o['flags']))
    check('every flag says it is not a rejection',
          all('not rejected here' in f['action'] for f in o['flags']))
    # NB: the flag text contains the word "rejected" inside the phrase "not
    # rejected here", so a substring scan is the wrong instrument. What matters
    # is that every flag's ACTION is the flag sentence and nothing else.
    check('every flag action is a flag, never a decision',
          all(f['action'] == 'FLAGGED FOR RE-EXAMINATION -- not rejected here'
              for f in o['flags']))
    check('and no flag carries a decision field',
          not any({'decision', 'promoted', 'accepted'} & set(f)
                  for f in o['flags']))
    kinds = {f['kind'] for f in o['flags']}
    check('flags are attributed to one of the three blocks',
          kinds <= {'MARGINAL_CALIBRATION', 'JOINT_DEPENDENCE',
                    'ACCOUNTING_COHERENCE'}, kinds)


if __name__ == '__main__':
    if not _artifacts_present():
        _blocked_and_exit()
    for t in (test_physical_invariants, test_pre_and_post_are_both_reported,
              test_marginals_cannot_be_silently_replaced,
              test_cannot_enter_a_decision_path, test_guard_deletion,
              test_the_scaffold_flags_but_does_not_decide):
        t()
    print(f'\n{P} passed, {F} failed')
    sys.exit(1 if F else 0)
