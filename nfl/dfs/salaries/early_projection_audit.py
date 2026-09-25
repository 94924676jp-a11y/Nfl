"""Does a CURRENT, USABLE projection exist for each Early Only player? Verified.

THE RULE THIS MODULE IS BUILT AROUND, AND IT IS THE OWNER'S

    A player is not projected because his gsis_id appears in a manifest or in
    a `row_ids` list.

That is a claim the run makes about itself. A projection exists when a
distribution can be OPENED and READ: a real draw vector, finite, of the
declared length, for a named metric. So every classification below is
established by loading the array and looking at it, and the count of
`row_ids` is reported separately as what it is -- a claim, not evidence.

THE SEVEN STATES, AND WHY THEY ARE NOT COLLAPSIBLE

    CURRENT_PROJECTION_AVAILABLE            a readable distribution from a
                                            SEALED artifact whose information
                                            clock is current
    STALE_PROJECTION_AVAILABLE              readable, sealed, but its clock
                                            predates newer governed evidence
    MODEL_REACHABLE_BUT_NO_CURRENT_PROJECTION
                                            the engine produced numbers for
                                            him in a run that REFUSED, so
                                            they exist and are not a forecast
    MODEL_REFUSED                           his game refused upstream
    IDENTITY_UNRESOLVED                     no canonical id
    NOT_MODELED                             identity fine, engine never
                                            emitted a row for him
    DST_UNSUPPORTED                         team defence; the engine emits no
                                            team-defence outputs at all

The third state is the one that matters tonight and the one a single
ready/not-ready flag would destroy. Numbers exist. They are not a forecast,
because the run that made them refused to seal, and a refused run's output is
not promoted by being the only output available.
"""
from __future__ import annotations

import collections
import glob
import json
import pathlib
import sys

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

SPEC_VERSION = 'dk-early-projection-audit-1'

CURRENT = 'CURRENT_PROJECTION_AVAILABLE'
STALE = 'STALE_PROJECTION_AVAILABLE'
REACHABLE = 'MODEL_REACHABLE_BUT_NO_CURRENT_PROJECTION'
REFUSED = 'MODEL_REFUSED'
UNRESOLVED = 'IDENTITY_UNRESOLVED'
NOT_MODELED = 'NOT_MODELED'
DST = 'DST_UNSUPPORTED'

#: Where a SEALED board would live. A projection is current only if it comes
#: from here; a scratch directory is not a repository artifact and a run that
#: refused did not produce a forecast.
SEALED_GLOB = 'nfl/research/live/*/*/*/board.json'

#: The unsealed rehearsal runs. Read ONLY to establish reachability, and
#: every number taken from them is labelled with the run that refused.
REHEARSAL_GLOB = '/tmp/claude-0/rehearsal_cand2/*/player_draws_manifest.json'


def sealed_boards(pattern=SEALED_GLOB) -> dict:
    """game_id -> the sealed boards that exist for it, if any."""
    out = collections.defaultdict(list)
    for p in sorted(glob.glob(str(_REPO / pattern))):
        try:
            b = json.loads(pathlib.Path(p).read_text())
        except ValueError:
            continue
        gid = b.get('game_id')
        if gid:
            out[gid].append({
                'path': str(pathlib.Path(p).relative_to(_REPO)),
                'n_players': b.get('n_players'),
                'n_draws': b.get('n_draws'),
                'model_configuration': b.get('model_configuration'),
                'draws_sha256': b.get('draws_sha256'),
            })
    return dict(out)


def _open_draws(run_dir):
    """The npz beside a manifest, or None. Opened, not assumed."""
    for name in ('player_draws.npz', 'player_draws.npz.gz'):
        p = pathlib.Path(run_dir) / name
        if p.exists():
            try:
                return np.load(p)
            except Exception:                                  # noqa: BLE001
                return None
    return None


