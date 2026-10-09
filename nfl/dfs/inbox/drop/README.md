# Drop your manual exports here

Any file name is fine. Each file is recognised by its own header, not its name:

| You download | From | It becomes |
|---|---|---|
| DKSalaries.csv | DraftKings, the contest's salary export | DK ids and salaries for the slate (`DK_SALARIES`) |
| DKEntries.csv | DraftKings, the entries export for your upcoming lineups | your entries, read only (`DK_ENTRIES`, private) |
| contest-standings-NNNN.csv | DraftKings, the standings export once the contest is final | postgame grading and realised ownership (`DK_CONTEST_STANDINGS`, postlock only) |
| Fantasy Cruncher players CSV | Fantasy Cruncher, the player-pool export | benchmark only, never a model input (`FC_PLAYERS_EXPORT`) |

Then run `python3.12 nfl/integrations/inbox.py`. The original file is never changed or deleted; a second copy
of the same bytes is ignored. A file that is not recognised is refused with a named code and appears on the
status page. Nothing here uploads, enters, edits or pays for anything.

Menu names on DraftKings and Fantasy Cruncher are not documented by either company and may change; the file
is recognised by its columns either way.
