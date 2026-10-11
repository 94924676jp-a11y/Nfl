#!/usr/bin/env python3.12
"""The release record: what a Classic upload file IS, stated by code rather than by a person after the fact.

    python3.12 nfl/tools/classic_release.py 2026W5 [--tag NO_MCLAURIN_1623Z] [--latest-packet PACKET.json]

WHY THIS EXISTS (task #45, owner contract 2026-10-11, clauses 2, 7 and 10). On 2026-10-11 three upload files existed
for one slate, and what each one was had to be argued in chat: the 16:03Z file built before the 16-club packet, the
16:17Z file built on it, and the 16:32Z file that removed one player from every candidate pool without any new
forecast. The owner's release states were then written into a board document (WEEK5_SUNDAY_PRELOCK_BOARD.md,
e21176c9) and into no code. This module computes the state from the artifacts themselves and writes it beside the
upload, so a selection-only file cannot be presented as a fresh football rebuild, and no file can be called
certified while a mandatory requirement fails.

THE FIVE STATES (owner ruling 2026-10-11), and the precedence this module applies:

  BLOCKED                  a mandatory artifact is missing, the hash chain from state to upload is broken, or the
                           independent upload verifier did not pass. No release.
  SELECTION_ONLY_OVERRIDE  the portfolio removed players from the candidate pools (`classic_portfolio --exclude`)
                           without a new forecast. Its forecast is STALE_FORECAST for the scenario that motivated the
                           override: the projection and the worlds still describe the player as the forecast saw him.
  STALE_FORECAST           evidence newer than the forecast exists (the latest evidence packet is not the one the
                           state consumed).
  CURRENT_BUT_UNCERTIFIED  the chain is intact and the evidence is current, but at least one certification
                           requirement fails (world accounting, an open forecast defect, unmodelled evidence, contests
                           that share lineups).
  CURRENT_AND_CERTIFIED    every requirement below passes. While OPEN_FORECAST_DEFECTS is non-empty this state is
                           unreachable, and that is intended.

THE CHAIN, each link checked by hash, never by file time:
  STATE -> DRAWS.state_sha256; PROJ -> DRAWS.projection_sha256 and WORLDS.meta.projection_sha256;
  BOOK.inputs_sha256 == {STATE, PROJ, DRAWS, WORLDS}; SEAL == {PROJ, WORLDS, BOOK};
  PORTFOLIOS.inputs_sha256 == {STATE, PROJ, DRAWS} and PORTFOLIOS.research_book_sha256 == BOOK;
  VERIFY.upload_sha256 == UPLOAD and VERIFY PASS.

It changes no forecast, no lineup and no upload. It reads them and writes one JSON record.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome  # noqa: E402

SPEC_VERSION = 'classic-release-1'
OUT_DIR = _REPO / 'nfl/dfs/salaries'

CURRENT_AND_CERTIFIED = 'CURRENT_AND_CERTIFIED'
CURRENT_BUT_UNCERTIFIED = 'CURRENT_BUT_UNCERTIFIED'
STALE_FORECAST = 'STALE_FORECAST'
SELECTION_ONLY_OVERRIDE = 'SELECTION_ONLY_OVERRIDE'
BLOCKED = 'BLOCKED'
RELEASE_STATES = (CURRENT_AND_CERTIFIED, CURRENT_BUT_UNCERTIFIED, STALE_FORECAST, SELECTION_ONLY_OVERRIDE, BLOCKED)

#: FORECAST DEFECTS OPEN IN THE ENGINE, each with the audit line that measured it (AUDIT_45_AT_e21176c9.md). While any
#: entry stands, no release is CURRENT_AND_CERTIFIED. An entry leaves this register only in a commit that also adds the
#: test proving the defect closed at the real consumer; deleting a line to reach the certified state is the bypass
#: this register exists to make visible in review.
OPEN_FORECAST_DEFECTS = {
    'W5-G18_QB_NOT_CONDITIONED': 'team volume, receiver targets and efficiency, scoring and the opposing DST do not '
                                 'depend on quarterback identity (proj_v1.team_volume, proj_v1.py:167)',
    'NO_PARTICIPATION_STATE': 'a limited, restricted or questionable player cannot be represented; evidence items are '
                              'ACTIVE or INACTIVE only (sunday_evidence.py:91)',
    'APPEARANCE_NOT_DRAWN': 'p_plays is folded into each player\'s mean share and never drawn per world '
                            '(showdown_draws._shares, :103)',
    'L4_DEPTH_SURVIVORSHIP': 'the depth and appearance table counts only players on 2026 rosters, understating backups '
                             '(proj_v1.depth_shares via player_prior.position_index)',
}

#: Equal-size contests may share at most this many identical lineups (owner contract clause 6: the two 20-max contests
#: must not share identical lineups by default). A certification requirement, not a DraftKings legality rule.
MAX_SHARED_LINEUPS_EQUAL_SIZE = 0


def _sha(p: pathlib.Path):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def paths(slate_id: str, tag: str = '', out_dir: pathlib.Path = None) -> dict:
    d = pathlib.Path(out_dir or OUT_DIR)
    b = f'DK_{slate_id}_EARLY'
    p = {k: d / f'{b}_{n}' for k, n in (('state', 'STATE.json'), ('proj', 'PROJ.json'), ('draws', 'DRAWS.json'),
                                         ('worlds', 'WORLDS.npz'), ('book', 'RESEARCH_BOOK.json'),
                                         ('seal', 'SEAL.json'))}
    if tag:
        s = d / 'sensitivity'
        p.update(portfolios=s / f'{b}_PORTFOLIOS.{tag}.json', upload=s / f'{b}_UPLOAD.{tag}.csv',
                 verify=s / f'{b}_UPLOAD_VERIFY.{tag}.json', out=s / f'{b}_RELEASE.{tag}.json')
    else:
        p.update(portfolios=d / f'{b}_PORTFOLIOS.json', upload=d / f'{b}_UPLOAD.csv',
                 verify=d / f'{b}_UPLOAD_VERIFY.json', out=d / f'{b}_RELEASE.json')
    return p


def _worlds_meta(p: pathlib.Path) -> dict:
    import numpy as np
    z = np.load(p, allow_pickle=False)
    return json.loads(bytes(z['meta']).decode())


def world_accounting(state_p, draws_p, worlds_p) -> dict:
    """Run nfl/tools/world_accounting_check on exactly these three files (it globs a directory, so link them)."""
    from nfl.tools import world_accounting_check as WAC
    with tempfile.TemporaryDirectory(prefix='release_wac_') as td:
        t = pathlib.Path(td)
        for src, name in ((state_p, 'R_STATE.json'), (draws_p, 'R_DRAWS.json'), (worlds_p, 'R_WORLDS.npz')):
            (t / name).symlink_to(pathlib.Path(src).resolve())
        r = WAC.check(t)
    by_law = {}
    for k, v in (r.get('VIOLATED') or {}).items():
        law = k.split(':')[-1]
        by_law[law] = by_law.get(law, 0) + v
    return {'spec_version': r.get('spec_version'), 'n_worlds': r.get('n_worlds'), 'violations_by_law': by_law,
            'total_violations': sum(by_law.values()), 'stage': r.get('stage')}


def _code_identity() -> dict:
    def g(*a):
        try:
            return subprocess.run(['git', *a], cwd=_REPO, capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None
    dirty = g('status', '--porcelain', '--untracked-files=no', '--', 'nfl/tools', 'nfl/opt', 'nfl/sim')
    return {'commit': g('rev-parse', 'HEAD'), 'engine_code_dirty': bool(dirty),
            'engine_code_dirty_paths': (dirty or '').splitlines()[:20]}


def _clock(now=None) -> dict:
    from zoneinfo import ZoneInfo
    n = now or dt.datetime.now(dt.timezone.utc)
    return {'utc': n.astimezone(dt.timezone.utc).isoformat(), 'et': n.astimezone(ZoneInfo('America/New_York')).isoformat(),
            'source': 'injected (replay)' if now else 'system clock read at record time'}


def _shared_equal_size(verify_doc: dict, portfolios: dict) -> list:
    """Equal-size contest pairs and how many identical lineups they share, from the independent verifier's counts."""
    size = {c['contest_id']: c['n_entries'] for c in portfolios.get('contests') or []}
    out = []
    for k, v in (verify_doc.get('cross_contest_identical_lineups') or {}).items():
        a, b = k.split('_in_')
        if size.get(a) is not None and size.get(a) == size.get(b):
            out.append({'contests': [a, b], 'size': size[a], 'shared_lineups': v.get('shared_lineups')})
    return out


