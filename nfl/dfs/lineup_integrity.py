"""Refuse an entered lineup the engine cannot actually account for.

WHY THIS IS NOT A LINEUP RANKER

It makes no claim about whether a lineup is good. Ranking lineups needs
ceiling and tail, and those need cross-player covariance the draw artifact
declares it does not carry. This checks something the current evidence fully
supports: whether every slot in an entered lineup resolves to a player the
engine models, prices and can say something about.

WHAT IT CAUGHT THE DAY IT WAS WRITTEN

Against the live ATL @ GB Showdown entry on 2026-09-24:

* `P. Strong Jr.` -- Pierre Strong, GB RB, roster status DEV, absent from all
  ten draw layers and from all 958 rows of the DK salary file we held. The
  contest priced him; the engine had no projection for him at all. Scoring
  that lineup would have summed five of six slots and reported a number.
* `B. Robinson` -- Atlanta rosters Bijan and Brian. A rendered abbreviation
  cannot distinguish them and the difference is $11,100 of captain salary.

Both are the same failure in different clothes: a lineup that looks complete
because the parts that resolved were summed and the part that did not was
passed over. So this refuses the whole lineup by name rather than returning a
partial total, which is the discipline the rest of this repository is built
on.

WHAT IT REFUSES TO DECIDE

It does not guess which Robinson. An ambiguous slot is reported with every
candidate and their salaries so a human or a contest export can resolve it.
Inferring from price would be a fuzzy match wearing arithmetic.
"""
from __future__ import annotations

import unicodedata
import re

SPEC_VERSION = 'dfs-lineup-integrity/1.0.0'

#: DK Showdown: one captain at 1.5x salary and 1.5x points, five flex.
CAPTAIN_MULTIPLIER = 1.5
SHOWDOWN_SLOTS = 6
#: Declared, not discovered. If a contest uses a different cap it is passed in.
DEFAULT_SALARY_CAP = 50000

_PUNCT = re.compile(r"[.'\-]")
_SUFFIX = re.compile(r"\s+(jr|sr|ii|iii|iv|v)$")
_SPACE = re.compile(r"\s+")
_INITIAL = re.compile(r'^([A-Za-z])\.?\s+(.+)$')


class LineupRefusal(RuntimeError):
    """The lineup cannot be accounted for. Carries a named code."""

    def __init__(self, code: str, detail: str, **evidence):
        super().__init__(f'{code}: {detail}')
        self.code = code
        self.detail = detail
        self.evidence = evidence


def normalise(name: str) -> str:
    s = unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode()
    s = _PUNCT.sub('', s).casefold().strip()
    return _SUFFIX.sub('', _SPACE.sub(' ', s))


def candidates_for(entry_name: str, pool_names) -> list[str]:
    """Pool names an entry string could mean.

    An entry may be a full name or the abbreviated form a contest UI renders,
    `B. Robinson`. The abbreviated form is matched on initial plus surname,
    which is genuinely ambiguous when a club rosters two -- and reporting both
    is the point, not a problem to be resolved by picking one.
    """
    want = normalise(entry_name)
    exact = [p for p in pool_names if normalise(p) == want]
    if exact:
        return sorted(set(exact))
    m = _INITIAL.match((entry_name or '').strip())
    if not m:
        return []
    initial, surname = m.group(1).casefold(), normalise(m.group(2))
    hits = []
    for p in pool_names:
        parts = normalise(p).split()
        if len(parts) < 2:
            continue
        if parts[0][:1] == initial and ' '.join(parts[1:]) == surname:
            hits.append(p)
    return sorted(set(hits))


