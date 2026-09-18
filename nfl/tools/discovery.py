#!/usr/bin/env python3.12
"""CONTINUOUS_DISCOVERY: inspect the repository's own signals, mechanically.

    python3.12 nfl/tools/discovery.py           # print
    python3.12 nfl/tools/discovery.py --write   # write nfl/DISCOVERY.json

WHY THIS IS A TOOL AND NOT A CHECKLIST

The directive says to inspect prospective results, assumption statuses,
calibration, unresolved gaps, suite classifications and newly available data
after every queue cycle. Done by hand that is six greps that get shorter every
time they are run, and the one that stops being run is the one that would have
found something.

It already nearly happened. `INFORMATION_GAP_REGISTRY.json` records
"MEASURED: both 404 for 2026 as of 2026-09-08" for the participation sources.
Ten days later the sibling `injuries` source had been publishing since
2026-09-07 -- 9 content-addressed vintages, weeks 1 and 2, with report_status
and practice_status -- and nothing in the repository said so, because the
registry has no freshness field and nothing re-reads it. `newly_publishing`
below is that check, and it is the reason this file exists.

WHAT IT REFUSES TO DO

**It does not score candidates.** The ranking the directive asks for is
downstream impact x uncertainty x measurability x expected value of
information, and not one of those four is measurable from this tree. Emitting
numbers for them would be four silent constants dressed as a measurement, which
is the defect this project audits itself for. So this tool surfaces the
EVIDENCE for each factor and names the candidate; the ranking is a judgement,
it lives in `nfl/WORK_QUEUE.md`, and it carries its reasoning in words.

**It does not invent work.** A candidate appears only when a mechanical
condition fires: a source began publishing after something recorded it absent,
a gap claim is older than its recheck horizon, a CRITICAL assumption is
falsified with no successor specification, a debt blocks promotion and names a
next action. An empty `candidates` list is a valid and expected result, and it
means do validation and monitoring rather than reach for something to build.
"""
from __future__ import annotations

import collections
import datetime as dt
import glob
import json
import pathlib
import re
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

OUT = _REPO / 'nfl' / 'DISCOVERY.json'
GENERATOR = 'nfl/tools/discovery.py'
SPEC_VERSION = 'nfl-continuous-discovery-1'

#: A gap claim older than this, with no recheck, is surfaced. Not a threshold
#: on truth -- a claim does not become false by ageing. It is a threshold on
#: ATTENTION: the injuries source began publishing eleven days after the claim
#: that its sibling was absent, and nobody looked.
GAP_RECHECK_DAYS = 7

#: A source whose first successful capture is this recent is "newly
#: publishing". Read together with whether anything earlier recorded it absent.
NEWLY_PUBLISHING_DAYS = 21

_DATE = re.compile(r'(20\d\d-\d\d-\d\d)')
_NOT_PUBLISHED = ('SOURCE_NOT_YET_PUBLISHED', 'NOT_PUBLISHED', '404',
                  'NOT_FOUND')


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse(t):
    if not t:
        return None
    s = str(t)
    try:
        v = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
        # A BARE DATE PARSES NAIVE. The gap registry's claims are dates
        # ("as of 2026-09-08") and its blobs also carry full instants, so both
        # shapes reach here; subtracting a naive one from an aware `now` raises
        # rather than being wrong, which is the right failure but not a useful
        # one. Naive is read as UTC, which is what every stamp in this
        # repository is.
        return v if v.tzinfo else v.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        pass
    m = re.match(r'^(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)', s)
    if m:
        y, mo, d, h, mi, se = (int(x) for x in m.groups())
        return dt.datetime(y, mo, d, h, mi, se, tzinfo=dt.timezone.utc)
    return None


def _age_days(t) -> float | None:
    p = _parse(t)
    return None if p is None else round((_now() - p).total_seconds() / 86400, 2)


# ------------------------------------------------------------- captures

