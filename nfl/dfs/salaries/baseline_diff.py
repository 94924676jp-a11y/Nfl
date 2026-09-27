"""Diff a frozen slate baseline against a later snapshot of the same contest.

WHAT THIS IS FOR

`DK_WEEK3_EARLY_BASELINE.json` records what was known before Sunday news. Its
only purpose is to be compared against, so the comparison has to be a program
rather than a reading. A human diffing 457 rows by eye on a Sunday morning is
the failure mode this repository keeps paying for.

WHAT IT REPORTS, AND WHY EACH ONE IS SEPARATE

  contest identity   Did the CONTEST change? A different contest id, kickoff or
                     game set is not a change within the slate, it is a
                     different slate, and comparing across it is a category
                     error. This is checked first and refuses.
  pool membership    Rows added and rows removed, by dk_id. DraftKings does
                     remove players from a pool.
  salary             Rows whose price moved, with both values.
  identity           Rows that resolved since the baseline, and -- the one that
                     matters more -- rows that STOPPED resolving.
  position / team    Rows DraftKings reclassified.

THREE THINGS IT REFUSES TO DO

It will not report "no change" when it could not compare. An empty diff and a
failed comparison are different results, and `NOTHING_TO_COMPARE` is returned
rather than a clean bill of health.

It will not treat a missing field as an unchanged field. A field absent from one
side is `FIELD_ABSENT_ONE_SIDE`, counted separately from a field present on
both and equal.

It will not compute an availability delta. Availability comes from the official
inactives path (`nfl/production/nonqb/inactives.py`), which is the only thing
entitled to assert it, and it is keyed on canonical ids the baseline's six
UNMATCHED rows do not have. A salary file cannot tell you who is playing, and
this module does not guess from price movement -- a price drop is not an
inactive, it is a price drop.
"""
from __future__ import annotations

import json
import pathlib

from sportsplatform.governance.outcome import Outcome

SPEC_VERSION = 'dk-baseline-diff-1'

#: Fields compared row by row. `dk_id` is the key and is not in this list.
COMPARED = ('salary', 'dk_pos', 'team', 'dk_name')

#: Fields that identify the CONTEST rather than a row in it. Several spellings
#: of the kickoff are listed because the baseline artifact writes `kickoff_utc`
#: and `kickoff_et` while a raw pool row writes `kickoff`. A name this check
#: does not know is a field it silently does not compare, which would make the
#: check decorative on the very artifact it exists for.
CONTEST = ('kickoff', 'kickoff_utc', 'kickoff_et', 'n_games', 'games')

#: At least one of these must be present, or contest sameness is not
#: established and the comparison defers. A game set alone does not pin a
#: contest: the same nine games appear in the early slate and in a full-day
#: slate.
CONTEST_REQUIRED_ONE_OF = ('kickoff', 'kickoff_utc', 'kickoff_et')


def _rows(obj):
    """The pool rows out of either a baseline artifact or a raw row list."""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        slate = obj.get('slate') or {}
        for key in ('rows', 'pool_rows', 'pool'):
            v = slate.get(key) if isinstance(slate, dict) else None
            if isinstance(v, list):
                return v
            v = obj.get(key)
            if isinstance(v, list):
                return v
    return None


def _by_id(rows):
    out = {}
    for r in rows:
        k = r.get('dk_id')
        if k:
            out[str(k)] = r
    return out


#: `match_method` value marking a row that is not a person and so never has a
#: player id. A DST is not an unresolved identity.
NOT_A_PERSON = 'NOT_A_PERSON'


def _canonical(r):
    """The canonical id on a row, under any of the names it travels under."""
    for k in ('gsis_id', 'canonical_id', 'nfl_id'):
        if r.get(k):
            return r[k]
    return None


def _identity_applies(r):
    """Whether a player identity is even expected for this row.

    A missing `gsis_id` covers TWO different states and they must not be one
    number. Measured on the Week-3 baseline: 24 rows carry no `gsis_id`, of
    which 18 are DST -- team defences, which never have a player id under any
    circumstances -- and 6 are players we failed to resolve. Reporting 24
    unresolved identities would be false, and reporting a DST as having
    "stopped resolving" tomorrow would be a manufactured defect.
    """
    return r.get('match_method') != NOT_A_PERSON and r.get('dk_pos') != 'DST'


