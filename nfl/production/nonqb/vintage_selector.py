"""One cutoff-aware selector per perishable source family. WS-C.

THE DEFECT THIS EXISTS FOR, STATED ONCE.

A chronology GATE and the FEED THE MODEL EATS were two different selectors and
only the gate had a clock. `readiness.team_readiness` cut its observation set
at `min(written_at, kickoff)`; `readiness.latest_injuries_rows`, which is what
`layers.py:145` actually hands to the appearance mechanism, applied no bound at
all and took the newest capture on disk. Measured at HEAD 837d52f: the consumed
capture was retrieved at or after kickoff for 28 of 32 week-1 teams. The gate
and the feed were answering the same question from two different information
sets, and the one that reached the model was the unbounded one.

The generalisation is the rule this module enforces: THERE IS ONE SELECTOR PER
FAMILY, IT TAKES A CLOCK, AND THERE IS NO WAY TO CALL IT WITHOUT ONE.

WHAT A SELECTION MUST CARRY

`roster_status.status_map` is the reference design and the only family WS12
scored PROVEN_CLEAN, because it checks the clock AND the content and names its
refusal. Every selection here returns the same seven things, so no consumer has
to reconstruct them:

    source identity        family + manifest `source` + blob path + capture_id
    retrieved_at           when WE got the bytes
    published_at           when the SOURCE says they became true, where known
    content_sha256         what the bytes were
    chronology             the verdict, from a closed vocabulary
    fallback_reason        why this is not the preferred vintage, if it is not
    evidence_ceiling       what this metadata cannot answer, when it cannot

FORBIDDEN, AND ENFORCED BY THE SORT KEY

  * "the latest file on disk"
  * filesystem mtime as information time
  * glob order, filename order, file size or row count as a tiebreak

Selection is `max(retrieved_at, content_sha256)` over the candidates that are
lawful at the cut. The sha256 tiebreak is not cosmetic: two captures can share
a retrieved_at to the microsecond, and without a content-derived tiebreak the
answer would fall back to whatever order the manifest happened to be read in.

NO CLOCK IS NOT ANY CLOCK. `resolve_as_of` raises `VintageClockUnresolved`
rather than defaulting to "now" or to "no bound". A missing clock is a wiring
defect in the caller, and it is loud here so it cannot be quiet downstream.
"""
from __future__ import annotations

import contextlib
import contextvars
import dataclasses
import datetime as dt
import gzip
import hashlib
import json
import pathlib
import sys
from typing import Optional

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import (Cause,               # noqa: E402
                                               Outcome, State)

SPEC_VERSION = 'vintage-selector-1'

MANIFEST = _REPO / 'nfl' / 'vintage_manifest.jsonl'
VINTAGE = _REPO / 'nfl' / 'vintage'
RAW = _REPO / 'nfl_vintage' / 'raw'


class VintageClockUnresolved(RuntimeError):
    """No `as_of` was supplied and none could be resolved from the context.

    Named and raised rather than defaulted, because every silent default here
    is a leak: "now" admits post-kickoff captures and "no bound" admits every
    capture ever taken.
    """


class NoLawfulVintage(RuntimeError):
    """A clock was resolved and no capture predates it.

    Distinct from VintageClockUnresolved on purpose. The first is a wiring
    defect; this one is a true statement about the world at that cutoff, and
    the correct response to it is to refuse the forecast, never to widen the
    cut.
    """


# ------------------------------------------------------------------ clocks
_CLOCK: contextvars.ContextVar = contextvars.ContextVar(
    'nfl_vintage_clock', default=None)


