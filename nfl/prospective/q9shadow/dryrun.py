"""The dry-run proof: the sealing path is deterministic and cannot read outcomes.

    python3.12 -m nfl.prospective.q9shadow.dryrun

TEN CHECKS, AND EACH ONE IS A DIFFERENT WAY THE PATH COULD BE WRONG. A single
"it worked" would prove almost nothing; what follows is written so that any
one of them failing names the specific claim that is false.

  1  DETERMINISTIC              two seals of identical inputs produce the
                                same artifact_id, draw hash, spec hash,
                                payload hash and identity fingerprint
  2  OUTCOME_READERS_POISONED   every named outcome reader is replaced by a
                                function that raises, and the seal still
                                completes. This is the behavioural proof: if
                                the path touched an outcome it would die.
  3  OUTCOME_SHAPED_INPUT       an input bundle carrying a realised key or a
                                play-by-play source is refused BY NAME
  4  SCHEDULE_PROJECTED         the raw schedule row carries home_score,
                                away_score, result and spread_line; the
                                projected row carries none of them. The first
                                half of that check is what stops the second
                                from being vacuous
  5  FEATURE_PROJECTED          the panel row carries the realised target
                                count; the row handed to the frozen
                                featuriser does not
  6  NO_READER_IN_NAMESPACE     no sealing module has an outcome reader bound
                                in its namespace at all
  7  MUTATION_REFUSED           an artifact edited after written_at is
                                refused, and a correction naming `supersedes`
                                is accepted
  8  RESEAL_REFUSED             a second seal of one forecast_id with
                                different content is refused
  9  POST_KICKOFF_REFUSED       written_at at or after kickoff is refused
 10  DRY_RUN_NOT_EVIDENCE       a dry-run row is refused as evidence by the
                                ledger

WHAT THIS PROOF IS NOT. It is not evidence about Q9's accuracy, it is not a
prospective forecast, and its artifacts are stamped `dry_run: true` and
`prospective_evidence: false` and live under `dryrun/`, never under `sealed/`.
"""
from __future__ import annotations

import argparse
import copy
import importlib
import json
import pathlib
import shutil
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import State                   # noqa: E402
from nfl.prospective import artifact as ART                           # noqa: E402
from nfl.prospective.q9shadow import candidate as CAND                # noqa: E402
from nfl.prospective.q9shadow import inputs as IN                     # noqa: E402
from nfl.prospective.q9shadow import ledger as LED                    # noqa: E402
from nfl.prospective.q9shadow import seal as SEAL                     # noqa: E402
from nfl.prospective.q9shadow import shadow as SH                     # noqa: E402

SPEC_VERSION = 'q9-shadow-dryrun-proof-1'
HERE = _REPO / 'nfl' / 'prospective' / 'q9shadow'
PROOF = HERE / 'Q9_PROSPECTIVE_DRYRUN_PROOF.json'
PROOF_ROOT = HERE / 'dryrun' / 'proof'

CHECKS = ('DETERMINISTIC', 'OUTCOME_READERS_POISONED',
          'OUTCOME_SHAPED_INPUT_REFUSED', 'SCHEDULE_PROJECTED',
          'FEATURE_PROJECTED', 'NO_READER_IN_NAMESPACE', 'MUTATION_REFUSED',
          'RESEAL_REFUSED', 'POST_KICKOFF_REFUSED', 'DRY_RUN_NOT_EVIDENCE')

# The frozen slice the proof runs on. Historical, small, and fixed here so the
# proof is not quietly run on whatever happened to be convenient.
SLICE_SEASON = 2024
SLICE_GAMES = 1
SLICE_DRAWS = 120
WRITTEN_AT = '2026-09-12T12:00:00Z'

IDENTITY_KEYS = ('artifact_id', 'spec_hash', 'draw_artifact_sha256',
                 'draw_content_sha256', 'feature_set_hash', 'forecast_id')


class OutcomeReaderTouched(RuntimeError):
    """Raised by every poisoned reader. Reaching one is the failure."""


def _poison():
    """Replace every named outcome reader with one that raises. Returns undo."""
    undo = []
    for full in IN.OUTCOME_READERS:
        mod_name, fn = full.rsplit('.', 1)
        try:
            mod = importlib.import_module(mod_name)
        except Exception:                                     # noqa: BLE001
            continue
        if not hasattr(mod, fn):
            continue
        original = getattr(mod, fn)

        def _raise(*_a, _full=full, **_k):
            raise OutcomeReaderTouched(
                f'the sealing path called {_full}. A pregame seal that reads '
                f'a realised outcome is not a pregame seal.')

        setattr(mod, fn, _raise)
        undo.append((mod, fn, original))
    return undo


