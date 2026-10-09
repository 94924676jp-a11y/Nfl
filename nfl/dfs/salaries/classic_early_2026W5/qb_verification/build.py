import csv,gzip,json,collections,hashlib,os,sys
RAW='/home/user/nfl/nfl/dfs/salaries/raw/classic_early_2026W5/'
OUT=sys.argv[1]
INJ=RAW+'NFLVERSE_INJURIES_2026.21e35d2a84353248.slate16.csv.gz'
DC=RAW+'NFLVERSE_DEPTH_CHARTS_2026_LATEST.fa165ba061c4bbe8.slate16.csv.gz'
GM=RAW+'NFLVERSE_GAMES_2026.368c6c5011f078ae.slate16.csv.gz'
PBP=RAW+'NFLVERSE_PBP_2026.e7c162e793cb0f82.csv.gz'
SUP=RAW+'NEWS_SUPPLEMENT_WEB_2026-10-09.b3ee915757230e90.json'
RET='2026-10-09T15:40Z..16:15Z (WebSearch session)'
CHECKED='2026-10-09T16:14Z'
rd=lambda f: list(csv.DictReader(gzip.open(f,'rt')))
inj=rd(INJ); dc=rd(DC); gm=rd(GM)
teams=['CHI','GB','CIN','MIA','LV','NE','MIN','NO','CLE','NYJ','IND','PIT','HOU','TEN','NYG','WAS']
opp={}
for r in gm:
    if r['week']=='5' and r['gametime']=='13:00':
        opp[r['away_team']]=('@'+r['home_team'],r['away_qb_name']); opp[r['home_team']]=('vs '+r['away_team'],r['home_qb_name'])
att=collections.defaultdict(collections.Counter)
for r in csv.DictReader(gzip.open(PBP,'rt')):
    if r.get('pass_attempt')=='1' and r.get('passer_player_name') and r['posteam'] in teams and r.get('sack')!='1':
        att[(r['posteam'],int(r['week']))][r['passer_player_name']]+=1
qbs={t:sorted([r for r in dc if r['team']==t and r['pos_abb']=='QB'],key=lambda r:int(r['pos_rank'])) for t in teams}
w5={(r['team'],r['full_name']):r for r in inj if r['week']=='5' and r['position']=='QB'}
def prac(t):
    out=[]
    for q in qbs[t]:
        r=w5.get((t,q['player_name']))
        if r: out.append({'qb':q['player_name'],'dc_rank':int(q['pos_rank']),'week5_practice':f"{r['practice_status']} ({r['practice_primary_injury']})",'week5_game_status':r['report_status'] or 'BLANK (no game designation in capture)'})
        else: out.append({'qb':q['player_name'],'dc_rank':int(q['pos_rank']),'week5_practice':'NOT LISTED on week-5 report in capture','week5_game_status':'BLANK'})
    return out
