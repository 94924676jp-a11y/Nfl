"""B13: preserve the DISTRIBUTION, not four numbers from it.

WHAT WAS WRONG

Every metric left the production path as `{mean, p10, p50, p90}`. From four
quantiles you cannot compute CRPS, you cannot compute a log score, you cannot
form a PIT value, you cannot read coverage at any level you did not store, you
cannot answer "what is P(passing yards > 312.5)", and -- the one that cannot be
recovered by storing more quantiles -- you cannot ask any question about
DEPENDENCE. A per-metric marginal summary discards which draw went with which,
and the joint structure is gone the moment it is written.

WHAT IS STORED INSTEAD, AND WHY THIS REPRESENTATION

RAW DRAWS, losslessly encoded, as one 2-D matrix per (layer, metric) with
shape (n_rows, n_draws), in a single deterministic compressed zip container
referenced from the JSON forecast artifact by sha256.

  * Raw draws are the SIMPLEST representation from which every listed
    consumer -- proper scoring, PIT, coverage, tail probability, dependence,
    replay -- is computed EXACTLY, with no parametric assumption and no
    interpolation. Any summary is a lossy function of the draws; the draws are
    not a lossy function of any summary. Storing the draws is therefore the
    representation that needs no argument about which summaries will be wanted
    later.
  * The COLUMN AXIS IS THE DRAW INDEX and it is shared by every matrix in the
    file. Column j of `qb/pyds` and column j of `qb/ptd` are the same iteration
    of the same stream, for the same row. That is the joint structure a
    per-metric marginal summary destroys, and keeping the matrices column-
    aligned is what preserves it.
  * ENCODING IS LOSSLESS BY CONSTRUCTION, not by tolerance. A narrower dtype
    is used only when the round trip is EXACTLY equal to the source, checked
    element-wise on write and again on read-back. Nothing is clipped, rounded
    or rescaled to fit -- if int16 would not represent a value exactly, the
    array is stored in a dtype that does. Compactness is taken only where it
    is free.
  * SIZE. Counts and small yardages fall into int16, so a 16-game slate at 200
    draws is kilobytes per game rather than megabytes, and the JSON artifact
    carries only the manifest and the hash.

WHAT THE DRAW INDEX DOES AND DOES NOT MEAN -- READ THIS BEFORE USING IT FOR A
DEPENDENCE DIAGNOSTIC

`qb2_lib.simulate` seeds ONE GENERATOR PER ROW, from
`[seed, ord, gsis_id]`. Consequently:

    within a row, across metrics   -> the same simulated world. Column j of
                                      db/att/cmp/pyds for row i all come from
                                      one iteration of row i's stream, so
                                      cross-metric dependence read off these
                                      columns is REAL.
    across rows (players/teams)    -> INDEPENDENT streams that happen to be
                                      column-aligned. Column j of player A and
                                      column j of player B are NOT a shared
                                      game state. A cross-player correlation
                                      measured on this axis measures the
                                      absence of coupling in the generator,
                                      which is a fact about the model, not a
                                      fact about football.

That distinction is declared in the manifest (`draw_index_semantics`) rather
than left for a reader to rediscover, because the alignment is real and the
coupling is not, and a diagnostic that confuses them would report a finding
about the world.

ABSENCE IS NEVER SUCCESS. An empty draw set, a ragged draw index, a metric
whose matrix has no columns, or a file whose bytes do not hash to the recorded
digest each return a NAMED refusal. There is no path through this module that
turns nothing into a pass.
"""
from __future__ import annotations

import hashlib
import io
import json
import pathlib
import sys
import zipfile

import numpy as np

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402

DRAW_ARTIFACT_VERSION = 'nfl-draw-artifact-1'
DRAW_FILE_NAME = 'player_draws.npz'
MANIFEST_FILE_NAME = 'player_draws_manifest.json'

# A fixed zip timestamp. Without it the container embeds the wall clock and two
# byte-identical draw sets hash differently, which would make the file hash
# useless as a replay identity -- the one job it is being given.
_FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)

# The two things the draw index does. Declared, not inferred.
WITHIN_ROW = 'SAME_SIMULATED_WORLD'
ACROSS_ROWS = 'INDEPENDENT_STREAMS_COLUMN_ALIGNED'