def _unpoison(undo):
    for mod, fn, original in undo:
        setattr(mod, fn, original)


def _seal_once(out_root, written_at=WRITTEN_AT):
    return SEAL.seal_season(
        SLICE_SEASON, source=SH.HISTORICAL_FRAME, n_games=SLICE_GAMES,
        out_root=out_root, n_draws=SLICE_DRAWS, written_at=written_at,
        dry_run=True)


def _ident(sealed):
    return [{k: s.value.get(k) for k in IDENTITY_KEYS}
            | {'seal_payload_sha256': s.value['seal']['payload_sha256'],
               'identity_fingerprint': s.value['seal']['identity_fingerprint'],
               'team': s.value['team']}
            for s in sealed]


def run(keep=False):
    res = {k: {'state': 'NOT_RUN'} for k in CHECKS}
    if PROOF_ROOT.exists():
        shutil.rmtree(PROOF_ROOT)

    # ---- 1 and 2 together: the second seal runs with every outcome reader
    # poisoned, so determinism and outcome-blindness are shown on the same
    # inputs rather than on two different runs.
    a = _seal_once(PROOF_ROOT / 'run1')
    undo = _poison()
    try:
        b = _seal_once(PROOF_ROOT / 'run2')
        poisoned_ok = True
        poison_detail = (f'{len(undo)} reader(s) poisoned; the seal completed '
                         f'without calling any of them')
    except OutcomeReaderTouched as exc:
        b, poisoned_ok, poison_detail = None, False, str(exc)
    finally:
        _unpoison(undo)

    if a['status'] != 'OK' or not a['sealed']:
        res['DETERMINISTIC'] = {'state': 'FAIL',
                                'detail': f'the first seal did not produce a '
                                          f'forecast: {a["status"]} '
                                          f'{a.get("detail", "")[:200]}'}
        res['OUTCOME_READERS_POISONED'] = {
            'state': 'FAIL' if not poisoned_ok else 'NOT_RUN',
            'detail': poison_detail}
    else:
        ia = _ident(a['sealed'])
        ib = _ident(b['sealed']) if b and b.get('sealed') else []
        same = ia == ib
        res['DETERMINISTIC'] = {
            'state': 'PASS' if same else 'FAIL',
            'n_forecasts': len(ia),
            'identity_keys_compared': list(IDENTITY_KEYS) + [
                'seal_payload_sha256', 'identity_fingerprint'],
            'run1': ia, 'run2': ib,
            'detail': ('two seals of identical inputs are identical on every '
                       'compared hash' if same else
                       'two seals of identical inputs DIFFER; the sealing '
                       'path is not deterministic')}
        res['OUTCOME_READERS_POISONED'] = {
            'state': 'PASS' if poisoned_ok else 'FAIL',
            'n_readers_poisoned': len(undo),
            'readers': list(IN.OUTCOME_READERS),
            'detail': poison_detail}

    # ---- 3 an outcome-shaped input is refused by name
    probe = {'sources': {
        'depth_charts': {'sha256': 'a' * 64, 'observed_at': WRITTEN_AT},
        'nflverse_pbp': {'sha256': 'b' * 64, 'observed_at': WRITTEN_AT}}}
    g1 = IN.assert_no_outcome_shaped_inputs(probe)
    probe2 = {'sources': {'depth_charts': {
        'sha256': 'a' * 64, 'observed_at': WRITTEN_AT,
        'home_score': 27}}}
    g2 = IN.assert_no_outcome_shaped_inputs(probe2)
    clean = IN.assert_no_outcome_shaped_inputs({'sources': {
        'depth_charts': {'sha256': 'a' * 64, 'observed_at': WRITTEN_AT},
        'weekly_rosters': {'sha256': 'c' * 64, 'observed_at': WRITTEN_AT}}})
    res['OUTCOME_SHAPED_INPUT_REFUSED'] = {
        'state': 'PASS' if (g1.state is State.FAIL and g2.state is State.FAIL
                            and clean.state is State.PASS) else 'FAIL',
        'outcome_source': f'{g1.state.value}[{g1.code}]',
        'outcome_shaped_key': f'{g2.state.value}[{g2.code}]',
        'clean_bundle_with_restricted_source':
            f'{clean.state.value}[{clean.code}]',
        'restricted_from_stage_1': clean.evidence.get(
            'restricted_from_stage_1'),
        'detail': ('a play-by-play source and a realised key are each '
                   'refused; a bundle carrying only a RESTRICTED source '
                   'passes and records the restriction')}

    # ---- 4 the schedule projection, with the non-vacuity half first
    import csv as _csv
    import gzip as _gzip
    raw_cols = []
    hits = sorted(SEAL.SCHEDULES.glob('schedules.*.csv.gz'))
    if hits:
        with _gzip.open(hits[-1], 'rt', newline='') as fh:
            raw_cols = list(next(_csv.DictReader(fh)))
    banned = ('home_score', 'away_score', 'result', 'total', 'overtime',
              'spread_line', 'total_line', 'home_moneyline', 'away_moneyline')
    present_in_raw = sorted(c for c in banned if c in raw_cols)
    sch = SEAL.schedule_pregame(SLICE_SEASON)
    proj_cols = sorted(sch.value[0]) if sch.state is State.PASS else []
    leaked = sorted(c for c in banned if c in proj_cols)
    res['SCHEDULE_PROJECTED'] = {
        'state': 'PASS' if (present_in_raw and not leaked) else 'FAIL',
        'banned_columns_present_in_raw_capture': present_in_raw,
        'banned_columns_surviving_projection': leaked,
        'projected_columns': proj_cols,
        'detail': (f'the raw capture carries {len(present_in_raw)} outcome or '
                   f'market column(s) and the projection carries '
                   f'{len(leaked)}. The first number is what makes the '
                   f'second meaningful')}

    # ---- 5 the feature projection
    fr = SH.feature_rows(SH.HISTORICAL_FRAME, season=SLICE_SEASON)
    if fr.state is State.PASS:
        row = next(r for r in fr.value if r['s'] == SLICE_SEASON)
        proj = IN.project_feature_row(row)
        realised_in_panel = sorted(
            k for k in row if k in ('targets', 'share_targets', 'carries',
                                    'q7_yds', 'snap', 'appeared'))
        realised_in_proj = sorted(k for k in proj if k in realised_in_panel)
        res['FEATURE_PROJECTED'] = {
            'state': 'PASS' if (realised_in_panel and not realised_in_proj)
                     else 'FAIL',
            'realised_keys_on_the_panel_row': realised_in_panel,
            'realised_keys_surviving_projection': realised_in_proj,
            'feature_row_keys': list(IN.FEATURE_ROW_KEYS),
            'derived_from': 'nfl.research.q9.hurdle.featurise source',
            'detail': (f'the panel row carries {len(realised_in_panel)} '
                       f'realised column(s); the projected row carries '
                       f'{len(realised_in_proj)}')}
    else:
        res['FEATURE_PROJECTED'] = {'state': 'FAIL',
                                    'detail': f'{fr.code}: {fr.detail[:200]}'}

    # ---- 6 no reader bound in any sealing module's namespace
    ns = {}
    for mod in (SEAL, SH, IN, CAND):
        o = IN.assert_no_outcome_reader_imported(mod)
        ns[mod.__name__] = f'{o.state.value}[{o.code}]'
    res['NO_READER_IN_NAMESPACE'] = {
        'state': 'PASS' if all(v.startswith('PASS') for v in ns.values())
                 else 'FAIL',
        'modules': ns,
        'outcome_reader_modules': list(IN.OUTCOME_READER_MODULES),
        'detail': 'the sealing modules cannot reach an outcome reader even by '
                  'mistake, because none is bound in them'}

    # ---- 7, 8, 9, 10 on the sealed artifact from run1
    if a.get('sealed'):
        art = a['sealed'][0].value
        edited = copy.deepcopy(art)
        edited['player_ids'] = list(edited['player_ids'])[:-1]
        mut = ART.assert_not_mutated(art, edited)
        corrected = copy.deepcopy(art)
        corrected['supersedes'] = ART.artifact_id(art)
        corrected['written_at'] = '2026-09-12T13:00:00Z'
        sup = ART.assert_not_mutated(art, corrected)
        res['MUTATION_REFUSED'] = {
            'state': 'PASS' if (mut.state is State.FAIL
                                and sup.state is State.PASS) else 'FAIL',
            'edited_in_place': f'{mut.state.value}[{mut.code}]',
            'lawful_correction': f'{sup.state.value}[{sup.code}]',
            'detail': 'an in-place edit is refused; a NEW artifact naming '
                      'what it supersedes is the only lawful correction'}

        from nfl.identity import seal as ISEAL
        led = PROOF_ROOT / 'reseal_ledger.jsonl'
        s0 = ISEAL.Seal(
            forecast_id=art['forecast_id'], game_id=art['game_id'],
            written_at=art['written_at'], kickoff_utc=art['kickoff_utc'],
            payload_sha256=art['seal']['payload_sha256'],
            identity_fingerprint=art['seal']['identity_fingerprint'],
            identity={}, consumed_partition_ids=tuple(
                art['seal']['consumed_partition_ids']))
        first = ISEAL.append_seal(s0, led)
        again = ISEAL.append_seal(s0, led)
        s1 = ISEAL.Seal(**(s0.as_dict() | {'payload_sha256': 'f' * 64}))
        diff = ISEAL.append_seal(s1, led)
        res['RESEAL_REFUSED'] = {
            'state': 'PASS' if (first.state is State.PASS
                                and again.state is State.NOT_APPLICABLE
                                and diff.state is State.FAIL) else 'FAIL',
            'first': f'{first.state.value}[{first.code}]',
            'identical_again': f'{again.state.value}[{again.code}]',
            'different_content': f'{diff.state.value}[{diff.code}]',
            'detail': 'an identical re-record adds nothing and says so; a '
                      'different one under the same forecast_id is refused'}

        late = copy.deepcopy(art)
        late['written_at'] = art['kickoff_utc']
        v = ART.validate(late)
        earlier = copy.deepcopy(art)
        earlier['source_captures'] = [
            dict(c, retrieved_at='2026-09-12T23:00:00Z')
            for c in art['source_captures']]
        v2 = ART.validate(earlier)
        res['POST_KICKOFF_REFUSED'] = {
            'state': 'PASS' if (v.state is State.FAIL
                                and v.code == 'WRITTEN_AFTER_KICKOFF'
                                and v2.state is State.FAIL
                                and v2.code == 'INPUT_RETRIEVED_AFTER_FORECAST')
                     else 'FAIL',
            'written_at_equals_kickoff': f'{v.state.value}[{v.code}]',
            'input_retrieved_after_write': f'{v2.state.value}[{v2.code}]',
            'detail': 'retrieved_at <= written_at < kickoff, both halves, '
                      'enforced by the contract and not by this proof'}

        nd = LED.assert_not_dry_run(art)
        fake = copy.deepcopy(art)
        fake['dry_run'] = False
        fake['prospective_evidence'] = True
        nd2 = LED.assert_not_dry_run(fake)
        res['DRY_RUN_NOT_EVIDENCE'] = {
            'state': 'PASS' if (nd.state is State.NOT_APPLICABLE
                                and nd2.state is State.PASS) else 'FAIL',
            'dry_run_row': f'{nd.state.value}[{nd.code}]',
            'prospective_row': f'{nd2.state.value}[{nd2.code}]',
            'detail': 'the ledger refuses a dry-run row as evidence by '
                      'reading the same two flags the seal stamps'}
    else:
        for k in ('MUTATION_REFUSED', 'RESEAL_REFUSED',
                  'POST_KICKOFF_REFUSED', 'DRY_RUN_NOT_EVIDENCE'):
            res[k] = {'state': 'FAIL',
                      'detail': 'no sealed artifact to exercise'}

    if not keep and PROOF_ROOT.exists():
        shutil.rmtree(PROOF_ROOT)

    failed = sorted(k for k, v in res.items() if v.get('state') != 'PASS')
    return {
        'artifact': 'NFL_Q9_PROSPECTIVE_DRYRUN_PROOF',
        'spec_version': SPEC_VERSION,
        'candidate': CAND.CANDIDATE_NAME,
        'promoted': False, 'shadow_only': True,
        'is_evidence_about_accuracy': False,
        'slice': {'season': SLICE_SEASON, 'n_games': SLICE_GAMES,
                  'n_draws': SLICE_DRAWS, 'written_at': WRITTEN_AT,
                  'feature_source': SH.HISTORICAL_FRAME,
                  'note': 'frozen historical features, labelled synthetic '
                          'kickoff, written under dryrun/ and never under '
                          'sealed/'},
        'checks': res,
        'n_checks': len(CHECKS),
        'n_failed': len(failed),
        'failed': failed,
        'status': 'DRY_RUN_PROOF_HOLDS' if not failed else 'DRY_RUN_PROOF_FAILED',
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--keep', action='store_true',
                    help='keep the proof artifacts under dryrun/proof')
    a = ap.parse_args(argv)
    out = run(a.keep)
    PROOF.write_text(json.dumps(out, indent=1, default=str) + '\n')
    for k in CHECKS:
        c = out['checks'][k]
        print(f"  {c['state']:5s} {k:30s} {(c.get('detail') or '')[:110]}")
    print(f"status : {out['status']}  ({out['n_checks'] - out['n_failed']}"
          f"/{out['n_checks']})")
    return 0 if out['n_failed'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