def parse_ts(t) -> Optional[dt.datetime]:
    """ISO-8601 -> aware UTC datetime, or None. Never a string comparison.

    E4 in WS12: `roster_status.py:144` and `make_board.py:146` compared ISO
    timestamps as STRINGS, which is correct only while both sides carry the
    same `...Z` shape. `2026-09-10T16:00:00+00:00` sorts `'+'` below `'Z'`, so
    a caller supplying an offset-form cutoff mis-orders same-second
    comparisons. Everything in this module compares parsed instants.
    """
    if t is None or t == '':
        return None
    if isinstance(t, dt.datetime):
        return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
    try:
        d = dt.datetime.fromisoformat(str(t).replace('Z', '+00:00'))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def as_of_cut(kickoff_utc=None, written_at=None) -> Optional[dt.datetime]:
    """THE CONSUMED-CLOCK CONTRACT: `retrieved_at <= written_at < kickoff`.

    Canonical. `readiness.as_of_cut` delegates here so the gate and the feed
    cannot drift apart again by one of them growing a second copy of the rule.

    Returns None only when the caller supplied neither clock. That is the
    "what is true now" reading and it is NOT a licence to select: every
    selector in this module refuses a None cut.
    """
    w = parse_ts(written_at)
    k = parse_ts(kickoff_utc)
    if w is None and k is None:
        return None
    if w is None:
        # Strictly before kickoff. One microsecond is the resolution the
        # timestamps carry, so it expresses `<` without inventing a tolerance.
        return k - dt.timedelta(microseconds=1)
    if k is None:
        return w
    return min(w, k - dt.timedelta(microseconds=1))


@dataclasses.dataclass(frozen=True)
class Clock:
    """The cutoff a run consumes, and where it came from."""
    as_of: dt.datetime
    written_at: Optional[str] = None
    kickoff_utc: Optional[str] = None
    origin: str = 'unspecified'

    def record(self) -> dict:
        return {'as_of': self.as_of.isoformat(), 'written_at': self.written_at,
                'kickoff_utc': self.kickoff_utc, 'origin': self.origin}


@contextlib.contextmanager
def clock(written_at=None, kickoff_utc=None, origin='unspecified',
          as_of=None):
    """Declare the consumed clock for everything selected inside this block.

    WHY AN AMBIENT CLOCK AND NOT A PARAMETER. The leaking call site is
    `nfl/production/nonqb/layers.py:145`, and `layers.py` is hashed by Q9's
    frozen candidate identity `481f005f682cd721`. It cannot be edited, so the
    clock cannot be threaded through it as an argument. The C1 repair met the
    same wall and placed the corrected behaviour UPSTREAM, in
    `football_engine.py`; this is the same move. The upstream caller declares
    the cut once, and the selector below the frozen module honours it.

    It is a `contextvars.ContextVar`, so it is per-thread and per-task rather
    than process-global, and it is restored on exit even if the block raises.
    A nested block replaces it for its own extent only.

    The default OUTSIDE any such block is not "now" and not "no bound": it is
    a refusal. See `resolve_as_of`.
    """
    cut = parse_ts(as_of) if as_of is not None else as_of_cut(
        kickoff_utc, written_at)
    if cut is None:
        raise VintageClockUnresolved(
            f'VINTAGE_CLOCK_UNRESOLVED: clock(origin={origin!r}) was given '
            f'neither written_at nor kickoff_utc nor as_of, so there is no '
            f'cut to declare. An undeclared cut is not an open cut.')
    tok = _CLOCK.set(Clock(as_of=cut, written_at=(str(written_at)
                                                  if written_at else None),
                           kickoff_utc=(str(kickoff_utc) if kickoff_utc
                                        else None), origin=origin))
    try:
        yield _CLOCK.get()
    finally:
        _CLOCK.reset(tok)


def current_clock() -> Optional[Clock]:
    """The declared clock for this thread/task, or None."""
    return _CLOCK.get()


_UNSET = object()
# Public alias. A caller that wants to say "I was given nothing" needs the
# same sentinel this module tests against; a private one of its own would be
# read as an explicit, unparseable as_of.
UNSET = _UNSET


def resolve_as_of(as_of=_UNSET, *, caller: str) -> dt.datetime:
    """Explicit argument, else the declared context, else a NAMED refusal.

    `as_of=None` passed explicitly is NOT "no cut" -- it is the same refusal.
    Letting None mean "unbounded" is precisely how `latest_injuries_rows`
    came to consume post-kickoff bytes.
    """
    if as_of is not _UNSET and as_of is not None:
        got = parse_ts(as_of)
        if got is None:
            raise VintageClockUnresolved(
                f'VINTAGE_CLOCK_UNPARSEABLE: {caller} was given as_of='
                f'{as_of!r}, which is not an ISO-8601 instant.')
        return got
    cur = _CLOCK.get()
    if cur is not None:
        return cur.as_of
    raise VintageClockUnresolved(
        f'VINTAGE_CLOCK_UNRESOLVED: {caller} was called with no as_of and no '
        f'declared vintage_selector.clock(...) context. Selecting without a '
        f'clock means taking the newest capture on disk, which is how a '
        f'post-kickoff injury report reached a pregame forecast for 28 of 32 '
        f'week-1 teams. Refusing rather than guessing a cutoff.')