def evaluate(slate_id: str, *, tag: str = '', latest_packet=None, out_dir=None, now=None,
             run_accounting: bool = True) -> dict:
    """The release record as a dict. Never raises on a missing or inconsistent artifact: that is BLOCKED, named."""
    P = paths(slate_id, tag, out_dir)
    rec = {'ARTIFACT': 'CLASSIC_RELEASE_RECORD', 'spec_version': SPEC_VERSION, 'slate_id': slate_id, 'tag': tag or None,
           'clock': _clock(now), 'code': _code_identity(),
           'files': {k: str(v) for k, v in P.items() if k != 'out'}}
    blocked, uncert, stale = [], [], []
    missing = [k for k in ('state', 'proj', 'draws', 'worlds', 'book', 'seal', 'portfolios', 'upload', 'verify')
               if not P[k].exists()]
    if missing:
        # Still say what the evidence was, when the state survives: an untraceable file can also be stale, and
        # both facts belong in the record (2026-10-11: the 16:03Z build's draws and worlds were overwritten in place
        # by the 16:08Z rebuild, so its chain cannot be re-verified, and it predates the 16:10Z packet).
        stale = []
        if P['state'].exists():
            oi = json.loads(P['state'].read_text()).get('official_inactives') or {}
            rec['evidence'] = {'consumed': {'packet_id': oi.get('packet_id'), 'packet_sha256': oi.get('packet_sha256')}}
            if latest_packet is not None:
                lp = pathlib.Path(latest_packet)
                if _sha(lp) != oi.get('packet_sha256'):
                    stale.append(f"EVIDENCE_NEWER_THAN_FORECAST the state consumed {oi.get('packet_id')!r}; the newest "
                                 f"packet is {json.loads(lp.read_text()).get('packet_id')!r}")
        rec.update(release_state=BLOCKED, forecast_state=BLOCKED,
                   reasons={'blocking': [f'MISSING_ARTIFACT {k}: {P[k].name}' for k in missing], 'stale': stale,
                            'uncertified': []})
        return rec
    sha = {k: _sha(P[k]) for k in ('state', 'proj', 'draws', 'worlds', 'book', 'seal', 'portfolios', 'upload')}
    rec['sha256'] = sha
    J = {k: json.loads(P[k].read_text()) for k in ('state', 'draws', 'book', 'seal', 'portfolios', 'verify')}
    dr, bk, sl, po, vf = J['draws'], J['book'], J['seal'], J['portfolios'], J['verify']
    wm = _worlds_meta(P['worlds'])
    links = {
        'DRAWS.state_sha256 == STATE': dr.get('state_sha256') == sha['state'],
        'DRAWS.projection_sha256 == PROJ': dr.get('projection_sha256') == sha['proj'],
        'WORLDS.meta.projection_sha256 == PROJ': wm.get('projection_sha256') == sha['proj'],
        'BOOK.inputs == STATE, PROJ, DRAWS, WORLDS': (bk.get('inputs_sha256') or {}) == {
            'STATE.json': sha['state'], 'PROJ.json': sha['proj'], 'DRAWS.json': sha['draws'],
            'WORLDS.npz': sha['worlds']},
        'SEAL == PROJ, WORLDS, BOOK': (sl.get('projection_sha256'), sl.get('worlds_sha256'),
                                       sl.get('research_book_sha256')) == (sha['proj'], sha['worlds'], sha['book']),
        'PORTFOLIOS.inputs == STATE, PROJ, DRAWS': (po.get('inputs_sha256') or {}) == {
            'state': sha['state'], 'proj': sha['proj'], 'draws': sha['draws']},
        'PORTFOLIOS.research_book_sha256 == BOOK': po.get('research_book_sha256') == sha['book'],
        'VERIFY.upload_sha256 == UPLOAD': vf.get('upload_sha256') == sha['upload'],
        'VERIFY PASS': vf.get('state') == 'PASS',
    }
    rec['chain'] = links
    blocked += [f'LINEAGE_BROKEN {k}' for k, ok in links.items() if not ok and k != 'VERIFY PASS']
    if not links['VERIFY PASS']:
        blocked.append(f'UPLOAD_VERIFY_NOT_PASS {vf.get("state")}[{vf.get("code")}]')

    # EVIDENCE CURRENCY: the packet the state consumed against the newest packet the run was told about.
    oi = J['state'].get('official_inactives') or {}
    used = {'packet_id': oi.get('packet_id'), 'packet_sha256': oi.get('packet_sha256'), 'source': oi.get('source')}
    rec['evidence'] = {'consumed': used}
    if latest_packet is not None:
        lp = pathlib.Path(latest_packet)
        lj = json.loads(lp.read_text())
        latest = {'path': str(lp), 'packet_id': lj.get('packet_id'), 'packet_sha256': _sha(lp),
                  'received_at': lj.get('received_at')}
        rec['evidence']['latest_known'] = latest
        if latest['packet_sha256'] != used['packet_sha256']:
            stale.append(f'EVIDENCE_NEWER_THAN_FORECAST the state consumed {used["packet_id"]!r}; '
                         f'the newest packet is {latest["packet_id"]!r} (received {latest["received_at"]})')
    else:
        rec['evidence']['latest_known'] = 'NOT_SUPPLIED: currency against newer evidence was not checked'
        uncert.append('EVIDENCE_CURRENCY_UNCHECKED no latest packet was supplied to compare against')

    # EVIDENCE THE ENGINE CANNOT REPRESENT, recorded by the packet as not modelled (interim convention until the
    # participation schema exists: the resolution note carries "NOT MODELLED").
    unmod = []
    for k, p in (J['state'].get('players') or {}).items():
        note = (((p.get('current_availability') or {}).get('resolution') or {}).get('note') or '')
        if 'NOT MODELLED' in note.upper():
            unmod.append({'dk_id': k, 'name': p.get('name'), 'team': p.get('team'), 'note': note[:240]})
    rec['evidence']['unmodelled'] = unmod
    if unmod:
        uncert.append(f'UNMODELLED_EVIDENCE {len(unmod)} player(s): '
                      + ', '.join(f"{u['name']} {u['team']}" for u in unmod[:6]))

    # WORLD ACCOUNTING on the published worlds (the arrays the optimiser scored).
    if run_accounting:
        wa = world_accounting(P['state'], P['draws'], P['worlds'])
        rec['world_accounting'] = wa
        if wa['total_violations']:
            uncert.append('WORLD_ACCOUNTING_VIOLATED ' + ', '.join(f'{k} {v}' for k, v in
                                                                  sorted(wa['violations_by_law'].items())))
    else:
        rec['world_accounting'] = 'NOT_RUN'
        uncert.append('WORLD_ACCOUNTING_NOT_RUN')

    # CONTEST INDEPENDENCE (clause 6).
    shared = _shared_equal_size(vf, po)
    rec['equal_size_contest_overlap'] = shared
    for s in shared:
        if (s['shared_lineups'] or 0) > MAX_SHARED_LINEUPS_EQUAL_SIZE:
            uncert.append(f"CONTESTS_SHARE_LINEUPS {s['contests'][0]} and {s['contests'][1]} ({s['size']} entries "
                          f"each) share {s['shared_lineups']} identical lineup(s)")

    rec['open_forecast_defects'] = OPEN_FORECAST_DEFECTS
    if OPEN_FORECAST_DEFECTS:
        uncert.append(f'OPEN_FORECAST_DEFECTS {len(OPEN_FORECAST_DEFECTS)}: ' + ', '.join(OPEN_FORECAST_DEFECTS))

    # SEEDS AND LOCK.
    rec['seeds'] = {'draws_per_game': {g: v.get('seed') for g, v in (dr.get('per_game') or {}).items()},
                    'portfolio': po.get('seed', 'NOT_RECORDED_BY_THIS_PORTFOLIO_BUILD')}
    ko = sl.get('kickoff_utc')
    built = po.get('built_at_utc')
    rec['lock'] = {'kickoff_utc': ko, 'portfolio_built_at_utc': built,
                   'portfolio_built_before_lock': (bool(ko and built) and
                                                   dt.datetime.fromisoformat(built) < dt.datetime.fromisoformat(ko))}

    # OVERRIDE: players removed from every pool with no forecast change.
    sens = po.get('sensitivity') or {}
    excl = sens.get('exclude') or []
    if excl:
        names = {k: (J['state']['players'].get(k) or {}).get('name') for k in excl}
        rec['override'] = {'kind': 'EXCLUDE_FROM_EVERY_POOL', 'excluded': names,
                           'forecast_changed': False,
                           'MEANING': 'the projection and the worlds are the ones the unrestricted portfolio used; only '
                                      'selection changed'}
        stale.append('OVERRIDE_WITHOUT_FORECAST the excluded player(s) keep their projection and draws, and no '
                     'teammate, quarterback or world was recomputed')

    if blocked:
        state, forecast_state = BLOCKED, BLOCKED
    else:
        forecast_state = STALE_FORECAST if stale else (CURRENT_BUT_UNCERTIFIED if uncert else CURRENT_AND_CERTIFIED)
        state = SELECTION_ONLY_OVERRIDE if excl else forecast_state
    rec.update(release_state=state, forecast_state=forecast_state,
               reasons={'blocking': blocked, 'stale': stale, 'uncertified': uncert},
               NOT_CLAIMED=('a release state describes how this file was produced and what is known to be wrong '
                            'with it. CURRENT_AND_CERTIFIED would not mean the forecast is accurate or the portfolio '
                            'profitable; those are separate claims with their own evidence.'))
    return rec


