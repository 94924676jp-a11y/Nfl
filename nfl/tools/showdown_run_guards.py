"""Fail-closed guards for one Showdown scenario run: starter-state integrity and the execution receipt.

Independent P0 regression closure, 2026-10-08. Standard library only, so the same functions can be exercised by an
independent harness without importing the model.

STARTER STATE (fixtures QB-*). A scenario says who starts at QB for each club, which players are designated, and what
the scenario is. The built slate state must say the same thing, POSITIVELY and COMPLETELY, before any projection or
simulation runs:

  SCENARIO          the state carries this scenario's identity (bound by `bind_scenario`), not another's
  IDENTITY          every expected player exists under his canonical id, and his id agrees with the identity source
  TEAM              each expected starter is on the club he is expected to start for
  STARTING_FLAG     each expected starter is flagged as starting; no other QB of that club is
  AVAILABILITY      each expected starter is not absent
  STARTER_EVIDENCE  each expected starter carries evidence bound to this scenario's starters file
  DESIGNATION       each designated name is exactly one player carrying that designation, and an OUT designation
                    is an absent status (an OUT may not be overwritten by an active one)
  ORDINARY_OUT      players the scenario declares out are absent

Not a one-QB rule: an active backup or package QB with no starting flag is legitimate.

EXECUTION RECEIPT (fixtures READY-*). The build writes RUN_RECEIPT.json as its LAST act, binding run id, commit,
scenario identity, freeze seal, environment and the sha256 of every football-state and publication artifact.
Finalization requires that receipt, from THIS run, at THIS commit, with every artifact present and unchanged, a
replay that exited 0, and a replay whose football state is the receipt's. Matching upload bytes alone never pass.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import sys

RECEIPT = 'RUN_RECEIPT.json'
SPEC = 'showdown-run-guards-1'
#: absent statuses (availability.ABSENT_STATUSES) plus the plain OUT a designation may carry
ABSENT_DEFAULT = ('CONFIRMED_INACTIVE', 'REPORTED_INACTIVE_OFFICIAL_RELEASE_CITED', 'REPORTED_INACTIVE_HIGH_CONFIDENCE',
                  'REPORTED_OUT_UNVERIFIED', 'NO_OFFENSIVE_ROLE', 'OUT', 'INACTIVE')


def sha256_file(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _canon(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def starters_digest(starters):
    """Digest of the scenario's starter evidence ({name: club}); what a starter's evidence must be bound to."""
    return 'stv:' + _canon(starters or {})[:32]


# ------------------------------------------------------------------ scenario identity and binding
def scenario_identity(tag, scenario, designations, starters):
    """What the scenario IS: its tag, name, designations and starters. Not where it ran."""
    return 'scn:' + _canon({'tag': tag, 'scenario': scenario, 'designations': designations or {},
                            'starters': starters or {}})[:32]


def identity_from_depth_chart(csv_path, names):
    """Canonical (gsis) id per name and club from the captured depth chart: the latest snapshot per club.
    An independent identity source -- not the slate state's own resolver."""
    rows = list(csv.DictReader(open(csv_path, newline='')))
    latest = {}
    for r in rows:
        c = r.get('team') or r.get('club_code')
        latest[c] = max(latest.get(c, ''), r.get('dt') or '')
    out = {}
    for r in rows:
        c = r.get('team') or r.get('club_code')
        if (r.get('dt') or '') == latest.get(c) and r.get('player_name') in names and r.get('gsis_id'):
            out.setdefault(r['player_name'], set()).add((r['gsis_id'], c))
    return {n: sorted(v) for n, v in out.items()}


def expected_state(tag, scenario, designations, starters, identity):
    """The expectation a state must meet. `identity`: {name: [(canonical_id, club), ...]} from an independent
    source. A name with no identity, or with two, is refused rather than guessed."""
    problems, ids = [], {}
    for n in sorted(set(starters) | set(designations or {})):
        got = identity.get(n) or []
        if len(got) == 1:
            ids[n] = got[0][0]
        elif n in (starters or {}) or len(got) > 1:
            # a starter must be identified; an ambiguous identity is never guessed. A designated player the
            # identity source does not list (a defender DK does not price) is checked by name on the slate only.
            problems.append(f'IDENTITY_SOURCE:{n}:{len(got)}')
    return {'scenario_identity': scenario_identity(tag, scenario, designations, starters),
            'starting_qbs': {club: ids.get(n) for n, club in (starters or {}).items()},
            'starter_names': dict(starters or {}),
            'required_ids': sorted(ids[n] for n in (starters or {}) if n in ids),
            'ordinary_out': sorted(ids[n] for n, s in (designations or {}).items()
                                   if str(s).upper() == 'OUT' and n in ids),
            'designations': dict(designations or {}),
            'identity_problems': problems}