def check(lineup, *, pool, crosswalk=None, modelled_ids=None,
          availability=None, salary_cap=DEFAULT_SALARY_CAP) -> dict:
    """Account for every slot, or refuse.

    `lineup`  : [{'slot': 'CPT'|'FLEX', 'name': str}, ...]
    `pool`    : {name: {'FLEX': salary, 'CPT': salary, 'team': str}}
    `crosswalk`: {name: gsis_id} for identity resolution
    `modelled_ids`: gsis_ids the draw artifact actually carries
    `availability`: {gsis_id: 'OUT'|...} terminal states
    """
    if not lineup:
        raise LineupRefusal('LINEUP_EMPTY',
                            'no slots were supplied; an empty lineup is not a '
                            'valid one and must not score zero silently')
    if len(lineup) != SHOWDOWN_SLOTS:
        raise LineupRefusal(
            'LINEUP_WRONG_SIZE',
            f'{len(lineup)} slots supplied against {SHOWDOWN_SLOTS} for a '
            f'Showdown lineup', n_slots=len(lineup))
    if sum(1 for s in lineup if s.get('slot') == 'CPT') != 1:
        raise LineupRefusal(
            'LINEUP_CAPTAIN_COUNT',
            'a Showdown lineup carries exactly one captain')

    pool_names = list(pool)
    rows, unresolved, ambiguous, unmodelled, unavailable = [], [], [], [], []
    salary = 0

    for slot in lineup:
        name, kind = slot.get('name'), slot.get('slot', 'FLEX')
        cands = candidates_for(name, pool_names)
        if not cands:
            unresolved.append(name)
            rows.append({'entered': name, 'slot': kind,
                         'resolution': 'NOT_IN_POOL'})
            continue
        if len(cands) > 1:
            ambiguous.append({
                'entered': name, 'slot': kind,
                'candidates': [{'name': c, 'team': pool[c].get('team'),
                                'salary': pool[c].get(
                                    'CPT' if kind == 'CPT' else 'FLEX')}
                               for c in cands]})
            rows.append({'entered': name, 'slot': kind,
                         'resolution': 'AMBIGUOUS', 'candidates': cands})
            continue

        resolved = cands[0]
        sal = pool[resolved].get('CPT' if kind == 'CPT' else 'FLEX')
        if sal is None:
            unresolved.append(name)
            rows.append({'entered': name, 'slot': kind,
                         'resolution': 'NO_SALARY_FOR_SLOT'})
            continue
        salary += int(sal)
        gid = (crosswalk or {}).get(resolved)
        row = {'entered': name, 'resolved': resolved, 'slot': kind,
               'team': pool[resolved].get('team'), 'salary': int(sal),
               'gsis_id': gid, 'resolution': 'RESOLVED'}
        if modelled_ids is not None and (gid is None or gid not in modelled_ids):
            unmodelled.append(resolved)
            row['modelled'] = False
        elif modelled_ids is not None:
            row['modelled'] = True
        state = (availability or {}).get(gid)
        if state:
            unavailable.append({'name': resolved, 'availability': state})
            row['availability'] = state
        rows.append(row)

    verdict = {
        'spec_version': SPEC_VERSION,
        'slots': rows,
        'salary_used': salary,
        'salary_cap': salary_cap,
        'salary_remaining': salary_cap - salary,
        'n_unresolved': len(unresolved),
        'n_ambiguous': len(ambiguous),
        'n_unmodelled': len(unmodelled),
        'ambiguous': ambiguous,
        'unmodelled': unmodelled,
        'declared_unavailable': unavailable,
    }

    problems = []
    if unresolved:
        problems.append(f'{len(unresolved)} slot(s) are not in the salary '
                        f'pool at all: {unresolved}')
    if ambiguous:
        problems.append(f'{len(ambiguous)} slot(s) are ambiguous: '
                        + ', '.join(f"{a['entered']} -> "
                                    f"{[c['name'] for c in a['candidates']]}"
                                    for a in ambiguous))
    if unmodelled:
        problems.append(f'{len(unmodelled)} slot(s) resolve to a player the '
                        f'engine does not model: {unmodelled}')

    if problems:
        verdict['state'] = 'REFUSED'
        verdict['code'] = 'LINEUP_NOT_ACCOUNTABLE'
        verdict['detail'] = (
            '; '.join(problems)
            + '. The lineup is refused whole rather than scored on the slots '
              'that did resolve: a partial total reported as a total is how a '
              'missing player becomes invisible.')
        return verdict

    if salary > salary_cap:
        verdict['state'] = 'REFUSED'
        verdict['code'] = 'LINEUP_OVER_CAP'
        verdict['detail'] = (f'{salary} exceeds the cap of {salary_cap} by '
                             f'{salary - salary_cap}')
        return verdict

    verdict['state'] = 'ACCOUNTABLE'
    verdict['code'] = 'LINEUP_FULLY_ACCOUNTED'
    verdict['detail'] = (
        f'all {SHOWDOWN_SLOTS} slots resolve to modelled, priced players; '
        f'{salary} of {salary_cap} used. This says the lineup can be reasoned '
        f'about. It says NOTHING about whether it is a good lineup.')
    return verdict
