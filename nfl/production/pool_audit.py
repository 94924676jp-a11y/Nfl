"""Who was CONSIDERED for a game, and what actually decided it. L3.

WHAT THIS IS FOR

`POSITION ALONE DOES NOT ESTABLISH ELIGIBILITY.` Owner instruction, and it is
aimed at a measured defect: the forecast pool is built from a roster vintage
whose reduced form carries `season, week, team, gsis_id, position` and NOTHING
ELSE, so at the moment the pool is constructed there is no eligibility fact in
the frame at all. WS21 measured the consequence -- 29 non-ACT quarterbacks
(15 practice squad, 7 released, 5 reserve, 2 retired) entered sealed QB rooms
across the 14 week-1 boards, holding the equivalent of 1.82 whole teams'
dropbacks.

This module does not repair that. It REPORTS it, per player, with the vintage
each column came from, so the question "was this player eligible" has a written
answer instead of an inference.

THE THREE RULES IT IS BUILT ON

1. ABSENCE IS NOT A STATE. A player missing from the injury feed is not a
   player with no injury; a club missing from the inactives page is not a club
   with nobody out. Every such cell is `UNRESOLVED` and names what would
   settle it. Nothing here promotes anyone to `GAME_ACTIVE`: no source we hold
   establishes that, and `inactives.GAME_ACTIVE` is deliberately never emitted.

2. NO LATEST-ON-DISK, EVER. Every input is chosen through
   `vintage_selector` under a declared clock. Filesystem mtime, glob order,
   filename order, file size and row count are all forbidden inputs, and the
   selector says so in its own `forbidden_inputs` record.

3. AN EMPTY RESULT IS AN ERROR. Every stage asserts its output is non-empty
   and schema-correct before returning, and raises a NAMED Outcome otherwise.

WHAT IT DELIBERATELY DOES NOT DO

It repairs nothing, reweights nobody, and hand-fixes no individual player. A
wrong pool membership is reported as the MECHANISM that produced it.
"""
from __future__ import annotations

import csv
import datetime as dt
import gzip
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from sportsplatform.governance.outcome import Cause, Outcome, State  # noqa: E402
from nfl.production.nonqb import vintage_selector as VS              # noqa: E402
from nfl.production.nonqb import depth_vintage as DV                 # noqa: E402
from nfl.production.nonqb import readiness as RD                     # noqa: E402
from nfl.production.nonqb import inactives as IN                     # noqa: E402

SPEC_VERSION = 'pool-audit-1'

# ---------------------------------------------------------------- vocabulary
# Roster-status codes, taken from `roster_status.EXCLUDED` rather than
# restated, so the two cannot drift. The meanings are the nflverse codes
# observed in the captures; anything outside this table is UNDECODED and is
# reported as such rather than guessed into a category.
ACTIVE = 'ACT'
PRACTICE_SQUAD = {'DEV': 'practice squad / developmental'}
RESERVE_LIST = {'RES': 'reserve or injured reserve',
                'EXE': 'exempt list'}
RELEASED = {'CUT': 'released'}
RETIRED = {'RET': 'retired'}
# INA is a GAMEDAY OUTCOME and its presence proves the capture is post-kickoff
# for that club. It is never a pregame category.
POSTHOC = {'INA': 'inactive for a game already played -- a gameday outcome'}

# Eligibility vocabulary. Imported names, not new ones: `inactives.py:74-78`
# already owns this and two vocabularies would be one too many.
ROSTER_ACTIVE = IN.ROSTER_ACTIVE
OFFICIAL_INACTIVE = IN.OFFICIAL_INACTIVE
UNKNOWN = IN.UNKNOWN
ROSTER_EXCLUDED = 'ROSTER_EXCLUDED'
UNRESOLVED = 'UNRESOLVED'
# GAME_ACTIVE is defined in `inactives` and is DELIBERATELY NOT EMITTED HERE.
# Dressing tonight is established by the official inactive list and by nothing
# else, and absence from a list that was never published is not evidence.

# The position strings the engine compares against, imported so a rename in the
# engine cannot leave this audit describing a pool that no longer exists.
try:
    from nfl.production.nonqb.football_engine import (  # noqa: E402
        RECEIVING_POS, CARRY_POS)
except Exception:                                            # noqa: BLE001
    RECEIVING_POS, CARRY_POS = ('WR', 'TE', 'RB'), ('RB',)

QB_POS = 'QB'

# What a roster row must carry to survive `run_forecast`'s non-QB frame check
# (`run_forecast.py:651`), and `identity_resolution` (`:450`).
FRAME_FIELDS = ('gsis_id', 'position', 'team')


class PoolAuditRefused(RuntimeError):
    """Raised only where an Outcome cannot be returned. Always named."""


def _iso(x):
    return None if x is None else str(x)


def _open(path):
    """A capture blob, gzipped or not. The suffix decides, never a guess."""
    path = pathlib.Path(path)
    return (gzip.open(path, 'rt') if path.suffix == '.gz'
            else open(path, 'rt'))


