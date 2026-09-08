"""The production pipeline orchestrator.

FOURTEEN STAGES, each returning success/failure, input hashes, model/spec
version, warnings, a refusal code if blocked, and timing.

TWO STRUCTURAL RULES

1. NO STAGE MAY CONSUME ANOTHER STAGE'S POSTGAME OUTPUT. Stages declare what
   they read, and the orchestrator refuses a declaration that names a postgame
   field.
2. A STAGE WITH NO PRODUCTION MODEL RETURNS A NAMED REFUSAL, never a fabricated
   forecast. `STAGE_NOT_IMPLEMENTED` is a result; a made-up number is not.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import hashlib
import json
import pathlib
import sys
import time
from typing import Callable, Optional

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.production import refusal as RF                             # noqa: E402

PIPELINE_VERSION = 'nfl-production-pipeline-1'

STAGES = ('capture_validation', 'identity_resolution', 'feature_build',
          'team_environment', 'appearance', 'participation',
          'targets_carries', 'conversion', 'td_layer', 'qb_layer',
          'joint_reconciliation', 'player_draws', 'scoring',
          'artifact_sealing')

# Fields that exist only after a game is played. A stage declaring any of these
# as an input is refused before it runs.
POSTGAME_FIELDS = {
    'n_td', 'rec_td', 'rush_td', 'pass_td', 'targets', 'receptions',
    'rec_yards', 'rush_yards', 'pass_yards', 'carries', 'interceptions',
    'sacks', 'completions', 'attempts', 'snaps', 'pass_snaps', 'offense_snaps',
    'final_status', 'inactive', 'appeared', 'did_not_appear', 'score',
    'result', 'weekly_rosters.status',
}


@dataclasses.dataclass
class StageResult:
    stage: str
    state: str
    code: str
    detail: str = ''
    input_hashes: dict = dataclasses.field(default_factory=dict)
    spec_version: Optional[str] = None
    warnings: list = dataclasses.field(default_factory=list)
    refusal_code: Optional[str] = None
    elapsed_s: float = 0.0
    # Stage-reported measurements. `elapsed_s` is orchestrator wall clock for
    # the stage; a stage that generates draws reports the draw-generation time
    # separately here, because the two are not the same number and reporting
    # only the first would overstate how much of the run is modelling.
    metrics: dict = dataclasses.field(default_factory=dict)
    value: object = None

    def as_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d.pop('value', None)
        return d


def assert_no_postgame_inputs(stage: str, declared_inputs) -> Outcome:
    """A stage may not declare a postgame field as an input."""
    bad = sorted(set(declared_inputs) & POSTGAME_FIELDS)
    if bad:
        return Outcome.fail(
            'POSTGAME_INPUT_DECLARED',
            f'{stage} declares {bad} as inputs. Those exist only after the '
            f'game. A pipeline that reads them is not forecasting.',
            stage=stage, fields=bad)
    return Outcome.ok('INPUTS_ARE_PREGAME', value=sorted(declared_inputs))


class Pipeline:
    def __init__(self, run_id: str, out_dir: pathlib.Path, arm: str,
                 written_at: str):
        self.run_id = run_id
        self.out_dir = pathlib.Path(out_dir)
        self.arm = arm
        self.written_at = written_at
        self.results: list = []
        self.refusals: list = []
        self.halted_by = None
        self.started = time.time()

    def run_stage(self, stage: str, fn: Callable, declared_inputs=(),
                  spec_version: str = None) -> StageResult:
        if stage not in STAGES:
            raise ValueError(f'{stage!r} is not a declared pipeline stage')
        t0 = time.time()
        # HALT ON THE FIRST REFUSAL. A stage after a refusal must not run: the
        # pipeline previously recorded IDENTITY_UNRESOLVED and then went on to
        # execute the QB model on those unresolved players and SEAL an
        # artifact. The overall status was REFUSED, so nothing published -- but
        # modelling on inputs that failed validation, and sealing the result,
        # is exactly the 'prefer NO FORECAST over an unverifiable one' rule
        # being broken. Every stage still gets a record, so the stage count is
        # unchanged and the skip is visible rather than silent.
        if self.halted_by is not None:
            r = StageResult(
                stage=stage, state='NOT_APPLICABLE', code='STAGE_NOT_REACHED',
                detail=f'not run: the pipeline refused at '
                       f'{self.halted_by[0]} with {self.halted_by[1]}. '
                       f'Running a model on inputs that failed validation '
                       f'would produce a number nobody should read.',
                spec_version=spec_version)
            self.results.append(r)
            return r
        pg = assert_no_postgame_inputs(stage, declared_inputs)
        if pg.state is not State.PASS:
            r = StageResult(stage=stage, state='FAIL', code=pg.code,
                            detail=pg.detail, spec_version=spec_version,
                            elapsed_s=time.time() - t0)
            self.halted_by = (stage, r.code)
            self.results.append(r)
            return r
        try:
            out = fn()
        except Exception as exc:                                  # noqa: BLE001
            r = StageResult(stage=stage, state='FAIL',
                            code='STAGE_RAISED',
                            detail=f'{type(exc).__name__}: {exc}',
                            spec_version=spec_version,
                            elapsed_s=time.time() - t0)
            self.halted_by = (stage, r.code)
            self.results.append(r)
            return r
        code = getattr(out, 'code', 'OK')
        st = getattr(out, 'state', None)
        state = st.value if st is not None else 'PASS'
        ev = getattr(out, 'evidence', {}) or {}
        r = StageResult(
            stage=stage, state=state, code=code,
            detail=(getattr(out, 'detail', '') or '')[:400],
            input_hashes=ev.get('input_hashes', {}),
            metrics={k: ev[k] for k in
                     ('draw_generation_seconds', 'n_qb_games', 'n_draws',
                      'draw_cells', 'qb_frame_sha256')
                     if ev.get(k) is not None},
            spec_version=spec_version,
            warnings=list(ev.get('warnings', [])),
            refusal_code=(code if state == 'BLOCKED' and code in RF.REFUSALS
                          else None),
            elapsed_s=time.time() - t0,
            value=getattr(out, 'value', None))
        if r.state in ('FAIL', 'BLOCKED'):
            self.halted_by = (stage, r.code)
        if r.refusal_code:
            self.refusals.append({'code': r.refusal_code, 'stage': stage,
                                  'detail': r.detail, 'run_id': self.run_id,
                                  'at': _dt.datetime.now(
                                      _dt.timezone.utc).isoformat()})
        self.results.append(r)
        return r

    def status(self) -> str:
        """STARTED / INPUT_VALIDATED / MODELED / RECONCILED / SEALED / REFUSED."""
        done = {r.stage for r in self.results if r.state == 'PASS'}
        if any(r.state in ('FAIL', 'BLOCKED') for r in self.results):
            return 'REFUSED'
        if 'artifact_sealing' in done:
            return 'SEALED'
        if 'joint_reconciliation' in done:
            return 'RECONCILED'
        if 'player_draws' in done or 'td_layer' in done:
            return 'MODELED'
        if 'capture_validation' in done:
            return 'INPUT_VALIDATED'
        return 'STARTED'

    def summary(self) -> dict:
        return {
            'run_id': self.run_id, 'arm': self.arm,
            'written_at': self.written_at,
            'pipeline_version': PIPELINE_VERSION,
            'status': self.status(),
            'elapsed_s': round(time.time() - self.started, 4),
            'stages': [r.as_dict() for r in self.results],
            'n_refusals': len(self.refusals),
            'refusals': self.refusals,
            'first_failure': next((r.as_dict() for r in self.results
                                   if r.state in ('FAIL', 'BLOCKED')), None),
        }

    def persist(self) -> Outcome:
        self.out_dir.mkdir(parents=True, exist_ok=True)
        (self.out_dir / 'run_status.json').write_text(
            json.dumps(self.summary(), indent=1, default=str) + '\n')
        RF.persist(self.refusals, self.out_dir)
        return Outcome.ok('RUN_PERSISTED', value=str(self.out_dir))
