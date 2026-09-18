"""The prior-season OAS1 fit: the builder the committed artifact never had.

`OAS1_PRIOR_2025.json` was in the repository with no committed script that
produced it. That is the shape of defect this project has paid for before: a
result exists, the thing that made it does not, and "we have a number" quietly
becomes "we can reproduce the number".

Measured 2026-09-18, before anything was built on top of it: **it reproduces
exactly.** Rebuilding from `frame.build` + `fit.select_lambda_forward` +
`fit.fit_season` gives the same chosen lambda (10000.0, the grid maximum) and
all 128 unit strengths to a maximum absolute difference of 0.0 in both classes.
`verify_committed` is that check, and `nfl/tests/test_oas1_prior_season.py`
runs it.

WHAT THIS MODULE IS FOR BESIDES THE CHECK

The Week-2 inner forward chain needs a prior for EVERY fold, not only for the
2026 fold, and it needs the lawful one. A fold forecasting 2025 week 12 may not
carry a prior fitted on all of 2025 -- that is the whole of the rest of the
season leaking backwards into it. Its lawful prior is the 2024 fit, which is
the declared carryover depth of one prior season applied to that fold rather
than only to the last one. So this module builds a prior for any captured
season, and `week2` selects the right one per fold.

NOTHING HERE IS A FORECAST. A prior-season fit is `theta_prev`: a carryover
input, not a prediction and not a promotion candidate. The committed 2025
artifact says so of itself (`promoted: false`, `prospective_eligible: false`)
and this module does not change that.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.research.oas1 import design as DS                           # noqa: E402
from nfl.research.oas1 import fit as FT                              # noqa: E402
from nfl.research.oas1 import frame as FR                            # noqa: E402

SPEC_VERSION = 'oas1-prior-season-builder-1'

CODE_OK = 'OAS1_PRIOR_SEASON_BUILT'
CODE_NO_BLOB = 'OAS1_PRIOR_BLOB_MISSING'
CODE_FRAME = 'OAS1_PRIOR_FRAME_FAILED'
CODE_SELECT = 'OAS1_PRIOR_LAMBDA_SELECTION_FAILED'
CODE_FIT = 'OAS1_PRIOR_FIT_FAILED'
CODE_REPRO = 'OAS1_PRIOR_REPRODUCES'
CODE_DRIFT = 'OAS1_PRIOR_DOES_NOT_REPRODUCE'

#: The captured blobs, by season, exactly as `WEEK2_FIT_CONFIG.json` names
#: them. Not globbed: a glob would silently pick up a recapture and change a
#: prior underneath a fit that had already used it.
BLOBS = {
    2024: 'nfl/vintage/pbp_2024.23370d5d10f8104d.csv.gz',
    2025: 'nfl/vintage/pbp_2025.2f135887790a013f.csv.gz',
    2026: 'nfl/vintage/pbp_2026.b69f55a172965e16.csv.gz',
}

CLASSES = ('pass', 'rush')

_CACHE: dict = {}


def _sha_of(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(season: int, *, gt_rule: str = 'none',
          reg_only: bool = True) -> Outcome:
    """One season -> `theta_prev` per class, by the committed procedure.

    Cached per (season, gt_rule): the frame parse is the expensive step and
    the inner chain asks for the same season many times. The cache is per
    PROCESS and keyed on the arguments, so it cannot serve one season's fit
    for another.
    """
    key = (season, gt_rule, reg_only)
    if key in _CACHE:
        return _CACHE[key]
    rel = BLOBS.get(int(season))
    if rel is None:
        return Outcome.blocked(
            CODE_NO_BLOB,
            f'season {season} has no declared capture in BLOBS. A prior for a '
            f'season whose bytes are not captured cannot be built, and '
            f'substituting a neighbouring season would be a different model.',
            cause=Cause.DATA, declared=sorted(BLOBS))
    blob = _REPO / rel
    if not blob.exists():
        return Outcome.blocked(
            CODE_NO_BLOB, f'{rel} is declared and absent', cause=Cause.DATA)
    sha = _sha_of(blob)
    f = FR.build(blob, vintage_sha256=sha, gt_rule=gt_rule,
                 reg_only=reg_only)
    if f.state is not State.PASS:
        return Outcome.fail(CODE_FRAME, f'{season}: {f.code}: {f.detail}')
    rows = f.value['rows'] if isinstance(f.value, dict) else f.value
    fits, sel_ev, ident = {}, {}, {}
    for cls in CLASSES:
        sel = FT.select_lambda_forward(rows, play_class=cls)
        if sel.state is not State.PASS:
            return Outcome.fail(
                CODE_SELECT, f'{season} {cls}: {sel.code}: {sel.detail}')
        fit = FT.fit_season(rows, play_class=cls, lam=sel.value)
        if fit.state is not State.PASS:
            return Outcome.blocked(
                CODE_FIT, f'{season} {cls}: {fit.code}: {fit.detail}',
                cause=Cause.DATA)
        fits[cls] = fit.value
        sel_ev[cls] = {k: v for k, v in sel.evidence.items()
                       if k not in ('folds',)}
        ident[cls] = DS.identify(rows, play_class=cls).evidence
    theta = {}
    for cls in CLASSES:
        for u in fits[cls]['units']:
            theta[(u['team'], u['unit'])] = float(u['strength'])
    o = Outcome.ok(
        CODE_OK,
        value={'season': int(season), 'theta_prev': theta, 'fits': fits,
               'lambda_selection': sel_ev, 'identification': ident,
               'blob': rel, 'blob_sha256': sha, 'gt_rule': gt_rule,
               'n_units': len(theta)},
        detail=f'{season}: {len(theta)} unit(s) over {len(CLASSES)} class(es); '
               f'lambda ' + ', '.join(
                   f'{c}={sel_ev[c]["chosen_lambda"]:g}' for c in CLASSES),
        season=int(season), n_units=len(theta), blob_sha256=sha)
    _CACHE[key] = o
    return o


COMMITTED_2025 = _REPO / 'nfl/research/oas1/OAS1_PRIOR_2025.json'


def verify_committed(path=None) -> Outcome:
    """Does the committed prior artifact reproduce from committed code?

    Compares the 128 unit strengths and the chosen lambda per class. It does
    NOT compare the artifact's `stable_content_sha256`, and that limit is
    stated rather than glossed: the JSON wrapper carries fields
    (`lambda_boundary_sensitivity`, `unit_family_summary`) whose exact
    construction was never committed, so a wrapper-level hash comparison would
    fail for reasons that say nothing about the numbers. What is checked is the
    substance -- every strength and both lambdas -- which is what anything
    downstream actually consumes.
    """
    p = pathlib.Path(path or COMMITTED_2025)
    if not p.exists():
        return Outcome.blocked(CODE_NO_BLOB, f'{p} is absent',
                               cause=Cause.DATA)
    committed = json.loads(p.read_text())
    got = build(int(committed['season']))
    if got.state is not State.PASS:
        return got
    cu = {(u['team'], u['unit']): float(u['strength'])
          for u in committed['units']}
    rebuilt = got.value['theta_prev']
    missing = sorted(k for k in cu if k not in rebuilt)
    extra = sorted(k for k in rebuilt if k not in cu)
    diffs = {f'{t}/{u}': abs(rebuilt[(t, u)] - v)
             for (t, u), v in cu.items() if (t, u) in rebuilt}
    worst = max(diffs.values()) if diffs else None
    lam_ok, lams = True, {}
    for cls in CLASSES:
        a = float(committed['lambda_selection'][cls]['chosen_lambda'])
        b = float(got.value['lambda_selection'][cls]['chosen_lambda'])
        lams[cls] = {'committed': a, 'rebuilt': b}
        lam_ok = lam_ok and a == b
    ev = {'n_units_committed': len(cu), 'n_units_rebuilt': len(rebuilt),
          'n_compared': len(diffs), 'max_abs_strength_difference': worst,
          'missing_from_rebuild': missing, 'extra_in_rebuild': extra,
          'chosen_lambda': lams,
          'not_compared': 'stable_content_sha256, and the wrapper fields '
                          'lambda_boundary_sensitivity and '
                          'unit_family_summary, whose construction was never '
                          'committed'}
    if missing or extra or not lam_ok or worst is None or worst > 0.0:
        return Outcome.fail(
            CODE_DRIFT,
            f'the committed prior does not reproduce: {len(missing)} unit(s) '
            f'missing, {len(extra)} extra, max strength difference {worst}, '
            f'lambda agreement {lam_ok}',
            **ev)
    return Outcome.ok(
        CODE_REPRO, value=ev,
        detail=f'{len(diffs)} unit strength(s) reproduce to a maximum '
               f'absolute difference of {worst}, and both chosen lambdas '
               f'agree exactly',
        **ev)


def main() -> int:
    o = verify_committed()
    print(f'{o.state.value}[{o.code}] {o.detail}')
    print(json.dumps(o.evidence, indent=1, default=str)[:1500])
    return 0 if o.state is State.PASS else 1


if __name__ == '__main__':
    raise SystemExit(main())
