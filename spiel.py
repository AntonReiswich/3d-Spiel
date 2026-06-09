import math
import random
import time
import tkinter as tk
from dataclasses import dataclass


WIDTH = 1100
HEIGHT = 720
CENTER_X = WIDTH // 2
CENTER_Y = HEIGHT // 2
FOV = 520
TUNNEL_RADIUS = 5.0
SPAWN_Z = 86.0
NEAR_Z = 1.2
CENTERLINE_RADIUS = 10.0
CENTERLINE_TURN_RATE = 0.009
RING_SEGMENTS = 24
STAR_COUNT = 130
RING_SPACING = 12.0
RING_NEAR_Z = 4.5
RING_FAR_Z = 98.0


def clamp(value, low, high):
    return max(low, min(high, value))


def blend(c1, c2, t):
    t = clamp(t, 0.0, 1.0)
    a = tuple(int(c1[i : i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(c2[i : i + 2], 16) for i in (1, 3, 5))
    out = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return f"#{out[0]:02x}{out[1]:02x}{out[2]:02x}"


def inside_tunnel(x, y, margin=0.0):
    return x * x + y * y <= (TUNNEL_RADIUS - margin) ** 2


RING_POINTS = [
    (
        math.cos(i * math.tau / RING_SEGMENTS) * TUNNEL_RADIUS,
        math.sin(i * math.tau / RING_SEGMENTS) * TUNNEL_RADIUS,
    )
    for i in range(RING_SEGMENTS)
]


@dataclass
class FlyingObject:
    kind: str
    x: float
    y: float
    z: float
    size: float
    rot: float
    spin: float
    collected: bool = False
    home_x: float = 0.0
    home_y: float = 0.0
    move_radius: float = 0.0
    move_phase: float = 0.0

    def __post_init__(self):
        self.home_x = self.x
        self.home_y = self.y


class NebulaRunner:
    def __init__(self, root):
        self.root = root
        self.root.title("Nebula Courier - 3D Python Spiel")
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(root, width=WIDTH, height=HEIGHT, bg="#06070d", highlightthickness=0)
        self.canvas.pack()
        self.canvas.focus_set()

        self.keys = set()
        self.last_time = time.perf_counter()
        self.last_spawn = 0.0
        self.after_id = None
        self.draw_dx = 0.0
        self.draw_dy = 0.0

        self.stars = []
        self.objects = []
        self.reset()

        root.bind_all("<KeyPress>", self.on_key_down)
        root.bind_all("<KeyRelease>", self.on_key_up)
        self.canvas.bind("<Button-1>", lambda _event: self.canvas.focus_set())
        root.after(100, self.canvas.focus_set)
        self.loop()

    def reset(self):
        random.seed()
        self.player_x = 0.0
        self.player_y = 0.0
        self.vel_x = 0.0
        self.vel_y = 0.0
        self.score = 0
        self.combo = 0
        self.energy = 100.0
        self.lives = 3
        self.distance = 0.0
        self.speed = 18.0
        self.shake = 0.0
        self.flash = 0.0
        self.game_over = False
        self.win = False
        self.objects.clear()
        self.last_spawn = 0.0
        self.stars = [
            {
                "x": random.uniform(-18, 18),
                "y": random.uniform(-10, 10),
                "z": random.uniform(4, 90),
                "tw": random.random() * math.tau,
            }
            for _ in range(STAR_COUNT)
        ]
        for z in range(18, 88, 14):
            self.spawn_wave(float(z))

    def on_key_down(self, event):
        key = self.normalize_key(event)
        self.keys.add(key)
        if key == "r" and (self.game_over or self.win):
            self.reset()
        if key == "escape":
            self.root.destroy()

    def on_key_up(self, event):
        self.keys.discard(self.normalize_key(event))

    def normalize_key(self, event):
        char = (event.char or "").lower()
        if char in {"w", "a", "s", "d", "r", " "}:
            return "space" if char == " " else char
        return event.keysym.lower()

    def centerline_point(self, distance):
        angle = distance * CENTERLINE_TURN_RATE
        return (
            math.sin(angle) * CENTERLINE_RADIUS,
            math.cos(angle) * CENTERLINE_RADIUS,
        )

    def tunnel_curve(self, z):
        if hasattr(self, "curve_origin"):
            here_x, here_y = self.curve_origin
        else:
            here_x, here_y = self.centerline_point(self.distance)
        ahead_x, ahead_y = self.centerline_point(self.distance + z)
        return ahead_x - here_x, ahead_y - here_y

    def project_with_curve(self, x, y, z, curve_x=0.0, curve_y=0.0):
        z = max(z, 0.05)
        scale = FOV / z
        sx = CENTER_X + (x + curve_x - self.player_x) * scale + self.draw_dx
        sy = CENTER_Y + (y + curve_y - self.player_y) * scale + self.draw_dy
        return sx, sy, scale

    def project(self, x, y, z, curved=True):
        if curved:
            curve_x, curve_y = self.tunnel_curve(z)
            return self.project_with_curve(x, y, z, curve_x, curve_y)
        return self.project_with_curve(x, y, z)

    def stationary_ring_depths(self):
        first_world_distance = math.floor((self.distance + RING_NEAR_Z) / RING_SPACING) * RING_SPACING
        if first_world_distance < self.distance + RING_NEAR_Z:
            first_world_distance += RING_SPACING

        depths = []
        world_distance = first_world_distance
        far_world_distance = self.distance + RING_FAR_Z
        while world_distance <= far_world_distance:
            depths.append(world_distance - self.distance)
            world_distance += RING_SPACING
        return depths

    def loop(self):
        now = time.perf_counter()
        dt = min(0.033, now - self.last_time)
        self.last_time = now
        self.update(dt)
        self.draw()
        self.after_id = self.root.after(16, self.loop)

    def update(self, dt):
        if self.game_over or self.win:
            self.flash = max(0.0, self.flash - dt * 2)
            return

        boost = "space" in self.keys and self.energy > 4
        target_speed = 31.0 if boost else 18.0 + min(8.0, self.distance / 260.0)
        self.speed += (target_speed - self.speed) * min(1.0, dt * 2.8)
        if boost:
            self.energy = max(0.0, self.energy - dt * 34)
        else:
            self.energy = min(100.0, self.energy + dt * 13)

        steer_x = int("d" in self.keys or "right" in self.keys) - int("a" in self.keys or "left" in self.keys)
        steer_y = int("s" in self.keys or "down" in self.keys) - int("w" in self.keys or "up" in self.keys)
        target_vel_x = steer_x * 8.2
        target_vel_y = steer_y * 6.4
        response = 1.0 - (0.0009 ** dt)
        self.vel_x += (target_vel_x - self.vel_x) * response
        self.vel_y += (target_vel_y - self.vel_y) * response
        self.player_x += self.vel_x * dt
        self.player_y += self.vel_y * dt
        self.keep_player_in_tunnel()

        self.distance += self.speed * dt
        self.shake = max(0.0, self.shake - dt * 5)
        self.flash = max(0.0, self.flash - dt * 2.8)

        for star in self.stars:
            star["z"] -= self.speed * dt * (0.7 + star["tw"] % 0.5)
            star["tw"] += dt * 4
            if star["z"] < NEAR_Z:
                star["x"] = random.uniform(-18, 18)
                star["y"] = random.uniform(-10, 10)
                star["z"] = random.uniform(65, 95)

        for obj in self.objects:
            obj.z -= self.speed * dt
            obj.rot += obj.spin * dt
            if obj.kind == "blue_crystal":
                self.move_blue_crystal(obj)
            if obj.z < 3.0 and not obj.collected:
                dx = obj.x - self.player_x
                dy = obj.y - self.player_y
                radius = obj.size + 0.45
                if dx * dx + dy * dy < radius * radius:
                    if obj.kind in {"crystal", "blue_crystal"}:
                        obj.collected = True
                        self.combo += 1
                        if obj.kind == "blue_crystal":
                            self.score += 250 + self.combo * 45
                            self.energy = min(100.0, self.energy + 20)
                        else:
                            self.score += 100 + self.combo * 25
                            self.energy = min(100.0, self.energy + 12)
                        self.flash = 0.35
                    else:
                        obj.collected = True
                        self.combo = 0
                        self.lives -= 1
                        self.shake = 1.0
                        self.flash = 0.6
                        if self.lives <= 0:
                            self.game_over = True

        self.objects = [obj for obj in self.objects if obj.z > -7 and not (obj.collected and obj.z < 8)]

        if self.distance - self.last_spawn > 18:
            self.last_spawn = self.distance
            self.spawn_wave(SPAWN_Z)

        if self.distance >= 1400:
            self.win = True
            self.score += self.lives * 500

    def spawn_wave(self, z):
        lanes_x = [-3.6, -1.8, 0.0, 1.8, 3.6]
        lanes_y = [-3.6, -1.8, 0.0, 1.8, 3.6]
        lanes = [(x, y) for x in lanes_x for y in lanes_y if inside_tunnel(x, y, 0.6)]
        blocked = random.sample(lanes, k=random.randint(3, 5))
        for x, y in blocked:
            self.objects.append(
                FlyingObject(
                    "asteroid",
                    x + random.uniform(-0.35, 0.35),
                    y + random.uniform(-0.25, 0.25),
                    z + random.uniform(-5, 7),
                    random.uniform(0.65, 1.15),
                    random.random() * math.tau,
                    random.uniform(-2.8, 2.8),
                )
            )
        for _ in range(random.randint(3, 5)):
            x, y = random.choice(lanes)
            x += random.uniform(-0.25, 0.25)
            y += random.uniform(-0.25, 0.25)
            self.objects.append(
                FlyingObject(
                    "crystal",
                    x,
                    y,
                    z + random.uniform(-10, 12),
                    random.uniform(0.32, 0.48),
                    random.random() * math.tau,
                    random.uniform(2.0, 4.5),
                )
            )
        for _ in range(random.randint(1, 2)):
            x, y = random.choice(lanes)
            x += random.uniform(-0.2, 0.2)
            y += random.uniform(-0.2, 0.2)
            self.objects.append(
                FlyingObject(
                    "blue_crystal",
                    x,
                    y,
                    z + random.uniform(-8, 13),
                    random.uniform(0.36, 0.52),
                    random.random() * math.tau,
                    random.uniform(3.2, 5.4),
                    move_radius=random.uniform(0.55, 1.05),
                    move_phase=random.random() * math.tau,
                )
            )

    def move_blue_crystal(self, obj):
        obj.x = obj.home_x + math.cos(obj.rot + obj.move_phase) * obj.move_radius
        obj.y = obj.home_y + math.sin(obj.rot * 0.8 + obj.move_phase) * obj.move_radius
        limit = TUNNEL_RADIUS - 0.7
        dist = math.hypot(obj.x, obj.y)
        if dist > limit:
            scale = limit / max(dist, 0.001)
            obj.x *= scale
            obj.y *= scale

    def keep_player_in_tunnel(self):
        limit = TUNNEL_RADIUS - 0.7
        dist = math.hypot(self.player_x, self.player_y)
        if dist <= limit:
            return
        scale = limit / max(dist, 0.001)
        self.player_x *= scale
        self.player_y *= scale
        self.vel_x *= 0.35
        self.vel_y *= 0.35

    def draw(self):
        self.canvas.delete("all")
        self.draw_dx = random.uniform(-8, 8) * self.shake
        self.draw_dy = random.uniform(-5, 5) * self.shake
        self.curve_origin = self.centerline_point(self.distance)

        self.draw_background()
        self.draw_tunnel()

        for obj in sorted(self.objects, key=lambda item: item.z, reverse=True):
            if obj.z > NEAR_Z and not obj.collected:
                if obj.kind in {"crystal", "blue_crystal"}:
                    self.draw_crystal(obj)
                else:
                    self.draw_asteroid(obj)

        self.draw_cockpit()
        self.draw_hud()
        if self.flash > 0:
            color = "#9df7ff" if self.combo else "#ff5f5f"
            self.canvas.create_rectangle(0, 0, WIDTH, HEIGHT, fill=color, outline="", stipple="gray75")

        if self.game_over or self.win:
            self.draw_end_screen()

    def draw_background(self):
        for i in range(18):
            t = i / 17
            color = blend("#050711", "#101c33", t)
            self.canvas.create_rectangle(0, i * HEIGHT / 18, WIDTH, (i + 1) * HEIGHT / 18, fill=color, outline="")

        for star in self.stars:
            x, y, scale = self.project(star["x"], star["y"], star["z"], curved=False)
            r = clamp(scale * 0.025, 0.7, 3.0)
            twinkle = 0.55 + 0.45 * math.sin(star["tw"])
            color = blend("#6da6ff", "#ffffff", twinkle)
            self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="")

    def draw_tunnel(self):
        ring_zs = self.stationary_ring_depths()

        for z in sorted(ring_zs, reverse=True):
            curve_x, curve_y = self.tunnel_curve(z)
            pts = []
            for x, y in RING_POINTS:
                sx, sy, _scale = self.project_with_curve(x, y, z, curve_x, curve_y)
                pts.extend((sx, sy))
            pts.extend(pts[:2])
            shade = 1.0 - clamp((z - 7) / 90, 0, 1)
            color = blend("#163151", "#43e4ff", shade)
            width = max(1, int(4 - z / 24))
            self.canvas.create_line(*pts, fill=color, width=width, smooth=True)

        z_path = [6, 11, 17, 24, 32, 42, 54, 68, 84, 96]
        curve_cache = {z: self.tunnel_curve(z) for z in z_path}
        for i in range(0, RING_SEGMENTS, 4):
            x, y = RING_POINTS[i]
            self.draw_curved_depth_line(x, y, z_path, curve_cache, "#224467", 1)

        for radius in [TUNNEL_RADIUS * 0.34, TUNNEL_RADIUS * 0.67]:
            for i in range(0, RING_SEGMENTS, 8):
                angle = i * math.tau / RING_SEGMENTS + self.distance * 0.01
                x = math.cos(angle) * radius
                y = math.sin(angle) * radius
                self.draw_curved_depth_line(x, y, z_path, curve_cache, "#142842", 1)

    def draw_curved_depth_line(self, x, y, z_values, curve_cache, color, width):
        pts = []
        for z in z_values:
            curve_x, curve_y = curve_cache[z]
            sx, sy, _scale = self.project_with_curve(x, y, z, curve_x, curve_y)
            pts.extend((sx, sy))
        self.canvas.create_line(*pts, fill=color, width=width, smooth=True)

    def draw_crystal(self, obj):
        x, y, scale = self.project(obj.x, obj.y, obj.z)
        r = obj.size * scale
        pulse = 1.0 + 0.12 * math.sin(obj.rot * 2.1)
        r *= pulse
        points = [
            (x, y - r * 1.5),
            (x + r * 0.9, y),
            (x, y + r * 1.5),
            (x - r * 0.9, y),
        ]
        if obj.kind == "blue_crystal":
            color = blend("#3c86ff", "#f4fbff", clamp((70 - obj.z) / 70, 0, 1))
            outline = "#1f6fff"
            glow = "#55a6ff"
        else:
            color = blend("#38ff6b", "#f5fff7", clamp((70 - obj.z) / 70, 0, 1))
            outline = "#12d94f"
            glow = "#3cff80"
        self.canvas.create_polygon(points, fill=color, outline=outline, width=2)
        self.canvas.create_line(x, y - r * 1.5, x, y + r * 1.5, fill="#ffffff", width=1)
        self.canvas.create_oval(x - r * 1.8, y - r * 1.8, x + r * 1.8, y + r * 1.8, outline=glow)

    def draw_asteroid(self, obj):
        x, y, scale = self.project(obj.x, obj.y, obj.z)
        r = obj.size * scale
        pts = []
        for i in range(10):
            angle = obj.rot + i * math.tau / 10
            wobble = 0.78 + 0.25 * math.sin(i * 2.7 + obj.size * 8)
            pts.append((x + math.cos(angle) * r * wobble, y + math.sin(angle) * r * wobble))
        depth = clamp((SPAWN_Z - obj.z) / SPAWN_Z, 0, 1)
        fill = blend("#242838", "#a68b74", depth)
        outline = blend("#34384d", "#ffd2a8", depth)
        self.canvas.create_polygon(pts, fill=fill, outline=outline, width=max(1, int(r / 18)))
        self.canvas.create_line(x - r * 0.35, y - r * 0.2, x + r * 0.32, y + r * 0.18, fill="#d5b493")
        self.canvas.create_oval(x - r * 0.25, y - r * 0.45, x + r * 0.05, y - r * 0.15, fill="#383642", outline="")

    def draw_cockpit(self):
        px, py, scale = self.project(self.player_x, self.player_y, 7.5)
        nose_y = HEIGHT - 88
        lean = clamp(self.vel_x * 2.4, -42, 42)
        self.canvas.create_polygon(
            CENTER_X - 92 + lean,
            HEIGHT,
            CENTER_X,
            nose_y,
            CENTER_X + 92 + lean,
            HEIGHT,
            fill="#121a28",
            outline="#2cddff",
            width=2,
        )
        self.canvas.create_line(CENTER_X, nose_y, px, py, fill="#58f0ff", width=2)
        self.canvas.create_oval(px - 8, py - 8, px + 8, py + 8, outline="#ffffff", width=2)

    def draw_hud(self):
        self.canvas.create_text(24, 22, anchor="nw", fill="#eaf8ff", font=("Segoe UI", 18, "bold"), text=f"Score {self.score}")
        self.canvas.create_text(24, 52, anchor="nw", fill="#86dfff", font=("Segoe UI", 12), text=f"Distanz {int(self.distance)} / 1400")
        self.canvas.create_text(24, 76, anchor="nw", fill="#ffcf86", font=("Segoe UI", 12), text=f"Leben {self.lives}   Combo x{self.combo}")

        bar_x = WIDTH - 244
        self.canvas.create_text(bar_x, 24, anchor="nw", fill="#eaf8ff", font=("Segoe UI", 12, "bold"), text="BOOST")
        self.canvas.create_rectangle(bar_x, 50, bar_x + 210, 67, outline="#315a72", width=2)
        self.canvas.create_rectangle(bar_x + 2, 52, bar_x + 2 + self.energy * 2.06, 65, fill="#46f0b4", outline="")

        hint = "WASD/Pfeile: fliegen   Space: Boost   R: Neustart   Esc: Ende"
        self.canvas.create_text(CENTER_X, HEIGHT - 24, fill="#d8ebff", font=("Segoe UI", 11), text=hint)

    def draw_end_screen(self):
        self.canvas.create_rectangle(0, 0, WIDTH, HEIGHT, fill="#03050a", stipple="gray50", outline="")
        title = "Mission geschafft" if self.win else "Schiff verloren"
        subtitle = "Du hast den Nebelkurier heil durchgebracht." if self.win else "Der Tunnel war diesmal schneller."
        self.canvas.create_text(CENTER_X, CENTER_Y - 66, fill="#ffffff", font=("Segoe UI", 34, "bold"), text=title)
        self.canvas.create_text(CENTER_X, CENTER_Y - 15, fill="#95e8ff", font=("Segoe UI", 16), text=subtitle)
        self.canvas.create_text(CENTER_X, CENTER_Y + 30, fill="#ffcf86", font=("Segoe UI", 18, "bold"), text=f"Score: {self.score}")
        self.canvas.create_text(CENTER_X, CENTER_Y + 82, fill="#eaf8ff", font=("Segoe UI", 13), text="Druecke R fuer eine neue Runde oder Esc zum Beenden.")


def main():
    root = tk.Tk()
    NebulaRunner(root)
    root.mainloop()


if __name__ == "__main__":
    main()