# --------------------------------------------------------------- encoding
def encode(a: np.ndarray):
    """The narrowest dtype that reproduces `a` EXACTLY. Never a tolerance.

    Returns (encoded, dtype_name). The caller verifies the round trip; this
    function only proposes, and it proposes nothing it has not already
    round-tripped here.
    """
    src = np.ascontiguousarray(np.asarray(a, dtype=np.float64))
    finite = np.isfinite(src).all()
    if finite and np.array_equal(src, np.rint(src)):
        lo, hi = float(src.min()), float(src.max())
        for dt in (np.int16, np.int32, np.int64):
            info = np.iinfo(dt)
            if lo >= info.min and hi <= info.max:
                enc = src.astype(dt)
                if np.array_equal(enc.astype(np.float64), src):
                    return enc, np.dtype(dt).name
    if finite:
        enc = src.astype(np.float32)
        if np.array_equal(enc.astype(np.float64), src):
            return enc, 'float32'
    return src, 'float64'


def _canonical_bytes(a: np.ndarray) -> bytes:
    """Content bytes for hashing: float64, C-order, encoding-independent.

    Hashing the ENCODED bytes would make the digest depend on which dtype the
    encoder happened to pick, so a re-encode of identical draws would look like
    changed draws. Hashing the canonical form means the digest changes if and
    only if a draw changes.
    """
    return np.ascontiguousarray(np.asarray(a, dtype=np.float64)).tobytes()


