"""Choose when the shrinking circle must take priority over a detour or duel."""
import math


class Placement:
    """Use changes in the surviving field to decide when to bank a free heal."""

    def __init__(self, near_range):
        self.near_range = near_range
        self.alive = None
        self.last_other_elimination = -math.inf
        self.last_damage = -math.inf
        self.healing = False

    def recover(self, obs, opponents):
        me, now, alive = obs["self"], obs["t"], obs["alive"]
        own_eliminations = sum(event["type"] == "kill" for event in obs["events"])
        if self.alive is not None and self.alive - alive > own_eliminations:
            self.last_other_elimination = now
        self.alive = alive
        if any(e["type"] == "damaged" for e in obs["events"]):
            self.last_damage = now

        stats = me["stats"]
        # Compare the missing health to the value and duration of a regen window.
        missing = me["max_hp"] - me["hp"]
        worthwhile = missing >= (0.12 if self.healing else 0.24) * me["max_hp"]
        window = stats["regen_delay"] + min(12, missing / max(1, stats["regen_per_s"]))
        self.healing = (alive >= 3 and worthwhile and me["in_zone"]
                        and now - self.last_other_elimination <= window
                        and now - self.last_damage >= 0.5 * stats["regen_delay"])
        if self.healing:
            for rival in opponents:
                distance = math.dist(me["pos"], rival["pos"])
                weak = rival.get("hp", me["max_hp"]) <= 0.2 * rival.get("max_hp", me["max_hp"])
                if distance <= self.near_range or (weak and distance <= 3 * self.near_range):
                    self.healing = False
                    break
        return self.healing


def circle_priority(obs):
    zone, me, now = obs["zone"], obs["self"], obs["t"]
    r, end_r = zone["radius"], zone["next_radius"]
    pos = me["pos"][:2]
    center = zone["center"]
    end = zone["next_center"]
    if not me["in_zone"] or math.dist(pos, center) > r:
        return True
    if r <= 13:
        return True
    if r > 150 and zone["dps"] < 60:
        return False
    # Look ahead by the time this mech needs to walk back into the next
    # circle, with a turn allowance for buildings and actual acceleration.
    speed = max(1, me["stats"]["walk_speed"])
    outside_next = max(0, math.dist(pos, end) - end_r)
    horizon = 3.0 + 1.5 * outside_next / speed
    wait = max(0, zone["shrink_start"] - now)
    remaining = max(0.01, zone["shrink_end"] - max(now, zone["shrink_start"]))
    fraction = max(0, min(1, (horizon - wait) / remaining))
    fx = center[0] + fraction * (end[0] - center[0])
    fy = center[1] + fraction * (end[1] - center[1])
    future_r = r + fraction * (end_r - r)
    clearance = min(10, max(2, future_r * 0.35))
    return math.dist(pos, (fx, fy)) >= max(0, future_r - clearance)