def bind_scenario(state, identity, starters_sha256, starter_tier, known_at=None):
    """Stamp the scenario identity on the state and evidence on each named starter's context. Metadata only: no
    projection input is changed (the TB@DAL equivalence check compares projection rows and draws)."""
    state['scenario_identity'] = identity
    known_at = known_at or dt.datetime.now(dt.timezone.utc).isoformat()
    for p in state.get('players', {}).values():
        ctx = p.get('predicted_lineup_context') or {}
        if ctx.get('in_predicted_starting_group'):
            ctx['evidence'] = {'confirmed': True, 'tier': starter_tier, 'source_digest': starters_sha256,
                               'known_at': known_at}
    return state


def _canonical(p):
    a, b = p.get('canonical_player_id'), p.get('gsis_id')
    if a and b and a != b:
        return None
    return a or b


def verify_starter_state(state, expected, absent_statuses=ABSENT_DEFAULT, starters_sha256=None):
    """Reason codes for every way the state disagrees with the expectation; [] only when all of it holds."""
    bad = list(expected.get('identity_problems') or [])
    if state.get('scenario_identity') != expected['scenario_identity']:
        bad.append(f'SCENARIO:{state.get("scenario_identity")}!={expected["scenario_identity"]}')
    players = list((state.get('players') or {}).values())
    by_id = {}
    for p in players:
        c = _canonical(p)
        if c:
            by_id.setdefault(c, []).append(p)
    for pid in expected['required_ids']:
        if len(by_id.get(pid, [])) != 1:
            bad.append(f'IDENTITY:{pid}:{len(by_id.get(pid, []))}')
    absent = set(absent_statuses)
    for club, pid in expected['starting_qbs'].items():
        hits = by_id.get(pid) or []
        if len(hits) != 1:
            bad.append(f'STARTER_MISSING:{club}:{pid}')
            continue
        p = hits[0]
        ctx = p.get('predicted_lineup_context') or {}
        av = p.get('current_availability') or {}
        if p.get('team') != club or (ctx.get('relayed_club') and ctx.get('relayed_club') != club):
            bad.append(f'TEAM:{pid}:{p.get("team")}/{ctx.get("relayed_club")}!={club}')
        if ctx.get('in_predicted_starting_group') is not True:
            bad.append(f'STARTING_FLAG:{pid}')
        if av.get('status') in absent or str(av.get('designation') or '').upper() == 'OUT':
            bad.append(f'STARTER_AVAILABILITY:{pid}:{av.get("status")}')
        ev = ctx.get('evidence') or {}
        if ev.get('confirmed') is not True or not ev.get('source_digest') or not ev.get('tier'):
            bad.append(f'STARTER_EVIDENCE:{pid}')
        elif starters_sha256 and ev.get('source_digest') != starters_sha256:
            bad.append(f'STARTER_EVIDENCE_FOREIGN:{pid}')
    # exactly the expected starter carries the starting flag among each club's QBs (backups stay legitimate)
    for club, pid in expected['starting_qbs'].items():
        flagged = sorted(_canonical(p) or '?' for p in players
                         if p.get('team') == club and p.get('position', 'QB') == 'QB'
                         and (p.get('predicted_lineup_context') or {}).get('in_predicted_starting_group') is True)
        if flagged and flagged != [pid]:
            bad.append(f'STARTER_SET:{club}:{flagged}')
    for pid in expected['ordinary_out']:
        hits = by_id.get(pid) or []
        if len(hits) > 1 or (hits and (hits[0].get('current_availability') or {}).get('status') not in absent):
            bad.append(f'ORDINARY_OUT:{pid}')       # absent from the slate entirely is not a lineup risk
    for name, des in (expected.get('designations') or {}).items():
        hits = [p for p in players if p.get('name') == name]
        if not hits:
            continue        # a designated player DraftKings does not price is outside the slate, not a mismatch
        av = (hits[0].get('current_availability') or {}) if len(hits) == 1 else {}
        if len(hits) != 1 or str(av.get('designation') or '').upper() != str(des).upper():
            bad.append(f'DESIGNATION:{name}')
        elif str(des).upper() == 'OUT' and av.get('status') not in absent:
            bad.append(f'OUT_OVERWRITTEN:{name}:{av.get("status")}')
    return bad