# ---------------------------------------------------------------- families
# DECLARED, NOT DISCOVERED. A family is in scope only if its selection rule,
# its clock field and the ceiling on its metadata have been written down.
FAMILIES = {
    'injuries': {
        'manifest_source': 'injuries',
        'information_clock': 'retrieved_at',
        'publication_clock': 'effective_scope.valid_from',
        'publication_authority': 'DERIVED_DETERMINISTIC (HTTP Last-Modified)',
        'perishable': True,
        'serves': ['appearance: practice_progression, teammate_availability'],
        'declared_columns': ('season', 'week', 'team', 'gsis_id',
                             'report_status', 'practice_status'),
        'ceiling': ('The league\'s own filing instant is not recorded. '
                    '`valid_from` is the mirror file\'s HTTP Last-Modified, '
                    'which is an upper bound on publication and a lower bound '
                    'on nothing. Retrieval is never earlier than publication, '
                    'so `retrieved_at <= cut` still implies the bytes existed '
                    'by the cut -- the direction is conservative, and that is '
                    'all it is.'),
    },
    'depth_charts': {
        'manifest_source': 'depth_charts',
        'information_clock': 'retrieved_at',
        'row_clock': 'dt',
        'publication_clock': 'effective_scope.valid_from',
        'publication_authority': 'SOURCE_PROVIDED (HTTP Last-Modified)',
        'perishable': True,
        'serves': ['role_prior.assign_tiers (R6 tier fallback)',
                   'product board depth_chart column'],
        'ceiling': ('The vendor `dt` inside the rows is a real publication '
                    'clock and is preferred over retrieval for this family. '
                    'It is a DAILY stamp, so intra-day ordering is not '
                    'recoverable from it. AND THE SERIES IS MOSTLY NOT '
                    'DURABLE: WS-L measured 171 of 177 captured `dt` slices '
                    'persisted NOWHERE -- only 6 reduced blobs survive, one '
                    '`dt` each. So for most historical cutoffs there is no '
                    'stored chart to select, and the correct answer is this '
                    'ceiling rather than the nearest chart that does exist. '
                    'The reduction also DROPS `pos_slot`, which is the '
                    'vendor tiebreak within a `pos_abb`; see '
                    'depth_vintage.daily, RL-10.'),
        'declared_columns': ('dt', 'team', 'gsis_id', 'pos_abb', 'pos_rank'),
    },
    'weekly_rosters': {
        'manifest_source': 'weekly_rosters',
        'information_clock': 'retrieved_at',
        'publication_clock': 'effective_scope.valid_from',
        'publication_authority': 'DERIVED_DETERMINISTIC (HTTP Last-Modified)',
        'perishable': True,
        'serves': ['roster_status.status_map (raw)',
                   'board.roster_identity (reduced)'],
        'ceiling': ('The reduced vintage DROPS `status`, so the reduced blobs '
                    'cannot answer roster membership at all and the raw '
                    'retained files are the only source for it. A clock check '
                    'alone is insufficient for this family: after a team '
                    'plays, the vendor re-partitions ACT/INA, so '
                    '`roster_status` runs a CONTENT check as well. That pair '
                    'is the reference design for this module.'),
    },
    'schedules': {
        'manifest_source': 'schedules',
        'information_clock': 'retrieved_at',
        'publication_clock': 'effective_scope.valid_from',
        'publication_authority': 'DERIVED_DETERMINISTIC (HTTP Last-Modified)',
        'perishable': True,
        'serves': ['coverage.load_week_plan (kickoff times)',
                   'team_volume_v1.coaches (coach_prior)'],
        'ceiling': ('WS12 scored this UNPROVABLE rather than leaking, and '
                    'this module does not upgrade that verdict. No leak has '
                    'been measured: the readers take only season, week, '
                    'game_type, gameday, gametime and team codes. What is '
                    'true is that the committed blob carries `result`, '
                    '`home_score`, `spread_line` and `total_line` in all 46 '
                    'columns, and that both existing selectors order by '
                    'filesystem mtime or by content-hash string, neither of '
                    'which is a clock. The guard today is the absence of a '
                    'reader, not a bound on the selector.'),
    },
}

