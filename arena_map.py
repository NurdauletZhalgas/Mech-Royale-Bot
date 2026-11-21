"""Terrain and roof heights sampled on the Mech Royale movement grid."""
import bisect
import heapq
import json
import math
import sys
from array import array
from pathlib import Path


class Arena:
    step = 6

    def __init__(self, directory):
        folder = Path(directory) / "v2"
        with (folder / "world.json").open(encoding="utf8") as stream:
            world = json.load(stream)
        terrain = world["terrain"]
        samples = array("h")
        with (folder / terrain["file"]).open("rb") as stream:
            samples.fromfile(stream, terrain["nx"] * terrain["ny"])
        if sys.byteorder != "little":
            samples.byteswap()
        self.x0 = math.ceil(world["bounds"]["minX"]) + 3
        self.y0 = math.ceil(world["bounds"]["minY"]) + 3
        self.cols = int((world["bounds"]["maxX"] - 3 - self.x0) / self.step) + 1
        self.rows = int((world["bounds"]["maxY"] - 3 - self.y0) / self.step) + 1
        xs = [self.x0 + i * self.step for i in range(self.cols)]
        ys = [self.y0 + j * self.step for j in range(self.rows)]
        tx = [round((x - terrain["minX"]) / terrain["step"]) for x in xs]
        self.ground = []
        for y in ys:
            start = round((y - terrain["minY"]) / terrain["step"]) * terrain["nx"]
            self.ground.extend(samples[start + i] * terrain["scale"] for i in tx)
        self.height = self.ground.copy()
        for prism in world["prisms"]:
            rings = [prism["ring"], *prism["holes"]]
            ring_y = rings[0][1::2]
            for row in range(bisect.bisect_left(ys, min(ring_y)), bisect.bisect_left(ys, max(ring_y))):
                y = ys[row]
                crossings = []
                for ring in rings:
                    x1, y1 = ring[-2:]
                    for v in range(0, len(ring), 2):
                        x2, y2 = ring[v], ring[v + 1]
                        if (y1 > y) != (y2 > y):
                            crossings.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
                        x1, y1 = x2, y2
                crossings.sort()
                for left, right in zip(crossings[::2], crossings[1::2]):
                    for col in range(bisect.bisect_left(xs, left), bisect.bisect_left(xs, right)):
                        i = row * self.cols + col
                        self.height[i] = max(self.height[i], prism["top"])
        self.roofs = []
        for row in range(1, self.rows - 1, 2):
            for col in range(1, self.cols - 1, 2):
                i = row * self.cols + col
                rise = self.height[i] - self.ground[i]
                if rise < 7:
                    continue
                neighbours = (i + 1, i - 1, i + self.cols, i - self.cols)
                room = sum(abs(self.height[n] - self.height[i]) < 2.0 for n in neighbours)
                if room >= 3:
                    self.roofs.append((xs[col], ys[row], rise, room))

    def cell(self, x, y):
        col = max(0, min(self.cols - 1, round((x - self.x0) / self.step)))
        row = max(0, min(self.rows - 1, round((y - self.y0) / self.step)))
        return row * self.cols + col

    def xy(self, i):
        row, col = divmod(i, self.cols)
        return self.x0 + self.step * col, self.y0 + self.step * row

    def retreat(self, pos, zone, previous):
        x, y, z = pos
        cx, cy = zone["next_center"]
        radius = zone["next_radius"]
        best_value = -math.inf
        best = (cx, cy)
        for px, py, rise, room in self.roofs:
            center_dist = math.hypot(px - cx, py - cy)
            if center_dist > max(0, radius - 6):
                continue
            travel = math.hypot(px - x, py - y)
            top = self.height[self.cell(px, py)]
            if top - z > 51 and travel < 36:
                continue
            value = (min(rise, 48) + room * 2 - 0.16 * travel
                     - 0.025 * center_dist - 0.65 * max(0, top - z - 33))
            if previous == (px, py):
                value += 6
            if value > best_value:
                best_value, best = value, (px, py)
        return best