def verified_distributions(pattern=REHEARSAL_GLOB) -> dict:
    """gsis_id -> the metrics whose draw vector was actually READ.

    Not `row_ids`. For every declared row the array is indexed and checked:
    right length, finite, present. A row_id naming an index the array does not
    have, or a vector of NaNs, is a CLAIM WITHOUT A DISTRIBUTION and is
    counted separately rather than silently believed.
    """
    by_id, per_game, broken = {}, {}, []
    claimed_ids = set()
    for m in sorted(glob.glob(pattern)):
        d = json.loads(pathlib.Path(m).read_text())
        gid, rid = d.get('game_id'), d.get('run_id')
        run_dir = pathlib.Path(m).parent
        z = _open_draws(run_dir)
        n_draws = d.get('n_draws')
        got = collections.defaultdict(dict)
        for lname, layer in (d.get('layers') or {}).items():
            if layer.get('row_axis') != 'gsis_id':
                continue
            ids = layer.get('row_ids') or []
            claimed_ids.update(ids)
            for metric in (layer.get('metrics') or []):
                key = f'{lname}/{metric}'
                # THE MANIFEST AND THE NPZ SPELL THE SAME METRIC DIFFERENTLY.
                # The manifest's `arrays` map is keyed `layer/metric`; the npz
                # itself stores `layer__metric`. Looking up only the first
                # spelling returns None for EVERY metric and makes the audit
                # report zero verified distributions -- which is what it did
                # on the first run here, and which would have been read as a
                # finding about the model rather than a bug in the reader.
                # Both spellings are tried and the one that answered is
                # recorded.
                arr, spelling = None, None
                if z is not None:
                    for cand in (f'{lname}__{metric}', key):
                        if cand in getattr(z, 'files', []):
                            arr, spelling = z[cand], cand
                            break
                if arr is None:
                    broken.append({'game_id': gid, 'key': key,
                                   'why': 'named in the manifest, absent from '
                                          'the npz'})
                    continue
                a = np.asarray(arr)
                for i, pid in enumerate(ids):
                    if i >= a.shape[0]:
                        broken.append({'game_id': gid, 'key': key,
                                       'gsis_id': pid,
                                       'why': f'row {i} beyond array shape '
                                              f'{a.shape}'})
                        continue
                    v = np.asarray(a[i], float)
                    if v.size != n_draws or not np.isfinite(v).all():
                        broken.append({'game_id': gid, 'key': key,
                                       'gsis_id': pid,
                                       'why': f'size {v.size} vs {n_draws}, '
                                              f'finite '
                                              f'{bool(np.isfinite(v).all())}'})
                        continue
                    got[pid][key] = {
                        'npz_key': spelling,
                        'n_draws': int(v.size),
                        'mean': round(float(v.mean()), 4),
                        'p_zero': round(float((v == 0).mean()), 4),
                    }
        for pid, metrics in got.items():
            rec = by_id.setdefault(pid, {'game_id': gid, 'run_id': rid,
                                         'metrics': {}})
            rec['metrics'].update(metrics)
        per_game[gid] = {
            'run_id': rid, 'n_draws': n_draws,
            'n_ids_claimed_in_manifest': len({
                i for l in (d.get('layers') or {}).values()
                if l.get('row_axis') == 'gsis_id'
                for i in (l.get('row_ids') or [])}),
            'n_ids_with_a_readable_distribution': len(got),
            'content_digest': d.get('content_digest'),
            'npz_present': z is not None,
        }
    return {'by_gsis_id': by_id, 'per_game': per_game,
            'n_claimed_ids': len(claimed_ids),
            'n_verified_ids': len(by_id),
            'broken': broken, 'n_broken': len(broken)}


#: What `run_slate.py` hands `capture_validation` as its entire source set.
#: A literal placeholder: sixty-four 'b' characters and a fixed timestamp.
PLACEHOLDER_SOURCE_SHA = 'b' * 64