def _manifest_pass_rows(source):
    for line in VS.MANIFEST.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get('source') == source and r.get('state') == 'PASS':
            yield r.get('value') or {}


def raw_counterpart(vintage, as_of):
    """The FULL-COLUMN bytes of the SAME capture as `vintage`, or a split.

    THIS IS THE DEFECT THIS FUNCTION EXISTS FOR, AND IT WENT LIVE TODAY.

    `roster_status._raw_rosters()` and `vintage_selector.raw_candidates()` both
    resolve full-column bytes by globbing `nfl_vintage/raw/<source>.*.csv` --
    an UNCOMPRESSED file, in a directory `capture_vintage._persist` labels
    `full_bytes_ephemeral_at`. The retention repair now writes the full bytes
    as `nfl/vintage/<source>.<sha>.raw.csv.gz` and records them on the
    manifest row as `raw_blob`, with `raw_blob_durable`. Neither glob matches
    that name, that directory or that suffix, so for a capture retained only
    the new way the raw counterpart is INVISIBLE and the globbers silently fall
    back to an older capture that still has an ephemeral file.

    Measured 2026-09-14: the reduced roster vintage lawful at 16:20Z is
    `bdab6ecee12d44a4` (retrieved 16:16Z) and the newest raw file
    `raw_candidates` can see is `cef497eaeddef07b` (observed 2026-09-13
    15:45Z) -- a 24.5-hour split between the roster the pool is built from and
    the roster the eligibility map is read from. WS21 recorded that split as
    P3d and LATENT. It is no longer latent.

    So this resolves the raw bytes BY CONTENT HASH from the manifest row of the
    same capture, and reports a split as a split rather than taking whatever
    the glob found.
    """
    src = VS.FAMILIES[vintage.family]['manifest_source']
    for v in _manifest_pass_rows(src):
        if v.get('sha256') != vintage.content_sha256:
            continue
        rb = v.get('raw_blob')
        if rb and (_REPO / rb).exists():
            return {'path': str(_REPO / rb), 'blob': rb,
                    'content_sha256': v.get('raw_blob_content_sha256'),
                    'durable': bool(v.get('raw_blob_durable')),
                    'same_capture': True,
                    'basis': 'manifest raw_blob of the SAME capture',
                    'retrieved_at': vintage.retrieved_at}
    lawful, _rej = VS.raw_candidates(vintage.family, as_of=as_of)
    same = [x for x in lawful if x.content_sha256 == vintage.content_sha256]
    if same:
        return {'path': same[0].blob, 'blob': same[0].blob,
                'content_sha256': same[0].content_sha256, 'durable': False,
                'same_capture': True,
                'basis': 'ephemeral nfl_vintage/raw file of the SAME capture',
                'retrieved_at': same[0].retrieved_at}
    if lawful:
        return {'path': lawful[0].blob, 'blob': lawful[0].blob,
                'content_sha256': lawful[0].content_sha256, 'durable': False,
                'same_capture': False,
                'basis': 'DIFFERENT CAPTURE -- the only raw bytes the glob '
                         'can see',
                'retrieved_at': lawful[0].retrieved_at}
    return None


def _nonempty(rows, code, detail, **ev) -> None:
    """ZEROS AND EMPTIES ARE ERRORS. The whole point of the assertion.

    Every read in this module goes through here so that "the file had no rows
    for these teams" can never be returned as "these teams have no players".
    """
    if not rows:
        raise PoolAuditRefused(json.dumps(
            {'code': code, 'detail': detail, 'evidence': ev}))


