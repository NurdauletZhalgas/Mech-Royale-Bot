"""Choose when the shrinking circle must take priority over a detour or duel."""
import math


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