REPO_INJ={'tier':'REPOSITORY_GSIS_DERIVED','tier_note':'nflverse copy of the official practice report; practice participation only, NOT a game designation and NOT a starter announcement; latest practice day only (day not identified in file); captured 2026-10-09T13:30Z per PROVENANCE.json','source':'nflverse injuries','url_or_path':INJ}
def E(tier,claim,src,url,pub,ret=RET): return {'tier':tier,'claim':claim,'source':src,'url_or_path':url,'published':pub,'retrieved':ret}
S='SECONDARY'
ev={
'CHI':[
 E(S,"Ben Johnson on ESPN 1000 (Mon 2026-10-05): 'Tyson will be the guy'; Williams (Grade 2 hamstring) out vs GB. Coach statement seen ONLY via relays; radio interview, not a press conference; not read first-hand.","Chicago Sun-Times","https://chicago.suntimes.com/bears/2026/10/05/bears-rule-out-qb-caleb-williams-vs-packers-will-start-backup-tyson-bagent-again","2026-10-05"),
 E(S,"Same quote relayed: 'Tyson will be the guy,' Johnson told ESPN 1000's Jeff Joniak.","theScore","https://www.thescore.com/nfl/news/3615988/bears-coach-johnson-names-bagent-starter-vs-packers","not shown"),
 E(S,"Johnson tells ESPN1000 Bagent expected to start vs Packers.","ABC7 Chicago","https://abc7chicago.com/post/chicago-bears-coach-ben-johnson-tells-espn1000-quarterback-tyson-bagent-expected-start-green-bay-packers-sunday/19910474/","not shown"),
 E(S,"Williams to miss Week 5; Bagent set for second start.","CBS Sports","https://www.cbssports.com/nfl/news/caleb-williams-to-miss-bears-week-5-rivalry-packers-tyson-bagent/","not shown"),
 E(S,"Bagent expected to start Week 5 vs Packers.","NBC Sports / PFT","https://www.nbcsports.com/nfl/profootballtalk/rumor-mill/news/tyson-bagent-is-expected-to-start-week-5-vs-packers","not shown"),
 E(S,"Bagent will start Week 5 vs Packers.","NBC Sports/Rotoworld (via earlier supplement)","https://www.nbcsports.com/fantasy/football/player-news/2026-10-05/tyson-bagent-will-start-in-week-5-against-packers","2026-10-05",'2026-10-09T13:43Z (supplement)'),
 E(S,"Johnson said Williams won't practice this week; 'week-to-week'.","SI (betting)","https://www.si.com/betting/concerning-caleb-williams-injury-update-doesnt-hurt-bears-odds-vs-packers-in-nfl-week-5","not shown"),
 E(S,"Search summary: Packers' Oct 8 injury report lists Williams DNP Wed and Thu. Club page NOT read (snippet only) so not upgraded.","packers.com (snippet)","https://www.packers.com/news/packers-bears-injury-report-oct-8-2026","2026-10-08 (from URL)"),
 E(S,"Case Keenum is Bagent's backup.","Chicago Sun-Times (via search summary)","https://chicago.suntimes.com/bears/2026/10/05/bears-rule-out-qb-caleb-williams-vs-packers-will-start-backup-tyson-bagent-again","2026-10-05"),
 dict(REPO_INJ,claim="Caleb Williams week 5: Did Not Participate (Hamstring); report_status blank. Bagent, Keenum not listed."),
 {'tier':'REPOSITORY_GSIS_DERIVED','claim':"PBP: W4 vs NYJ all 34 attempts by T.Bagent; W3 all 34 by C.Keenum; Williams W1-W2.",'source':'nflverse pbp','url_or_path':PBP,'published':'capture 2026-10-09T13:29Z','retrieved':'repo'},
 {'tier':'REPOSITORY_LISTING','claim':"nflverse schedule lists Tyson Bagent as CHI QB for week 5 (listing, not announcement). NOTE: same file lists Case Keenum as CHI W4 QB while PBP shows Bagent threw all 34 W4 attempts -- schedule QB field unreliable for CHI.",'source':'nflverse games','url_or_path':GM,'published':'capture','retrieved':'repo'},
 {'tier':'NOT_FOUND','claim':f"Friday 2026-10-09 official Bears/NFL injury report with game designations: NOT FOUND as of {CHECKED} (~12:14 ET; normally released Friday afternoon ET). WebFetch nfl.com/injuries and chicagobears.com failed: getaddrinfo ENOTFOUND.",'source':'nfl.com / chicagobears.com','url_or_path':'https://www.nfl.com/injuries/league/2026/reg5 ; https://www.chicagobears.com/news/injury-report','published':'n/a','retrieved':CHECKED},
],
'GB':[E(S,"Love described as healthy in Week 5 preview.","DK Network","https://dknetwork.draftkings.com/?p=454802","not shown"),
      E(S,"Week 4: Love 22/30.","Sharp Football Analysis","https://www.sharpfootballanalysis.com/?p=130374","not shown"),
      E(S,"No 2026 result shows Love injured or replaced (earlier supplement; tracker checked 2026-09-27).","Legion Report","https://legionreport.com/is-jordan-love-playing/","checked 2026-09-27",'2026-10-09T13:43Z (supplement)')],
'CIN':[E(S,"Burrow on Bengals' Wednesday Week 5 report with knee, full practice. CONFLICTS with nflverse capture, which has no Burrow week-5 row; unreconciled.","AtoZ Sports","https://atozsports.com/nfl/cincinnati-bengals-news/bengals-wednesday-injury-report-week-5-at-dolphins-jamarr-chase-tee-higgins-dexter-lawrence/","not shown"),
       E(S,"No Week 5 designation, has not missed a game; no explicit team statement.","StatChasers (supplement)","https://statchasers.com/nfl/players/joe-burrow/injury/","checked 2026-10-08",'2026-10-09T13:43Z (supplement)')],
'MIA':[E(S,"Willis named Dolphins starter Sept 8; no Week 5 change found (none found today either).","Fantasy Nerds (supplement)","https://fantasynerds.com/news/story/2026/09/08/malik-willis-named-dolphins-starting-qb-reflects-on-journey-1617255","2026-09-08",'2026-10-09T13:43Z (supplement)')],
'LV':[E(S,"Raiders named Cousins starter over Mendoza (August).","NFL.com (supplement)","https://www.nfl.com/news/raiders-name-kirk-cousins-starting-fernando-mendoza-officially-backup","not shown (Aug)",'2026-10-09T13:43Z (supplement)'),
      E(S,"AP preview treats Cousins as Week 5 starter.","AP via Bozeman Daily Chronicle (supplement)","https://www.bozemandailychronicle.com/wire/sports/kirk-cousins-and-raiders-look-to-build-on-fast-start-against-patriots-defense-dealing-with/article_c61530c9-88c8-5c9e-b2eb-a5ed5c231827.html","not shown",'2026-10-09T13:43Z (supplement)'),
      E(S,"Tracker found no designation for Cousins (checked Oct 5).","Legion Report","https://legionreport.com/is-kirk-cousins-playing/","checked 2026-10-05")],
'NE':[E(S,"Maye (right shoulder) full participant all practice days prior week; played W4. Week 5 listed with shoulder, full Thursday.","Boston Globe / Patriots.com (supplement, snippet)","https://www.bostonglobe.com/2026/10/02/sports/mike-vrabel-drake-maye-shoulder/ ; https://www.patriots.com/news/week-5-injury-report-patriots-vs-raiders","2026-10-02 / not shown",'2026-10-09T13:43Z (supplement)')],
'MIN':[E(S,"Murray expected to start Week 5; not on Week 5 report; started W3, W4.","Star Tribune / Vikings.com (supplement)","https://www.startribune.com/minnesota-vikings-new-orleans-saints-week-5-kyler-murray-stats-kevin-oconnell-offense-jj-mccarthy/601897922","not shown",'2026-10-09T13:43Z (supplement)'),
       E(S,"Search today found no current Murray injury item; Week 1 concussion history.","Bolavip","https://bolavip.com/en/nfl/vikings-hc-kevin-oconnell-provides-injury-update-on-kyler-murray-after-concussion-vs-packers","Week 1 (old)")],
'NO':[E(S,"Shough (left, non-throwing hand) limited Wednesday; says 'it's not going to limit me really at all', expects to play.","Fantasy Footballers / Field Level Media","https://www.thefantasyfootballers.com/news/641222/tyler-shough-limited-with-left-hand-issue/ ; https://fieldlevelmedia.com/news/saints-qb-tyler-shough-dealing-with-sore-left-hand-expects-to-play-sunday/","not shown"),
      E(S,"Wednesday status CONFLICTS across outlets (limited vs full vs sat out); starter role not in dispute.","SI / Vikings.com (supplement)","https://www.vikings.com/news/saints-injury-report-week-5-2026-nfl-season","not shown",'2026-10-09T13:43Z (supplement)')],
'CLE':[E(S,"Watson expected starter; won job in August; first-team reps Oct 7; Monken: starting QB isn't week-to-week issue.","Forbes / ClevelandBrowns.com photo gallery (supplement)","https://www.forbes.com/sites/johncassillo/2026/10/08/nfl-week-5-storylines-can-browns-match-best-start-since-1999-return/ ; https://www.clevelandbrowns.com/photos/browns-practice-for-2026-week-5-matchup-vs-jets","2026-10-08 / 2026-10-07",'2026-10-09T13:43Z (supplement)'),
       E(S,"Browns Wednesday report: QB Dillon Gabriel (back) FP; no other QB listed.","AtoZ / search summary","https://atozsports.com/?p=501327","not shown")],
'NYJ':[E(S,"Geno Smith is the starter; no Week 5 change found. Jets Wednesday report lists no QB.","NBC Sports/Rotoworld (supplement); newyorkjets.com (snippet)","https://www.nbcsports.com/fantasy/football/player-news/2026-10-04/geno-has-8-completions-in-week-4-loss ; https://www.newyorkjets.com/news/jets-injury-report-week-5-vs-browns-wednesday-10-07-2026","2026-10-04 / 2026-10-07")],
'IND':[E(S,"Daniel Jones gave Week 5 press conference; not on injury report.","Colts.com video / FOX59 (supplement)","https://www.colts.com/video/daniel-jones-colts-vs-steelers-week-5","not shown",'2026-10-09T13:43Z (supplement)')],
'PIT':[E(S,"Rodgers on no Week 5 report; no QB change found.","NBC Sports/Rotoworld; Steelers.com (supplement)","https://www.nbcsports.com/fantasy/football/player-news/2026-10-01/aaron-rodgers-steelers-fall-to-2-2-in-loss-to-cle ; https://www.steelers.com/news/week-5-injury-report-colts","2026-10-01 / not shown",'2026-10-09T13:43Z (supplement)')],
'HOU':[E(S,"Stroud on no Week 5 report; no QB change found.","Sharp Football Analysis (supplement)","https://www.sharpfootballanalysis.com/fantasy/texans-titans-week-5-fantasy-football-preview-nfl-worksheet-rich-hribar-2026/amp/","not shown",'2026-10-09T13:43Z (supplement)')],
'TEN':[E(S,"Week 5 preview lists Cam Ward as Titans QB.","Stats Insider","https://www.statsinsider.com.au/news/titans-vs-texans-prediction-and-preview-nfl-week-5-2026","not shown"),
       E(S,"Ward started W4 at BAL; no Week 5 injury listing found.","FantasyData (supplement)","https://fantasydata.com/nfl/boxscore/19504-tennessee-titans-vs-baltimore-ravens-week-4-2026","2026-10-04",'2026-10-09T13:43Z (supplement)')],
'NYG':[E(S,"Harbaugh: 'He'll be the starter' (Winston); Dart out for regular season.","Giants.com / FOX Sports Radio NJ (supplement)","https://www.giants.com/news/jaxson-dart-to-miss-rest-of-regular-season-jameis-winston-to-start-quarterback-injury-john-harbaugh ; https://foxsportsradionewjersey.com/2026/10/02/giants-to-start-jameis-winston-again-j-j-mccarthy-will-be-backup-for-now/","Sept / 2026-10-02",'2026-10-09T13:43Z (supplement)'),
       E(S,"Winston expected to start at WAS; Harbaugh suggested McCarthy could be QB2; role not settled.","Sharp Football Analysis / Yardbarker","https://www.sharpfootballanalysis.com/fantasy/giants-commanders-week-5-fantasy-football-preview-nfl-worksheet-rich-hribar-2026/","not shown"),
       E(S,"QB2 CONFLICT: McCarthy listed QB2 (ClutchPoints) vs McCarthy-or-Haener emergency QB3 (Yardbarker); Haener roster status conflicting.","ClutchPoints / Yardbarker / Larry Brown Sports (supplement)","https://clutchpoints.com/nfl/new-york-giants/giants-news-jj-mccarthy-officially-listed-qb2-new-york-week-5-depth-chart","not shown",'2026-10-09T13:43Z (supplement)')],
'WAS':[E(S,"Commanders Week 5 report (snippet): Daniels left elbow Full Wed, Full Thu; Mariota knee DNP Wed, DNP Thu; Friday columns blank. Club page NOT read first-hand.","commanders.com (snippet)","https://commanders.com/news/commanders-vs-giants-week-5-injury-report","not shown"),
       E(S,"Team/OC: Daniels 'full go'; Quinn expects him to start barring setback; Daniels said decision is ultimately his.","theScore / SI / Yardbarker","https://www.thescore.com/nfl/news/3618375/commanders-daniels-full-go-for-week-5-vs-giants ; https://www.yardbarker.com/nfl/articles/updates_emerge_on_jayden_daniels_marcus_mariota_for_week_5_game_vs_giants/s1_13132_44388827","not shown"),
       E(S,"Mariota right knee MCL sprain, multi-week; if Daniels and Mariota cannot go, rookie Athan Kaliakmanis starts.","TSN / Fantasy Footballers","https://www.tsn.ca/nfl/article/commanders-mariota-sidelined-with-mcl-sprain-while-daniels-preps-to-practice-n1-50112842/ ; https://www.thefantasyfootballers.com/news/640903/marcus-mariota-mcl-sprain-confirmed/","not shown"),
       {'tier':'NOT_FOUND','claim':f"Friday 2026-10-09 Commanders game designations NOT FOUND as of {CHECKED}.",'source':'search','url_or_path':'n/a','published':'n/a','retrieved':CHECKED}],
}
expected={'CHI':'Tyson Bagent','GB':'Jordan Love','CIN':'Joe Burrow','MIA':'Malik Willis','LV':'Kirk Cousins','NE':'Drake Maye','MIN':'Kyler Murray','NO':'Tyler Shough','CLE':'Deshaun Watson','NYJ':'Geno Smith','IND':'Daniel Jones','PIT':'Aaron Rodgers','HOU':'C.J. Stroud','TEN':'Cam Ward','NYG':'Jameis Winston','WAS':'Jayden Daniels'}
backup={'CHI':('Case Keenum','DC rank 3; DC rank 1 Williams is DNP and reported out, so Keenum is effective QB2'),
 'WAS':('Athan Kaliakmanis','DC rank 2 Mariota DNP Wed/Thu (knee MCL); Kaliakmanis (DC rank 3) threw 33 of 37 W4 attempts and is effective QB2'),
 'NYG':('J.J. McCarthy','DC rank 2; QB2 vs Haener is CONFLICTING in secondary sources')}
