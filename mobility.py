"""Movement policy for the arena's independent torso, legs and jet controls."""
import math


class Movement:
    def __init__(self, arena, slot):
        self.arena = arena
        self.side = 1 if slot % 2 else -1
        self.sprinting = False
        self.jump_at = 0

    def duel(self, obs, enemy, goal, purpose, action, recovering=False, opponents=1):
        me, zone, now = obs["self"], obs["zone"], obs["t"]
        x, y, z = me["pos"]
        ex, ey, _ = enemy["pos"]
        dx, dy = ex - x, ey - y
        distance = max(0.01, math.hypot(dx, dy))
        if distance > 180 or not me["in_zone"]:
            return
        # Keep moving while the torso stays on the game's opponent. Shorter circles suit lightning.
        has_lightning = any(w and w["kind"] == "lightning" for w in me["weapons"])
        ideal = 30 if has_lightning else 47
        if recovering and enemy.get("hp", 1000) > me["max_hp"] * 0.3:
            ideal = max(ideal, 95)
        if opponents >= 3:
            ideal += 22
        radial = max(-1.0, min(1.35, (distance - ideal) / 29))
        dx, dy = dx / distance, dy / distance
        collecting = purpose in ("cube", "weapon", "drop")
        if collecting:
            # Finishing the last few metres matters: pickups have a vertical
            # limit, and the drop capture clock needs four continuous seconds.
            goal_dist = math.dist((x, y), goal)
            if goal_dist < 17 or action["jump"] or (action["boost"] and not me["grounded"]):
                return
            goal_weight = 3.2 if purpose == "drop" else 2.5
        else:
            goal_weight = 0.12
        gx, gy = action["move"]
        candidates = []
        for side in (self.side, -self.side):
            vx = radial * dx - side * dy + goal_weight * gx
            vy = radial * dy + side * dx + goal_weight * gy
            size = max(math.hypot(vx, vy), 0.001)
            vx, vy = vx / size, vy / size
            cost = 0 if side == self.side else 4
            ahead = z
            for step in (6, 13, 22):
                px, py = x + step * vx, y + step * vy
                height = self.arena.height[self.arena.cell(px, py)]
                ahead = max(ahead, height)
                cost += max(0, height - z - 2) * 1.7
                cost += max(0, z - height - 7) * 0.24
                cost += 3 * max(0, math.dist((px, py), zone["center"]) - zone["radius"] + 4)
            candidates.append((cost, side, vx, vy, ahead))
        _, self.side, vx, vy, ahead = min(candidates)
        energy = me["energy"] / max(1, me["max_energy"])
        if energy < 0.25:
            self.sprinting = False
        elif energy > 0.80:
            self.sprinting = True
        obstacle = ahead - z > 2
        jump = me["grounded"] and energy > 0.35 and now >= self.jump_at
        if jump:
            self.jump_at = now + (1.4 if obstacle else 2.6)
        action.update(move=[vx, vy], jump=jump,
                      boost=(self.sprinting and me["grounded"]) or (obstacle and energy > 0.2))