# --------------------------------------------------------------- draw set
class DrawSet:
    """Accumulate every layer's draw matrices on one shared draw index."""

    def __init__(self, run_id: str, game_id: str, seed, seed_protocol: str,
                 n_draws: int = None):
        self.run_id = run_id
        self.game_id = game_id
        self.seed = seed
        self.seed_protocol = seed_protocol
        self.n_draws = n_draws
        self.layers: dict = {}
        self.arrays: dict = {}
        self.problems: list = []

    # -- building
    def add_layer(self, layer: str, row_ids, matrices: dict,
                  spec_version: str, rng_stream: str,
                  row_axis: str = 'gsis_id') -> Outcome:
        """One layer's matrices. Every one must share the run's draw index."""
        if not layer or '/' in layer:
            return Outcome.fail(
                'DRAW_LAYER_NAME_INVALID',
                f'{layer!r} is not a usable layer name; "/" separates layer '
                f'from metric in the container key.')
        if layer in self.layers:
            return Outcome.fail('DRAW_LAYER_DUPLICATED',
                                f'{layer} was added twice')
        rows = [str(r) for r in (row_ids or [])]
        if not rows:
            return Outcome.fail(
                'DRAW_LAYER_NO_ROWS',
                f'{layer} supplied no row identities. A matrix whose rows name '
                f'nobody cannot be joined to a player or a team later, and '
                f'accepting it would store numbers that can never be scored.')
        if not matrices:
            return Outcome.fail(
                'DRAW_LAYER_NO_METRICS',
                f'{layer} supplied no metric matrices. An empty layer is an '
                f'absence, not a distribution.')
        staged = {}
        for metric, mat in sorted(matrices.items()):
            arr = np.asarray(mat, dtype=np.float64)
            if arr.ndim == 1:
                arr = arr.reshape(1, -1)
            if arr.ndim != 2:
                return Outcome.fail(
                    'DRAW_MATRIX_NOT_2D',
                    f'{layer}/{metric} has shape {arr.shape}; a draw matrix is '
                    f'(rows x draws) so that the draw index survives.')
            if arr.shape[0] != len(rows):
                return Outcome.fail(
                    'DRAW_MATRIX_ROW_MISMATCH',
                    f'{layer}/{metric} has {arr.shape[0]} row(s) against '
                    f'{len(rows)} row identity(ies). A matrix that cannot be '
                    f'attributed row-by-row is not auditable.')
            if arr.shape[1] == 0:
                return Outcome.fail(
                    'DRAW_MATRIX_NO_DRAWS',
                    f'{layer}/{metric} carries zero draws. Zero draws is an '
                    f'absence wearing a distribution\'s costume.')
            if self.n_draws is None:
                self.n_draws = int(arr.shape[1])
            if int(arr.shape[1]) != int(self.n_draws):
                return Outcome.fail(
                    'DRAW_INDEX_RAGGED',
                    f'{layer}/{metric} has {arr.shape[1]} draws against the '
                    f'run\'s {self.n_draws}. A shared draw index is the whole '
                    f'reason these are stored jointly; a ragged one silently '
                    f'destroys every dependence diagnostic downstream.',
                    metric=f'{layer}/{metric}', got=int(arr.shape[1]),
                    expected=int(self.n_draws))
            if not np.isfinite(arr).all():
                return Outcome.fail(
                    'DRAW_MATRIX_NOT_FINITE',
                    f'{layer}/{metric} contains a non-finite draw. It is '
                    f'stored as-is or not at all -- nothing here replaces a '
                    f'NaN with a number.',
                    n_bad=int((~np.isfinite(arr)).sum()))
            staged[metric] = arr
        for metric, arr in staged.items():
            self.arrays[f'{layer}/{metric}'] = arr
        self.layers[layer] = {
            'spec_version': spec_version, 'rng_stream': rng_stream,
            'row_axis': row_axis, 'row_ids': rows,
            'metrics': sorted(staged), 'shape': [len(rows), int(self.n_draws)]}
        return Outcome.ok(f'DRAW_LAYER_ADDED', value=len(staged),
                          layer=layer, n_rows=len(rows),
                          n_metrics=len(staged), n_draws=int(self.n_draws))

    # -- reading back out, for the quantile view and for the consistency check
    def row_index(self, layer: str, row_id: str):
        ids = self.layers.get(layer, {}).get('row_ids', [])
        try:
            return ids.index(str(row_id))
        except ValueError:
            return None

    def vector(self, layer: str, metric: str, row: int) -> np.ndarray:
        return self.arrays[f'{layer}/{metric}'][row]

    # -- identity
    def content_digest(self) -> str:
        """Changes if and ONLY if a draw changes.

        Independent of the container and of the chosen encoding, so a re-write
        of identical draws reproduces it exactly and a single altered cell does
        not.
        """
        h = hashlib.sha256()
        h.update(DRAW_ARTIFACT_VERSION.encode())
        for key in sorted(self.arrays):
            a = self.arrays[key]
            h.update(b'\x00' + key.encode() + b'\x00')
            h.update(json.dumps(list(a.shape)).encode())
            h.update(_canonical_bytes(a))
        for layer in sorted(self.layers):
            h.update(b'\x01' + layer.encode() + b'\x00')
            h.update(json.dumps(self.layers[layer]['row_ids']).encode())
        return h.hexdigest()

    def manifest(self) -> dict:
        return {
            'draw_artifact_version': DRAW_ARTIFACT_VERSION,
            'run_id': self.run_id, 'game_id': self.game_id,
            'n_draws': int(self.n_draws) if self.n_draws else 0,
            'n_layers': len(self.layers),
            'n_matrices': len(self.arrays),
            'n_draw_cells': int(sum(a.size for a in self.arrays.values())),
            'rng': {
                'seed': self.seed,
                'seed_protocol': self.seed_protocol,
                'generator': 'numpy.random.default_rng (PCG64)',
            },
            'draw_index_semantics': {
                'within_row_across_metrics': WITHIN_ROW,
                'across_rows': ACROSS_ROWS,
                'note': ('column j is the same iteration of one row\'s stream '
                         'for every metric of that row, so cross-metric '
                         'dependence on this axis is real. Rows are seeded '
                         'independently, so a CROSS-ROW correlation read off '
                         'the same axis measures the generator\'s lack of '
                         'coupling, not a football quantity.'),
            },
            'layers': {k: dict(v) for k, v in sorted(self.layers.items())},
            'content_digest': self.content_digest(),
        }

    # -- writing
    def write(self, out_dir) -> Outcome:
        """Write the container and the manifest, then VERIFY BY READING BACK.

        A write that is not read back is a claim, and this project has paid for
        several of those. The returned manifest is only produced after the file
        on disk has been decoded and compared cell-by-cell with what is in
        memory.
        """
        if not self.arrays:
            return Outcome.fail(
                'DRAW_SET_EMPTY',
                'no layer produced a draw matrix, so there is no distribution '
                'to preserve. Writing an empty container and reporting success '
                'is the exact defect this artifact exists to end.')
        if not self.n_draws:
            return Outcome.fail('DRAW_SET_NO_DRAW_INDEX',
                                'the draw set carries no draw index')
        out_dir = pathlib.Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / DRAW_FILE_NAME

        encoded, entries = {}, {}
        for key in sorted(self.arrays):
            src = self.arrays[key]
            enc, dtype_name = encode(src)
            if not np.array_equal(np.asarray(enc, dtype=np.float64), src):
                return Outcome.fail(
                    'DRAW_ENCODING_LOSSY',
                    f'{key} does not survive encoding to {dtype_name} exactly. '
                    f'Refusing to store an approximation of a draw -- the '
                    f'alternative would be a silent numerical correction.',
                    key=key, dtype=dtype_name)
            encoded[key] = enc
            entries[key] = {'dtype': dtype_name, 'shape': list(enc.shape),
                            'sha256': hashlib.sha256(
                                _canonical_bytes(src)).hexdigest()}

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for key in sorted(encoded):
                nb = io.BytesIO()
                np.lib.format.write_array(nb, encoded[key],
                                          allow_pickle=False)
                info = zipfile.ZipInfo(filename=key.replace('/', '__') + '.npy',
                                       date_time=_FIXED_ZIP_DATE)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                zf.writestr(info, nb.getvalue())
        blob = buf.getvalue()
        path.write_bytes(blob)

        file_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if file_sha != hashlib.sha256(blob).hexdigest():
            return Outcome.fail(
                'DRAW_FILE_NOT_PERSISTED',
                f'{path} does not hash to the bytes just written')

        man = self.manifest()
        man['arrays'] = entries
        man['file'] = {'name': DRAW_FILE_NAME, 'sha256': file_sha,
                       'bytes': len(blob)}
        rb = verify(path, man, expect=self.arrays)
        if rb.state is not State.PASS:
            return rb
        (out_dir / MANIFEST_FILE_NAME).write_text(
            json.dumps(man, indent=1, sort_keys=True) + '\n')
        return Outcome.ok(
            'DRAW_ARTIFACT_WRITTEN', value=man,
            detail=f'{man["n_matrices"]} matrix(es), {man["n_draw_cells"]} '
                   f'draw cell(s), {len(blob)} byte(s), verified by read-back',
            path=str(path), sha256=file_sha, bytes=len(blob),
            n_draw_cells=man['n_draw_cells'], n_draws=man['n_draws'])