# ------------------------------------------------------------------- inputs
def roster_rows(season, week, teams, as_of) -> Outcome:
    """The roster frame, from the RAW retained capture, with a column check.

    TWO VINTAGES, ONE CAPTURE, AND THE AUDIT SAYS SO. The pool the production
    path builds comes from the REDUCED blob (`make_board.py:149-157`); the only
    place `status` exists is the RAW retained file. This selects both, and
    refuses unless they are the same content hash -- because if they are not,
    the eligibility map describes a different roster from the pool, which is
    WS21's latent P3d and is invisible from either file alone.
    """
    red = VS.select('weekly_rosters', as_of=as_of)
    if red.state is not State.PASS:
        return red
    rv = red.value
    # THE COLUMN CHECK THE FAMILY CANNOT RUN FOR ITSELF.
    # `vintage_selector.FAMILIES['weekly_rosters']` declares NO
    # `declared_columns`, so `column_check` returns NOT_APPLICABLE for exactly
    # the family whose reduction is known to drop a needed column. The columns
    # are named HERE instead of left undeclared.
    cc = VS.column_check(rv, required=('season', 'week', 'team', 'gsis_id',
                                       'position', 'status', 'full_name'))
    reduced_missing = list(cc.evidence.get('missing') or []) \
        if cc.state is State.FAIL else []

    rc = raw_counterpart(rv, as_of)
    if rc is None:
        return Outcome.blocked(
            'POOL_AUDIT_NO_RAW_ROSTER',
            f'the reduced roster vintage is missing {reduced_missing} and no '
            f'full-column roster bytes are reachable at all at {as_of}. '
            f'Roster status cannot be read, so the eligibility half of this '
            f'audit has no input. This is the retention decision WS05 '
            f'recorded as E5, not a modelling gap.',
            cause=Cause.DATA, spec_version=SPEC_VERSION,
            reduced=rv.record())
    if not rc['same_capture']:
        return Outcome.blocked(
            'POOL_AUDIT_VINTAGE_SPLIT',
            f'the pool would be built from reduced {rv.content_sha256} '
            f'(retrieved {rv.retrieved_at}) while status would be read from '
            f'{rc["blob"]} ({rc["retrieved_at"]}). Two different rosters '
            f'cannot be audited as one. This is WS21 P3d, and the cause is '
            f'that the raw-bytes globbers look only in nfl_vintage/raw/ for '
            f'an uncompressed .csv, while the retained full bytes of this '
            f'capture are nfl/vintage/*.raw.csv.gz.',
            cause=Cause.DATA, spec_version=SPEC_VERSION,
            reduced=rv.record(), raw=rc)

    with _open(rc['path']) as fh:
        rows = [r for r in csv.DictReader(fh)
                if r.get('season') == str(season)
                and r.get('week') == str(week) and r.get('team') in teams]
    _nonempty(rows, 'POOL_AUDIT_ROSTER_EMPTY',
              f'{rc["blob"]} carries no {season} week {week} row for '
              f'{sorted(teams)}', blob=rc['blob'])
    missing_here = [c for c in ('status', 'full_name')
                    if c not in (rows[0] or {})]
    if missing_here:
        return Outcome.blocked(
            'POOL_AUDIT_ROSTER_STATUS_COLUMN_ABSENT',
            f'{rc["blob"]} is the full-column counterpart of the selected '
            f'roster vintage and it does not carry {missing_here}. A consumer '
            f'reading those names gets None on every row, which is '
            f'indistinguishable from a real absence of value.',
            cause=Cause.DATA, spec_version=SPEC_VERSION, blob=rc['blob'],
            missing=missing_here)
    # CONTENT GUARD, NOT ONLY A CLOCK GUARD. `roster_status` is the reference
    # design and the reason is measured: the vendor took ~12h to populate INA
    # after a kickoff, so a capture inside that window is post-game AND
    # INA-free. Both checks or neither.
    posthoc = sorted({(r.get('status') or '').strip().upper() for r in rows}
                     & set(POSTHOC))
    if posthoc:
        return Outcome.fail(
            'POOL_AUDIT_POSTHOC_ROSTER',
            f'{rc["blob"]} carries {posthoc} for {sorted(teams)}. That code '
            f'is assigned after a game is played, so this capture is not '
            f'pregame information for these clubs.',
            posthoc=posthoc, blob=rc['blob'],
            observed_at=rc['retrieved_at'])
    return Outcome.ok(
        'POOL_AUDIT_ROSTER_OK', value=rows, spec_version=SPEC_VERSION,
        n_rows=len(rows), reduced=rv.record(), raw=rc,
        reduced_missing_columns=reduced_missing,
        reduced_column_check=cc.code,
        pool_is_built_from='reduced blob (make_board.py:149-157)',
        status_is_read_from='raw retained file (roster_status.py RAW)')


def depth_rows(teams, as_of) -> Outcome:
    """The point-in-time depth listing, clocked by the vendor's own `dt`.

    A DEPTH RANK IS NOT AN ELIGIBILITY SIGNAL and this module never reads it as
    one: WS05 measured 232 reserve-list players and 25 post-hoc inactives
    holding depth ranks in a single capture. It is reported in its own column
    and it decides nothing here.
    """
    paths = [p for _, p in VS.lawful_paths('depth_charts', as_of=as_of)]
    if not paths:
        return Outcome.blocked(
            'POOL_AUDIT_NO_DEPTH_VINTAGE',
            f'no depth-chart capture is lawful at {as_of}', cause=Cause.DATA,
            spec_version=SPEC_VERSION)
    d = DV.captured(list(teams), _iso(as_of), blobs=paths)
    return d