# ------------------------------------------------------------------ execution receipt
def git_head(repo):
    try:
        r = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=20)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:  # noqa: BLE001
        return None


def tracked_code_dirty(repo):
    """Tracked .py files that differ from HEAD. None if it cannot be determined (treated as dirty)."""
    try:
        r = subprocess.run(['git', '-C', str(repo), 'status', '--porcelain', '--untracked-files=no', '--', '*.py'],
                           capture_output=True, text=True, timeout=60)
        return sorted(l[3:] for l in r.stdout.splitlines()) if r.returncode == 0 else None
    except Exception:  # noqa: BLE001
        return None


def environment_fingerprint(env):
    keep = {k: v for k, v in env.items() if k.startswith('SHOWDOWN_') and k not in ('SHOWDOWN_RUN_ID',)}
    return {'python': sys.version.split()[0], 'showdown_env': keep, 'sha256': _canon(keep)}


def football_bundle(sd, tag):
    sd = pathlib.Path(sd)
    return {k: sd / f'SHOWDOWN_{tag}_{k}' for k in ('STATE.json', 'PROJ.json', 'DRAWS.json', 'WORLDS.npz')}


def write_receipt(sd, *, run_id, commit, scenario, scenario_identity, freeze_seal, env, tag, publication):
    """The build's last act. `publication`: the upload, lineups, projections and board it produced."""
    sd = pathlib.Path(sd)
    arts = {}
    for k, p in {**{f'football/{p.name}': p for p in football_bundle(sd, tag).values()},
                 **{f'publication/{pathlib.Path(p).name}': p for p in publication}}.items():
        arts[k] = sha256_file(p) if pathlib.Path(p).is_file() else None
    for extra in ('ROLE_STATE.json', 'DST_RATES.json'):
        if (sd / extra).is_file():
            arts[f'football/{extra}'] = sha256_file(sd / extra)
    body = {'ARTIFACT': 'SHOWDOWN_RUN_RECEIPT', 'spec': SPEC, 'terminal': 'COMPLETE' if all(arts.values()) else 'PARTIAL',
            'run_id': run_id, 'commit': commit, 'scenario': scenario, 'scenario_identity': scenario_identity,
            'freeze_seal': freeze_seal, 'environment': environment_fingerprint(env), 'tag': tag,
            'artifacts': arts, 'completed_at': dt.datetime.now(dt.timezone.utc).isoformat()}
    (sd / RECEIPT).write_text(json.dumps(body, indent=1, sort_keys=True))
    return body


def verify_receipt(sd, run, tag, scenario, *, replay_rc=None, replay_dir=None):
    """Blockers for finalization. `run`: {'run_id', 'commit', 'freeze_seal', 'scenario_identity', 'environment_sha256',
    'repo'} from the CURRENT run. Every check is independent: no single matching hash can stand in for another."""
    blockers = []
    sd = pathlib.Path(sd)
    if not run or not run.get('run_id') or not run.get('commit'):
        return ['RUN_CONTEXT_ABSENT (no current run id / commit; a direct or legacy call cannot finalize)']
    if replay_rc is None:
        blockers.append('REPLAY_NOT_RUN')
    elif replay_rc != 0:
        blockers.append(f'REPLAY_EXIT_NONZERO rc={replay_rc} (a failed replay blocks whatever its output hash)')
    rp = sd / RECEIPT
    if not rp.is_file():
        return blockers + ['RUN_RECEIPT_ABSENT (the build never recorded completion)']
    try:
        r = json.loads(rp.read_text())
    except Exception as e:  # noqa: BLE001
        return blockers + [f'RUN_RECEIPT_UNREADABLE {e}']
    if r.get('terminal') != 'COMPLETE':
        blockers.append(f'RUN_RECEIPT_NOT_TERMINAL {r.get("terminal")}')
    for k, want in (('run_id', run['run_id']), ('commit', run['commit']), ('scenario', scenario), ('tag', tag),
                    ('freeze_seal', run.get('freeze_seal')), ('scenario_identity', run.get('scenario_identity'))):
        if want is None or r.get(k) != want:
            blockers.append(f'RUN_RECEIPT_{k.upper()}_MISMATCH {str(r.get(k))[:16]} != {str(want)[:16]}')
    if run.get('environment_sha256') and (r.get('environment') or {}).get('sha256') != run['environment_sha256']:
        blockers.append('RUN_RECEIPT_ENVIRONMENT_MISMATCH')
    head = git_head(run['repo']) if run.get('repo') else run['commit']
    if head != run['commit']:
        blockers.append(f'COMMIT_MOVED_DURING_RUN {str(run["commit"])[:12]} -> {str(head)[:12]}')
    arts = r.get('artifacts') or {}
    need = [f'football/{p.name}' for p in football_bundle(sd, tag).values()]
    for k in need:
        if not arts.get(k):
            blockers.append(f'FOOTBALL_BUNDLE_INCOMPLETE {k}')
    for k, want in arts.items():
        p = sd / k.split('/', 1)[1]
        if not p.is_file():
            blockers.append(f'ARTIFACT_MISSING {k}')
        elif want and sha256_file(p) != want:
            blockers.append(f'ARTIFACT_CHANGED {k}')
    if replay_dir is not None:
        for k in need:
            q = pathlib.Path(replay_dir) / k.split('/', 1)[1]
            if not q.is_file():
                blockers.append(f'REPLAY_FOOTBALL_STATE_ABSENT {k}')
            elif arts.get(k) and sha256_file(q) != arts[k]:
                blockers.append(f'REPLAY_FOOTBALL_STATE_DIFFERS {k} (matching portfolio bytes cannot stand in)')
    return blockers