def captures() -> dict:
    """Per source: when it last succeeded, and whether it is newly publishing."""
    man = _REPO / 'nfl' / 'vintage_manifest.jsonl'
    if not man.exists():
        return {'state': 'NOT_MEASURED', 'why': 'vintage_manifest.jsonl absent'}
    first_ok, last_ok, states, absent_codes, blobs = {}, {}, {}, {}, {}
    for ln in man.read_text(errors='replace').splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        s = d.get('source') or '?'
        st = d.get('state') or '?'
        states.setdefault(s, collections.Counter())[st] += 1
        code = str(d.get('code') or '')
        if any(k in code.upper() for k in _NOT_PUBLISHED):
            absent_codes.setdefault(s, collections.Counter())[code] += 1
        if st != 'PASS':
            continue
        v = d.get('value') or {}
        ev = d.get('evidence') or {}
        t = (v.get('retrieved_at') or ev.get('retrieved_at')
             or d.get('capture_id'))
        p = _parse(t)
        if p is not None:
            if s not in first_ok or p < first_ok[s]:
                first_ok[s] = p
            if s not in last_ok or p > last_ok[s]:
                last_ok[s] = p
        b = (v.get('blob') or ev.get('blob') or '')
        if b:
            blobs.setdefault(s, set()).add(b.split('/')[-1])
    out = {}
    for s in sorted(states):
        f, l = first_ok.get(s), last_ok.get(s)
        out[s] = {
            'states': dict(states[s]),
            'first_success_utc': f.isoformat() if f else None,
            'last_success_utc': l.isoformat() if l else None,
            'days_since_last_success': (
                _age_days(l.isoformat()) if l else None),
            'days_since_first_success': (
                _age_days(f.isoformat()) if f else None),
            'n_distinct_blobs': len(blobs.get(s, ())),
            'absent_codes_recorded': dict(absent_codes.get(s, {})),
        }
    return out


def newly_publishing(caps: dict) -> list:
    """A source that started succeeding recently AND was recorded absent.

    Both halves matter. "Recently started" alone is just a new source; "was
    recorded absent" alone is history. Together they are a claim in this
    repository that has been overtaken by data in this repository.
    """
    out = []
    for s, c in (caps or {}).items():
        if not isinstance(c, dict) or c.get('days_since_first_success') is None:
            continue
        if c['days_since_first_success'] > NEWLY_PUBLISHING_DAYS:
            continue
        if not c['absent_codes_recorded']:
            continue
        out.append({
            'source': s,
            'first_success_utc': c['first_success_utc'],
            'days_since_first_success': c['days_since_first_success'],
            'n_distinct_blobs': c['n_distinct_blobs'],
            'previously_recorded_absent_as': c['absent_codes_recorded'],
            'why_it_matters': 'this source was recorded absent and is now '
                              'publishing; anything that treated it as '
                              'unavailable may be acting on a stale fact',
        })
    return out


# ---------------------------------------------------------- gap registry

def gaps() -> list:
    p = _REPO / 'nfl' / 'INFORMATION_GAP_REGISTRY.json'
    if not p.exists():
        return []
    d = json.loads(p.read_text())
    items = d if isinstance(d, list) else (
        d.get('gaps') or d.get('items') or list(d.values()))
    out = []
    for g in items:
        if not isinstance(g, dict):
            continue
        blob = json.dumps(g)
        dates = sorted(set(_DATE.findall(blob)))
        newest = dates[-1] if dates else None
        out.append({
            'id': g.get('id'),
            'action': g.get('action'),
            'evidence_status': (g.get('evidence_status') or '')[:200],
            'newest_date_in_claim': newest,
            'claim_age_days': _age_days(newest) if newest else None,
            'stale_beyond_recheck_horizon': bool(
                newest and (_age_days(newest) or 0) > GAP_RECHECK_DAYS),
            'has_no_date_at_all': not dates,
        })
    return out


# ----------------------------------------------------------- assumptions