def vendor_depth(teams, as_of) -> Outcome:
    """The vendor's OWN within-position rank and slot, from the raw chart.

    WHY BOTH THIS AND `depth_rows`. They are different quantities and the audit
    reports both rather than picking one.

      * `depth_vintage.captured()` -- what the appearance layer consumes --
        returns a TEAM-WIDE ordinal over skill players, 1..n, not the vendor's
        within-position `pos_rank`. Measured for DEN on the 2026-09-13 chart:
        TE1 Engram 1, RB1 Dobbins 2, WR1 Waddle 3, QB1 Nix 4.
      * Its cross-position ties -- four players all at `pos_rank` 1 -- fall
        through to `gsis_id`, because `pos_slot` is absent from every persisted
        REDUCED blob (`pos_slot_available: False`). An identifier is not a
        football fact, and RL-10 is why this is visible rather than silent.
      * The raw chart DOES carry `pos_slot`, and since the retention repair it
        is durable. The reduction still drops it.

    Reported, not repaired: re-ranking anybody is a model change.
    """
    sel = VS.select('depth_charts', as_of=as_of)
    if sel.state is not State.PASS:
        return sel
    rc = raw_counterpart(sel.value, as_of)
    if rc is None or not rc['same_capture']:
        return Outcome.blocked(
            'POOL_AUDIT_NO_RAW_DEPTH',
            f'no full-column depth chart of the selected capture '
            f'{sel.value.content_sha256} is reachable at {as_of}; the '
            f'vendor pos_rank/pos_slot columns are unavailable for it',
            cause=Cause.DATA, spec_version=SPEC_VERSION,
            reduced=sel.value.record(), raw=rc)
    with _open(rc['path']) as fh:
        rows = [r for r in csv.DictReader(fh) if r.get('team') in teams]
    _nonempty(rows, 'POOL_AUDIT_RAW_DEPTH_EMPTY',
              f'{rc["blob"]} carries no row for {sorted(teams)}',
              blob=rc['blob'])
    dts = sorted({r['dt'] for r in rows if r.get('dt')})
    _nonempty(dts, 'POOL_AUDIT_RAW_DEPTH_NO_DT',
              f'{rc["blob"]} carries no dt stamp', blob=rc['blob'])
    cutp = VS.parse_ts(as_of)
    usable = [d for d in dts if VS.parse_ts(d) is not None
              and VS.parse_ts(d) < cutp]
    if not usable:
        return Outcome.blocked(
            'POOL_AUDIT_RAW_DEPTH_NOT_POINT_IN_TIME',
            f'every dt slice in {rc["blob"]} is at or after {as_of}',
            cause=Cause.DATA, spec_version=SPEC_VERSION, dts=dts[-4:])
    chosen = usable[-1]
    # OFFENSIVE SKILL LISTINGS ONLY, AND THE REASON IS A DEFECT THIS MODULE
    # MADE ONCE. Taking the minimum `pos_rank` across ALL of a player's rows
    # reported Marvin Mims as PR1 and Tyler Badie as KR2 -- their punt- and
    # kick-return listings outrank their offensive ones, and a return rank is
    # not a receiving or carrying depth status. The skill set is
    # `depth_vintage.SKILL`, imported so the two cannot drift.
    skill = set(getattr(DV, 'SKILL', ('QB', 'RB', 'WR', 'TE', 'FB', 'HB')))
    out, other = {}, {}
    for r in rows:
        if r.get('dt') != chosen or not r.get('gsis_id'):
            continue
        try:
            rk = int(r['pos_rank'])
        except (TypeError, ValueError, KeyError):
            continue
        pos = (r.get('pos_abb') or '').upper()
        cand = {'pos_abb': pos, 'pos_rank': rk,
                'pos_slot': r.get('pos_slot'),
                'player_name': r.get('player_name')}
        bucket = out if pos in skill else other
        cur = bucket.get(r['gsis_id'])
        if cur is None or rk < cur['pos_rank']:
            bucket[r['gsis_id']] = cand
    for pid, v in other.items():
        # A PLAYER LISTED ONLY ON SPECIAL TEAMS IS CHARTED, AND HE IS NOT
        # CHARTED AT A SKILL POSITION. Both halves are said.
        out.setdefault(pid, dict(v, non_skill_only=True))
    _nonempty(out, 'POOL_AUDIT_RAW_DEPTH_NO_RANKS',
              f'{rc["blob"]} slice {chosen} yielded no resolvable pos_rank',
              blob=rc['blob'], dt=chosen)
    return Outcome.ok('POOL_AUDIT_VENDOR_DEPTH_OK', value=out,
                      spec_version=SPEC_VERSION, blob=rc['blob'],
                      chosen_dt=chosen, n_players=len(out),
                      n_dt_slices_held=len(dts),
                      n_dt_slices_rejected_as_later=len(dts) - len(usable),
                      pos_slot_present=('pos_slot' in (rows[0] or {})))


