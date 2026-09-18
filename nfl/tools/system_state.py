#!/usr/bin/env python3.12
"""Generate `SYSTEM_STATE.json`, then render `CURRENT_STATE.md` from it.

    python3.12 nfl/tools/system_state.py           # print the state, write nothing
    python3.12 nfl/tools/system_state.py --write   # write both files

THE DEFECT THIS REPAIRS

`CURRENT_STATE.md` was hand-written on 2026-09-07 and was read eleven days
later still saying "1,230 assertions across 19 suites, 0 failing". The suite
at that moment was 1,944 functions and 10,335 checks with 61 failing. The file
also said "No predictive model", "Week 1 kicks off 2026-09-09 (2 days)", and
gave the branch as `main @ a559da2`. Every one of those was a number or a fact
that existed elsewhere in the repository and had been retyped into prose, and
prose does not move when the repository does.

So this generator measures, and `CURRENT_STATE.md` is rendered from what it
measured. Nothing in the rendered file is typed by a person.

THE PART THAT IS NOT MEASURABLE, AND IS NOT THEREBY DROPPED

Some true and load-bearing statements cannot be settled by reading this tree:
that this executor has no egress, that a second agent holds the odds
connector, that real money is not enabled. Dropping them would lose real
information; measuring them is impossible; retyping them beside measurements
is what produced the defect above.

They live in `nfl/STATE_DECLARATIONS.md`, each with who declared it, when, why
it is not measurable, and what would turn it into a measurement. This
generator reads them and renders them in a section of their own, labelled.
A reader can always tell which lines were measured and which were asserted.

WHAT IT REFUSES

A measurement that comes back empty is recorded as `NOT_MEASURED` with the
reason, never as a zero. A suite total is recorded together with the commit
the log was produced at, and with whether that commit is HEAD -- a stale
measurement presented as current is the whole defect, so the file says so
rather than leaving the reader to check.
"""
from __future__ import annotations

import collections
import datetime as dt
import glob
import json
import pathlib
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / 'nfl' / 'tools'))

STATE = _REPO / 'SYSTEM_STATE.json'
RENDERED = _REPO / 'CURRENT_STATE.md'
DECLARATIONS = _REPO / 'nfl' / 'STATE_DECLARATIONS.md'
GENERATOR = 'nfl/tools/system_state.py'
SPEC_VERSION = 'nfl-system-state-1'

NOT_MEASURED = 'NOT_MEASURED'


def _git(*args) -> str:
    try:
        return subprocess.run(['git'] + list(args), cwd=_REPO,
                              capture_output=True, text=True,
                              timeout=90).stdout.strip()
    except Exception:                                          # noqa: BLE001
        return ''


def _unmeasured(why: str) -> dict:
    return {'state': NOT_MEASURED, 'why': why}


# ------------------------------------------------------------------ git

def measure_git() -> dict:
    # WORKING-TREE STATE COMES FROM `nfl/identity/`, WHICH OWNS IT.
    #
    # A first version ran `git status --porcelain` here and joined
    # `commit_claim.py` on the offender list of
    # `test_determinism_proof.test_v_only_the_identity_module_reads_working_tree_state`.
    # Calling `code_identity` instead is not merely compliance: a second,
    # independently computed view of "what is dirty" is exactly the two-truths
    # defect this generator exists to remove.
    import agent_state as _AS
    wt = _AS.worktree_state()
    return {
        'head': _git('rev-parse', 'HEAD'),
        'head_short': _git('rev-parse', '--short', 'HEAD'),
        'head_subject': _git('log', '-1', '--pretty=%s'),
        'head_committed_at': _git('log', '-1', '--pretty=%cI'),
        'branch': _git('rev-parse', '--abbrev-ref', 'HEAD'),
        'remote_head': _git('rev-parse', 'origin/' + (
            _git('rev-parse', '--abbrev-ref', 'HEAD') or 'HEAD')),
        'worktree': wt,
        'dirty_source_files': wt.get('dirty_source_files', []),
        'is_clean': bool(wt.get('source_scope_clean')),
        'n_commits_on_branch': int(_git('rev-list', '--count', 'HEAD') or 0),
    }


# ----------------------------------------------------------------- code