# ------------------------------------------------------------------ football-model completeness (owner directive 2026-10-08)
#: The club environment (team volume, scoring centre) is a club-level blend of the club's own history: current-season
#: games before the slate plus the prior season at proj_v1.TEAM_VOLUME_PRIOR_GAMES pseudo-games. It represents a
#: quarterback only if he threw a MAJORITY of the club's pass attempts in that blend. Below that, the environment is
#: another QB's, and no stage of the model conditions on the change (docs/QB_DEPENDENCY_AUDIT_2026-10-08.md).
#: MAJORITY is a declared definition, not a fitted constant.
QB_ENV_MAJORITY = 0.5


def qb_environment_share(panel, club, qb_gsis, season, week, prior_games):
    """Blended share of the club's pass attempts thrown by `qb_gsis`, over the window the club environment uses."""
    def share(yr, wk_max):
        team = sum(v.get('pass_attempts') or 0 for w, v in (panel['teams'].get(club, {}).get(str(yr)) or {}).items()
                   if wk_max is None or int(w) < wk_max)
        mine = sum(v.get('pass_attempts') or 0 for w, v in
                   ((panel['players'].get(qb_gsis) or {}).get(str(yr)) or {}).items()
                   if v.get('team') == club and (wk_max is None or int(w) < wk_max))
        n = len([w for w in (panel['teams'].get(club, {}).get(str(yr)) or {}) if wk_max is None or int(w) < wk_max])
        return (mine / team if team else None), n
    cur, n_cur = share(season, week)
    prv, _ = share(season - 1, None)
    parts = [(n_cur, cur), (prior_games, prv)]
    num = sum(w * s for w, s in parts if s is not None)
    den = sum(w for w, s in parts if s is not None)
    return {'club': club, 'qb': qb_gsis, 'current_share': cur, 'n_current_games': n_cur, 'prior_season_share': prv,
            'blended_share': (num / den) if den else None}


def football_model_status(state, panel, prior_games):
    """COMPLETE_FOR_STARTERS when every named starter's club environment is predominantly his; else INCOMPLETE."""
    rows, bad = [], []
    for p in (state.get('players') or {}).values():
        ctx = p.get('predicted_lineup_context') or {}
        if p.get('position') == 'QB' and ctx.get('in_predicted_starting_group') and p.get('gsis_id'):
            r = qb_environment_share(panel, p['team'], p['gsis_id'], int(state['season']), int(state['week']), prior_games)
            r['name'] = p['name']
            rows.append(r)
            if r['blended_share'] is None or r['blended_share'] <= QB_ENV_MAJORITY:
                bad.append(f"QB_CHANGE_NOT_MODELLED {p['team']}:{p['name']} share {r['blended_share']}")
    return {'status': 'INCOMPLETE_QB_ENVIRONMENT' if bad else 'COMPLETE_FOR_STARTERS', 'reasons': bad,
            'starters': rows, 'RULE': f'club environment represents a QB only above a {QB_ENV_MAJORITY} blended share '
                                      'of the club pass attempts it is built from'}