def injury_rows(season, week, teams, as_of) -> Outcome:
    """Per-team injury blocks, walking the lawful series newest-first.

    The feed is NOT monotone -- one capture carries 32 clubs and 167 rows, a
    later one 20 clubs and 48 -- so a club's latest filed block can sit in an
    older capture than the newest. `select` would take one file and lose it.
    """
    out, provenance = {}, {}
    n_files = 0
    for ts, p in VS.lawful_paths('injuries', as_of=as_of):
        n_files += 1
        with gzip.open(p, 'rt') as fh:
            rows = [r for r in csv.DictReader(fh)
                    if r.get('season') == str(season)
                    and r.get('week') == str(week) and r.get('team') in teams]
        # NEWEST-FIRST, AND AN OLDER CAPTURE NEVER OVERWRITES A NEWER ONE.
        for t in sorted({r['team'] for r in rows}):
            if t not in provenance:
                provenance[t] = {'retrieved_at': ts, 'blob': str(p.name)}
                out[t] = [r for r in rows if r['team'] == t]
    if n_files == 0:
        return Outcome.blocked(
            'POOL_AUDIT_NO_INJURY_VINTAGE',
            f'no injuries capture is lawful at {as_of}', cause=Cause.DATA,
            spec_version=SPEC_VERSION)
    by_id = {}
    for t, rows in out.items():
        for r in rows:
            if r.get('gsis_id'):
                by_id[r['gsis_id']] = r
    # ABSENCE OF A BLOCK IS ABSENCE OF A REPORT. It is reported, never
    # rendered as "this club has nobody injured".
    unfiled = [t for t in teams if t not in out]
    return Outcome.ok(
        'POOL_AUDIT_INJURIES_OK', value=by_id, spec_version=SPEC_VERSION,
        n_files_walked=n_files, provenance=provenance,
        clubs_with_no_filed_block=unfiled,
        n_rows={t: len(v) for t, v in out.items()},
        n_report_status_filled={t: sum(1 for r in v if (r.get('report_status')
                                                        or '').strip())
                                for t, v in out.items()})


def official_inactive_state(teams, as_of, game_id) -> Outcome:
    """Has an official inactive list been published for THIS game?

    Returns PASS only when BOTH clubs are covered by real bytes. Everything
    else is a refusal that names the club. A parsed page that hits an
    empty-state marker is `INACTIVES_PAGE_EMPTY_STATE` and is NOT an empty
    list: D02 records that the empty page once parsed to 311 fake names.
    """
    blobs, rows = [], []
    for line in VS.MANIFEST.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get('source') != IN.SOURCE or r.get('state') != 'PASS':
            continue
        v = r.get('value') or {}
        ts = VS.parse_ts(v.get('retrieved_at'))
        if ts is None or ts > as_of:
            continue
        b = v.get('blob')
        if b and b not in blobs and (_REPO / b).exists():
            blobs.append(b)
            rows.append({'blob': b, 'retrieved_at': v.get('retrieved_at'),
                         'source_url': v.get('source_url')})
    found = {}
    for rec in rows:
        html = gzip.open(_REPO / rec['blob'], 'rt', errors='replace').read()
        for t in teams:
            o = IN.parse(html, [t])
            if o.state is State.PASS and o.value:
                found.setdefault(t, {'blob': rec['blob'],
                                     'retrieved_at': rec['retrieved_at'],
                                     'names': o.value})
    missing = [t for t in teams if t not in found]
    if missing:
        return Outcome.blocked(
            'POOL_AUDIT_NO_OFFICIAL_INACTIVES',
            f'no official inactive list has been published for {missing} at '
            f'{as_of}. {len(rows)} capture(s) are lawful and none carries a '
            f'usable list for this game. ABSENCE FROM AN UNPUBLISHED LIST IS '
            f'NOT ACTIVITY: every player of these clubs is UNRESOLVED on '
            f'game-day status, and no player may be promoted to GAME_ACTIVE.',
            cause=Cause.DATA, spec_version=SPEC_VERSION, game_id=game_id,
            clubs_without_a_list=missing, n_captures_examined=len(rows),
            covered=sorted(found))
    return Outcome.ok('POOL_AUDIT_OFFICIAL_INACTIVES_OK', value=found,
                      spec_version=SPEC_VERSION, game_id=game_id)


def transaction_state() -> Outcome:
    """Can 'newly signed' or 'newly elevated' be established from a feed?

    No. `official_transactions` carries `url_template=None` and 177 BLOCKED
    manifest rows with zero bytes. This returns the refusal rather than letting
    a caller infer the categories from a roster diff and present the inference
    as a fact.
    """
    n = 0
    for line in VS.MANIFEST.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        if r.get('source') == 'official_transactions':
            n += 1
    return Outcome.blocked(
        'POOL_AUDIT_NO_TRANSACTIONS_FEED',
        f'`official_transactions` has no URL at all: {n} manifest row(s), all '
        f'BLOCKED, zero bytes on disk. Signings, releases, IR placements and '
        f'standard elevations are therefore NOT OBSERVABLE as events with '
        f'their own effective time. A roster-vintage diff can show that a row '
        f'appeared between two OBSERVATIONS; it cannot date the transaction, '
        f'and it cannot distinguish a signing from a vendor correction.',
        cause=Cause.DATA, spec_version=SPEC_VERSION, n_manifest_rows=n,
        would_settle_it='a verified official_transactions endpoint (WS05 E1)')