def measure_code() -> dict:
    pkgs = ('nfl/production', 'nfl/capture', 'nfl/research', 'nfl/dfs',
            'nfl/product', 'nfl/tests', 'nfl/tools', 'nfl/postgame',
            'nfl/prospective', 'nfl/identity', 'sportsplatform')
    out, total_f, total_l = {}, 0, 0
    for pkg in pkgs:
        fs = sorted((_REPO / pkg).glob('**/*.py'))
        lines = sum(len(f.read_text(errors='replace').splitlines())
                    for f in fs)
        out[pkg] = {'modules': len(fs), 'lines': lines}
        total_f += len(fs)
        total_l += lines
    out['TOTAL'] = {'modules': total_f, 'lines': total_l}
    return out


# ---------------------------------------------------------------- suite

def _parse_totals(log: pathlib.Path) -> dict:
    import re
    for line in log.read_text(errors='replace').splitlines():
        m = re.match(
            r'^modules (\d+)\s+test functions (\d+)\s+checks (\d+)\s+'
            r'FAILING CHECKS (\d+)\s+RAISED (\d+)\s+'
            r'ZERO-CHECK FUNCTIONS (\d+)\s+BLOCKED FUNCTIONS (\d+)', line)
        if m:
            k = ('modules', 'test_functions', 'checks', 'failing_checks',
                 'raised', 'zero_check_functions', 'blocked_functions')
            return dict(zip(k, (int(x) for x in m.groups())))
    return {}


def measure_suite(head: str) -> dict:
    """The newest suite diff artifact, and whether it was taken at HEAD."""
    fs = sorted(glob.glob(str(
        _REPO / 'nfl/research/suite_attribution/SUITE_DIFF_*.json')))
    if not fs:
        return _unmeasured('no SUITE_DIFF_*.json artifact on disk; run '
                           'nfl/tests/run_suite.py and nfl/tools/suite_diff.py')
    p = pathlib.Path(max(fs, key=lambda x: pathlib.Path(x).stat().st_mtime))
    d = json.loads(p.read_text())
    cur_commit = (d.get('current') or {}).get('commit') or 'NO_COMMIT_RECORDED'
    at_head = (bool(head) and cur_commit not in ('', 'NO_COMMIT_RECORDED')
               and head.startswith(cur_commit))
    return {
        'artifact': str(p.relative_to(_REPO)),
        'measured_at_commit': cur_commit,
        'is_current_head': at_head,
        'staleness_note': (
            'measured at HEAD' if at_head else
            f'measured at {cur_commit}, HEAD is {head[:7] or "?"}. This total '
            f'is not a statement about the tree as it stands.'),
        'totals': (d.get('current') or {}).get('totals') or {},
        'verdict': (d.get('current') or {}).get('verdict'),
        'baseline_commit': (d.get('baseline') or {}).get('commit'),
        'baseline_totals': (d.get('baseline') or {}).get('totals') or {},
        'delta_totals': d.get('delta_totals') or {},
        'counts_by_classification': d.get('counts_by_classification') or {},
        'newly_introduced': [
            {'module': r.get('module'), 'kind': r.get('kind'),
             'detail': (r.get('detail') or '')[:160]}
            for r in (d.get('newly_introduced') or [])],
    }


# -------------------------------------------------------------- capture

def measure_capture() -> dict:
    man = _REPO / 'nfl' / 'vintage_manifest.jsonl'
    if not man.exists():
        return _unmeasured('nfl/vintage_manifest.jsonl is absent')
    by_source = collections.Counter()
    by_state = collections.Counter()
    stamps = []
    n = 0
    for ln in man.read_text(errors='replace').splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        n += 1
        by_source[d.get('source') or '?'] += 1
        by_state[d.get('state') or '?'] += 1
        t = ((d.get('evidence') or {}).get('retrieved_at')
             or d.get('retrieved_at'))
        if t:
            stamps.append(str(t))
    store = collections.Counter()
    for f in (_REPO / 'nfl' / 'vintage').glob('*'):
        if f.is_file():
            store[f.name.split('.')[0]] += 1
    return {
        'manifest_rows': n,
        'by_source': dict(sorted(by_source.items())),
        'by_state': dict(sorted(by_state.items())),
        'retrieved_at_earliest': min(stamps) if stamps else NOT_MEASURED,
        'retrieved_at_latest': max(stamps) if stamps else NOT_MEASURED,
        'vintage_store_files': sum(store.values()),
        'vintage_store_by_family': dict(sorted(store.items())),
    }