scen={'WAS':(True,'Daniels returning from dislocated elbow, first game back; Friday designation not out; Mariota DNP; Kaliakmanis is the plausible alternate starter.'),
 'CHI':(False,'Williams starting is implausible (DNP all week, coach-relayed ruling). Not CONFIRMED_OFFICIAL: re-check Friday designation; flip to true if Williams is NOT listed Out or Bagent appears on the report.')}
status={t:'REPORTED_SECONDARY_CONSISTENT' for t in teams}
notes={'CIN':'Secondary (AtoZ) says Burrow on Wed report with knee, full; nflverse capture has no Burrow week-5 row. Injury-listing conflict, not a starter conflict.',
 'NO':'Wed practice status conflicting across outlets; capture shows Full (Hand). Starter not in dispute.',
 'MIA':'Only positive naming found is Sept 8; continuity inferred from W1-W4 PBP and absence from report.',
 'GB':'Positive secondary naming is thin (preview copy). Rests mainly on PBP continuity and absence from report.',
 'CLE':'Depth chart QB4 Dillon Gabriel on report (back, Full); not relevant to starter.'}
res={'meta':{'built_utc':CHECKED,'slate':'NFL 2026 Week 5, Sunday 2026-10-11 13:00 ET, 8 games','tier_rules':'Only OFFICIAL can confirm. No OFFICIAL document was read first-hand: WebFetch of nfl.com and chicagobears.com failed (getaddrinfo ENOTFOUND); club-site pages seen only as search snippets are labelled SECONDARY. REPOSITORY_GSIS_DERIVED = nflverse capture of the official practice report; used as practice data only, never upgraded to a starter confirmation.',
 'friday_official_report':f'NOT FOUND for any club as of {CHECKED} (~12:14 ET). Friday game designations are normally released Friday afternoon ET; they had very likely not been published yet. Re-check required.',
 'result':'0 of 16 CONFIRMED_OFFICIAL. 16 REPORTED_SECONDARY_CONSISTENT. 1 scenario_needed (WAS).',
 'repo_inputs':[INJ,DC,GM,PBP,SUP,'/home/user/nfl/nfl/dfs/salaries/classic_early_2026W5/WEEK5_QB_REGIME_BOARD.json']},'clubs':{}}
