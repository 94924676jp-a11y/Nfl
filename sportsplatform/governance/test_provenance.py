"""Five clocks, tested on the defect that came from having one."""
import datetime as dt, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from governance.outcome import State
from governance.provenance import Provenance, validate, assert_usable_for

P = F = 0
def check(l, c, d=''):
    global P, F
    if c: P += 1; print(f'  ok   {l}')
    else: F += 1; print(f'  FAIL {l}  {d}')

NOW = dt.datetime(2026, 9, 1, 20, 47, tzinfo=dt.timezone.utc)

def prov(**kw):
    base = dict(source='open-meteo', source_timestamp='2026-09-01T20:47:00+00:00',
                retrieved_at='2026-09-01T20:47:00+00:00',
                generated_at='2026-09-01T20:47:00+00:00',
                effective_for_date='2026-09-02', schema_version='1')
    base.update(kw)
    return Provenance(**base)


def test_the_v7_weather_defect():
    print('\nA. THE defect: fresh wrapper around a 30-minute-old forecast')
    p = prov(source_timestamp='2026-09-01T20:17:00+00:00',
             retrieved_at='2026-09-01T20:17:00+00:00',
             cache_timestamp='2026-09-01T20:17:00+00:00')
    check('generated_at reads 0s old -- what V7 read',
          p.age_seconds('generated_at', NOW) == 0.0)
    check('effective age reads 1800s -- the truth',
          p.effective_age_seconds(NOW) == 1800.0)
    o = assert_usable_for(p, '2026-09-02', max_effective_age_s=900, now=NOW)
    check('and it is now refused', o.state is State.FAIL, str(o)[:60])
    check('  naming staleness', o.code == 'PROVENANCE_STALE', o.code)
    check('  and saying which clock it measured',
          'not on generated_at' in o.detail, o.detail[:80])


def test_there_is_no_unqualified_age():
    print('\nB. "how old is this" has four answers, so it must be named')
    p = prov()
    try:
        p.age_seconds('age', NOW)
        check('an unnamed clock refuses', False, 'accepted')
    except ValueError as e:
        check('an unnamed clock refuses', 'name the clock' in str(e))
    for c in ('source_timestamp', 'retrieved_at', 'generated_at'):
        check(f'{c} answers', p.age_seconds(c, NOW) == 0.0)


def test_a_cache_hit_cannot_claim_it_was_just_retrieved():
    print('\nC. a cache hit reporting retrieved_at=now is the V7 defect exactly')
    p = prov(cache_timestamp='2026-09-01T20:17:00+00:00',
             retrieved_at='2026-09-01T20:47:00+00:00')
    o = validate(p)
    check('refused', o.state is State.FAIL, str(o)[:60])
    check('  named', o.code == 'CACHE_RETRIEVAL_CONFLATED', o.code)
    ok = prov(cache_timestamp='2026-09-01T20:17:00+00:00',
              source_timestamp='2026-09-01T20:17:00+00:00',
              retrieved_at='2026-09-01T20:17:00+00:00')
    check('an honest cache hit passes', validate(ok).state is State.PASS)


def test_impossible_orderings_refuse():
    print('\nD. clocks that cannot be in that order')
    o = validate(prov(retrieved_at='2026-09-01T20:00:00+00:00',
                      source_timestamp='2026-09-01T20:30:00+00:00'))
    check('retrieved before the source produced it', o.state is State.FAIL,
          str(o)[:60])
    o = validate(prov(generated_at='2026-09-01T20:00:00+00:00',
                      retrieved_at='2026-09-01T20:30:00+00:00',
                      source_timestamp='2026-09-01T20:30:00+00:00'))
    check('wrapper predating its contents', o.state is State.FAIL, str(o)[:60])


def test_missing_fields_block():
    print('\nE. a field without provenance does not enter the model')
    for f in ('source', 'source_timestamp', 'schema_version'):
        o = validate(prov(**{f: ''}))
        check(f'missing {f} blocks', o.state is State.BLOCKED, str(o)[:50])


def test_leakage_and_staleness_are_separate_questions():
    print('\nF. leakage and staleness are not the same check')
    leaky = prov(source_timestamp='2026-09-02T13:00:00+00:00',
                 retrieved_at='2026-09-02T13:00:00+00:00',
                 generated_at='2026-09-02T13:00:00+00:00')
    o = assert_usable_for(leaky, '2026-09-02')
    check('data from the game date itself is LEAKAGE',
          o.code == 'PROVENANCE_LEAKAGE', o.code)
    stale = prov(source_timestamp='2026-08-01T00:00:00+00:00',
                 retrieved_at='2026-08-01T00:00:00+00:00',
                 generated_at='2026-08-01T00:00:00+00:00')
    o = assert_usable_for(stale, '2026-09-02', max_effective_age_s=900, now=NOW)
    check('old-but-not-leaky data is STALE, a different code',
          o.code == 'PROVENANCE_STALE', o.code)
    good = prov(source_timestamp='2026-09-01T20:40:00+00:00',
                retrieved_at='2026-09-01T20:40:00+00:00',
                generated_at='2026-09-01T20:47:00+00:00')
    o = assert_usable_for(good, '2026-09-02', max_effective_age_s=900, now=NOW)
    check('fresh pre-game data passes both', o.state is State.PASS, str(o)[:60])
    o = assert_usable_for(good, '2026-09-05')
    check('and the wrong date blocks', o.code == 'PROVENANCE_WRONG_DATE', o.code)


if __name__ == '__main__':
    for t in (test_the_v7_weather_defect, test_there_is_no_unqualified_age,
              test_a_cache_hit_cannot_claim_it_was_just_retrieved,
              test_impossible_orderings_refuse, test_missing_fields_block,
              test_leakage_and_staleness_are_separate_questions):
        t()
    print(f'\n{P} passed, {F} failed')
    sys.exit(1 if F else 0)