# ---------------------------------------------------------- assumptions

def measure_assumptions() -> dict:
    try:
        from nfl.production.assumptions import registry as AR
        rows = [{'id': a.id, 'status': a.status, 'criticality': a.criticality,
                 'claim': (a.claim or '')[:200]}
                for a in AR.all_assumptions()]
    except Exception as exc:                                   # noqa: BLE001
        return _unmeasured(f'registry did not load: '
                           f'{type(exc).__name__}: {exc}')
    return {'n': len(rows),
            'by_status': dict(sorted(collections.Counter(
                r['status'] for r in rows).items())),
            'assumptions': rows}


# ------------------------------------------------------------------ DAG

def measure_dag() -> dict:
    try:
        from nfl.production import pipeline as PL
        inv = PL.read_inventory()
    except Exception as exc:                                   # noqa: BLE001
        return _unmeasured(f'pipeline did not load: '
                           f'{type(exc).__name__}: {exc}')
    return {
        'spec_version': inv['spec_version'],
        'phase': inv['phase'],
        'not_implemented': inv['not_implemented'],
        'audit_state': inv['audit']['state'],
        'audit_code': inv['audit']['code'],
        'n_edges': sum(len(v) for v in inv['by_producer'].values()),
        'readers_per_producer': {k: len(v)
                                 for k, v in inv['by_producer'].items()},
        'n_runtime_keyed': len(inv['runtime_keyed_reads']),
        'audited_roots': inv['audited_roots'],
    }


# ----------------------------------------------------- forecast artifacts

def measure_forecasts() -> dict:
    runs = sorted((_REPO / 'nfl').glob('**/run_status.json'))
    statuses = collections.Counter()
    for r in runs[:2000]:
        try:
            statuses[json.loads(r.read_text()).get('status') or '?'] += 1
        except Exception:                                      # noqa: BLE001
            statuses['UNREADABLE'] += 1
    live = sorted(p.name for p in (_REPO / 'nfl/research/live').glob('*')
                  if p.is_dir()) if (_REPO / 'nfl/research/live').exists() \
        else []
    return {
        'sealed_run_status_files': len(runs),
        'run_status_by_status': dict(sorted(statuses.items())),
        'live_board_directories': len(live),
        'live_board_names_sample': live[:6],
    }


# -------------------------------------------------------------- postgame

def measure_postgame() -> dict:
    out = {}
    led = _REPO / 'nfl/research/postgame/PROSPECTIVE_EVALUATION_LEDGER.jsonl'
    if led.exists():
        rows = [ln for ln in led.read_text().splitlines() if ln.strip()]
        # THE LEDGER'S OWN FIELD NAME, read from a row rather than guessed.
        # A first version counted `kind`, which no row carries, and rendered
        # `{'?': 2}` -- a measurement that looked like data and said nothing.
        kinds = collections.Counter()
        blocks = set()
        for ln in rows:
            try:
                r = json.loads(ln)
            except ValueError:
                kinds['UNPARSEABLE'] += 1
                continue
            kinds[r.get('status') or 'NO_STATUS_FIELD'] += 1
            if r.get('block_id'):
                blocks.add(r['block_id'])
        out['prospective_evaluation_ledger'] = {
            'rows': len(rows), 'by_status': dict(sorted(kinds.items())),
            'blocks': sorted(blocks)}
    else:
        out['prospective_evaluation_ledger'] = _unmeasured('ledger absent')
    oc = sorted((_REPO / 'nfl').glob('**/POSTGAME_OUTCOME/OUTCOME.json'))
    out['captured_outcomes'] = {
        'n': len(oc),
        'games': [str(p.relative_to(_REPO)).split('/')[-3] for p in oc]}
    return out


# ------------------------------------------------------------ governance

def measure_governance() -> dict:
    out = {}
    pr = _REPO / 'nfl/production/production_readiness.json'
    if pr.exists():
        d = json.loads(pr.read_text())
        caps = d.get('capabilities') or []
        out['production_readiness'] = {
            'artifact': str(pr.relative_to(_REPO)),
            'updated_utc': d.get('updated_utc'),
            'n_capabilities': len(caps),
            'by_state': dict(sorted(collections.Counter(
                c.get('state') or '?' for c in caps).items())),
            'not_green': [{'id': c.get('id'), 'name': c.get('name'),
                           'state': c.get('state')}
                          for c in caps if c.get('state') != 'GREEN'],
        }
    else:
        out['production_readiness'] = _unmeasured('artifact absent')
    return out