# E3 in WS12: for `official_inactives` and `official_injury_report` the
# "source-provided exact timestamp" is the HTTP `Date` response header -- the
# instant the origin answered OUR request -- with a measured lag of exactly
# 0.000 hours in 188 of 188 rows. It is retrieval time wearing publication
# authority. Recorded here so a consumer of `published_at` cannot read it as
# the league's clock.
_RETRIEVAL_TIME_AUTHORITIES = {'official_inactives', 'official_injury_report'}


# ------------------------------------------------------------- the record
@dataclasses.dataclass(frozen=True)
class Vintage:
    """One candidate capture, with everything a consumer needs to audit it."""
    family: str
    source: str
    blob: Optional[str]
    capture_id: Optional[str]
    retrieved_at: Optional[str]
    published_at: Optional[str]
    published_authority: Optional[str]
    content_sha256: Optional[str]
    chronology: str
    as_of: Optional[str] = None
    fallback_reason: Optional[str] = None
    evidence_ceiling: Optional[str] = None
    selection_rule: str = 'max(retrieved_at, content_sha256) over lawful'
    extra: dict = dataclasses.field(default_factory=dict)

    @property
    def sort_key(self):
        return (self.retrieved_at or '', self.content_sha256 or '')

    def path(self) -> Optional[pathlib.Path]:
        return (_REPO / self.blob) if self.blob else None

    def record(self) -> dict:
        d = dataclasses.asdict(self)
        d['spec_version'] = SPEC_VERSION
        return d


# The closed chronology vocabulary. A verdict outside it is a bug, not a
# nuance.
LAWFUL = 'RETRIEVED_AT_OR_BEFORE_CUT'
REJECT_LATE = 'RETRIEVED_AFTER_CUT'
REJECT_NO_CLOCK = 'NO_RETRIEVAL_CLOCK_RECORDED'
REJECT_NO_BLOB = 'BLOB_ABSENT_ON_DISK'
CHRONOLOGY = (LAWFUL, REJECT_LATE, REJECT_NO_CLOCK, REJECT_NO_BLOB)


def _manifest_rows(manifest_lines=None):
    if manifest_lines is not None:
        return list(manifest_lines)
    if not MANIFEST.exists():
        return []
    return MANIFEST.read_text().splitlines()