def roster_diff(season, week, teams, as_of) -> Outcome:
    """Observation-level movement between consecutive lawful roster captures.

    DERIVED, AND LABELLED DERIVED. This is not a transactions feed and is never
    presented as one; see `transaction_state`. What it establishes is the
    weaker and true statement: this row was not present at observation A and
    was present at observation B.
    """
    lawful, _rej = VS.candidates('weekly_rosters', as_of=as_of)
    series = []
    for v in lawful:
        rc = raw_counterpart(v, as_of)
        if rc is not None and rc['same_capture']:
            series.append((v.retrieved_at, rc['path'], rc['blob']))
    if len(series) < 2:
        return Outcome.blocked(
            'POOL_AUDIT_DIFF_NEEDS_TWO_CAPTURES',
            f'{len(series)} roster capture(s) lawful at {as_of} have '
            f'full-column bytes of their own; a diff needs two. Captures '
            f'whose raw counterpart was not retained cannot contribute, and '
            f'substituting another capture\'s bytes would invent movement.',
            cause=Cause.DATA, spec_version=SPEC_VERSION,
            n_lawful=len(lawful), n_with_raw=len(series))

    def load(path):
        with _open(path) as fh:
            return {r['gsis_id']: r for r in csv.DictReader(fh)
                    if r.get('season') == str(season)
                    and r.get('week') == str(week)
                    and r.get('team') in teams and r.get('gsis_id')}

    steps = []
    for newer, older in zip(series, series[1:]):
        a, b = load(newer[1]), load(older[1])
        _nonempty(a, 'POOL_AUDIT_DIFF_EMPTY',
                  f'{newer[2]} carries no rows for {sorted(teams)}')
        steps.append({
            'from_observed_at': older[0], 'from_blob': older[2],
            'to_observed_at': newer[0], 'to_blob': newer[2],
            'appeared': [{'gsis_id': k, 'team': a[k]['team'],
                          'full_name': a[k].get('full_name'),
                          'position': a[k].get('position'),
                          'status': a[k].get('status'),
                          'status_description_abbr':
                              a[k].get('status_description_abbr')}
                         for k in sorted(set(a) - set(b))],
            'disappeared': [{'gsis_id': k, 'team': b[k]['team'],
                             'full_name': b[k].get('full_name'),
                             'position': b[k].get('position'),
                             'status': b[k].get('status')}
                            for k in sorted(set(b) - set(a))],
            'status_changed': [{'gsis_id': k, 'team': a[k]['team'],
                                'full_name': a[k].get('full_name'),
                                'position': a[k].get('position'),
                                'from': b[k].get('status'),
                                'to': a[k].get('status'),
                                'to_abbr':
                                    a[k].get('status_description_abbr')}
                               for k in sorted(set(a) & set(b))
                               if a[k].get('status') != b[k].get('status')],
        })
    return Outcome.ok('POOL_AUDIT_DIFF_OK', value=steps,
                      spec_version=SPEC_VERSION, n_steps=len(steps),
                      n_captures=len(series),
                      n_lawful_without_raw_bytes=len(lawful) - len(series),
                      basis='OBSERVATION TIME, NOT TRANSACTION TIME')


# ------------------------------------------------------------------- verdict
def _eligibility(status):
    """Roster-membership state from a status code. Never from a position."""
    s = (status or '').strip().upper()
    if not s:
        return UNRESOLVED, 'ROSTER_STATUS_BLANK'
    if s == ACTIVE:
        return ROSTER_ACTIVE, None
    for table in (PRACTICE_SQUAD, RESERVE_LIST, RELEASED, RETIRED):
        if s in table:
            return ROSTER_EXCLUDED, f'ROSTER_STATUS_{s}'
    if s in POSTHOC:
        return UNRESOLVED, f'ROSTER_STATUS_POSTHOC_{s}'
    # AN UNRECOGNISED CODE IS NOT AN EXCLUSION. It is also not an activity.
    return UNRESOLVED, f'ROSTER_STATUS_UNDECODED_{s}'


def _gameday(ia, team, full_name):
    """Dressing tonight, or UNRESOLVED. There is no third answer.

    A player is OFFICIAL_INACTIVE only when an official list for HIS club
    names him. He is never GAME_ACTIVE: not being named on a list that was
    never published is not evidence, and `inactives.GAME_ACTIVE` exists
    precisely so that the state we cannot establish has a name we can refuse
    to emit.
    """
    if ia.state is not State.PASS:
        return UNRESOLVED
    blk = (ia.value or {}).get(team)
    if not blk:
        return UNRESOLVED
    names = blk.get('names')
    hit = False
    if isinstance(names, dict):
        hit = any(full_name in (v or []) for v in names.values())
    elif isinstance(names, (list, tuple, set)):
        hit = full_name in names
    return OFFICIAL_INACTIVE if hit else UNRESOLVED