def diff(before, after) -> Outcome:
    """Compare two snapshots of one contest. Neither side is modified."""
    b_rows, a_rows = _rows(before), _rows(after)
    if not b_rows or not a_rows:
        return Outcome.fail(
            'NOTHING_TO_COMPARE',
            'one side carries no pool rows, so there is no comparison to '
            'report. This is NOT an empty diff: a failed comparison and a '
            'clean comparison are different results.',
            n_before=len(b_rows or ()), n_after=len(a_rows or ()))

    b, a = _by_id(b_rows), _by_id(a_rows)
    if not b or not a:
        return Outcome.fail(
            'NOTHING_TO_COMPARE',
            'pool rows are present but carry no dk_id, so they cannot be '
            'keyed. Joining on name and team instead is the defect DEF-082 '
            'was filed for and is not done here.',
            n_keyed_before=len(b), n_keyed_after=len(a))

    added = sorted(set(a) - set(b))
    removed = sorted(set(b) - set(a))
    common = sorted(set(a) & set(b))

    changed = {f: [] for f in COMPARED}
    absent_one_side = {f: [] for f in COMPARED}
    for k in common:
        for f in COMPARED:
            hb, ha = f in b[k], f in a[k]
            if hb != ha:
                absent_one_side[f].append(
                    {'dk_id': k, 'present_before': hb, 'present_after': ha})
            elif hb and b[k][f] != a[k][f]:
                changed[f].append({'dk_id': k, 'dk_name': b[k].get('dk_name'),
                                   'before': b[k][f], 'after': a[k][f]})

    resolved_since, stopped_resolving, identity_not_applicable = [], [], []
    for k in common:
        if not (_identity_applies(b[k]) and _identity_applies(a[k])):
            identity_not_applicable.append(k)
            continue
        cb, ca = _canonical(b[k]), _canonical(a[k])
        if cb is None and ca is not None:
            resolved_since.append({'dk_id': k, 'dk_name': a[k].get('dk_name'),
                                   'canonical_id': ca})
        elif cb is not None and ca is None:
            stopped_resolving.append({'dk_id': k,
                                      'dk_name': b[k].get('dk_name'),
                                      'was': cb})

    ev = {
        'spec_version': SPEC_VERSION,
        'n_before': len(b), 'n_after': len(a),
        'n_common': len(common),
        'added': [{'dk_id': k, 'dk_name': a[k].get('dk_name'),
                   'dk_pos': a[k].get('dk_pos'), 'team': a[k].get('team'),
                   'salary': a[k].get('salary')} for k in added],
        'removed': [{'dk_id': k, 'dk_name': b[k].get('dk_name'),
                     'dk_pos': b[k].get('dk_pos'), 'team': b[k].get('team'),
                     'salary': b[k].get('salary')} for k in removed],
        'changed': {f: v for f, v in changed.items() if v},
        'field_absent_one_side': {f: v for f, v in absent_one_side.items()
                                  if v},
        'identity_resolved_since_baseline': resolved_since,
        'identity_stopped_resolving': stopped_resolving,
        'n_identity_not_applicable': len(identity_not_applicable),
        'what_not_applicable_means':
            'rows for which no player identity is expected at all -- DST are '
            'team defences and never carry a player id. They are excluded from '
            'the identity comparison rather than counted as unresolved.',
        'AVAILABILITY_NOT_COMPUTED_HERE':
            'A salary snapshot does not establish who is playing. Availability '
            'comes from the official inactives path and nowhere else. A price '
            'movement is a price movement, not an inactive.',
    }
    n = (len(added) + len(removed)
         + sum(len(v) for v in changed.values())
         + sum(len(v) for v in absent_one_side.values())
         + len(resolved_since) + len(stopped_resolving))
    ev['n_differences'] = n

    if stopped_resolving:
        return Outcome.fail(
            'IDENTITY_REGRESSED',
            f'{len(stopped_resolving)} row(s) resolved to a canonical id in '
            f'the baseline and do not now. That is a regression in the '
            f'identity chain, not news about a player, and it is reported as '
            f'a failure so it cannot pass as an ordinary slate change.', **ev)
    if n == 0:
        return Outcome.ok('SLATE_UNCHANGED',
                          value=ev,
                          detail='the two snapshots agree on every compared '
                                 'field of every keyed row', **ev)
    return Outcome.ok('SLATE_CHANGED', value=ev,
                      detail=f'{n} difference(s) across {len(common)} common '
                             f'row(s)', **ev)


def contest_identity(before, after) -> Outcome:
    """Refuse before diffing if these are not snapshots of the SAME contest."""
    def ident(o):
        s = (o.get('slate') or {}) if isinstance(o, dict) else {}
        return {k: s.get(k) for k in CONTEST if k in s}

    ib, ia = ident(before), ident(after)
    if not ib or not ia:
        return Outcome.deferred(
            'CONTEST_IDENTITY_NOT_STATED',
            'at least one side does not state the contest it describes, so '
            'sameness cannot be established. Diffing anyway would risk '
            'comparing two different slates and calling the result news.',
            before=ib, after=ia)
    for side, got in (('before', ib), ('after', ia)):
        if not any(k in got for k in CONTEST_REQUIRED_ONE_OF):
            return Outcome.deferred(
                'CONTEST_KICKOFF_NOT_STATED',
                f'the {side} snapshot states no kickoff under any of '
                f'{list(CONTEST_REQUIRED_ONE_OF)}, so the one field that '
                f'separates this contest from another over the same games is '
                f'not being compared. A check that silently skips it is '
                f'decorative.',
                side=side, stated=sorted(got))
    differing = {k: {'before': ib.get(k), 'after': ia.get(k)}
                 for k in set(ib) | set(ia) if ib.get(k) != ia.get(k)}
    if differing:
        return Outcome.fail(
            'DIFFERENT_CONTEST',
            'the two snapshots do not describe the same contest. A changed '
            'kickoff or game set is not a change WITHIN the slate, it is a '
            'different slate, and comparing across it is a category error.',
            differing=differing)
    return Outcome.ok('SAME_CONTEST', value=ib, **{'checked': sorted(ib)})


def main(argv=None):
    import sys
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 2:
        print('usage: baseline_diff.py BEFORE.json AFTER.json')
        return 2
    before = json.loads(pathlib.Path(args[0]).read_text())
    after = json.loads(pathlib.Path(args[1]).read_text())
    ident = contest_identity(before, after)
    print(f'contest: {ident.state.name} {ident.code}')
    if ident.state.name == 'FAIL':
        print(json.dumps(ident.evidence.get('differing'), indent=1))
        return 1
    o = diff(before, after)
    print(f'diff:    {o.state.name} {o.code} -- {o.detail}')
    ev = o.value if isinstance(o.value, dict) else o.evidence
    print(json.dumps({k: v for k, v in ev.items()
                      if k != 'AVAILABILITY_NOT_COMPUTED_HERE'}, indent=1))
    return 0 if o.state.name == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
