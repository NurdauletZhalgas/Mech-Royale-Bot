# Mech-Royale-Bot

Future winner of buildathon

The track scores mean placement across matches. First place earns 15 points and sixteenth earns zero. The organizers list the Python starter at **1.15**. Our first experiment asks whether collecting an early cube improves that score.

## Bots

- `example_bot.py` runs the official Python starter. Its entry point also supports importing its behavior.
- `bot.py` runs the first candidate. During the opening hold it looks for a nearby, similarly elevated cube or crate. It skips the detour when another actor is visible, after recent damage, or if the trip leaves too little time to reach the next circle. After collecting its first cube, it resumes the starter strategy.

## Run the official check

From this directory, with Python 3.9 or later on your path, run each bot against the kit's recording.

```sh
python check/check.py -- python -u example_bot.py
python check/check.py -- python -u bot.py
```

To check the submission image on a Linux Docker host, run the following from the same directory.

```sh
docker build --platform linux/amd64 -t mech-royale .
python check/check.py --map-dir /arena -- docker run --rm -i --platform linux/amd64 --network none --cpus 1 --memory 512m --read-only --tmpfs /tmp:rw,size=64m --user 65534:65534 -v "$PWD/arena:/arena:ro" mech-royale
```

The checker replays fixed observations. The first candidate and starter both passed locally with 300 on-time answers. The recorded route did not trigger the candidate's loot behavior. Separate constructed observations exercised cube collection decisions, crate targeting, abandoning a stalled detour, and returning to the starter behavior under pressure. The Docker image and official practice score are pending.

## Competition plan

1. **Get a score.** Run the image check, publish an approved public repository, and enter its URL on the track page. Record the submitted commit, score, and one-sentence description of the change.
2. **Beat 1.15 in practice.** The 15 house mechs cooperate. Hiding alone gives them little reason to die. Use the first score and any available replays to decide whether the next change should improve early upgrades, getting around buildings, or finishing one opponent before more arrive. Change one behavior per scored run. The rules allow four submissions per hour.
3. **Prepare for qualifying and the final.** Other teams fight each other on fresh seeds. Test a rule for leaving a fight while hurt and reaching a safe part of the next circle, then a rule for when to re-enter. Use observable game state so the same bot can handle both formats.
4. **Lock a reproducible entry.** The brief lists Sunday at 9 PM GMT+5 as the cutoff. Leave time for a fresh image build and a scored practice run. Verify the selected commit and keep all submitted commits publicly accessible through results.

The exact game mechanics and message formats are in [protocol.md](protocol.md). The event brief is on the [Mech Royale track page](https://www.joinbuilders.org/buildathon/tracks/builders).