def build(slate_id: str, *, tag: str = '', latest_packet=None, out_dir=None, write: bool = True, now=None) -> Outcome:
    rec = evaluate(slate_id, tag=tag, latest_packet=latest_packet, out_dir=out_dir, now=now)
    out = paths(slate_id, tag, out_dir)['out']
    if write:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rec, indent=1, default=str) + '\n')
    st = rec['release_state']
    detail = f"{st} (forecast {rec.get('forecast_state')}); " + '; '.join(
        (rec.get('reasons') or {}).get('blocking') or (rec.get('reasons') or {}).get('stale')
        or (rec.get('reasons') or {}).get('uncertified') or [] if isinstance(rec.get('reasons'), dict)
        else rec.get('reasons') or [])[:300]
    if st == BLOCKED:
        return Outcome.blocked('RELEASE_BLOCKED', detail, cause=Cause.DATA, record=rec)
    return Outcome.ok(f'RELEASE_{st}', rec, detail, path=str(out))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('slate_id')
    ap.add_argument('--tag', default='')
    ap.add_argument('--latest-packet', default=None)
    a = ap.parse_args()
    o = build(a.slate_id, tag=a.tag, latest_packet=a.latest_packet)
    print(f'{o.state.value}[{o.code}] {o.detail}')
    return 0 if o.state.value == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
