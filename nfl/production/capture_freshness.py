"""How old the EVIDENCE is, and WHICH TREE that was measured in.

THE DEFECT THIS EXISTS FOR, AND IT IS MINE. On 2026-09-19 I measured capture
freshness from this branch's working tree and reported that no source was
fresher than 39.7 hours, with the official status sources at 98.3. I began
writing that up as a Sunday-readiness blocker. It was false. The scheduled
capture had been running every thirty minutes throughout, writing to the
`capture-prod` branch, and the six core sources were half an hour old.

It was the second time in this project. The 2026-09-15 reconciliation had to
withdraw "main stopped capturing on 09-11" for the same reason -- a stale
remote-tracking ref read as a dead executor.

So the rule this module makes executable: **a freshness number means nothing
unless it names the tree it was measured in**, and a tree that is not the
capture surface can only report how far behind it is, never how fresh the
system is. `measure()` therefore refuses to emit an age without a
`tree_identity` beside it, and `assess()` will not return PASS from a tree it
cannot show is current with the surface.

WHY NOT ONE EXPIRY. `nfl/production/freshness.py` is the sibling of this
module and answers a different question: whether a MODEL INPUT reaches the
ordinal it needs. That one is in ordinals because a file cannot be made fresh
by touching it. This one is in wall-clock hours because a capture is an event
in time and its staleness is a fact about the clock. They are not
interchangeable and neither subsumes the other.

Each source declares its own expiry with a reason. A single constant would
either spam the sources that republish hourly or sleep through the ones that
matter, and the one that matters most -- official inactives -- is not stale at
94 hours between slates and is catastrophically stale at 3 hours on a Sunday.
That is why `expiry_hours` is a function of the SLATE CLOCK for the
game-anchored sources and a constant only for the league-wide ones.

ABSENT IS NOT STALE, AND NEITHER IS ASSIGNED. Three states that a single
"stale" flag would collapse and that need different actions:

    FRESH      captured inside its expiry
    STALE      captured, and too long ago
    ABSENT     never captured successfully at all
    ASSIGNED   cannot be captured from here; somebody else owes it

`official_transactions` has 654 BLOCKED records and zero successes. Calling
that "stale" would suggest a refresh would fix it. It would not: there is no
verified endpoint, and the fix is an outbox entry.
"""
from __future__ import annotations

import collections
import datetime as _dt
import json
import pathlib
import re
import subprocess
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'nfl-capture-freshness-1'

#: Bumped whenever a source is added, removed or changes expiry. A registry
#: that can change silently is not a registry.
REGISTRY_VERSION = 1

#: The branch the scheduled capture writes to. NOT the branch a forecast runs
#: in, and that difference is the whole reason this module exists.
CAPTURE_SURFACE = 'capture-prod'

CODE_FRESH = 'CAPTURE_FRESH'
CODE_STALE = 'CAPTURE_STALE'
CODE_ABSENT = 'CAPTURE_ABSENT'
CODE_ASSIGNED = 'CAPTURE_ASSIGNED_ELSEWHERE'
CODE_UNDECLARED = 'CAPTURE_SOURCE_UNDECLARED'
CODE_TREE_UNVERIFIED = 'CAPTURE_TREE_NOT_VERIFIED_AGAINST_SURFACE'
CODE_TREE_BEHIND = 'CAPTURE_TREE_BEHIND_SURFACE'
CODE_ALL_FRESH = 'ALL_REQUIRED_CAPTURES_FRESH'
CODE_REFUSE = 'REQUIRED_CAPTURE_NOT_FRESH'

LEAGUE_WIDE = 'LEAGUE_WIDE'
GAME_ANCHORED = 'GAME_ANCHORED'