def assumptions() -> dict:
    try:
        from nfl.production.assumptions import registry as AR
        rows = [{'id': a.id, 'status': a.status,
                 'criticality': a.criticality,
                 'test': a.test,
                 'has_evidence': bool(a.evidence),
                 'downstream': list(a.downstream_dependencies)}
                for a in AR.all_assumptions()]
    except Exception as exc:                                   # noqa: BLE001
        return {'state': 'NOT_MEASURED',
                'why': f'{type(exc).__name__}: {exc}'}
    spec_dir = _REPO / 'nfl' / 'research' / 'assumptions'
    specs = {p.name for p in spec_dir.glob('*')} if spec_dir.exists() else set()
    for r in rows:
        stem = r['id'].split('_')[0]
        r['has_successor_spec'] = any(
            n.startswith(stem) and 'SUCCESSOR' in n.upper() for n in specs)
        r['untested'] = r['test'] in (None, '', 'NOT_YET_WRITTEN')
    return {'n': len(rows),
            'by_status': dict(collections.Counter(r['status'] for r in rows)),
            'assumptions': rows}


# ----------------------------------------------------------- suite state

def suite() -> dict:
    fs = sorted(glob.glob(str(
        _REPO / 'nfl/research/suite_attribution/SUITE_DIFF_*.json')))
    if not fs:
        return {'state': 'NOT_MEASURED', 'why': 'no SUITE_DIFF artifact'}
    p = pathlib.Path(max(fs, key=lambda x: pathlib.Path(x).stat().st_mtime))
    d = json.loads(p.read_text())
    return {'artifact': str(p.relative_to(_REPO)),
            'measured_at_commit': (d.get('current') or {}).get('commit'),
            'totals': (d.get('current') or {}).get('totals'),
            'counts_by_classification': d.get('counts_by_classification'),
            'n_newly_introduced': len(d.get('newly_introduced') or [])}


# ------------------------------------------------------------ prospective

def prospective() -> dict:
    """How much GRADED prospective evidence exists. The gate's own floor."""
    led = _REPO / 'nfl/research/postgame/PROSPECTIVE_EVALUATION_LEDGER.jsonl'
    rows = []
    if led.exists():
        for ln in led.read_text().splitlines():
            if ln.strip():
                try:
                    rows.append(json.loads(ln))
                except ValueError:
                    pass
    by_status = collections.Counter(r.get('status') or '?' for r in rows)
    graded = [r for r in rows if (r.get('status') or '') == 'GRADED']
    outcomes = sorted((_REPO / 'nfl').glob(
        '**/POSTGAME_OUTCOME/OUTCOME.json'))
    return {
        'ledger_rows': len(rows),
        'by_status': dict(by_status),
        'n_graded_blocks': len(graded),
        'blocks': sorted({r.get('block_id') for r in rows if r.get('block_id')}),
        'captured_game_outcomes': len(outcomes),
        'note': 'the calibration gate is a GATE and its floor is 300 graded '
                'units, rising to 500 below 0.2 implied probability. These '
                'counts are blocks and games, not graded units, and they are '
                'not the same thing -- do not read one for the other.',
    }


# --------------------------------------------------------- technical debt

def debt() -> list:
    p = _REPO / 'nfl' / 'TECHNICAL_DEBT_REGISTRY.json'
    if not p.exists():
        return []
    d = json.loads(p.read_text())
    items = d if isinstance(d, list) else (
        d.get('debts') or d.get('items') or list(d.values()))
    out = []
    for it in items:
        if isinstance(it, list):
            out.extend(x for x in it if isinstance(x, dict))
        elif isinstance(it, dict):
            out.append(it)
    return [{'id': x.get('id'), 'severity': x.get('severity'),
             'blocks_promotion': x.get('blocks_promotion'),
             'blocks_research': x.get('blocks_research'),
             'state': (x.get('state') or '')[:160],
             'next_action': (x.get('next_action') or '')[:200]}
            for x in out]


# ------------------------------------------------------------- candidates