def candidates(family: str, as_of=_UNSET, manifest_lines=None,
               require_blob: bool = True):
    """Every PASS capture of `family`, judged against the cut. Newest first.

    Returns (lawful, rejected). BOTH lists are returned: a selector that
    discards what it rejected cannot tell you how close the refusal was, and
    "there was nothing" then reads the same as "there were six and all of them
    were late".

    `manifest_lines` exists so a test can permute the manifest's READ ORDER and
    assert the selection does not move. Nothing in this function may depend on
    that order.
    """
    if family not in FAMILIES:
        raise KeyError(f'VINTAGE_FAMILY_UNDECLARED: {family!r} is not one of '
                       f'{sorted(FAMILIES)}. A family is in scope only when '
                       f'its clock and its ceiling have been written down.')
    spec = FAMILIES[family]
    cut = resolve_as_of(as_of, caller=f'candidates({family!r})')
    src = spec['manifest_source']
    lawful, rejected = [], []
    for line in _manifest_rows(manifest_lines):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get('source') != src or r.get('state') != 'PASS':
            continue
        v = r.get('value') or {}
        p = v.get('provenance') or {}
        scope = v.get('effective_scope') or {}
        ts = v.get('retrieved_at') or p.get('retrieved_at')
        auth = scope.get('authority')
        if src in _RETRIEVAL_TIME_AUTHORITIES:
            auth = f'{auth} [RECORDED AUTHORITY IS RETRIEVAL TIME -- see E3]'
        vt = Vintage(
            family=family, source=src, blob=v.get('blob'),
            capture_id=r.get('capture_id'), retrieved_at=ts,
            published_at=scope.get('valid_from'), published_authority=auth,
            content_sha256=v.get('sha256'),
            chronology=LAWFUL, as_of=cut.isoformat(),
            evidence_ceiling=spec['ceiling'],
            extra={'n_data_rows': v.get('n_data_rows'),
                   'source_timestamp_header': v.get(
                       'source_timestamp_header')})
        got = parse_ts(ts)
        if got is None:
            rejected.append(dataclasses.replace(
                vt, chronology=REJECT_NO_CLOCK,
                fallback_reason='the manifest row carries no retrieved_at, so '
                                'it cannot be placed against any cutoff'))
            continue
        if require_blob and (not vt.blob or not vt.path().exists()):
            rejected.append(dataclasses.replace(
                vt, chronology=REJECT_NO_BLOB,
                fallback_reason=f'the manifest names {vt.blob!r} and it is '
                                f'not on disk'))
            continue
        if got > cut:
            rejected.append(dataclasses.replace(
                vt, chronology=REJECT_LATE,
                fallback_reason=f'retrieved {ts}, after the cut '
                                f'{cut.isoformat()}'))
            continue
        lawful.append(vt)
    # ONE ROW PER DISTINCT CONTENT, AT ITS EARLIEST OBSERVATION.
    #
    # The capture workflow re-fetches on a schedule and records a PASS row
    # every time, `content_unchanged: true` when the bytes did not move. Those
    # rows are the same vintage seen again, not new vintages, and keeping all
    # of them does two wrong things: it inflates every count, and -- worse --
    # taking the LATEST retrieved_at for a content hash would exclude those
    # bytes from a cut that falls between the first sighting and a later
    # re-fetch, even though they demonstrably existed at the first. This is
    # `information_set.first_observation`'s rule and the reason is the same:
    # the earliest observation of exact content is the tightest defensible
    # bound on when it became available, and it can only ever be conservative.
    by_content = {}
    for v in lawful:
        k = v.content_sha256 or v.blob
        cur = by_content.get(k)
        if cur is None or (v.retrieved_at or '') < (cur.retrieved_at or ''):
            by_content[k] = v
    n_recaptures = len(lawful) - len(by_content)
    lawful = list(by_content.values())
    # THE ONLY ORDERING IN THIS MODULE. Never mtime, never glob order, never
    # file size, never row count, never manifest position.
    lawful.sort(key=lambda x: x.sort_key, reverse=True)
    rejected.sort(key=lambda x: x.sort_key, reverse=True)
    if lawful:
        lawful[0] = dataclasses.replace(
            lawful[0], extra=dict(lawful[0].extra,
                                  n_recaptures_collapsed=n_recaptures))
    return lawful, rejected


def select(family: str, as_of=_UNSET, manifest_lines=None,
           require_columns=None) -> Outcome:
    """The single lawful vintage for `family` at the cut, or a named refusal.

    PASS carries the `Vintage` as the value and its full record as evidence.
    BLOCKED[VINTAGE_NO_LAWFUL_CAPTURE] carries the evidence ceiling and every
    rejected candidate with the reason it was rejected, so the refusal is
    readable without re-running anything.
    """
    cut = resolve_as_of(as_of, caller=f'select({family!r})')
    lawful, rejected = candidates(family, as_of=cut,
                                  manifest_lines=manifest_lines)
    if not lawful:
        return Outcome.blocked(
            'VINTAGE_NO_LAWFUL_CAPTURE',
            f'no {family} capture was retrieved at or before '
            f'{cut.isoformat()}. {len(rejected)} capture(s) exist and every '
            f'one of them is later, unclocked or missing. A later capture is '
            f'not evidence about an earlier cutoff, and widening the cut to '
            f'reach one would be the defect this selector exists to prevent.',
            cause=Cause.DATA, spec_version=SPEC_VERSION, family=family,
            as_of=cut.isoformat(), n_rejected=len(rejected),
            evidence_ceiling=FAMILIES[family]['ceiling'],
            rejected=[r.record() for r in rejected[:12]])
    best = lawful[0]
    if require_columns is not None:
        cc = column_check(best, require_columns)
        if cc.state is State.FAIL:
            return cc
    return Outcome.ok(
        'VINTAGE_SELECTED', value=best, spec_version=SPEC_VERSION,
        family=family, as_of=cut.isoformat(), vintage=best.record(),
        n_lawful=len(lawful), n_rejected=len(rejected),
        n_rejected_as_later=sum(1 for r in rejected
                                if r.chronology == REJECT_LATE),
        selection_rule=best.selection_rule,
        forbidden_inputs=('filesystem mtime', 'glob order', 'filename order',
                          'file size', 'row count'))


