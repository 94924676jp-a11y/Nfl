from nfl.tools import player_prior, proj_v1 as V, forward_chain as FC
panel = player_prior.load_panel().value
roster = player_prior.position_index()
pos_map, inferred = FC.positions_for_chain(panel, roster)
for through in (2025,):
    # season-level map as the harness uses for allocation (roster, else usage-inferred for that season)
    class M(dict):
        pass
    # depth_shares takes pos_of.get(g): use a per-gsis map from the latest season <= through
    aug = dict(roster)
    for (g, s), p in sorted(pos_map.items(), key=lambda x: x[0][1]):
        if g not in roster and s <= through:
            aug[g] = p
    a = V.depth_shares(panel, roster, through=through); b = V.depth_shares(panel, aug, through=through)
    for pos in ('RB', 'WR', 'TE'):
        ra, rb = a[pos]['by_rank'], b[pos]['by_rank']
        print(through, pos, 'n_club_weeks', a[pos]['n_club_weeks'], b[pos]['n_club_weeks'], ' appearance_rate roster-only vs all:',
              ' '.join(f"r{k}:{ra.get(f'rank_{k}',{}).get('appearance_rate')}/{rb.get(f'rank_{k}',{}).get('appearance_rate')}" for k in range(1, 7)))