# ----------------------------------------------------------- work queue

def measure_superseded_states() -> list:
    """Hand-written state files this generated one replaces.

    They are kept BYTE-IDENTICAL to what git holds and are not annotated: a
    note prepended to a historical document changes the document. The pointer
    lives here, in the successor, which is the direction supersession runs.
    """
    import hashlib
    d = _REPO / 'nfl' / 'research' / 'state'
    out = []
    for f in sorted(d.glob('CURRENT_STATE_*.md')) if d.exists() else []:
        b = f.read_bytes()
        out.append({'path': str(f.relative_to(_REPO)),
                    'bytes': len(b),
                    'sha256': hashlib.sha256(b).hexdigest()[:16],
                    'note': 'hand-written; superseded by this generated '
                            'file. Kept unedited.'})
    return out


def measure_queue() -> dict:
    try:
        import agent_state as AS
        q = AS.parse_queue()
    except Exception as exc:                                   # noqa: BLE001
        return _unmeasured(f'WORK_QUEUE.md did not parse: '
                           f'{type(exc).__name__}: {exc}')
    return {
        'n': len(q),
        'by_status': dict(sorted(collections.Counter(
            it['status'] for it in q).items())),
        'items': [{'id': it['id'], 'priority': it.get('priority'),
                   'status': it['status'],
                   'description': it.get('description', ''),
                   'blocker': it.get('blocker', '')} for it in q],
    }


# --------------------------------------------------------- declarations

def read_declarations(path=None) -> list:
    """The hand-authored, unmeasurable claims. Parsed, never summarised."""
    import re
    path = pathlib.Path(path or DECLARATIONS)
    if not path.exists():
        return []
    items, cur, field = [], None, None
    for line in path.read_text().splitlines():
        m = re.match(r'^## ID:\s*(\S+)\s*$', line)
        if m:
            cur = {'id': m.group(1)}
            items.append(cur)
            field = None
            continue
        if cur is None:
            continue
        m = re.match(r'^-\s+\*\*([\w ]+)\*\*:\s*(.*)$', line)
        if m:
            field = m.group(1).strip().replace(' ', '_')
            cur[field] = m.group(2).strip()
            continue
        if line.startswith('  ') and line.strip() and field:
            cur[field] = (cur[field] + ' ' + line.strip()).strip()
    return items


REQUIRED_DECLARATION_FIELDS = ('claim', 'declared_by', 'declared_at',
                               'why_not_measurable', 'what_would_verify',
                               'status')


class DeclarationError(RuntimeError):
    pass


def validate_declarations(items) -> list:
    bad = [(it['id'], [f for f in REQUIRED_DECLARATION_FIELDS
                       if not (it.get(f) or '').strip()])
           for it in items]
    bad = [(i, miss) for i, miss in bad if miss]
    if bad:
        raise DeclarationError(
            f'DECLARATION_INCOMPLETE: {bad}. A declaration without a stated '
            f'reason it cannot be measured is indistinguishable from a '
            f'measurement nobody took.')
    return items


# ------------------------------------------------------------------ build

_CACHE: dict = {}


def build(fresh: bool = False) -> dict:
    """One snapshot per process unless `fresh` is asked for.

    Every measurement here walks 650-odd modules, 4,500 manifest rows and 160
    run records, and the test module calls this once per test function. Ten
    rebuilds of an identical snapshot took eight minutes and told nobody
    anything. The cache is per PROCESS, so it cannot make a regenerated file
    look current in a later run; `--write` asks for a fresh one.
    """
    if not fresh and 'state' in _CACHE:
        return _CACHE['state']
    git = measure_git()
    out = {
        'spec_version': SPEC_VERSION,
        'generated_by': GENERATOR,
        'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
        'reading_rule':
            'Every value under `measured` was computed by reading this '
            'repository at the timestamp above. Every value under `declared` '
            'was asserted by somebody and says who, when, and why it cannot '
            'be measured here. Do not quote one as the other.',
        'measured': {
            'git': git,
            'code': measure_code(),
            'suite': measure_suite(git['head']),
            'capture': measure_capture(),
            'assumptions': measure_assumptions(),
            'dependency_dag': measure_dag(),
            'forecast_artifacts': measure_forecasts(),
            'postgame': measure_postgame(),
            'governance': measure_governance(),
            'work_queue': measure_queue(),
            'superseded_state_files': measure_superseded_states(),
        },
        'declared': validate_declarations(read_declarations()),
    }
    _CACHE['state'] = out
    return out


