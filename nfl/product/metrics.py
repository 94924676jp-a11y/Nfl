"""What V1 actually forecasts, and what it does not.

THIS FILE IS THE ANTI-FABRICATION SPINE OF THE PRODUCT LAYER.

A report is the place where a missing number is most tempting to invent,
because a blank cell looks like a bug and a plausible number looks like a
feature. So the supported set is declared once, here, from the layers the
engine really produces, and the renderer can only show what this file admits.
Anything absent is shown as UNAVAILABLE with the reason it is unavailable --
never as a blank, never as a zero, and never as a quantity derived on the spot.

THE ONE THAT MATTERS MOST: RB and WR RUSHING YARDS DO NOT EXIST IN V1.
`layers.rushing_conversion` refuses with RUSHING_CONVERSION_CONTROL_UNDEFINED
and names three open owner decisions. It also names the prohibited
implementation explicitly -- `rushing_yards = carries x yards_per_carry` -- 
which is exactly the number a product layer would otherwise be expected to
print. It is not printed. Quarterback rushing yards ARE supported, by a
different and adjudicated mechanism inside QB V1, and the asymmetry is real
rather than an oversight.
"""
from __future__ import annotations

# Availability, and the three states are genuinely different things.
MODELED = 'MODELED'            # a governed layer produced a full distribution
PROVISIONAL = 'PROVISIONAL'    # produced, but under a declared caveat
UNAVAILABLE = 'UNAVAILABLE'    # no governed control exists; nothing is shown

# (layer, key) -> how to present it.
#   label      what a reader sees
#   kind       'count' | 'yards' | 'rate'
#   status     MODELED / PROVISIONAL
#   caveat     required when status is PROVISIONAL
SUPPORTED = {
    ('qb', 'att'): {'label': 'Pass attempts', 'kind': 'count',
                    'status': MODELED},
    ('qb', 'cmp'): {'label': 'Completions', 'kind': 'count',
                    'status': MODELED},
    ('qb', 'db'): {'label': 'Dropbacks', 'kind': 'count', 'status': MODELED},
    ('qb', 'pyds'): {'label': 'Passing yards', 'kind': 'yards',
                     'status': MODELED},
    ('qb', 'ptd'): {'label': 'Passing TD', 'kind': 'count',
                    'status': PROVISIONAL,
                    'caveat': 'TD2 pooled positional control, governance '
                              'HOLD_TENTATIVE'},
    ('qb', 'int'): {'label': 'Interceptions', 'kind': 'count',
                    'status': MODELED},
    ('qb', 'sacks'): {'label': 'Sacks taken', 'kind': 'count',
                      'status': MODELED},
    ('qb', 'scr'): {'label': 'Scrambles', 'kind': 'count', 'status': MODELED},
    ('qb', 'rush_opp'): {'label': 'Rush attempts', 'kind': 'count',
                         'status': MODELED},
    ('qb', 'ryds'): {'label': 'Rushing yards', 'kind': 'yards',
                     'status': PROVISIONAL,
                     'caveat': 'QB V1 draws yards per rush from the passer\'s '
                               'own history mixed with the positional pool. '
                               'It is adjudicated, unlike the RB control.'},
    ('qb', 'rtd'): {'label': 'Rushing TD', 'kind': 'count',
                    'status': PROVISIONAL,
                    'caveat': 'TD2 pooled positional control, governance '
                              'HOLD_TENTATIVE'},

    ('receiving', 'targets'): {'label': 'Targets', 'kind': 'count',
                               'status': MODELED},
    ('receiving', 'receptions'): {'label': 'Receptions', 'kind': 'count',
                                  'status': MODELED},
    ('receiving', 'receiving_yards'): {
        'label': 'Receiving yards', 'kind': 'yards', 'status': PROVISIONAL,
        'caveat': 'RC1 baseline; the frozen governance on this layer is '
                  'SIGNAL_WEAK with a declared CALIBRATION_DEFECT'},
    ('receiving', 'receiving_td'): {
        'label': 'Receiving TD', 'kind': 'count', 'status': PROVISIONAL,
        'caveat': 'TD2 pooled positional control, governance HOLD_TENTATIVE'},

    ('rushing', 'carries'): {'label': 'Carries', 'kind': 'count',
                             'status': MODELED},
    ('rushing', 'rushing_td'): {
        'label': 'Rushing TD', 'kind': 'count', 'status': PROVISIONAL,
        'caveat': 'TD2 pooled positional control, governance HOLD_TENTATIVE'},
}

# Named absences. A reader is told the quantity exists as a question and that
# this model declines to answer it, which is a different statement from the
# player having no projection.
UNSUPPORTED = {
    ('rushing', 'rushing_yards'): {
        'label': 'Rushing yards (RB/WR/TE)', 'status': UNAVAILABLE,
        'code': 'RUSHING_CONVERSION_CONTROL_UNDEFINED',
        'reason': 'No governed control exists for carry -> rushing yards. '
                  'Three owner decisions are open (see '
                  'nfl/production/nonqb/rushing_inventory.json). The obvious '
                  'substitute, carries x yards-per-carry, is named in '
                  'layers.py as the prohibited implementation and is not '
                  'computed here.',
        'affects': ('RB', 'WR', 'TE')},
    ('receiving', 'air_yards'): {
        'label': 'Air yards / aDOT', 'status': UNAVAILABLE,
        'code': 'NO_AIR_YARDS_LAYER',
        'reason': 'V1 forecasts no air-yards distribution.',
        'affects': ('WR', 'TE', 'RB')},
    ('qb', 'rating'): {
        'label': 'Passer rating', 'status': UNAVAILABLE,
        'code': 'NO_RATE_COMPOSITE_LAYER',
        'reason': 'A composite of forecast components is not itself a '
                  'forecast distribution and would misstate its own '
                  'uncertainty.',
        'affects': ('QB',)},
}

# Which layers a position can draw from at all.
POSITION_LAYERS = {
    'QB': ('qb',),
    'RB': ('rushing', 'receiving'),
    'WR': ('receiving',),
    'TE': ('receiving',),
}

POSITION_ORDER = ('QB', 'RB', 'WR', 'TE')


def label(layer, key):
    spec = SUPPORTED.get((layer, key))
    return spec['label'] if spec else f'{layer}/{key}'


def status_of(layer, key):
    spec = SUPPORTED.get((layer, key))
    if spec:
        return spec['status'], spec.get('caveat')
    miss = UNSUPPORTED.get((layer, key))
    if miss:
        return UNAVAILABLE, miss['reason']
    return UNAVAILABLE, f'{layer}/{key} is not a declared V1 output'


def unavailable_for(position):
    """Every named absence that applies to this position."""
    return [dict(v, metric=f'{k[0]}/{k[1]}')
            for k, v in sorted(UNSUPPORTED.items())
            if position in v['affects']]