#: `expiry_hours` is the age at which a capture stops being usable evidence for
#: a forecast written now. `pregame_expiry_hours`, where present, replaces it
#: once the slate is inside `pregame_window_hours` of kickoff -- because the
#: same document that is perfectly good four days out is worthless ninety
#: minutes out, when it is the thing that changes.
REGISTRY = {
    'schedules': {
        'what': 'kickoff times, venue, roof, surface, coaches',
        'scope': LEAGUE_WIDE, 'expiry_hours': 48.0,
        'expiry_basis': 'a kickoff time moves rarely and a flex change is '
                        'announced days ahead; two days is loose enough not '
                        'to spam and tight enough to catch a reschedule',
        'required_for': ('capture_validation', 'team_environment'),
    },
    'weekly_rosters': {
        'what': 'the club roster with status',
        'scope': LEAGUE_WIDE, 'expiry_hours': 48.0,
        'expiry_basis': 'transactions land through the week; two days bounds '
                        'how far the player universe can have moved',
        'required_for': ('identity_resolution',),
    },
    'depth_charts': {
        'what': 'the vendor depth chart, with its own per-row instant',
        'scope': LEAGUE_WIDE, 'expiry_hours': 48.0,
        'pregame_expiry_hours': 24.0,
        'expiry_basis': 'the only source carrying a genuine effective instant; '
                        'inside a day of kickoff a chart older than a day has '
                        'missed at least one practice report',
        'required_for': ('appearance',),
    },
    'injuries': {
        'what': 'the nflverse injury table',
        'scope': LEAGUE_WIDE, 'expiry_hours': 48.0,
        'pregame_expiry_hours': 12.0,
        'expiry_basis': 'designations settle on Friday and move again on '
                        'Saturday; twelve hours inside the window is one '
                        'republication cycle',
        'required_for': (),
    },
    'official_injury_report': {
        'what': 'the league\'s own report, the authoritative designation',
        'scope': LEAGUE_WIDE, 'expiry_hours': 48.0,
        'pregame_expiry_hours': 12.0,
        'expiry_basis': 'same cycle as injuries, and this is the one that '
                        'governs when the two disagree',
        'required_for': (),
    },
    'espn_injuries_json': {
        'what': 'a second injury view, for disagreement detection',
        'scope': LEAGUE_WIDE, 'expiry_hours': 48.0,
        'expiry_basis': 'corroboration only; it never overrides the official '
                        'report, so it may lag it',
        'required_for': (),
    },
    'official_inactives': {
        'what': 'the final declaration, 90 minutes before kickoff',
        'scope': GAME_ANCHORED, 'expiry_hours': None,
        'pregame_expiry_hours': 1.5,
        'pregame_window_hours': 3.0,
        'expiry_basis': 'THE ONLY ONE WITH A HARD CLOCK. It does not exist '
                        'until T-90 and it is final once it does, so outside '
                        'the window its age is meaningless and inside the '
                        'window anything older than the window itself is a '
                        'missed capture, not a stale one.',
        'required_for': (),
    },
    'official_transactions': {
        'what': 'elevations, signings, IR moves',
        'scope': LEAGUE_WIDE, 'expiry_hours': 48.0,
        'expiry_basis': 'would bound roster movement if it existed',
        'assigned': 'OUT-017 -- no verified endpoint; a guessed URL that 404s '
                    'is indistinguishable from a real endpoint that is down',
        'required_for': (),
    },
    'pbp': {
        'what': 'play-by-play, the source of every current-season panel',
        'scope': LEAGUE_WIDE, 'expiry_hours': 96.0,
        'expiry_basis': 'it only changes when games are played, so its clock '
                        'is the slate\'s and not the wall\'s; four days spans '
                        'Thursday to Monday',
        'required_for': ('feature_build',),
    },
}

_TS = re.compile(r'^(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)')


def _now():
    return _dt.datetime.now(_dt.timezone.utc)


def _parse(t):
    if not t:
        return None
    s = str(t)
    try:
        v = _dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
        return v if v.tzinfo else v.replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        pass
    m = _TS.match(s)
    if not m:
        return None
    y, mo, d, h, mi, se = (int(x) for x in m.groups())
    return _dt.datetime(y, mo, d, h, mi, se, tzinfo=_dt.timezone.utc)


def _git(*args):
    try:
        return subprocess.run(('git',) + args, cwd=str(_REPO), timeout=60,
                              capture_output=True, text=True).stdout.strip()
    except Exception:                                          # noqa: BLE001
        return ''