# --------------------------------------------------------------- reading
def read(path) -> Outcome:
    """Decode a container into {key: float64 matrix}. Named refusals only."""
    path = pathlib.Path(path)
    if not path.exists():
        return Outcome.blocked(
            'DRAW_FILE_ABSENT', f'{path} does not exist, so the artifact that '
            f'references it cannot be scored.', cause=Cause.DATA)
    out = {}
    try:
        with zipfile.ZipFile(path) as zf:
            names = sorted(zf.namelist())
            if not names:
                return Outcome.fail(
                    'DRAW_FILE_EMPTY',
                    f'{path} contains no arrays. An empty container is an '
                    f'absence, and reading it as a draw set is how nothing '
                    f'becomes a forecast.')
            for n in names:
                with zf.open(n) as fh:
                    a = np.lib.format.read_array(io.BytesIO(fh.read()),
                                                 allow_pickle=False)
                out[n[:-4].replace('__', '/')] = np.asarray(a, dtype=np.float64)
    except (zipfile.BadZipFile, ValueError) as exc:
        return Outcome.fail('DRAW_FILE_UNREADABLE',
                            f'{path}: {type(exc).__name__}: {exc}')
    return Outcome.ok('DRAW_FILE_READ', value=out, n_matrices=len(out))


def verify(path, manifest: dict, expect: dict = None) -> Outcome:
    """The file on disk against the manifest, and optionally against memory."""
    got = read(path)
    if got.state is not State.PASS:
        return got
    arrays = got.value
    declared = manifest.get('arrays') or {}
    if not declared:
        return Outcome.fail(
            'DRAW_MANIFEST_LISTS_NO_ARRAYS',
            'the manifest names no matrices, so nothing about the file can be '
            'checked and "verified" would mean nothing.')
    missing = sorted(set(declared) - set(arrays))
    extra = sorted(set(arrays) - set(declared))
    if missing or extra:
        return Outcome.fail(
            'DRAW_FILE_MANIFEST_MISMATCH',
            f'file and manifest disagree: missing {missing}, unexpected '
            f'{extra}', missing=missing, unexpected=extra)
    bad = []
    for key, meta in sorted(declared.items()):
        a = arrays[key]
        if list(a.shape) != list(meta['shape']):
            bad.append({'key': key, 'why': 'shape',
                        'stored': list(a.shape), 'declared': meta['shape']})
            continue
        if hashlib.sha256(_canonical_bytes(a)).hexdigest() != meta['sha256']:
            bad.append({'key': key, 'why': 'content sha256'})
            continue
        if expect is not None and not np.array_equal(a, expect[key]):
            bad.append({'key': key, 'why': 'read-back differs from memory'})
    if bad:
        return Outcome.fail(
            'DRAW_ARTIFACT_CORRUPT',
            f'{len(bad)} matrix(es) on disk do not match the manifest. A draw '
            f'file that does not reproduce its own digest cannot support '
            f'deterministic replay.', offences=bad[:10])
    widths = {int(a.shape[1]) for a in arrays.values()}
    if len(widths) != 1:
        return Outcome.fail(
            'DRAW_INDEX_RAGGED',
            f'the stored matrices carry draw counts {sorted(widths)}. Column j '
            f'must mean the same iteration in every matrix or no dependence '
            f'diagnostic on this file is valid.', widths=sorted(widths))
    if manifest.get('n_draws') and int(manifest['n_draws']) not in widths:
        return Outcome.fail(
            'DRAW_INDEX_MANIFEST_MISMATCH',
            f'manifest declares {manifest["n_draws"]} draws, file carries '
            f'{sorted(widths)}')
    fmeta = manifest.get('file') or {}
    if fmeta.get('sha256'):
        actual = hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
        if actual != fmeta['sha256']:
            return Outcome.fail(
                'DRAW_FILE_HASH_MISMATCH',
                f'{path} hashes to {actual[:16]}... against the recorded '
                f'{fmeta["sha256"][:16]}...; the referenced bytes are not the '
                f'bytes that were sealed.')
    return Outcome.ok(
        'DRAW_ARTIFACT_VERIFIED',
        value={'n_matrices': len(arrays), 'n_draws': sorted(widths)[0]},
        detail=f'{len(arrays)} matrix(es) re-read and hashed, one shared draw '
               f'index of {sorted(widths)[0]}')