for t in teams:
    q=qbs[t]; w4=att[(t,4)]
    b=backup.get(t,(q[1]['player_name'],'depth-chart pos_rank 2'))
    s=scen.get(t,(False,'Expected starter took every/most W4 attempts, no adverse report, no competing QB named.'))
    res['clubs'][t]={'game':f"{t} {opp[t][0]}",'expected_starter':expected[t],'status':status[t],
     'depth_chart_qb1_capture':q[0]['player_name'],'depth_chart_capture_dt':q[0]['dt'],
     'depth_chart_qbs':[f"{x['pos_rank']}:{x['player_name']}" for x in q],
     'schedule_listed_qb_week5':opp[t][1],
     'week5_practice_lines':prac(t),
     'last_game_week4_attempt_leader':(w4.most_common(1)[0][0]+f" ({w4.most_common(1)[0][1]} att)") if w4 else 'NONE',
     'week4_attempts_all':dict(w4),
     'backup_qb':b[0],'backup_basis':b[1],
     'scenario_needed':s[0],'scenario_reason':s[1],'note':notes.get(t,''),
     'evidence':ev[t]+([] if t=='CHI' else [dict(REPO_INJ,claim='See week5_practice_lines for this club.'),{'tier':'REPOSITORY_GSIS_DERIVED','claim':'Week-4 attempt leader from PBP; see week4_attempts_all.','source':'nflverse pbp','url_or_path':PBP,'published':'capture 2026-10-09T13:29Z','retrieved':'repo'}])}
json.dump(res,open(OUT,'w'),indent=1)
for t in teams:
    c=res['clubs'][t]; print(t,c['expected_starter'],c['status'],c['depth_chart_qb1_capture'],c['last_game_week4_attempt_leader'],c['backup_qb'],c['scenario_needed'])