def tree_identity(*, verify_surface: bool = False) -> dict:
    """WHICH TREE. Never optional, and never inferred from a source's age.

    `verify_surface` reaches the network to compare this tree against the
    capture surface. Without it the answer is UNVERIFIED -- which is a real
    answer and is not the same as "current". This executor has no egress to
    most hosts but does reach the git remote, so the caller decides.
    """
    out = {
        'repo': str(_REPO),
        'branch': _git('rev-parse', '--abbrev-ref', 'HEAD') or None,
        'head': _git('rev-parse', 'HEAD') or None,
        'capture_surface': CAPTURE_SURFACE,
        'surface_head': None,
        'surface_state': CODE_TREE_UNVERIFIED,
        'behind_surface_commits': None,
        'why': 'a freshness number measured in a tree that is not the capture '
               'surface reports how far behind that tree is, never how fresh '
               'the system is',
    }
    if not verify_surface:
        return out
    ls = _git('ls-remote', 'origin', f'refs/heads/{CAPTURE_SURFACE}')
    sha = ls.split('\t')[0].strip() if ls else ''
    if not sha:
        out['surface_state'] = CODE_TREE_UNVERIFIED
        out['why_unverified'] = 'origin did not answer for the surface ref'
        return out
    out['surface_head'] = sha
    if out['head'] == sha:
        out['surface_state'] = 'CAPTURE_TREE_IS_THE_SURFACE'
        out['behind_surface_commits'] = 0
        return out
    cnt = _git('rev-list', '--count', f'{out["head"]}..{sha}')
    if cnt.isdigit():
        out['behind_surface_commits'] = int(cnt)
        out['surface_state'] = (CODE_TREE_BEHIND if int(cnt)
                                else 'CAPTURE_TREE_CURRENT_WITH_SURFACE')
    else:
        out['why_unverified'] = (
            'the surface commit is not in this object store; fetch it before '
            'claiming a distance')
    return out


def read_manifest(path=None) -> list:
    p = pathlib.Path(path) if path else (_REPO / 'nfl' / 'vintage_manifest.jsonl')
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(errors='replace').splitlines():
        if not ln.strip():
            continue
        try:
            out.append(json.loads(ln))
        except ValueError:
            continue
    return out


def _expiry(spec, hours_to_kickoff):
    """The expiry in force, and which rule chose it. Both are reported."""
    win = spec.get('pregame_window_hours')
    pre = spec.get('pregame_expiry_hours')
    if pre is not None and hours_to_kickoff is not None:
        if win is None or hours_to_kickoff <= win:
            if hours_to_kickoff >= 0:
                return pre, 'pregame'
    return spec.get('expiry_hours'), 'standing'


def measure(*, rows=None, now=None, hours_to_kickoff=None,
            verify_surface=False) -> dict:
    """Per declared source: when, what, how old, and against which expiry."""
    rows = read_manifest() if rows is None else rows
    now = now or _now()
    seen = collections.defaultdict(
        lambda: {'states': collections.Counter(), 'codes': collections.Counter(),
                 'last': None, 'first': None, 'blobs': set(), 'evidence': None})
    for r in rows:
        s = r.get('source')
        if not s:
            continue
        a = seen[s]
        a['states'][r.get('state') or '?'] += 1
        if r.get('code'):
            a['codes'][str(r['code'])] += 1
        if r.get('state') != 'PASS':
            continue
        v = r.get('value') or {}
        e = r.get('evidence') or {}
        t = _parse(v.get('retrieved_at') or e.get('retrieved_at')
                   or r.get('capture_id'))
        b = (v.get('blob') or e.get('blob') or '')
        if b:
            a['blobs'].add(b.split('/')[-1])
        if t is None:
            continue
        if a['first'] is None or t < a['first']:
            a['first'] = t
        if a['last'] is None or t > a['last']:
            a['last'] = t
            a['evidence'] = {
                'capture_id': r.get('capture_id'),
                'blob': b or None,
                'sha256': v.get('sha256'),
                'sha256_is_of': v.get('sha256_is_of'),
                'source_timestamp': (v.get('source_timestamp_header')
                                     or v.get('published_at')),
                'http_status': v.get('http_status'),
                'n_bytes': v.get('n_bytes'),
                'effective_scope': v.get('effective_scope'),
                'game_id': v.get('game_id'),
            }
    out = {}
    for sid, spec in sorted(REGISTRY.items()):
        a = seen.get(sid)
        exp, exp_rule = _expiry(spec, hours_to_kickoff)
        rec = {
            'source': sid, 'what': spec['what'], 'scope': spec['scope'],
            'expiry_hours': exp, 'expiry_rule': exp_rule,
            'expiry_basis': spec['expiry_basis'],
            'required_for': list(spec.get('required_for') or ()),
            'assigned': spec.get('assigned'),
            'n_records': sum((a or {}).get('states', {}).values()) if a else 0,
            'states': dict(a['states']) if a else {},
            'last_retrieved_utc': None, 'first_retrieved_utc': None,
            'age_hours': None, 'n_distinct_blobs': len(a['blobs']) if a else 0,
            'newest_evidence': (a or {}).get('evidence'),
        }
        if a and a['last'] is not None:
            rec['last_retrieved_utc'] = a['last'].isoformat()
            rec['first_retrieved_utc'] = a['first'].isoformat()
            rec['age_hours'] = round(
                (now - a['last']).total_seconds() / 3600.0, 2)
        if spec.get('assigned'):
            rec['status'] = CODE_ASSIGNED
        elif rec['age_hours'] is None:
            rec['status'] = CODE_ABSENT
        elif exp is None:
            # Outside its own window a game-anchored source has no meaningful
            # age. Saying FRESH would be as wrong as saying STALE.
            rec['status'] = 'CAPTURE_OUT_OF_WINDOW'
        else:
            rec['status'] = (CODE_FRESH if rec['age_hours'] <= exp
                             else CODE_STALE)
        out[sid] = rec
    undeclared = sorted(set(seen) - set(REGISTRY))
    return {
        'spec_version': SPEC_VERSION, 'registry_version': REGISTRY_VERSION,
        'measured_at_utc': now.isoformat(),
        'hours_to_kickoff': hours_to_kickoff,
        'tree_identity': tree_identity(verify_surface=verify_surface),
        'sources': out,
        'undeclared_sources_present': undeclared,
    }