def lawful_paths(family: str, as_of=_UNSET, manifest_lines=None):
    """[(retrieved_at, Path)] newest-first, for families read as a series.

    `injuries` is consumed this way: the feed is a whole-season file that is
    NOT monotone (measured week 1 2026: the 2026-09-11 capture carries 32 teams
    and 167 rows, the 2026-09-13T12:47 capture 20 teams and 48), so a team's
    latest filed block may sit in an older capture than the newest one. A
    consumer that needs a per-team block walks this list newest-first; a
    consumer that needs one file takes `select`.
    """
    lawful, _ = candidates(family, as_of=as_of, manifest_lines=manifest_lines)
    return [(v.retrieved_at, v.path()) for v in lawful]


def composite_hash(parts) -> str:
    """A content hash for a vintage composed from more than one capture.

    A composed selection still has to answer "what were the bytes". Hashing the
    sorted (key, sha256) pairs gives a stable identity for the composition that
    changes if any contributing capture changes.
    """
    h = hashlib.sha256()
    for k, sha in sorted(parts):
        h.update(f'{k}\x00{sha}\x00'.encode())
    return h.hexdigest()


def raw_candidates(family: str, as_of=_UNSET, raw_dir=None):
    """Retained RAW files for a family, joined to the manifest by content hash.

    `roster_status` needs `status`, which the vintage reduction drops, so it
    reads `nfl_vintage/raw/`. The raw files carry no metadata of their own --
    the filename holds the first 16 hex of the content hash and nothing else --
    so their clock comes from the manifest row for that same hash. Selection is
    therefore by observation time, exactly as for a reduced blob, and never by
    the filename or the file's mtime.
    """
    if family not in FAMILIES:
        raise KeyError(f'VINTAGE_FAMILY_UNDECLARED: {family!r}')
    cut = resolve_as_of(as_of, caller=f'raw_candidates({family!r})')
    src = FAMILIES[family]['manifest_source']
    from nfl.research.shadow import information_set as IS
    try:
        first = IS.first_observation()
    except Exception as e:                                    # noqa: BLE001
        raise NoLawfulVintage(
            f'VINTAGE_OBSERVATIONS_UNAVAILABLE: the information set could not '
            f'be built, so no raw file can be placed in time: {e}') from e
    by_sha = {sha: o for (s, sha), o in first.items() if s == src}
    root = pathlib.Path(raw_dir) if raw_dir else RAW
    lawful, rejected = [], []
    for f in sorted(root.glob(f'{src}.*.csv')):
        stem = f.name.split('.')[1]
        hit = next(((sha, o) for sha, o in sorted(by_sha.items())
                    if sha.startswith(stem)), None)
        if hit is None:
            rejected.append(Vintage(
                family=family, source=src, blob=str(f), capture_id=None,
                retrieved_at=None, published_at=None, published_authority=None,
                content_sha256=None, chronology=REJECT_NO_CLOCK,
                as_of=cut.isoformat(),
                fallback_reason=f'{f.name} matches no PASS manifest row, so '
                                f'nothing places it in time',
                evidence_ceiling=FAMILIES[family]['ceiling']))
            continue
        sha, o = hit
        at = o['observed_at']
        vt = Vintage(
            family=family, source=src, blob=str(f), capture_id=o['capture_id'],
            retrieved_at=at.isoformat().replace('+00:00', 'Z'),
            published_at=None,
            published_authority=f'observation basis: {o["observed_basis"]}',
            content_sha256=sha, chronology=LAWFUL, as_of=cut.isoformat(),
            evidence_ceiling=FAMILIES[family]['ceiling'],
            extra={'observed_basis': o['observed_basis'], 'raw': True})
        if at > cut:
            rejected.append(dataclasses.replace(
                vt, chronology=REJECT_LATE,
                fallback_reason=f'observed {vt.retrieved_at}, after the cut '
                                f'{cut.isoformat()}'))
            continue
        lawful.append(vt)
    lawful.sort(key=lambda x: x.sort_key, reverse=True)
    rejected.sort(key=lambda x: x.sort_key, reverse=True)
    return lawful, rejected