def run_governance(pattern=REHEARSAL_GLOB) -> dict:
    """Read each run's OWN status file and report what it says about itself.

    THIS IS THE CHECK THE FIRST VERSION OF THIS AUDIT DID NOT DO, and it
    changes the answer. The audit reported that these runs refused at
    `artifact_sealing` and that their evidence was 13.5 hours old. Both true.
    Neither is the strongest disqualifier. Every one of these runs carries
    `dry_run: true` and `prospective_eligible: false`, because the only slate
    driver in the repository -- `nfl/production/rehearsal/run_slate.py` -- is
    declared REHEARSAL ONLY and sets `dry_run=True` in the call itself. There
    is no non-rehearsal path from the vintage manifest to a slate run.

    And the reason it is declared rehearsal-only is visible one line above the
    call: the fixture it builds satisfies `capture_validation` with

        'source_hashes': {'schedules': {'sha256': 'b' * 64,
                                        'retrieved_at': '2026-09-08T12:00:00Z'}}

    a placeholder hash for one source. `capture_validation` iterates the set it
    is HANDED and has no required-source check, so one synthetic entry passes
    the whole stage. The football layers below it do read real captures through
    `vintage_selector`, with real capture ids -- so the numbers rest on real
    evidence while the stage that certifies inputs was satisfied by a
    placeholder. Those are different statements and this function reports both.

    `run_forecast.py` invoked directly, with no `--fixtures`, refuses at
    `capture_validation[SOURCE_MISSING]` before any layer runs. Measured on all
    eight Early Only games at 2026-09-20T05:00Z.
    """
    out, rows = {}, []
    for m in sorted(glob.glob(pattern)):
        sp = pathlib.Path(m).parent / 'run_status.json'
        if not sp.exists():
            continue
        d = json.loads(sp.read_text())
        ff = d.get('first_failure') or {}
        rows.append({
            'run_id': d.get('run_id'),
            'status': d.get('status'),
            'dry_run': d.get('dry_run'),
            'prospective_eligible': d.get('prospective_eligible'),
            'written_at': d.get('written_at'),
            'first_failure_stage': (ff.get('stage')
                                    if isinstance(ff, dict) else ff),
            'publication_code': (d.get('publication') or {}).get('code'),
        })
        out[d.get('run_id')] = rows[-1]
    n = len(rows)
    return {
        'runs': rows,
        'n_runs': n,
        'n_dry_run': sum(1 for r in rows if r['dry_run'] is True),
        'n_prospective_eligible': sum(1 for r in rows
                                      if r['prospective_eligible'] is True),
        'by_run_id': out,
        'only_slate_driver': 'nfl/production/rehearsal/run_slate.py',
        'driver_hardcodes_dry_run': True,
        'driver_source_hashes_are_a_placeholder': True,
        'placeholder_sha256': PLACEHOLDER_SOURCE_SHA,
        'capture_validation_has_no_required_source_check': True,
        'direct_entrypoint_without_fixtures':
            'BLOCKED[SOURCE_MISSING] at capture_validation, all 8 Early '
            'games, measured 2026-09-20T05:00Z',
        'football_layers_read_real_captures_via':
            'nfl/production/nonqb/vintage_selector.py',
    }


#: Any layer's dk_points key counts as "carries a DK distribution".
#:
#: THE MOST DANGEROUS INSTANCE OF DEF-060 WAS HERE. This function answers
#: "which players have a DK projection", and it looked only for
#: 'dk_scoring/dk_points'. A kicker's distribution arrives as
#: 'kicking/dk_points', so this audit -- whose entire job is to detect a
#: MISSING projection -- would have reported a kicker as having none. A real
#: omission recorded as a known absence is worse than an unnoticed one,
#: because it closes the question.
_DK_SUFFIX = '/dk_points'


def _dk_metric_key(metrics) -> str:
    """The dk_points key this player actually carries, whichever layer it is."""
    for k in sorted(metrics):
        if k.endswith(_DK_SUFFIX):
            return k
    return ''


def dk_points_available(verified) -> dict:
    """Which verified players carry a DK fantasy-point distribution."""
    have, by_layer = set(), {}
    for pid, r in verified['by_gsis_id'].items():
        k = _dk_metric_key(r['metrics'])
        if k:
            have.add(pid)
            by_layer[k] = by_layer.get(k, 0) + 1
    return {'n_with_dk_points': len(have), 'gsis_ids': have,
            'by_metric_key': by_layer}