def assess(m: dict) -> Outcome:
    """FAIL-CLOSED, and it will not pass from a tree it cannot place.

    Two independent reasons to refuse, reported separately because they need
    different actions: a required source is not fresh (capture again), or the
    tree cannot be shown current with the capture surface (merge, or verify).
    """
    ti = m['tree_identity']
    required = [r for r in m['sources'].values() if r['required_for']]
    bad = [r for r in required if r['status'] not in (CODE_FRESH,)]
    ev = {'spec_version': SPEC_VERSION, 'registry_version': REGISTRY_VERSION,
          'tree_identity': ti,
          'measured_at_utc': m['measured_at_utc'],
          'required_sources': sorted(r['source'] for r in required),
          'not_fresh': [{'source': r['source'], 'status': r['status'],
                         'age_hours': r['age_hours'],
                         'expiry_hours': r['expiry_hours'],
                         'expiry_rule': r['expiry_rule']} for r in bad],
          'undeclared_sources_present': m['undeclared_sources_present']}
    if ti['surface_state'] in (CODE_TREE_UNVERIFIED, CODE_TREE_BEHIND):
        return Outcome.blocked(
            ti['surface_state'],
            f'this tree is {ti["branch"]} at {str(ti["head"])[:12]} and has '
            f'not been shown current with {CAPTURE_SURFACE} '
            f'(behind_surface_commits='
            f'{ti["behind_surface_commits"]}). A freshness number from a tree '
            f'that is behind the capture surface reports the tree, not the '
            f'system -- which is exactly the error this module exists for.',
            cause=Cause.ENVIRONMENT, **ev)
    if bad:
        return Outcome.blocked(
            CODE_REFUSE,
            f'{len(bad)} required source(s) are not fresh: '
            f'{[r["source"] for r in bad]}.',
            cause=Cause.DATA, **ev)
    return Outcome.ok(
        CODE_ALL_FRESH, value=dict(ev),
        detail=f'{len(required)} required source(s) fresh in '
               f'{ti["branch"]} at {str(ti["head"])[:12]}', **ev)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--verify-surface', action='store_true',
                    help='reach origin to place this tree against '
                         f'{CAPTURE_SURFACE}')
    ap.add_argument('--hours-to-kickoff', type=float, default=None)
    ap.add_argument('--json', action='store_true')
    a = ap.parse_args()
    mm = measure(hours_to_kickoff=a.hours_to_kickoff,
                 verify_surface=a.verify_surface)
    o = assess(mm)
    if a.json:
        print(json.dumps({'measure': mm, 'state': o.state.value,
                          'code': o.code, 'detail': o.detail}, indent=1))
    else:
        ti = mm['tree_identity']
        print(f'tree {ti["branch"]} @ {str(ti["head"])[:12]} vs '
              f'{CAPTURE_SURFACE}: {ti["surface_state"]} '
              f'(behind {ti["behind_surface_commits"]})')
        print(f'{"source":24s} {"status":26s} {"age_h":>8s} {"exp_h":>7s} '
              f'{"rule":9s} blobs required_for')
        for sid, r in mm['sources'].items():
            print(f'{sid:24s} {r["status"]:26s} '
                  f'{"" if r["age_hours"] is None else r["age_hours"]:>8} '
                  f'{"" if r["expiry_hours"] is None else r["expiry_hours"]:>7} '
                  f'{r["expiry_rule"]:9s} {r["n_distinct_blobs"]:5d} '
                  f'{",".join(r["required_for"]) or "-"}')
        print(f'\n{o.state.value}[{o.code}] {o.detail}')