# ----------------------------------------------------------------- render

def _t(rows, header) -> list:
    out = ['| ' + ' | '.join(header) + ' |',
           '|' + '|'.join(['---'] * len(header)) + '|']
    for r in rows:
        out.append('| ' + ' | '.join(str(x) for x in r) + ' |')
    return out


def render(s: dict) -> str:
    m = s['measured']
    g, su, cap = m['git'], m['suite'], m['capture']
    L = ['# NFL — current state',
         '',
         f'**Generated** by `{GENERATOR}` at {s["generated_at"]} from '
         f'`SYSTEM_STATE.json`. Do not hand-edit this file: regenerate it.',
         '',
         s['reading_rule'],
         '',
         '---', '',
         '## 1. Repository', '']
    L += _t([
        ['branch', f'`{g["branch"]}`'],
        ['HEAD', f'`{g["head_short"]}` — {g["head_subject"]}'],
        ['HEAD committed', g['head_committed_at']],
        ['commits on branch', g['n_commits_on_branch']],
        ['source scope', 'clean' if g['is_clean']
         else f'{len(g["dirty_source_files"])} dirty source file(s)'],
        ['dirty tree entries (source and not)',
         g['worktree'].get('n_dirty_tree_entries_observed')],
        ['code_version', f'`{g["worktree"].get("code_version")}`'],
        ['python modules', m['code']['TOTAL']['modules']],
        ['lines of python', f'{m["code"]["TOTAL"]["lines"]:,}'],
    ], ['', ''])
    L += ['', '## 2. Test suite', '']
    if su.get('state') == NOT_MEASURED:
        L += [f'**{NOT_MEASURED}** — {su["why"]}', '']
    else:
        t, b = su['totals'], su['baseline_totals']
        L += [f'Source: `{su["artifact"]}`. {su["staleness_note"]}', '']
        L += _t([[k.replace('_', ' '), t.get(k), b.get(k),
                  su['delta_totals'].get(k)]
                 for k in ('modules', 'test_functions', 'checks',
                           'failing_checks', 'raised', 'zero_check_functions',
                           'blocked_functions')],
                ['', f'at {su["measured_at_commit"]}',
                 f'baseline {su["baseline_commit"]}', 'delta'])
        L += ['', f'Verdict: **{su["verdict"]}**. Classification against the '
                  f'baseline: {su["counts_by_classification"]}.', '']
        if su['newly_introduced']:
            L += ['Newly introduced since the baseline:', '']
            L += [f'- `{r["module"]}` [{r["kind"]}] {r["detail"]}'
                  for r in su['newly_introduced']]
            L += ['']
        else:
            L += ['No item is newly introduced since the baseline.', '']
    L += ['## 3. Captured evidence', '']
    if cap.get('state') == NOT_MEASURED:
        L += [f'**{NOT_MEASURED}** — {cap["why"]}', '']
    else:
        L += [f'`nfl/vintage_manifest.jsonl` carries **{cap["manifest_rows"]} '
              f'rows**; the vintage store holds **{cap["vintage_store_files"]} '
              f'files**. Retrieval spans {cap["retrieved_at_earliest"]} to '
              f'{cap["retrieved_at_latest"]}.', '']
        L += _t(sorted(cap['by_source'].items()), ['source', 'manifest rows'])
        L += ['', f'Manifest row states: {cap["by_state"]}.', '']
    L += ['## 4. Governed assumptions', '']
    a = m['assumptions']
    if a.get('state') == NOT_MEASURED:
        L += [f'**{NOT_MEASURED}** — {a["why"]}', '']
    else:
        L += _t([[r['id'], r['status'], r['criticality']]
                 for r in a['assumptions']],
                ['assumption', 'status', 'criticality'])
        L += ['', 'A FALSIFIED assumption blocks the production path that '
              'depends on it and rewrites no model output.', '']
    L += ['## 5. Dependency DAG (P7 Phase 1)', '']
    d = m['dependency_dag']
    if d.get('state') == NOT_MEASURED:
        L += [f'**{NOT_MEASURED}** — {d["why"]}', '']
    else:
        L += [f'`{d["phase"]}`, audit **{d["audit_state"]} '
              f'{d["audit_code"]}**, {d["n_edges"]} declared edges over '
              f'{len(d["audited_roots"])} package(s), '
              f'{d["n_runtime_keyed"]} runtime-keyed read(s).', '']
        L += _t(sorted(d['readers_per_producer'].items()),
                ['producer', 'declared readers'])
        L += ['', 'Not implemented:', '']
        L += [f'- {x}' for x in d['not_implemented']]
        L += ['']
    L += ['## 6. Forecast and postgame artifacts', '']
    f, pg = m['forecast_artifacts'], m['postgame']
    L += [f'{f["sealed_run_status_files"]} `run_status.json` file(s), by '
          f'status {f["run_status_by_status"]}. '
          f'{f["live_board_directories"]} live board directory(ies).', '']
    ledg = pg['prospective_evaluation_ledger']
    L += [f'Prospective evaluation ledger: '
          + (f'{ledg["rows"]} rows over {len(ledg["blocks"])} block(s) '
             f'{ledg["blocks"]}, by status {ledg["by_status"]}'
             if 'rows' in ledg else f'{NOT_MEASURED} — {ledg["why"]}')
          + f'. Captured game outcomes: {pg["captured_outcomes"]["n"]} '
            f'({", ".join(pg["captured_outcomes"]["games"]) or "none"}).', '']
    gov = m['governance']['production_readiness']
    if gov.get('state') != NOT_MEASURED:
        L += [f'Production readiness (`{gov["artifact"]}`, updated '
              f'{gov["updated_utc"]}): {gov["by_state"]} over '
              f'{gov["n_capabilities"]} capabilities.', '']
        if gov['not_green']:
            L += [f'- {c["id"]} {c["name"]}: **{c["state"]}**'
                  for c in gov['not_green']] + ['']
    L += ['## 7. Work queue', '']
    q = m['work_queue']
    if q.get('state') == NOT_MEASURED:
        L += [f'**{NOT_MEASURED}** — {q["why"]}', '']
    else:
        L += _t([[it['id'], it['priority'], it['status'],
                  (it['blocker'][:90] if it['status'] == 'BLOCKED' else '')]
                 for it in q['items']],
                ['id', 'priority', 'status', 'blocker'])
        L += ['', 'Source: `nfl/WORK_QUEUE.md`. Full descriptions and '
              'acceptance criteria are there.', '']
    L += ['## 8. Declared — asserted, not measured here', '']
    L += ['Each of these is a statement nobody can settle by reading this '
          'repository. They are kept because they are load-bearing, and '
          'labelled because a declaration standing beside a measurement in '
          'the same voice is how this file went eleven days wrong.', '']
    for dec in s['declared']:
        L += [f'**{dec["id"]}** — {dec["claim"]}', '',
              f'- declared by {dec["declared_by"]}, {dec["declared_at"]} '
              f'({dec["status"]})',
              f'- not measurable here: {dec["why_not_measurable"]}',
              f'- what would verify it: {dec["what_would_verify"]}', '']
    sup = m['superseded_state_files']
    if sup:
        L += ['## 9. Superseded', '',
              'Hand-written state files this generated one replaces. They are '
              'kept unedited, because a note prepended to a historical '
              'document changes the document; the pointer belongs in the '
              'successor.', '']
        L += [f'- `{x["path"]}` ({x["bytes"]} bytes, sha256 {x["sha256"]}…)'
              for x in sup]
        L += ['']
    L += ['---', '',
          'To refresh: `python3.12 nfl/tools/system_state.py --write`.', '']
    return '\n'.join(L)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    s = build(fresh=True)
    if '--write' in argv:
        STATE.write_text(json.dumps(s, indent=1, sort_keys=True) + '\n')
        RENDERED.write_text(render(s))
        print(f'wrote {STATE.name} and {RENDERED.name}')
    else:
        print(json.dumps(s, indent=1, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
