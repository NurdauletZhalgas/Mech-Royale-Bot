# Mech-Royale-Bot

Team **anti-67** is competing for first place in Mech Royale. Builders scores each match as `16 - place` and averages the points across matches.

The selected competition entry is [`495ba6e`](https://github.com/NurdauletZhalgas/Mech-Royale-Bot/commit/495ba6ef9236922c543b215ff451f65f8fae6934). It scored **5.06** across 48 official practice matches on November 21, 2026. The Dockerfile and all files it copies on `main` match that submission.

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
| Finish pickups and supply captures during encounters | `495ba6e` | **5.06** | `BB-A1849301` |
| Adjust energy use and encounter distance | `256e3ae` | 4.98 | `BB-8BD2A3E1` |
| Prioritize the shrinking circle | `879f19d` | 4.71 | `BB-6892A2E6` |
| Value cube piles by upgrade and prioritize the circle in the final three | `81de681` | 4.96 | `BB-89CFB778` |
| Search for a second weapon during the opening | `84aed5b` | 4.94 | Reported by anti-67 |

`python check/objectives.py` runs short single-objective trials using an approximate movement grid and the kit's timing and energy settings. Use `--seed` to change layouts and `--trials` to change the sample count. The test reports travel and capture times with no opponents.

## Competition plan

The final rewards the highest average placement score over 64 free-for-all matches on fresh seeds. Practice uses 15 cooperating house mechs. Use the best scored commit as the baseline, compare changes on matched local scenarios, and record official results for each candidate. The rules allow four submissions per rolling hour.

## Placement strategy candidate

This branch starts from the 5.06 entry. While the field is stable it uses that bot’s approach to encounters. When rivals are eliminating each other, an injured bot inside the circle can let its regeneration timer run. Incoming damage, a close rival, or a vulnerable rival within reach cancels the pause. Announced supply drops offer three cubes and a full repair, so the bot credits the distance it can cover before landing. When the last circle closes, it keeps its movement pointed into the safe area whenever its projected position is at risk.

| Matched local scenario | 5.06 entry | Placement candidate |
| --- | ---: | ---: |
| Announced drop captured within 7 seconds of landing, stationary rival, 96 layouts | 59 | 89 |
| Storm HP lost on average in the final shrink, 3 survivors, 32 open-ground layouts | 548.4 | 0.0 |

Reproduce the scenarios with `python check/objectives.py --announced --opponent --seed 945837 --trials 96` and `python check/closing_circle.py --alive 3 --seed 99467 --trials 32`. Both accept `--bot-root` for testing a different checkout on identical layouts. Opponents in these movement drills deal no damage. `python check/placement.py` exercises the recovery decision in 11 controlled game states. Official placement comes from the Builders scorer.

The exact game mechanics and message formats are in [protocol.md](protocol.md). The event brief is on the [Mech Royale track page](https://www.joinbuilders.org/buildathon/tracks/builders).