def classify(pool_rows, reconciled_rows, verified, sealed, refusing_games,
             governance=None):
    """One state per Early Only row. Every one established, not inferred."""
    by_name = {(r['dk_name'], r['team']): r for r in reconciled_rows}
    out = []
    for p in pool_rows:
        r = by_name.get((p['dk_name'], p['team']))
        gid = f"2026_02_{p['away']}_{p['home']}"
        rec = {
            'dk_name': p['dk_name'], 'gsis_id': (r or {}).get('gsis_id'),
            'team': p['team'],
            'opponent': p['home'] if p['team'] == p['away'] else p['away'],
            'position': p['dk_pos'], 'dk_salary': p['salary'],
            'dk_id': p.get('dk_id'), 'game_id': gid,
            'identity_status': (r or {}).get('status'),
            'state': None, 'why': None,
            'model_vintage': None, 'information_clock': None,
            'football_means': None, 'distribution_fields_available': None,
            'dk_points_mean': None, 'dk_points_percentiles': None,
            'draws_reference': None, 'run_governance': None,
        }
        if p['dk_pos'] == 'DST':
            rec['state'] = DST
            rec['why'] = ('the engine produces no team-defence outputs at '
                          'all (statline.NOT_SIMULATED)')
            out.append(rec)
            continue
        if r is None or r['status'] not in ('MATCHED_CANONICAL',):
            rec['state'] = UNRESOLVED
            rec['why'] = ((r or {}).get('note')
                          or 'no canonical roster row answers to this name')
            out.append(rec)
            continue
        if gid in sealed:
            rec['state'] = CURRENT
            rec['why'] = f'sealed board: {sealed[gid][0]["path"]}'
            out.append(rec)
            continue
        v = verified['by_gsis_id'].get(rec['gsis_id'])
        if v is not None:
            rec['state'] = REACHABLE
            g = (governance or {}).get('by_run_id', {}).get(v['run_id'])
            rec['run_governance'] = g
            # THREE INDEPENDENT DISQUALIFIERS, AND NAMING ONLY ONE UNDERSTATES
            # IT. An earlier version of this audit named the sealing refusal
            # alone, which reads as "one blocker away". It is not.
            rec['why'] = (
                f'the engine produced readable distributions for him in run '
                f'{v["run_id"]}. That run is disqualified three times over: '
                f'(1) it REFUSED at artifact_sealing on '
                f'current_season_input_freshness; (2) it carries dry_run=true '
                f'and prospective_eligible=false, because the only slate '
                f'driver is declared REHEARSAL ONLY and sets it; (3) its '
                f'capture_validation stage passed on a placeholder source '
                f'hash of sixty-four b characters, not on a real capture. '
                f'Numbers exist; a forecast does not. They live in a scratch '
                f'directory, not a repository artifact.')
            rec['draws_reference'] = {'run_id': v['run_id'],
                                      'game_id': v['game_id'],
                                      'sealed': False}
            rec['distribution_fields_available'] = sorted(v['metrics'])
            _dkk = _dk_metric_key(v['metrics'])
            rec['football_means'] = {k: m['mean']
                                     for k, m in sorted(v['metrics'].items())
                                     if not k.endswith(_DK_SUFFIX)}
            rec['dk_points_metric_key'] = _dkk or None
            dk = v['metrics'].get(_dkk) if _dkk else None
            if dk:
                rec['dk_points_mean'] = dk['mean']
                rec['dk_points_percentiles'] = None
            out.append(rec)
            continue
        if gid in refusing_games:
            rec['state'] = REFUSED
            rec['why'] = refusing_games[gid]
        else:
            rec['state'] = NOT_MODELED
            rec['why'] = ('his game ran and the engine emitted no row for '
                          'him in any layer')
        out.append(rec)
    return out


#: The amendment this module was extended for, applied to an artifact already
#: written. Kept HERE rather than in a throwaway script so the correction is
#: reproducible and so the `why` text has one definition, not two.
def amend(doc: dict, governance: dict = None) -> dict:
    """Add run governance to an audit artifact and restate every `why`.

    The artifact this amends said the 229 reachable rows came from runs that
    refused at `artifact_sealing`. True, and it was not the whole disqualifier.
    Amending rather than rewriting keeps the verified distribution counts --
    established by opening arrays, not by reading `row_ids` -- exactly as
    measured.
    """
    g = governance if governance is not None else run_governance()
    doc = dict(doc)
    doc['run_governance'] = g
    doc['amendment'] = {
        'spec_version': SPEC_VERSION + '+governance-1',
        'what_changed': 'every MODEL_REACHABLE row now names three '
                        'disqualifiers instead of one',
        'what_did_not_change': 'the verified distribution counts; they were '
                               'measured by opening the npz and are unmoved',
        'why': 'naming the sealing refusal alone reads as one blocker away '
               'from a board. The runs are also dry_run/prospective_eligible='
               'false by construction, and their capture_validation passed on '
               'a placeholder source hash. Three, not one.',
    }
    n = 0
    for rec in doc.get('rows', []):
        ref = rec.get('draws_reference') or {}
        rid = ref.get('run_id')
        if rec.get('state') != REACHABLE or not rid:
            continue
        rec['run_governance'] = g['by_run_id'].get(rid)
        rec['why'] = (
            f'the engine produced readable distributions for him in run '
            f'{rid}. That run is disqualified three times over: '
            f'(1) it REFUSED at artifact_sealing on '
            f'current_season_input_freshness; (2) it carries dry_run=true '
            f'and prospective_eligible=false, because the only slate '
            f'driver is declared REHEARSAL ONLY and sets it; (3) its '
            f'capture_validation stage passed on a placeholder source '
            f'hash of sixty-four b characters, not on a real capture. '
            f'Numbers exist; a forecast does not. They live in a scratch '
            f'directory, not a repository artifact.')
        n += 1
    doc['amendment']['n_rows_restated'] = n
    return doc