class OpeningSearch:
    """Look for an empty slot's first pickup in nearby, unexplored sectors."""

    def __init__(self, arena, slot):
        self.arena = arena
        self.direction = slot * math.tau / 16
        self.visited = []
        self.goal = None
        self.until = 0

    def destination(self, pos, zone, now):
        x, y, z = pos
        if self.goal is not None and now < self.until and math.dist((x, y), self.goal) > 9:
            return self.goal
        self.visited.append((x, y))
        best = -math.inf
        for i in range(12):
            angle = self.direction + i * math.tau / 12
            dx, dy = math.cos(angle), math.sin(angle)
            end = self.arena.cell(x + 80 * dx, y + 80 * dy)
            target = self.arena.xy(end)
            heights = [self.arena.height[self.arena.cell(x + d*dx, y + d*dy)] for d in (18, 36, 54, 72)]
            climb = max(0.0, max(heights + [self.arena.height[end]]) - z)
            clearance = min(math.dist(target, p) for p in self.visited)
            outside = max(0, math.dist(target, zone["next_center"]) - zone["next_radius"])
            score = min(95, clearance) - 1.5 * climb - 1.8 * outside
            if score > best:
                best, self.goal = score, target
        self.direction += math.pi / 4
        self.until = now + 8.0
        return self.goal


class Route:
    """Spread grid search over decisions to stay inside the match time limit."""
    def __init__(self, arena):
        self.arena = arena
        self.goal = None
        self.path = []
        self.frontier = []
        self.next_plan = 0

    def _start(self, src, dst):
        self.goal = dst
        self.path = []
        self.parent = {src: None}
        self.cost = {src: 0}
        self.frontier = [(0, 0, src)]

    def _advance(self, dst):
        arena = self.arena
        gx, gy = arena.xy(dst)
        for _ in range(180):
            if not self.frontier:
                return
            _, cost, cell = heapq.heappop(self.frontier)
            if cost != self.cost[cell]:
                continue
            if cell == dst:
                while self.parent[cell] is not None:
                    self.path.append(cell)
                    cell = self.parent[cell]
                self.path.reverse()
                self.frontier.clear()
                return
            row, col = divmod(cell, arena.cols)
            for dx, dy in ((1,0), (-1,0), (0,1), (0,-1), (1,1), (1,-1), (-1,1), (-1,-1)):
                if not (0 <= row + dy < arena.rows and 0 <= col + dx < arena.cols):
                    continue
                n = cell + dx + dy * arena.cols
                peak = arena.height[n]
                if dx and dy:
                    # The cylinder cannot move diagonally through two touching walls.
                    peak = max(peak, min(arena.height[cell + dx], arena.height[cell + dy * arena.cols]))
                climb = max(0, peak - arena.height[cell] - 1.2)
                if climb > 48:
                    continue
                distance = arena.step * (1.4142 if dx and dy else 1)
                new_cost = cost + distance + (10 + 1.6 * climb if climb > 0 else 0)
                if new_cost >= self.cost.get(n, math.inf):
                    continue
                self.parent[n] = cell
                self.cost[n] = new_cost
                x, y = arena.xy(n)
                estimate = new_cost + 1.35 * math.hypot(x - gx, y - gy)
                heapq.heappush(self.frontier, (estimate, new_cost, n))

    def waypoint(self, pos, goal, now):
        arena = self.arena
        src, dst = arena.cell(*pos[:2]), arena.cell(*goal)
        if dst != self.goal or now >= self.next_plan:
            self._start(src, dst)
            self.next_plan = now + 4
        if self.frontier:
            self._advance(dst)
        while self.path and math.dist(pos[:2], arena.xy(self.path[0])) < 4.5:
            self.path.pop(0)
        if self.path and not self.frontier:
            n = self.path[0]
            return (*arena.xy(n), arena.height[n])
        return (*goal, arena.height[dst])
