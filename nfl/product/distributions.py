"""Read a sealed forecast and its draws. Verify before believing.

The draw sidecar is the source for every number in the product layer. The
artifact's quantile view is a convenience over the same draws, so the two must
describe the same run -- and that is CHECKED here rather than assumed, because
a board rendered from a mismatched pair would be a confident report of two
different forecasts.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import pathlib

import numpy as np


class ForecastUnreadable(RuntimeError):
    """Named. A board that cannot read its forecast prints nothing."""


def _load_npz(path: pathlib.Path):
    if str(path).endswith('.gz'):
        with gzip.open(path, 'rb') as fh:
            raw = fh.read()
        return np.load(io.BytesIO(raw)), hashlib.sha256(raw).hexdigest()
    raw = path.read_bytes()
    return np.load(io.BytesIO(raw)), hashlib.sha256(raw).hexdigest()


class Forecast:
    """One sealed game forecast: artifact, manifest and draws together."""

    def __init__(self, directory):
        d = pathlib.Path(directory)
        self.dir = d
        art = d / 'forecast_artifact.json'
        if not art.exists():
            raise ForecastUnreadable(f'ARTIFACT_ABSENT: {art}')
        self.artifact = json.loads(art.read_text())
        man = d / 'player_draws_manifest.json'
        self.manifest = json.loads(man.read_text()) if man.exists() else {}
        npz = None
        for name in ('player_draws.npz.gz', 'player_draws.npz'):
            if (d / name).exists():
                npz = d / name
                break
        if npz is None:
            raise ForecastUnreadable(
                f'DRAWS_ABSENT: no player_draws.npz(.gz) beside {art}. The '
                f'quantile view alone cannot support a threshold probability, '
                f'a CRPS or a PIT value.')
        z, self.draws_sha256 = _load_npz(npz)
        self.arrays = {k: z[k] for k in z.files}
        self.draws_path = npz
        self._check()

    # ------------------------------------------------------------------
    def _check(self):
        if not self.arrays:
            raise ForecastUnreadable('DRAW_SET_EMPTY')
        widths = {a.shape[1] for a in self.arrays.values() if a.ndim == 2}
        if len(widths) != 1:
            raise ForecastUnreadable(
                f'DRAW_INDEX_RAGGED: widths {sorted(widths)}. These layers are '
                f'only comparable on one shared draw index.')
        self.n_draws = widths.pop()
        # THE TWO VIEWS MUST DESCRIBE ONE RUN. The artifact references draws by
        # content digest; if it names a different one, the quantile view and
        # the draws came from different executions and neither can be trusted
        # to describe the other.
        want = self.artifact.get('draw_content_digest')
        got = (self.manifest or {}).get('content_digest')
        if want and got and want != got:
            raise ForecastUnreadable(
                f'DRAW_CONTENT_DIGEST_MISMATCH: artifact names {want}, '
                f'manifest carries {got}')
        self.content_digest = got or want

    # ------------------------------------------------------------------
    @property
    def game_id(self):
        return self.artifact.get('game_id')

    @property
    def run_id(self):
        return self.artifact.get('spec_hash')

    def layers(self):
        return sorted({k.split('__')[0] for k in self.arrays})

    def row_index(self, layer, key, gsis_id):
        """Which row of `layer/key` belongs to this player, from the artifact's
        own draws_ref -- never from position in a list we rebuilt."""
        d = ((self.artifact.get('distributions') or {}).get(gsis_id)
             or {}).get(layer) or {}
        ref = (d.get(key) or {}).get('draws_ref') or {}
        return ref.get('row')

    def vector(self, layer, key, gsis_id):
        """This player's draws for one metric, or None if he has none."""
        arr = self.arrays.get(f'{layer}__{key}')
        if arr is None:
            return None
        i = self.row_index(layer, key, gsis_id)
        if i is None or i >= arr.shape[0]:
            return None
        return np.asarray(arr[i], float)

    def team_vector(self, key, team):
        arr = self.arrays.get(f'team_volume__{key}')
        if arr is None:
            return None
        teams = self.artifact.get('team_ids') or []
        if team not in teams:
            return None
        return np.asarray(arr[teams.index(team)], float)

    def players(self):
        """gsis_id -> {layer: [keys]} for everyone with a stored distribution."""
        out = {}
        for pid, block in (self.artifact.get('distributions') or {}).items():
            got = {}
            for layer, mets in (block or {}).items():
                keys = [k for k in mets
                        if self.vector(layer, k, pid) is not None]
                if keys:
                    got[layer] = sorted(keys)
            if got:
                out[pid] = got
        return out


# ---------------------------------------------------------------- summaries
PCTS = (10, 25, 50, 75, 90)


def summary(x) -> dict:
    """Mean, median and the quantiles the board shows. Draws only."""
    x = np.asarray(x, float)
    return {'mean': round(float(x.mean()), 2),
            'median': round(float(np.percentile(x, 50)), 2),
            'sd': round(float(x.std(ddof=1)), 2),
            **{f'p{p}': round(float(np.percentile(x, p)), 2) for p in PCTS},
            'n_draws': int(x.size)}


def p_at_least(x, k) -> float:
    """P(X >= k). Counts are integers, so `at least` is the honest form; a
    half-point line is used only where a value could land exactly on it."""
    x = np.asarray(x, float)
    return round(float((x >= k).mean()), 4)


def p_over(x, line) -> float:
    x = np.asarray(x, float)
    return round(float((x > line).mean()), 4)