def candidates(sig: dict) -> list:
    """Mechanically detected, never invented. An empty list is a real answer."""
    out = []
    for n in sig['newly_publishing']:
        out.append({
            'trigger': 'SOURCE_NEWLY_PUBLISHING',
            'subject': n['source'],
            'evidence': n,
            'impact_evidence': 'a source recorded absent is now publishing, '
                               'so any layer that was blocked on it may not '
                               'be blocked any more',
            'measurability_evidence': f'{n["n_distinct_blobs"]} '
                                      f'content-addressed vintage(s) already '
                                      f'captured in this repository',
            'ranking': 'NOT SCORED HERE -- see nfl/WORK_QUEUE.md'})
    for g in sig['gaps']:
        if g['stale_beyond_recheck_horizon'] and g['action'] in (
                'BLOCKED', 'HOLD', 'PROSPECTIVE_ONLY'):
            out.append({
                'trigger': 'GAP_CLAIM_OLDER_THAN_RECHECK_HORIZON',
                'subject': g['id'],
                'evidence': g,
                'impact_evidence': 'the gap is recorded as blocking or held '
                                   'on a claim nobody has re-read',
                'measurability_evidence': 'rechecking is a capture attempt, '
                                          'not a model change',
                'ranking': 'NOT SCORED HERE -- see nfl/WORK_QUEUE.md'})
    a = sig['assumptions']
    for r in (a.get('assumptions') or []):
        if r['status'] == 'FALSIFIED' and r['criticality'] == 'CRITICAL' \
                and not r['has_successor_spec']:
            out.append({
                'trigger': 'CRITICAL_ASSUMPTION_FALSIFIED_WITHOUT_SUCCESSOR',
                'subject': r['id'], 'evidence': r,
                'impact_evidence': f'blocks {len(r["downstream"])} declared '
                                   f'downstream consumer(s)',
                'measurability_evidence': 'the falsification already ran; the '
                                          'successor specification is writing',
                'ranking': 'NOT SCORED HERE -- see nfl/WORK_QUEUE.md'})
        if r['untested'] and r['criticality'] == 'CRITICAL':
            out.append({
                'trigger': 'CRITICAL_ASSUMPTION_UNTESTED',
                'subject': r['id'], 'evidence': r,
                'impact_evidence': f'blocks {len(r["downstream"])} declared '
                                   f'downstream consumer(s)',
                'measurability_evidence': 'the test is NOT_YET_WRITTEN; '
                                          'measurability is unestablished',
                'ranking': 'NOT SCORED HERE -- see nfl/WORK_QUEUE.md'})
    for x in sig['technical_debt']:
        if x.get('blocks_promotion') and (x.get('next_action') or '').strip():
            out.append({
                'trigger': 'DEBT_BLOCKS_PROMOTION_WITH_A_NAMED_NEXT_ACTION',
                'subject': x['id'], 'evidence': x,
                'impact_evidence': 'blocks promotion by its own declaration',
                'measurability_evidence': x['next_action'],
                'ranking': 'NOT SCORED HERE -- see nfl/WORK_QUEUE.md'})
    return out


def build() -> dict:
    caps = captures()
    sig = {
        'captures': caps,
        'newly_publishing': newly_publishing(caps),
        'gaps': gaps(),
        'assumptions': assumptions(),
        'suite': suite(),
        'prospective': prospective(),
        'technical_debt': debt(),
    }
    return {
        'spec_version': SPEC_VERSION,
        'generated_by': GENERATOR,
        'generated_at': _now().isoformat(),
        'ranking_rule':
            'Candidates are DETECTED here and RANKED in nfl/WORK_QUEUE.md. '
            'The four factors -- downstream impact, uncertainty, '
            'measurability, expected value of information -- are judgements, '
            'and none is measurable from this repository. A number for any of '
            'them here would be a silent constant wearing a measurement\'s '
            'clothes.',
        'empty_is_a_result':
            'An empty candidate list means do validation and monitoring, not '
            'find something to build.',
        'signals': sig,
        'candidates': candidates(sig),
    }


def main() -> int:
    d = build()
    if '--write' in sys.argv[1:]:
        OUT.write_text(json.dumps(d, indent=1, sort_keys=True,
                                  default=str) + '\n')
        print(f'wrote {OUT.relative_to(_REPO)}')
        print(f'{len(d["candidates"])} candidate(s) detected')
        for c in d['candidates']:
            print(f'  {c["trigger"]:52s} {c["subject"]}')
    else:
        print(json.dumps(d, indent=1, sort_keys=True, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