def _category(status):
    s = (status or '').strip().upper()
    if s in PRACTICE_SQUAD:
        return 'PRACTICE_SQUAD'
    if s in RESERVE_LIST:
        return 'RESERVE_LIST'
    if s in RELEASED:
        return 'RELEASED'
    if s in RETIRED:
        return 'RETIRED'
    if s == ACTIVE:
        return 'ACTIVE_ROSTER'
    return 'UNDECODED'


def audit(season, week, game_id, teams, kickoff_utc, written_at,
          mode_flags=None) -> Outcome:
    """One row per player CONSIDERED, with the vintage behind every column.

    `mode_flags` is the candidate mode's flag dict. `active_roster_only` is the
    ONLY eligibility filter in the production path and it is present in
    R5-R8 and ABSENT from `V1_CANDIDATE` and `PRODUCTION_BASELINE`, so the
    same player is in or out of the pool depending on the mode. Both answers
    are reported; neither is 'the' answer.
    """
    teams = tuple(teams)
    cut = VS.as_of_cut(kickoff_utc=kickoff_utc, written_at=written_at)
    if cut is None:
        return Outcome.blocked(
            'POOL_AUDIT_NO_CLOCK',
            'audit() was given neither written_at nor kickoff_utc. An '
            'undeclared cut is not an open cut.',
            cause=Cause.GOVERNANCE, spec_version=SPEC_VERSION)
    flags = dict(mode_flags or {})
    r5_on = bool(flags.get('active_roster_only'))

    try:
        ro = roster_rows(season, week, teams, cut)
        if ro.state is not State.PASS:
            return ro
        rows = ro.value
        do = depth_rows(teams, cut)
        depth = do.value if do.state is State.PASS else {}
        vd = vendor_depth(teams, cut)
        vdepth = vd.value if vd.state is State.PASS else {}
        io_ = injury_rows(season, week, teams, cut)
        if io_.state is not State.PASS:
            return io_
        inj = io_.value
        ia = official_inactive_state(teams, cut, game_id)
        tx = transaction_state()
        diff = roster_diff(season, week, teams, cut)
    except PoolAuditRefused as e:
        d = json.loads(str(e))
        return Outcome.fail(d['code'], d['detail'], **d['evidence'])

    # THE GATE THAT DECIDES WHETHER ANY NON-QB IS MODELLED AT ALL.
    # `layers.appearance` defers the WHOLE game when EITHER club is not READY
    # (`layers.py:117-127`), so a single club's unfiled report empties the
    # non-QB half of the board for both.
    ready = {t: RD.team_readiness(season, week, t, kickoff_utc=kickoff_utc,
                                  written_at=written_at) for t in teams}
    not_ready = [t for t, v in ready.items()
                 if not str(v.get('state', '')).startswith('READY')]
    appearance_runs = not not_ready

    out = []
    for r in rows:
        pid = r.get('gsis_id') or ''
        pos = (r.get('position') or '').strip()
        team = (r.get('team') or '').strip()
        status = (r.get('status') or '').strip().upper()
        elig, elig_reason = _eligibility(status)
        d = depth.get(pid)
        v = vdepth.get(pid)
        # THE VENDOR'S OWN RANK IS THE ONE A HUMAN MEANS BY "DEPTH STATUS".
        # The consumed ordinal is carried beside it, never instead of it.
        if v and v.get('non_skill_only'):
            depth_status = f'NOT_CHARTED_AT_SKILL (ST: {v["pos_abb"]}{v["pos_rank"]})'
        elif v:
            depth_status = f'{v["pos_abb"]}{v["pos_rank"]}'
        else:
            depth_status = 'CHARTED_RANK_UNRESOLVED' if d else 'NOT_CHARTED'
        irow = inj.get(pid)
        if irow is None:
            injury = 'NO_INJURY_ROW'
        else:
            rs = (irow.get('report_status') or '').strip()
            ps = (irow.get('practice_status') or '').strip()
            injury = f'{rs or "NO_DESIGNATION_FILED"} / {ps or "NO_PRACTICE_STATUS"}'

        # --- pool membership, reproducing the production path exactly -------
        reasons = []
        frame_missing = [k for k in FRAME_FIELDS
                         if not {'gsis_id': pid, 'position': pos,
                                 'team': team}[k]]
        if frame_missing:
            reasons.append('NO_GSIS_ID' if 'gsis_id' in frame_missing
                           else 'NONQB_FRAME_FIELD_MISSING')
        is_qb = pos == QB_POS
        if is_qb:
            # P3, run_forecast.py:735-736. The QB list bypasses active_pool
            # entirely; nothing but a gsis_id and the string 'QB' is required.
            allocation_pool = bool(pid)
            if not allocation_pool:
                reasons.append('NO_GSIS_ID')
            modelled = allocation_pool
            layer = 'qb'
            if allocation_pool and elig is not ROSTER_ACTIVE:
                reasons.append(f'QB_POOL_EXEMPT_FROM_R5({elig_reason})')
        else:
            in_recv = pos in RECEIVING_POS
            allocation_pool = bool(pid and pos and team) and in_recv
            if not in_recv:
                reasons.append(f'POSITION_NOT_MODELLED({pos or "BLANK"})')
            if allocation_pool and r5_on and elig is not ROSTER_ACTIVE:
                allocation_pool = False
                reasons.append(f'R5_{elig_reason}')
            layer = ('rushing+receiving' if pos in CARRY_POS else 'receiving')
            modelled = allocation_pool and appearance_runs
            if allocation_pool and not appearance_runs:
                reasons.append(
                    'APPEARANCE_DEFERRED('
                    + ','.join(f'{t}:{ready[t]["state"]}' for t in not_ready)
                    + ')')
        out.append({
            'player': r.get('full_name') or f'<no full_name:{pid}>',
            'gsis_id': pid,
            'team': team,
            'position': pos,
            'depth_chart_position': r.get('depth_chart_position'),
            'roster_status': status or 'BLANK',
            'roster_status_meaning': _category(status),
            'status_description_abbr': r.get('status_description_abbr') or '',
            'status_description_abbr_decoded': 'UNDECODED',
            'depth_status': depth_status,
            'depth_vendor_pos_slot': (v.get('pos_slot') if v else None),
            'depth_ordinal_consumed_by_appearance': (d[0] if d else None),
            'depth_ordinal_is': ('a TEAM-WIDE ordinal over skill players, not '
                                 'the vendor within-position rank'),
            'injury_status': injury,
            'gameday_status': _gameday(ia, team, r.get('full_name')),
            'eligible': elig,
            'eligibility_reason': elig_reason,
            'allocation_pool': allocation_pool,
            'model_pool': modelled,
            'model_layer': layer if modelled else None,
            'exclusion_reason': '; '.join(reasons) or None,
            'years_exp': r.get('years_exp'),
            'entry_year': r.get('entry_year'),
            'espn_id': r.get('espn_id') or '',
        })
    _nonempty(out, 'POOL_AUDIT_NO_ROWS',
              f'no player row was produced for {sorted(teams)}')
    out.sort(key=lambda x: (x['team'], x['position'], x['player']))

    vintages = {
        'roster_identity_and_position': ro.evidence['reduced'],
        'roster_status_and_name': ro.evidence['raw'],
        'depth_status_vendor_rank': ({'blob': vd.evidence.get('blob'),
                                      'chosen_dt': vd.evidence.get('chosen_dt'),
                                      'pos_slot_present':
                                          vd.evidence.get('pos_slot_present')}
                                     if vd.state is State.PASS
                                     else {'refused': vd.code}),
        'depth_ordinal_consumed': (do.evidence.get('chosen')
                                   if do.state is State.PASS
                                   else {'refused': do.code}),
        'injury_status': io_.evidence.get('provenance'),
        'gameday_status': ({'refused': ia.code,
                            'clubs_without_a_list':
                                ia.evidence.get('clubs_without_a_list')}
                           if ia.state is not State.PASS
                           else {'covered': sorted(ia.value)}),
        'transactions': {'refused': tx.code},
    }
    return Outcome.ok(
        'POOL_AUDIT_OK', value=out, spec_version=SPEC_VERSION,
        game_id=game_id, season=season, week=week, teams=list(teams),
        kickoff_utc=_iso(kickoff_utc), written_at=_iso(written_at),
        as_of=cut.isoformat(), mode_flags=flags, r5_active_roster_only=r5_on,
        n_considered=len(out),
        n_allocation_pool=sum(1 for x in out if x['allocation_pool']),
        n_model_pool=sum(1 for x in out if x['model_pool']),
        readiness={t: {'state': v.get('state'), 'n_rows': v.get('n_rows'),
                       'population': v.get('population'),
                       'reason': v.get('reason')} for t, v in ready.items()},
        appearance_runs=appearance_runs,
        vintages=vintages,
        depth_outcome=do.code, vendor_depth_outcome=vd.code,
        depth_pos_slot_available=(do.evidence.get('pos_slot_available')
                                  if do.state is State.PASS else None),
        inactives_outcome=ia.code,
        transactions_outcome=tx.code,
        transactions_detail=tx.detail,
        roster_diff=(diff.value if diff.state is State.PASS
                     else {'refused': diff.code}),
        reduced_missing_columns=ro.evidence.get('reduced_missing_columns'),
        injury_population=io_.evidence.get('n_report_status_filled'),
        clubs_with_no_filed_injury_block=io_.evidence.get(
            'clubs_with_no_filed_block'),
        forbidden_inputs=('filesystem mtime', 'glob order', 'filename order',
                          'file size', 'row count', 'latest on disk'),
        never_emitted='GAME_ACTIVE -- no source we hold establishes it')