def blob_columns(vintage: 'Vintage'):
    """The column names actually present in the selected bytes, or None."""
    path = vintage.path()
    if path is None or not path.exists():
        return None
    try:
        opener = (gzip.open(path, 'rt') if str(path).endswith('.gz')
                  else open(path, 'rt'))
        with opener as fh:
            head = fh.readline()
    except OSError:
        return None
    return [c.strip() for c in head.strip().split(',') if c.strip()]


def column_check(vintage: 'Vintage', required=None) -> Outcome:
    """A LAWFUL VINTAGE WHOSE BYTES LACK A DECLARED COLUMN HAS NOT SUCCEEDED.

    Two live instances of this, both found by WS-L and both the same shape as
    the leak this module exists for -- a read that returned nothing, used as a
    value:

      RL-10  `depth_vintage._daily_rows` read `int(r.get('pos_slot') or 0)`
             against a reduced blob with no `pos_slot` column at all, so the
             tiebreak silently evaluated to 0 on every row of every run.
      RL-11  `ingest_inactives.consumed_slice` declares `status` and reads the
             reduced blob, which does not carry it: 181 keep-strings, 181 of
             them ending `|None`.

    Neither raised, neither was reported, and both are invisible from the
    selection alone -- which is why the check belongs at selection.
    """
    req = tuple(required if required is not None
                else FAMILIES[vintage.family].get('declared_columns') or ())
    if not req:
        return Outcome.not_applicable(
            'VINTAGE_NO_DECLARED_COLUMNS',
            f'{vintage.family} declares no required columns, so there is '
            f'nothing to check. This is a gap in the declaration, not a pass.',
            family=vintage.family)
    got = blob_columns(vintage)
    if got is None:
        return Outcome.blocked(
            'VINTAGE_BLOB_UNREADABLE',
            f'the selected {vintage.family} blob {vintage.blob!r} could not '
            f'be opened to read its header', cause=Cause.DATA)
    missing = [c for c in req if c not in got]
    if missing:
        return Outcome.fail(
            'VINTAGE_DECLARED_COLUMN_ABSENT',
            f'the {vintage.family} vintage selected for '
            f'{vintage.as_of} is lawful on the clock and does not carry '
            f'{missing}. A consumer reading those names gets None on every '
            f'row, which is indistinguishable from a real absence of value. '
            f'A lawful vintage with a missing declared column is not a '
            f'successful selection.',
            blob=vintage.blob, missing=list(missing), present=got,
            declared=list(req))
    return Outcome.ok('VINTAGE_COLUMNS_OK', value=got, declared=list(req),
                      n_columns=len(got))


def describe(family: str) -> dict:
    """The declared contract for one family. Read, never recomputed."""
    spec = dict(FAMILIES[family])
    spec.update(family=family, spec_version=SPEC_VERSION,
                chronology_vocabulary=list(CHRONOLOGY),
                selection_rule='max(retrieved_at, content_sha256) over the '
                               'captures lawful at the cut',
                forbidden=('filesystem mtime', 'glob order', 'filename order',
                           'file size', 'row count', 'newest file on disk'))
    return spec


def contract() -> dict:
    """Every declared family, for an artifact that has to record the rule."""
    return {'artifact': 'VINTAGE_SELECTOR_CONTRACT',
            'spec_version': SPEC_VERSION,
            'families': {f: describe(f) for f in sorted(FAMILIES)}}
