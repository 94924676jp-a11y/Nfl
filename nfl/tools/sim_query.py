#!/usr/bin/env python3.12
"""Ask the stored simulation worlds a question. READ-ONLY; every number is counted from stored worlds.

    python3.12 nfl/tools/sim_query.py WORLDS.npz [--draws DRAWS.json] [--label PRODUCTION|RESEARCH|SHADOW]
        --query "P(rush_yards['Jalon Daniels|TB'] >= 50)" [--query ...]
        [--optimal CANDIDATES.csv] [--side-by-side WORLDS2.npz DRAWS2.json] [--min-worlds 50] [--out ANSWERS.json]

WHAT THIS IS. An analytical query interface over OUR OWN simulation worlds (the arrays the optimizer scores). It
never invents a probability, never calls a language model, never reads a sportsbook price, and never writes
anything except the optional --out JSON. A query is parsed by a closed recursive-descent grammar; nothing is
passed to eval/exec. An answer is only as good as the worlds it counts: calibration of the worlds is a separate
question this tool does not answer.

DATA CONTRACT. One worlds format is supported, and it is checked field by field on load:

  WORLDS_NPZ_V1  written by nfl/tools/classic_slate_run.py `_write_worlds` (also called by showdown_slate_run.py
                 and nfl/sim/event_consistent_worlds.py, so Classic, Showdown and the shadow event-consistent
                 worlds share it). Arrays: stats int16 [player, world, field] (yard fields stored in tenths,
                 meta.yard_scale), points float32 [game, world, (home, away)], meta = JSON bytes with keys,
                 fields, yard_scale, yard_fields, games[{game_id, home, away}], projection_sha256.
                 Layout SHOWDOWN when it holds one game, CLASSIC when it holds more than one.

  Refused by name: the showdown_draws.py `*_STATS.npz` sidecar (per-key float64 arrays, no club points) raises
  UNSUPPORTED_WORLDS_FORMAT; anything else raises UNKNOWN_WORLDS_FORMAT.

  DRAWS.json (optional) supplies dk_points: {'draws': {key: [DK points per world]}}, one list per player on the
  same world index. It is accepted only if n_sims and projection_sha256 agree with the worlds and DK points
  recomputed from the stored stat lines agree with the draws in >= ALIGNMENT_FLOOR of cells (otherwise
  DRAWS_WORLDS_MISALIGNED). Without it, any dk_points reference raises DRAWS_NOT_LOADED.

QUERY GRAMMAR (keywords case-insensitive)

  query    := P(pred) | P(pred | pred) | COUNT(pred) | JOINT(pred, pred)
            | MEAN(value [| pred]) | QUANTILES(value [, q ...] [| pred]) | CORR(value, value [| pred])
  pred     := disj ;  disj := conj (OR conj)* ;  conj := neg (AND neg)* ;  neg := NOT neg | atom
  atom     := ( pred ) | value OP value | wins['CLUB'] | tie['CLUB']        OP := >= > <= < == !=
  value    := NUMBER | FIELD['player key or name']
            | points['CLUB'] | opp_points['CLUB'] | margin['CLUB'] | total['CLUB' or 'GAME_ID']

  player FIELD: pass_att (pass_attempts), pass_yards, pass_td, carries (rush_att), rush_yards, rush_td, targets,
                receptions, rec_yards, rec_td, interceptions, any_td (= rush_td + rec_td), dk_points (dk).
  margin['DAL'] = DAL points minus its opponent's in the same world; wins['TB'] = TB points strictly greater.

  Examples:  P(rush_yards['Jalon Daniels|TB'] >= 50)        P(margin['DAL'] >= 20)        P(wins['TB'])
             P(any_td['Javonte Williams'] >= 1 AND any_td['Tyler Goodson'] >= 1)
             QUANTILES(dk['CeeDee Lamb'], 0.1, 0.5, 0.9 | dk['Dak Prescott'] < 14.2)
             CORR(dk['Javonte Williams'], dk['Tyler Goodson'])

  Optimal-lineup frequency (Showdown only): --optimal CANDIDATES.csv (columns captain, flex = 'A / B / C / D / E').
  In each world every candidate is scored 1.5 x CPT DK + sum of FLEX DK; the best candidate in the supplied pool
  wins the world (exact ties split equally). Shares are reported per player as CPT and as FLEX separately. It is
  optimal AMONG THE SUPPLIED POOL, not among all legal lineups.

GUARANTEES
  * Every number is a count or an order statistic over stored worlds; each answer carries value, n_worlds,
    numerator/denominator, a Monte Carlo SE with its method stated, the normalised query text and provenance
    (paths, sha256, n_worlds, model label PRODUCTION / RESEARCH / SHADOW, projection_sha256).
  * A conditional (or any) answer whose denominator is below the declared minimum (MIN_CONDITIONING_WORLDS, 50)
    returns status INSUFFICIENT_WORLDS and no value.
  * A player reference must match exactly one key after case/punctuation normalisation, else PLAYER_NOT_FOUND
    or PLAYER_AMBIGUOUS listing candidates. No fuzzy matching.
  * A football quantity the worlds do not carry (first TD, TD order, snaps, longest play, ...) raises
    NOT_IN_WORLDS. It is never approximated.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import pathlib
import re
import sys
from dataclasses import dataclass, field

SPEC_VERSION = 'sim-query-1'
FORMAT_V1 = 'WORLDS_NPZ_V1'
FORMAT_V1_WRITER = 'nfl/tools/classic_slate_run.py:_write_worlds'

#: DECLARED FLOOR, not fitted: at n = 50 the binomial SE of a probability near 0.5 is 0.071, the largest
#: imprecision this tool will print as a number. Below it the answer is INSUFFICIENT_WORLDS.
MIN_CONDITIONING_WORLDS = 50
#: DECLARED, measured not tuned: DK points recomputed from the stored stat line agree with the stored draws in
#: 0.99995-0.99998 of cells on TB@DAL OFFICIAL, TB@DAL shadow and Classic W5 (the residue is yards stored to 0.1
#: landing on a 100/300 bonus line). Worlds on a different index would agree only by coincidence.
ALIGNMENT_FLOOR = 0.99
#: Two-sided 95% normal quantile, used for every stated interval.
Z95 = 1.959963984540054
DK_TOLERANCE = 0.06                 # DK recomputation tolerance, as world_accounting_check.py uses
CPT_MULTIPLIER = 1.5                # DraftKings Showdown captain scoring rule

LABELS = ('PRODUCTION', 'RESEARCH', 'SHADOW')
DEFAULT_QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.95)

#: Player fields the query language knows. Value: the stored field(s) summed to make it.
PLAYER_FIELDS = {
    'pass_att': ('pass_att',), 'pass_yards': ('pass_yards',), 'pass_td': ('pass_td',),
    'carries': ('carries',), 'rush_yards': ('rush_yards',), 'rush_td': ('rush_td',),
    'targets': ('targets',), 'receptions': ('receptions',), 'rec_yards': ('rec_yards',), 'rec_td': ('rec_td',),
    'interceptions': ('interceptions',), 'any_td': ('rush_td', 'rec_td'),
}
FIELD_ALIASES = {'pass_attempts': 'pass_att', 'rush_att': 'carries', 'rush_attempts': 'carries',
                 'dk': 'dk_points', 'ints': 'interceptions'}
CLUB_VALUES = ('points', 'opp_points', 'margin', 'total')
CLUB_BOOLS = ('wins', 'tie')
#: Football quantities a world does not carry. Asking for one is refused, never approximated.
NOT_IN_WORLDS_FIELDS = {
    'first_td': 'touchdown ORDER is not simulated; worlds hold per-player counts only',
    'first_td_scorer': 'touchdown ORDER is not simulated', 'last_td': 'touchdown ORDER is not simulated',
    'td_order': 'touchdown ORDER is not simulated', 'snaps': 'snap counts are not in the worlds',
    'snap_share': 'snap counts are not in the worlds', 'routes': 'routes run are not in the worlds',
    'air_yards': 'air yards are not in the worlds', 'yac': 'yards after catch are not in the worlds',
    'longest_reception': 'play-level lengths are not in the worlds', 'longest_rush': 'play-level lengths are not in the worlds',
    'longest_pass': 'play-level lengths are not in the worlds', 'fumbles': 'fumbles are not drawn per player',
    'fumbles_lost': 'fumbles are not drawn per player', 'two_point': 'two-point conversions are not in the stat lines',
    'sacks': 'sacks are not in the player stat lines', 'sacks_taken': 'sacks are not in the player stat lines',
    'kick_return_td': 'return events are not in the worlds', 'punt_return_td': 'return events are not in the worlds',
    'return_yards': 'return events are not in the worlds', 'red_zone_targets': 'field position is not in the worlds',
    'first_half_points': 'scores are stored per game, not per half or quarter',
    'quarter_points': 'scores are stored per game, not per half or quarter',
    'completions': 'completions are not stored for passers (receptions are stored for receivers)',
    'fg_made': 'kicker events are not in the per-world stat arrays', 'tackles': 'defensive player stats are not simulated',
}


# --------------------------------------------------------------------------------------------------- errors
class SimQueryError(Exception):
    """A named refusal. `code` is stable; `evidence` carries what the caller needs to fix the query."""
    code = 'SIM_QUERY_ERROR'

    def __init__(self, detail, **evidence):
        super().__init__(f'{self.code}: {detail}')
        self.detail, self.evidence = detail, evidence


def _err(name):
    return type(name.title().replace('_', ''), (SimQueryError,), {'code': name})


UnknownWorldsFormat = _err('UNKNOWN_WORLDS_FORMAT')
UnsupportedWorldsFormat = _err('UNSUPPORTED_WORLDS_FORMAT')
WorldsDrawsMismatch = _err('WORLDS_DRAWS_MISMATCH')
DrawsWorldsMisaligned = _err('DRAWS_WORLDS_MISALIGNED')
DrawsNotLoaded = _err('DRAWS_NOT_LOADED')
LabelConflict = _err('LABEL_CONFLICT')
LabelUnresolved = _err('LABEL_UNRESOLVED')
PlayerNotFound = _err('PLAYER_NOT_FOUND')
PlayerAmbiguous = _err('PLAYER_AMBIGUOUS')
NotInWorlds = _err('NOT_IN_WORLDS')
UnknownField = _err('UNKNOWN_FIELD')
ClubNotFound = _err('CLUB_NOT_FOUND')
QueryParseError = _err('QUERY_PARSE_ERROR')
ShowdownOnly = _err('SHOWDOWN_ONLY')
ZeroVariance = _err('ZERO_VARIANCE')
CandidateInvalid = _err('CANDIDATE_INVALID')
OutputRefused = _err('OUTPUT_REFUSED')


# --------------------------------------------------------------------------------------------------- loading
def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def norm_name(s: str) -> str:
    """Case and punctuation only: 'D.J. Moore' == 'dj moore'; 'Spann-Ford' == 'spann ford'. Nothing fuzzier."""
    s = s.lower().replace('-', ' ')
    s = re.sub(r"[.,'’`]", '', s)
    return ' '.join(s.split())


def dk_from_stats_vec(S, F):
    """DraftKings scoring from stored stat arrays; identical to classic_slate_run.dk_from_stats, vectorised."""
    import numpy as np
    g = lambda f: S[..., F[f]]          # noqa: E731
    pyd, ryd, recyd = g('pass_yards'), g('rush_yards'), g('rec_yards')
    return (pyd * 0.04 + g('pass_td') * 4.0 + np.where(pyd >= 300, 3.0, 0.0) - g('interceptions')
            + ryd * 0.1 + g('rush_td') * 6.0 + np.where(ryd >= 100, 3.0, 0.0)
            + g('receptions') * 1.0 + recyd * 0.1 + g('rec_td') * 6.0 + np.where(recyd >= 100, 3.0, 0.0))


@dataclass
class WorldSet:
    stats: object                       # float64 [player, world, field], yards de-scaled
    keys: list
    fields: list
    points: object                      # float64 [game, world, (home, away)]
    games: list
    draws: dict | None                  # key -> float64 [world]
    layout: str                         # SHOWDOWN | CLASSIC
    provenance: dict
    _kidx: dict = field(default_factory=dict)

    @property
    def n_worlds(self) -> int:
        return int(self.stats.shape[1])

    @property
    def label(self) -> str:
        return self.provenance['model_label']

    # ---- resolution
    def _resolve(self, ref: str, domain: list, what: str) -> str:
        parts = ref.split('|')
        name, team = norm_name(parts[0]), (parts[1].strip().upper() if len(parts) > 1 else None)
        hits = [k for k in domain
                if norm_name(k.split('|')[0]) == name and (team is None or k.split('|')[1].upper() == team)]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise PlayerAmbiguous(f'{ref!r} matches {len(hits)} {what} keys; give the club', candidates=sorted(hits))
        toks = {t for t in name.split() if len(t) >= 3}
        cand = sorted(k for k in domain if toks & set(norm_name(k.split('|')[0]).split()))[:12]
        raise PlayerNotFound(f'{ref!r} matches no {what} key exactly (case/punctuation normalised only)',
                             candidates=cand)

    def stat_key(self, ref):
        try:
            return self._resolve(ref, self.keys, 'stat-line')
        except PlayerNotFound:
            if self.draws is not None:
                try:
                    k = self._resolve(ref, list(self.draws), 'DK-draw')
                except SimQueryError:
                    raise
                raise NotInWorlds(f'{k} has DK draws but no per-world stat line (a DST or kicker); '
                                  f'only dk_points can be asked of him', key=k)
            raise

    def dk_key(self, ref):
        if self.draws is None:
            raise DrawsNotLoaded('dk_points needs the DRAWS.json for these worlds (--draws)')
        return self._resolve(ref, list(self.draws), 'DK-draw')

    def club(self, c: str) -> tuple[int, int]:
        """(game index, column 0=home 1=away) of club c."""
        cu = c.strip().upper()
        for gi, g in enumerate(self.games):
            if g['home'].upper() == cu:
                return gi, 0
            if g['away'].upper() == cu:
                return gi, 1
        raise ClubNotFound(f'{c!r} is not a club in these worlds',
                           candidates=sorted({g[s] for g in self.games for s in ('home', 'away')}))

    def game_index(self, ref: str) -> int:
        for gi, g in enumerate(self.games):
            if g['game_id'] == ref:
                return gi
        return self.club(ref)[0]

    # ---- arrays
    def player_array(self, fld: str, ref: str):
        import numpy as np
        if fld == 'dk_points':
            k = self.dk_key(ref)
            return k, self.draws[k]
        k = self.stat_key(ref)
        missing = [f for f in PLAYER_FIELDS[fld] if f not in self._fidx]
        if missing:
            raise NotInWorlds(f'{fld} needs stored field(s) {missing}, which these worlds do not carry',
                              stored_fields=self.fields)
        i = self._kidx[k]
        return k, np.sum([self.stats[i, :, self._fidx[f]] for f in PLAYER_FIELDS[fld]], axis=0)

    def club_array(self, kind: str, ref: str):
        if kind == 'total':
            gi = self.game_index(ref)
            return self.games[gi]['game_id'], self.points[gi, :, 0] + self.points[gi, :, 1]
        gi, col = self.club(ref)
        own, opp = self.points[gi, :, col], self.points[gi, :, 1 - col]
        club = (self.games[gi]['home'] if col == 0 else self.games[gi]['away'])
        return club, {'points': own, 'opp_points': opp, 'margin': own - opp, 'wins': own > opp,
                      'tie': own == opp}[kind]

    def __post_init__(self):
        self._kidx = {k: i for i, k in enumerate(self.keys)}
        self._fidx = {f: i for i, f in enumerate(self.fields)}


def _infer_label(worlds: pathlib.Path, draws_doc: dict | None, passed: str | None) -> tuple[str, str]:
    marks_shadow = bool(draws_doc) and ('SHADOW' in str(draws_doc.get('ARM', '')).upper()
                                         or 'SHADOW_ONLY' in draws_doc)
    p = str(worlds.resolve()).replace('\\', '/')
    if passed is not None:
        lab = passed.upper()
        if lab not in LABELS:
            raise LabelConflict(f'label {passed!r} is not one of {LABELS}')
        if marks_shadow and lab != 'SHADOW':
            raise LabelConflict(f'the draws artifact marks itself a SHADOW arm (ARM={draws_doc.get("ARM")!r}); '
                                f'it cannot be labelled {lab}')
        return lab, 'PASSED'
    if marks_shadow:
        return 'SHADOW', 'ARTIFACT_MARKER (draws ARM / SHADOW_ONLY)'
    if re.search(r'EVENT_CONSISTENT|accounting_repair|/shadow', p, re.I):
        return 'SHADOW', 'PATH'
    if re.search(r'/research/|_research/|/runs/', p):
        return 'RESEARCH', 'PATH'
    if '/OFFICIAL/' in p:
        return 'PRODUCTION', 'PATH'
    raise LabelUnresolved(f'no model label can be inferred from {p}; pass label= one of {LABELS}')


def _receipt_check(worlds: pathlib.Path, sha: str) -> dict:
    rp = worlds.with_name('RUN_RECEIPT.json')
    if not rp.exists():
        return {'state': 'NO_RECEIPT'}
    try:
        arts = json.loads(rp.read_text()).get('artifacts') or {}
    except (OSError, ValueError):
        return {'state': 'RECEIPT_UNREADABLE', 'path': str(rp)}
    hit = {k: v for k, v in arts.items() if k.rsplit('/', 1)[-1] == worlds.name}
    if not hit:
        return {'state': 'NOT_LISTED', 'path': str(rp)}
    (k, v), = hit.items()
    return {'state': 'MATCH' if v == sha else 'MISMATCH', 'receipt_entry': k, 'receipt_sha256': v,
            'path': str(rp)}


def load(worlds_path, draws_path=None, label: str | None = None) -> WorldSet:
    """Load stored worlds (and optional DK draws) read-only, verifying format, alignment and provenance."""
    import numpy as np
    wp = pathlib.Path(worlds_path)
    try:
        z = np.load(wp, allow_pickle=False)
        names = set(z.files)
    except Exception as e:                                   # noqa: BLE001 - any unreadable file is one refusal
        raise UnknownWorldsFormat(f'{wp} is not a readable npz ({type(e).__name__}: {e})') from None
    if names != {'stats', 'points', 'meta'}:
        if names and 'meta' not in names and all(z[n].dtype == np.float64 and z[n].ndim == 2 and '|' in n
                                                 for n in names):
            raise UnsupportedWorldsFormat(
                f'{wp.name} is a showdown_draws.py *_STATS.npz sidecar (per-key float64, no club points); '
                f'query the *_WORLDS.npz instead', arrays=sorted(names)[:5])
        raise UnknownWorldsFormat(f'{wp.name} holds arrays {sorted(names)}; {FORMAT_V1} needs exactly '
                                  f"['meta', 'points', 'stats']")
    try:
        meta = json.loads(z['meta'].tobytes())
    except ValueError as e:
        raise UnknownWorldsFormat(f'{wp.name}: meta is not JSON ({e})') from None
    need = ('keys', 'fields', 'yard_scale', 'yard_fields', 'games')
    if not isinstance(meta, dict) or any(k not in meta for k in need):
        raise UnknownWorldsFormat(f'{wp.name}: meta lacks {[k for k in need if k not in (meta or {})]}')
    stats, pts = z['stats'], z['points']
    nk, nf, ng = len(meta['keys']), len(meta['fields']), len(meta['games'])
    if stats.dtype != np.int16 or stats.ndim != 3 or stats.shape[0] != nk or stats.shape[2] != nf:
        raise UnknownWorldsFormat(f'{wp.name}: stats {stats.dtype}{stats.shape} is not int16 [{nk}, worlds, {nf}]')
    if pts.dtype != np.float32 or pts.shape != (ng, stats.shape[1], 2):
        raise UnknownWorldsFormat(f'{wp.name}: points {pts.dtype}{pts.shape} is not float32 [{ng}, {stats.shape[1]}, 2]')
    if stats.shape[1] == 0 or nk == 0 or ng == 0:
        raise UnknownWorldsFormat(f'{wp.name}: empty worlds (players {nk}, worlds {stats.shape[1]}, games {ng})')
    if len(set(meta['keys'])) != nk or any(k.count('|') != 1 for k in meta['keys']):
        raise UnknownWorldsFormat(f'{wp.name}: keys are not unique Name|CLUB strings')
    if any(f not in meta['fields'] for f in meta['yard_fields']) or int(meta['yard_scale']) <= 0:
        raise UnknownWorldsFormat(f'{wp.name}: yard_fields/yard_scale inconsistent with fields')
    S = stats.astype(np.float64)
    for f in meta['yard_fields']:
        S[:, :, meta['fields'].index(f)] /= float(meta['yard_scale'])
    wsha = _sha(wp)
    prov = {'spec_version': SPEC_VERSION, 'read_only': True,
            'worlds_path': str(wp.resolve()), 'worlds_sha256': wsha, 'format': FORMAT_V1,
            'format_writer': FORMAT_V1_WRITER, 'n_worlds': int(stats.shape[1]), 'n_stat_players': nk,
            'stored_fields': list(meta['fields']), 'yard_storage': f"1/{meta['yard_scale']} yd",
            'games': meta['games'], 'projection_sha256': meta.get('projection_sha256'),
            'receipt_check': _receipt_check(wp, wsha)}
    draws, doc = None, None
    if draws_path is not None:
        dp = pathlib.Path(draws_path)
        doc = json.loads(dp.read_text())
        dd = doc.get('draws')
        if not isinstance(dd, dict) or not dd:
            raise WorldsDrawsMismatch(f'{dp.name} has no draws block')
        n = stats.shape[1]
        bad = [k for k, v in dd.items() if not isinstance(v, list) or len(v) != n]
        if bad or int(doc.get('n_sims', n)) != n:
            raise WorldsDrawsMismatch(f'{dp.name}: draws are not {n} worlds long ({len(bad)} keys differ, '
                                      f'n_sims={doc.get("n_sims")})', keys=bad[:10])
        ps_w, ps_d = meta.get('projection_sha256'), doc.get('projection_sha256')
        if ps_w and ps_d and ps_w != ps_d:
            raise WorldsDrawsMismatch(f'projection_sha256 differs: worlds {ps_w[:12]} vs draws {ps_d[:12]}')
        draws = {k: np.asarray(v, dtype=np.float64) for k, v in dd.items()}
        F = {f: i for i, f in enumerate(meta['fields'])}
        shared = [k for k in meta['keys'] if k in draws]
        if not shared:
            raise DrawsWorldsMisaligned(f'{dp.name} shares no key with the worlds')
        align = None
        if all(f in F for f in ('pass_yards', 'pass_td', 'rush_yards', 'rush_td', 'receptions', 'rec_yards',
                                'rec_td', 'interceptions')):
            idx = [meta['keys'].index(k) for k in shared]
            rec = dk_from_stats_vec(S[idx], F)
            got = np.stack([draws[k] for k in shared])
            gap = np.abs(rec - got)
            ok = (gap <= DK_TOLERANCE) | (np.abs(gap - 3.0) <= DK_TOLERANCE)     # bonus-line storage rounding
            align = float(ok.mean())
            if align < ALIGNMENT_FLOOR:
                raise DrawsWorldsMisaligned(f'DK recomputed from stored stats agrees with {dp.name} in only '
                                            f'{align:.4f} of cells (floor {ALIGNMENT_FLOOR}); not the same worlds',
                                            agreement=align)
        prov.update({'draws_path': str(dp.resolve()), 'draws_sha256': _sha(dp), 'n_draw_players': len(draws),
                     'draws_projection_sha256': ps_d, 'draws_artifact': doc.get('ARTIFACT'),
                     'draws_arm': doc.get('ARM'), 'draws_shadow_only': doc.get('SHADOW_ONLY'),
                     'dk_alignment': {'shared_keys': len(shared), 'agreement': align, 'floor': ALIGNMENT_FLOOR,
                                      'MEANING': 'share of player-world cells where DK recomputed from the stored '
                                                 'stat line equals the stored draw (within 0.06, or exactly a '
                                                 '3-point bonus line from 0.1-yd storage rounding)'}})
    lab, src = _infer_label(wp, doc, label)
    prov.update({'model_label': lab, 'label_source': src})
    return WorldSet(stats=S, keys=list(meta['keys']), fields=list(meta['fields']), points=pts.astype(np.float64),
                    games=list(meta['games']), draws=draws, layout='SHOWDOWN' if len(meta['games']) == 1 else 'CLASSIC',
                    provenance={**prov, 'layout': 'SHOWDOWN' if len(meta['games']) == 1 else 'CLASSIC'})


# --------------------------------------------------------------------------------------------------- parsing
_TOK = re.compile(r"""\s*(?:(?P<num>-?\d+(?:\.\d+)?)|(?P<str>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")
                     |(?P<op>>=|<=|==|!=|>|<)|(?P<punct>[()\[\],|])|(?P<id>[A-Za-z_][A-Za-z_0-9]*))""", re.X)
_FUNCS = ('P', 'COUNT', 'JOINT', 'MEAN', 'QUANTILES', 'CORR')


def _tokens(text: str):
    out, pos = [], 0
    text = text.strip()
    while pos < len(text):
        m = _TOK.match(text, pos)
        if not m or m.end() == pos:
            raise QueryParseError(f'cannot read the query at character {pos}: {text[pos:pos + 20]!r}')
        kind = m.lastgroup
        v = m.group(kind)
        if kind == 'str':
            v = re.sub(r'\\(.)', r'\1', v[1:-1])
        out.append((kind, v))
        pos = m.end()
        while pos < len(text) and text[pos].isspace():
            pos += 1
    return out


class _Parser:
    def __init__(self, text):
        self.t, self.i, self.text = _tokens(text), 0, text

    def peek(self, k=0):
        return self.t[self.i + k] if self.i + k < len(self.t) else (None, None)

    def take(self, kind=None, val=None):
        tk = self.peek()
        if tk[0] is None or (kind and tk[0] != kind) or (val is not None and str(tk[1]).upper() != val.upper()):
            raise QueryParseError(f'expected {val or kind} at token {self.i} of {self.text!r}, found {tk[1]!r}')
        self.i += 1
        return tk[1]

    def is_kw(self, w):
        k, v = self.peek()
        return k == 'id' and v.upper() == w

    def query(self):
        fn = self.take('id').upper()
        if fn not in _FUNCS:
            raise QueryParseError(f'unknown query {fn!r}; one of {_FUNCS}')
        self.take('punct', '(')
        q = {'fn': fn}
        if fn in ('P', 'COUNT'):
            q['pred'] = self.pred()
            if fn == 'P' and self.peek() == ('punct', '|'):
                self.take()
                q['given'] = self.pred()
        elif fn == 'JOINT':
            q['a'] = self.pred()
            self.take('punct', ',')
            q['b'] = self.pred()
        elif fn in ('MEAN', 'QUANTILES', 'CORR'):
            q['x'] = self.value()
            if fn == 'CORR':
                self.take('punct', ',')
                q['y'] = self.value()
            if fn == 'QUANTILES':
                qs = []
                while self.peek() == ('punct', ','):
                    self.take()
                    qs.append(float(self.take('num')))
                if any(not 0.0 <= x <= 1.0 for x in qs):
                    raise QueryParseError(f'quantile levels must lie in [0, 1]: {qs}')
                q['qs'] = tuple(qs) or DEFAULT_QUANTILES
            if self.peek() == ('punct', '|'):
                self.take()
                q['given'] = self.pred()
        self.take('punct', ')')
        if self.peek()[0] is not None:
            raise QueryParseError(f'unexpected trailing input {self.peek()[1]!r}')
        return q

    def pred(self):
        node = self.conj()
        while self.is_kw('OR'):
            self.take()
            node = ('OR', node, self.conj())
        return node

    def conj(self):
        node = self.neg()
        while self.is_kw('AND'):
            self.take()
            node = ('AND', node, self.neg())
        return node

    def neg(self):
        if self.is_kw('NOT'):
            self.take()
            return ('NOT', self.neg())
        return self.atom()

    def atom(self):
        if self.peek() == ('punct', '('):
            self.take()
            node = self.pred()
            self.take('punct', ')')
            return node
        k, v = self.peek()
        if k == 'id' and v.lower() in CLUB_BOOLS and self.peek(1) == ('punct', '['):
            self.take()
            self.take('punct', '[')
            ref = self.take('str')
            self.take('punct', ']')
            return ('BOOL', v.lower(), ref)
        left = self.value()
        k, op = self.peek()
        if k != 'op':
            raise QueryParseError(f'expected a comparison operator after {left}, found {op!r}')
        self.take()
        return ('CMP', op, left, self.value())

    def value(self):
        k, v = self.peek()
        if k == 'num':
            self.take()
            return ('NUM', float(v))
        if k == 'id':
            self.take()
            self.take('punct', '[')
            ref = self.take('str')
            self.take('punct', ']')
            return ('REF', v.lower(), ref)
        raise QueryParseError(f'expected a number or FIELD[\'key\'], found {v!r}')


def parse(text: str) -> dict:
    """Parse query text into a closed AST (tuples of literals). Never evaluates code."""
    return _Parser(text).query()


# --------------------------------------------------------------------------------------------------- evaluation
def _fmt_num(x):
    return str(int(x)) if float(x).is_integer() else repr(float(x))


class _Eval:
    def __init__(self, ws: WorldSet):
        self.ws = ws

    def value(self, node):
        if node[0] == 'NUM':
            return _fmt_num(node[1]), node[1]
        _, fld, ref = node
        fld = FIELD_ALIASES.get(fld, fld)
        if fld in NOT_IN_WORLDS_FIELDS:
            raise NotInWorlds(f'{fld}: {NOT_IN_WORLDS_FIELDS[fld]}', field=fld)
        if fld in PLAYER_FIELDS or fld == 'dk_points':
            key, arr = self.ws.player_array(fld, ref)
            return f'{fld}[{key!r}]', arr
        if fld in CLUB_VALUES:
            key, arr = self.ws.club_array(fld, ref)
            return f'{fld}[{key!r}]', arr
        if fld in CLUB_BOOLS:
            raise QueryParseError(f'{fld}[...] is a condition, not a value; use it on its own')
        raise UnknownField(f'{fld!r} is not a field of the query language',
                           player_fields=sorted(PLAYER_FIELDS) + ['dk_points'], club_values=list(CLUB_VALUES),
                           club_conditions=list(CLUB_BOOLS))

    def pred(self, node, top=False):
        """(normalised text, bool[world]). Binary nodes are parenthesised except at the top level."""
        import numpy as np
        op = node[0]
        if op == 'AND' or op == 'OR':
            ta, a = self.pred(node[1])
            tb, b = self.pred(node[2])
            t = f'{ta} {op} {tb}'
            return (t if top else f'({t})'), (a & b) if op == 'AND' else (a | b)
        if op == 'NOT':
            t, a = self.pred(node[1])
            return f'NOT {t}', ~a
        if op == 'BOOL':
            key, arr = self.ws.club_array(node[1], node[2])
            return f'{node[1]}[{key!r}]', np.asarray(arr, dtype=bool)
        _, cmp, l, r = node
        tl, a = self.value(l)
        tr, b = self.value(r)
        if l[0] == 'NUM' and r[0] == 'NUM':
            raise QueryParseError(f'{tl} {cmp} {tr} compares two constants; it measures nothing')
        f = {'>=': np.greater_equal, '>': np.greater, '<=': np.less_equal, '<': np.less,
             '==': np.equal, '!=': np.not_equal}[cmp]
        return f'{tl} {cmp} {tr}', np.broadcast_to(f(a, b), (self.ws.n_worlds,)).copy()


def _wilson(k, n):
    if n == 0:
        return None
    p = k / n
    d = 1 + Z95 ** 2 / n
    c = (p + Z95 ** 2 / (2 * n)) / d
    h = Z95 * math.sqrt(p * (1 - p) / n + Z95 ** 2 / (4 * n * n)) / d
    return [round(max(0.0, c - h), 6), round(min(1.0, c + h), 6)]


def _base(ws, text, kind, min_worlds):
    return {'query': text, 'kind': kind, 'n_worlds': ws.n_worlds, 'model_label': ws.label,
            'min_conditioning_worlds': min_worlds, 'provenance': ws.provenance}


def _insufficient(ans, n):
    ans.update({'status': 'INSUFFICIENT_WORLDS', 'value': None, 'se': None,
                'detail': f'{n} conditioning worlds, below the declared minimum {ans["min_conditioning_worlds"]}'})
    return ans


def _quantile_ci(xs_sorted, q):
    """Distribution-free order-statistic interval for the q-quantile (binomial ranks), and SE = width / (2 z)."""
    n = len(xs_sorted)
    s = Z95 * math.sqrt(n * q * (1 - q))
    lo = int(max(0, math.floor(n * q - s) - 1))
    hi = int(min(n - 1, math.ceil(n * q + s)))
    a, b = float(xs_sorted[lo]), float(xs_sorted[hi])
    return [a, b], (b - a) / (2 * Z95)


def ask(ws: WorldSet, text: str, min_worlds: int = MIN_CONDITIONING_WORLDS) -> dict:
    """Answer one query on one WorldSet. Raises a named SimQueryError on any refusal."""
    import numpy as np
    q = parse(text)
    ev = _Eval(ws)
    fn = q['fn']
    n = ws.n_worlds
    given_t, given = None, np.ones(n, dtype=bool)
    if 'given' in q:
        given_t, given = ev.pred(q['given'], top=True)
    ng = int(given.sum())
    if fn in ('P', 'COUNT'):
        pt, m = ev.pred(q['pred'], top=True)
        norm = f'{fn}({pt}' + (f' | {given_t})' if given_t else ')')
        ans = _base(ws, norm, 'CONDITIONAL_PROBABILITY' if given_t else ('COUNT' if fn == 'COUNT' else 'PROBABILITY'),
                    min_worlds)
        k = int((m & given).sum())
        ans.update({'numerator': k, 'denominator': ng, 'n_matching': k, 'n_conditioning': ng if given_t else None})
        if fn == 'COUNT':
            ans.update({'status': 'OK', 'value': k, 'se': None, 'se_method': 'a count of stored worlds; exact'})
            return ans
        if ng < min_worlds:
            return _insufficient(ans, ng)
        p = k / ng
        ans.update({'status': 'OK', 'value': round(p, 6), 'se': round(math.sqrt(p * (1 - p) / ng), 6),
                    'se_method': 'binomial sqrt(p(1-p)/denominator), worlds treated as independent draws',
                    'ci95_wilson': _wilson(k, ng)})
        if k == 0 or k == ng:
            ans['note'] = (f'{"no" if k == 0 else "every"} conditioning world; the binomial SE is 0 but the '
                           f'95% Wilson interval {ans["ci95_wilson"]} is the honest statement')
        return ans
    if fn == 'JOINT':
        ta, a = ev.pred(q['a'], top=True)
        tb, b = ev.pred(q['b'], top=True)
        ans = _base(ws, f'JOINT({ta}, {tb})', 'JOINT', min_worlds)
        if n < min_worlds:
            return _insufficient(ans, n)
        cells = {'A_and_B': a & b, 'A_and_notB': a & ~b, 'notA_and_B': ~a & b, 'notA_and_notB': ~a & ~b}
        tab = {c: {'count': int(v.sum()), 'p': round(v.mean(), 6),
                   'se': round(math.sqrt(v.mean() * (1 - v.mean()) / n), 6)} for c, v in cells.items()}
        pa, pb, pab = a.mean(), b.mean(), (a & b).mean()
        ans.update({'status': 'OK', 'value': tab, 'numerator': tab['A_and_B']['count'], 'denominator': n,
                    'n_matching': tab['A_and_B']['count'], 'p_A': round(pa, 6), 'p_B': round(pb, 6),
                    'p_A_times_p_B': round(pa * pb, 6),
                    'lift': round(pab / (pa * pb), 4) if pa * pb > 0 else None,
                    'se_method': 'binomial per cell over all worlds'})
        return ans
    tx, x = ev.value(q['x'])
    if q['x'][0] == 'NUM':
        raise QueryParseError(f'{fn} of a constant measures nothing')
    xs = x[given]
    if fn == 'MEAN':
        ans = _base(ws, f'MEAN({tx}' + (f' | {given_t})' if given_t else ')'), 'MEAN', min_worlds)
        ans.update({'denominator': ng, 'n_matching': ng, 'n_conditioning': ng if given_t else None})
        if ng < min_worlds:
            return _insufficient(ans, ng)
        ans.update({'status': 'OK', 'value': round(float(xs.mean()), 4),
                    'se': round(float(xs.std(ddof=1) / math.sqrt(ng)), 4), 'se_method': 'sd / sqrt(n)'})
        return ans
    if fn == 'QUANTILES':
        qs = q['qs']
        ans = _base(ws, f'QUANTILES({tx}, {", ".join(_fmt_num(v) for v in qs)}'
                        + (f' | {given_t})' if given_t else ')'), 'QUANTILES', min_worlds)
        ans.update({'denominator': ng, 'n_matching': ng, 'n_conditioning': ng if given_t else None})
        if ng < min_worlds:
            return _insufficient(ans, ng)
        srt = np.sort(xs)
        vals = {}
        for lv in qs:
            ci, se = _quantile_ci(srt, lv)
            vals[_fmt_num(lv)] = {'value': round(float(np.quantile(xs, lv)), 4), 'ci95': [round(c, 4) for c in ci],
                                  'se': round(se, 4)}
        ans.update({'status': 'OK', 'value': vals, 'mean': round(float(xs.mean()), 4),
                    'se_method': ('numpy.quantile (linear); SE = half-width of the distribution-free order-statistic '
                                  '95% interval (binomial ranks n*q +/- z*sqrt(n q (1-q))) divided by 1.96; '
                                  'no resampling, so the answer is deterministic')})
        return ans
    ty, y = ev.value(q['y'])
    ys = y[given]
    ans = _base(ws, f'CORR({tx}, {ty}' + (f' | {given_t})' if given_t else ')'), 'CORRELATION', min_worlds)
    ans.update({'denominator': ng, 'n_matching': ng, 'n_conditioning': ng if given_t else None})
    if ng < min_worlds:
        return _insufficient(ans, ng)
    if float(xs.std()) == 0.0 or float(ys.std()) == 0.0:
        raise ZeroVariance(f'{tx if float(xs.std()) == 0 else ty} is constant over the {ng} worlds; '
                           f'a correlation is undefined, not zero')
    r = float(np.corrcoef(xs, ys)[0, 1])
    zf, sz = math.atanh(max(min(r, 0.999999), -0.999999)), 1 / math.sqrt(ng - 3)
    ans.update({'status': 'OK', 'value': round(r, 4), 'se': round((1 - r * r) / math.sqrt(ng - 3), 4),
                'ci95': [round(math.tanh(zf - Z95 * sz), 4), round(math.tanh(zf + Z95 * sz), 4)],
                'se_method': 'Pearson over worlds; SE (1-r^2)/sqrt(n-3), ci95 by Fisher z',
                'mean_x': round(float(xs.mean()), 4), 'mean_y': round(float(ys.mean()), 4)})
    return ans


def ask_side_by_side(worldsets: list, text: str, min_worlds: int = MIN_CONDITIONING_WORLDS) -> list:
    """The same query on several WorldSets (e.g. PRODUCTION and SHADOW). A refusal on one is recorded, not hidden."""
    out = []
    for ws in worldsets:
        try:
            out.append(ask(ws, text, min_worlds))
        except SimQueryError as e:
            out.append({'query': text, 'model_label': ws.label, 'status': 'REFUSED', 'code': e.code,
                        'detail': e.detail, 'evidence': e.evidence, 'provenance': ws.provenance})
    return out


# --------------------------------------------------------------------------------------------------- optimal
def read_candidates(path) -> list:
    """[(captain name, [5 flex names])] from a candidate CSV with columns captain, flex ('A / B / C / D / E')."""
    p = pathlib.Path(path)
    with p.open(newline='') as fh:
        rd = csv.DictReader(fh)
        if not rd.fieldnames or 'captain' not in rd.fieldnames or 'flex' not in rd.fieldnames:
            raise CandidateInvalid(f'{p.name} lacks captain/flex columns ({rd.fieldnames})')
        rows = []
        for i, r in enumerate(rd):
            flex = [s.strip() for s in (r['flex'] or '').split(' / ') if s.strip()]
            cpt = (r['captain'] or '').strip()
            if not cpt or len(flex) != 5 or len({norm_name(x) for x in [cpt] + flex}) != 6:
                raise CandidateInvalid(f'{p.name} row {i + 2}: captain + 5 distinct flex required ({cpt!r}, {flex})')
            rows.append((cpt, flex, r))
    if not rows:
        raise CandidateInvalid(f'{p.name} holds no candidates')
    return rows


def optimal_frequency(ws: WorldSet, candidates_path, min_worlds: int = MIN_CONDITIONING_WORLDS) -> dict:
    """Per player, the share of worlds in which he is CPT / FLEX of the best candidate in the supplied pool."""
    import numpy as np
    if ws.layout != 'SHOWDOWN':
        raise ShowdownOnly(f'optimal-lineup frequency is defined for a one-game Showdown worldset, not {ws.layout}')
    if ws.draws is None:
        raise DrawsNotLoaded('optimal-lineup frequency scores DK points; load the DRAWS.json')
    rows = read_candidates(candidates_path)
    dkeys = list(ws.draws)
    cache, players = {}, []

    def rk(name):
        if name not in cache:
            cache[name] = ws.dk_key(name)
        return cache[name]
    resolved = [(rk(c), [rk(f) for f in fl]) for c, fl, _ in rows]
    players = sorted({k for c, fl in resolved for k in [c] + fl})
    pidx = {k: i for i, k in enumerate(players)}
    W = np.zeros((len(resolved), len(players)))
    for j, (c, fl) in enumerate(resolved):
        W[j, pidx[c]] = CPT_MULTIPLIER
        for f in fl:
            W[j, pidx[f]] += 1.0
    D = np.stack([ws.draws[k] for k in players])                       # [player, world]
    score = W @ D                                                       # [candidate, world]
    best = score.max(axis=0)
    winners = np.isclose(score, best[None, :], rtol=0, atol=1e-9)       # exact ties (float noise only)
    n_tied = winners.sum(axis=0)
    credit = winners / n_tied[None, :]                                  # ties split equally
    cand_worlds = credit.sum(axis=1)
    n = ws.n_worlds
    cpt_w = np.zeros(len(players))
    flex_w = np.zeros(len(players))
    for j, (c, fl) in enumerate(resolved):
        if cand_worlds[j] == 0:
            continue
        cpt_w[pidx[c]] += cand_worlds[j]
        for f in fl:
            flex_w[pidx[f]] += cand_worlds[j]
    se = lambda p: round(math.sqrt(p * (1 - p) / n), 6)                 # noqa: E731
    per = {k: {'cpt_worlds': round(float(cpt_w[i]), 3), 'cpt_share': round(float(cpt_w[i] / n), 6),
               'cpt_se': se(float(cpt_w[i] / n)),
               'flex_worlds': round(float(flex_w[i]), 3), 'flex_share': round(float(flex_w[i] / n), 6),
               'flex_se': se(float(flex_w[i] / n)),
               'any_share': round(float((cpt_w[i] + flex_w[i]) / n), 6)}
           for k, i in pidx.items()}
    per = dict(sorted(per.items(), key=lambda kv: (-kv[1]['any_share'], kv[0])))
    absent = sorted(k for k in dkeys if k not in pidx)
    cross = None
    if 'n_worlds_optimal' in rows[0][2]:
        try:
            stated = np.array([float(r['n_worlds_optimal']) for _, _, r in rows])
            cross = {'column': 'n_worlds_optimal', 'candidates_equal': int(np.isclose(stated, cand_worlds).sum()),
                     'of': len(rows), 'stated_total': float(stated.sum()), 'ours_total': float(cand_worlds.sum()),
                     'MEANING': 'agreement with the CSV\'s own per-candidate count; the CSV may count optimality '
                                'over a different pool, so disagreement is reported, not repaired'}
        except (TypeError, ValueError):
            cross = {'column': 'n_worlds_optimal', 'state': 'UNREADABLE'}
    top = np.argsort(-cand_worlds)[:10]
    return {'query': f'OPTIMAL_FREQUENCY(pool={pathlib.Path(candidates_path).name}, score=1.5*CPT+sum(FLEX))',
            'kind': 'OPTIMAL_LINEUP_FREQUENCY', 'status': 'OK' if n >= min_worlds else 'INSUFFICIENT_WORLDS',
            'n_worlds': n, 'denominator': n, 'n_candidates': len(rows), 'model_label': ws.label,
            'candidates_path': str(pathlib.Path(candidates_path).resolve()),
            'candidates_sha256': _sha(pathlib.Path(candidates_path)),
            'worlds_with_ties': int((n_tied > 1).sum()), 'tie_rule': 'exact ties split credit equally',
            'distinct_optimal_candidates': int((cand_worlds > 0).sum()),
            'se_method': 'binomial sqrt(p(1-p)/n_worlds) per share',
            'SCOPE': 'optimal AMONG THE SUPPLIED POOL only; a player absent from the pool has share 0 by construction',
            'players_in_draws_not_in_pool': absent,
            'per_player': per if n >= min_worlds else None,
            'top_candidates': [{'captain': resolved[j][0], 'flex': resolved[j][1],
                                'worlds': round(float(cand_worlds[j]), 3)} for j in top if cand_worlds[j] > 0],
            'cross_check_vs_csv': cross, 'provenance': ws.provenance}


# --------------------------------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument('worlds')
    ap.add_argument('--draws')
    ap.add_argument('--label', choices=LABELS)
    ap.add_argument('--query', action='append', default=[])
    ap.add_argument('--optimal', help='Showdown candidate CSV for optimal-lineup frequency')
    ap.add_argument('--side-by-side', nargs=2, action='append', default=[], metavar=('WORLDS', 'DRAWS'),
                    help='also answer every query on these worlds (e.g. the SHADOW arm)')
    ap.add_argument('--min-worlds', type=int, default=MIN_CONDITIONING_WORLDS)
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    try:
        sets = [load(a.worlds, a.draws, a.label)] + [load(w, d) for w, d in a.side_by_side]
        if a.out:
            outp = pathlib.Path(a.out).resolve()
            inputs = {pathlib.Path(p).resolve() for p in [a.worlds, a.draws, a.optimal] + sum(a.side_by_side, [])
                      if p}
            if outp in inputs:
                raise OutputRefused(f'--out {outp} is an input file; this tool never overwrites its inputs')
        if not a.query and not a.optimal:
            raise QueryParseError('nothing asked: give --query and/or --optimal')
        answers = [ask_side_by_side(sets, t, a.min_worlds) for t in a.query]
        if a.optimal:
            answers.append([optimal_frequency(ws, a.optimal, a.min_worlds) for ws in sets])
    except SimQueryError as e:
        print(f'REFUSED[{e.code}] {e.detail}', file=sys.stderr)
        if e.evidence:
            print(json.dumps(e.evidence, default=str)[:2000], file=sys.stderr)
        return 2
    for group in answers:
        for r in group:
            v = r.get('value')
            if r.get('kind') == 'OPTIMAL_LINEUP_FREQUENCY':
                v = {k: (x['cpt_share'], x['flex_share']) for k, x in list((r['per_player'] or {}).items())[:8]}
            print(f"[{r.get('model_label')}] {r.get('status')} {r.get('query')} = "
                  f"{json.dumps(v, default=str)} (se {r.get('se')}, {r.get('numerator', r.get('n_matching'))}/"
                  f"{r.get('denominator')}){(' ' + r['code']) if r.get('code') else ''}")
    refused = [r for g in answers for r in g if r.get('status') == 'REFUSED']
    for r in refused:
        print(f"REFUSED[{r['code']}] [{r['model_label']}] {r['detail']}", file=sys.stderr)
    if a.out:
        pathlib.Path(a.out).write_text(json.dumps({'spec_version': SPEC_VERSION, 'answers': answers},
                                                  indent=1, default=str))
    return 2 if refused else 0          # a refusal is never an exit-0 success


if __name__ == '__main__':
    sys.exit(main())