# --------------------------------------------------------------- summaries
QUANTILE_VIEW = ('p10', 'p50', 'p90')
_Q = {'p10': 0.10, 'p50': 0.50, 'p90': 0.90}


def quantile_view(vec) -> dict:
    """The convenient view. KEPT, never the only thing kept."""
    a = np.asarray(vec, dtype=np.float64).reshape(-1)
    if a.size == 0:
        raise ValueError('QUANTILE_VIEW_OF_EMPTY: an empty draw vector has no '
                         'quantiles, and returning zeros for one would be a '
                         'fabricated forecast')
    return {'mean': float(a.mean()),
            **{k: float(np.quantile(a, q)) for k, q in _Q.items()}}


def assert_summary_consistent(summaries: dict, ds: 'DrawSet') -> Outcome:
    """The stored quantile view must be recomputable from the stored draws.

    This is the check that makes the two representations one object. Without
    it the summary and the draws could describe different runs and nothing
    would say so -- and the summary is what a reader looks at first.

    `summaries` maps 'layer/metric/row_id' -> the emitted quantile dict.
    """
    if not summaries:
        return Outcome.fail(
            'SUMMARY_SET_EMPTY',
            'no quantile summary was emitted alongside the draws, so the two '
            'views cannot be checked against each other.')
    bad, unmatched = [], []
    for key, s in sorted(summaries.items()):
        layer, metric, row_id = key.split('/', 2)
        i = ds.row_index(layer, row_id)
        if i is None or f'{layer}/{metric}' not in ds.arrays:
            unmatched.append(key)
            continue
        want = quantile_view(ds.vector(layer, metric, i))
        for f in ('mean',) + QUANTILE_VIEW:
            if float(s[f]) != float(want[f]):
                bad.append({'key': key, 'field': f, 'summary': float(s[f]),
                            'from_draws': float(want[f])})
    if unmatched:
        return Outcome.fail(
            'SUMMARY_WITHOUT_DRAWS',
            f'{len(unmatched)} summary(ies) name a metric or row that is not '
            f'in the draw set. A number with no draws behind it cannot be '
            f'replayed or scored.', offences=unmatched[:10])
    if bad:
        return Outcome.fail(
            'SUMMARY_DRAWS_DISAGREE',
            f'{len(bad)} summary field(s) are not what the stored draws give. '
            f'The two representations describe different numbers, and the '
            f'quantile view is the one a reader trusts on sight.',
            offences=bad[:10])
    return Outcome.ok('SUMMARY_MATCHES_DRAWS', value=len(summaries),
                      detail=f'all {len(summaries)} summary(ies) recomputed '
                             f'exactly from the stored draws')
