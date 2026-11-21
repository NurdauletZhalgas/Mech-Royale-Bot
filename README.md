# Mech-Royale-Bot

Future winner of buildathon

The track scores mean placement across matches. First place earns 15 points and sixteenth earns zero. The organizers list the Python starter at **1.15**. Our first experiment asks whether collecting an early cube improves that score.

## Bots

- `example_bot.py` runs the official Python starter. Its entry point also supports importing its behavior.
- `bot.py` runs the competition candidate. It uses `arena_map.py` to route over the supplied terrain, `economy.py` to collect upgrades and hold supply rings, and `mobility.py` to move during encounters.

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

The checker replays fixed observations. The first candidate and starter both passed locally with 300 on-time answers. The recorded route did not trigger the candidate's loot behavior. Separate constructed observations exercised cube collection decisions, crate targeting, abandoning a stalled detour, and returning to the starter behavior under pressure.

On November 21, 2026, Builders scored team **anti-67** at **1.27** over 48 practice matches for commit `75bd73e`, receipt `BB-767D6A1E`. That is 0.12 points above the published starter score and corresponds to a mean finish of about 14.73 out of 16. The receipt reports the aggregate score only.

| Candidate | Submitted commit | Official score | Receipt |
| --- | --- | ---: | --- |
| Rooftop navigation | `b75ce9a` | 0.98 | `BB-5D46B8D8` |
| Resource collection and supply drops | `81943da` | 3.98 | `BB-A993554A` |
| Movement during encounters | `edb6e1f` | 4.44 | `BB-0E869D03` |

`python check/objectives.py` runs short single-objective trials using an approximate movement grid and the kit's timing and energy settings. Use `--seed` to change layouts and `--trials` to change the sample count. The test reports travel and capture times with no opponents.

## Competition plan

1. **Get a score.** Run the image check, publish an approved public repository, and enter its URL on the track page. Record the submitted commit, score, and one-sentence description of the change.
2. **Beat 1.15 in practice.** The 15 house mechs cooperate. Hiding alone gives them little reason to die. Use the first score and any available replays to decide whether the next change should improve early upgrades, getting around buildings, or finishing one opponent before more arrive. Change one behavior per scored run. The rules allow four submissions per hour.
3. **Prepare for qualifying and the final.** Other teams fight each other on fresh seeds. Test a rule for leaving a fight while hurt and reaching a safe part of the next circle, then a rule for when to re-enter. Use observable game state so the same bot can handle both formats.
4. **Lock a reproducible entry.** The brief lists Sunday at 9 PM GMT+5 as the cutoff. Leave time for a fresh image build and a scored practice run. Verify the selected commit and keep all submitted commits publicly accessible through results.

The exact game mechanics and message formats are in [protocol.md](protocol.md). The event brief is on the [Mech Royale track page](https://www.joinbuilders.org/buildathon/tracks/builders).
