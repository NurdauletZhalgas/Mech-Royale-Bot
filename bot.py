"""First practice candidate. Use quiet openings to earn the first cube upgrade."""
import math

import mechfight as mf
from example_bot import Bot as Starter


class Bot(Starter):
    name = "first-cube"

    def __init__(self, hello: mf.Hello):
        super().__init__(hello)
        self.crate_height = hello["config"]["crates"]["height"]
        self.regen_delay = hello["config"]["mech"]["regen_delay"]
        self.first_shrink = hello["config"]["zone"]["phases"][0]["hold_s"]
        self.last_damage = -math.inf
        self.target_id = None
        self.target_since = 0.0
        self.abandoned = set()

    def act(self, obs: mf.Observation) -> mf.Action:
        action = super().act(obs)
        me = obs["self"]
        now = obs["t"]
        if any(event["type"] == "damaged" for event in obs["events"]):
            self.last_damage = now
        if (me["cubes"] or now >= self.first_shrink or not me["in_zone"]
                or obs["mechs"] or now - self.last_damage < self.regen_delay):
            self.target_id = None
            return action

        # Bound the cost of following a pickup behind a wall or on a ledge.
        if self.target_id is not None and now - self.target_since > 6.0:
            self.abandoned.add(self.target_id)
            self.target_id = None

        x, y, z = me["pos"]
        zone = obs["zone"]
        for kind, items in (("cube", obs["cubes"]), ("crate", obs["crates"])):
            nearby = []
            for item in items:
                ix, iy, iz = item["pos"]
                distance = math.hypot(ix - x, iy - y)
                if item["id"] in self.abandoned or abs(iz - z) > 4 or distance > 40:
                    continue
                # Leave time to walk from the detour to the next circle.
                return_distance = max(0.0, math.dist((ix, iy), zone["next_center"]) - zone["next_radius"])
                travel_time = (distance + return_distance) / me["stats"]["walk_speed"]
                if now + travel_time + 6 < zone["shrink_end"]:
                    nearby.append((distance, item["id"], item))
            if not nearby:
                continue

            distance, item_id, item = min(nearby, key=lambda entry: entry[:2])
            if item_id != self.target_id:
                self.target_id, self.target_since = item_id, now
            ix, iy, iz = item["pos"]
            yaw = math.atan2(iy - y, ix - x)
            direction = 1
            pitch = 0.0
            fire = False
            if kind == "crate":
                # Give the starter gun a clear downward angle at close range.
                direction = -1 if distance < 12 else 0 if distance < 20 else 1
                pitch = math.atan2(iz + self.crate_height / 2 - z - me["stats"]["muzzle_height"], distance)
                yaw_error = math.remainder(yaw - me["aim"][0], math.tau)
                fire = abs(yaw_error) < 0.06 and abs(pitch - me["aim"][1]) < 0.06
            action.update(move=[direction * math.cos(yaw), direction * math.sin(yaw)],
                          aim=[yaw, pitch], fire=[fire, False], jump=False, boost=False)
            mf.draw.label(f"first {kind} {item_id}")
            return action

        self.target_id = None
        return action


if __name__ == "__main__":
    mf.run(Bot)
