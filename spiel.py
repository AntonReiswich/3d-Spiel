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
WORLD_X = 7.2
WORLD_Y = 4.5
SPAWN_Z = 86.0
NEAR_Z = 1.2


def clamp(value, low, high):
    return max(low, min(high, value))


def blend(c1, c2, t):
    t = clamp(t, 0.0, 1.0)
    a = tuple(int(c1[i : i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(c2[i : i + 2], 16) for i in (1, 3, 5))
    out = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return f"#{out[0]:02x}{out[1]:02x}{out[2]:02x}"


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
            for _ in range(180)
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

    def project(self, x, y, z):
        z = max(z, 0.05)
        scale = FOV / z
        sx = CENTER_X + (x - self.player_x) * scale + self.draw_dx
        sy = CENTER_Y + (y - self.player_y) * scale + self.draw_dy
        return sx, sy, scale

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
        self.player_x = clamp(self.player_x + self.vel_x * dt, -WORLD_X + 0.7, WORLD_X - 0.7)
        self.player_y = clamp(self.player_y + self.vel_y * dt, -WORLD_Y + 0.7, WORLD_Y - 0.7)

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
            if obj.z < 3.0 and not obj.collected:
                dx = obj.x - self.player_x
                dy = obj.y - self.player_y
                radius = obj.size + 0.45
                if dx * dx + dy * dy < radius * radius:
                    if obj.kind == "crystal":
                        obj.collected = True
                        self.combo += 1
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
        lanes_x = [-4.8, -2.4, 0.0, 2.4, 4.8]
        lanes_y = [-2.5, 0.0, 2.5]
        blocked = random.sample([(x, y) for x in lanes_x for y in lanes_y], k=random.randint(3, 5))
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
        for _ in range(random.randint(4, 7)):
            x = random.choice(lanes_x) + random.uniform(-0.25, 0.25)
            y = random.choice(lanes_y) + random.uniform(-0.25, 0.25)
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

    def draw(self):
        self.canvas.delete("all")
        self.draw_dx = random.uniform(-8, 8) * self.shake
        self.draw_dy = random.uniform(-5, 5) * self.shake

        self.draw_background()
        self.draw_tunnel()

        for obj in sorted(self.objects, key=lambda item: item.z, reverse=True):
            if obj.z > NEAR_Z and not obj.collected:
                if obj.kind == "crystal":
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
            x, y, scale = self.project(star["x"], star["y"], star["z"])
            r = clamp(scale * 0.025, 0.7, 3.0)
            twinkle = 0.55 + 0.45 * math.sin(star["tw"])
            color = blend("#6da6ff", "#ffffff", twinkle)
            self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=color, outline="")

    def draw_tunnel(self):
        ring_zs = [((self.distance * 0.38 + offset) % 18) + 7 for offset in range(0, 88, 9)]
        corners = [(-WORLD_X, -WORLD_Y), (WORLD_X, -WORLD_Y), (WORLD_X, WORLD_Y), (-WORLD_X, WORLD_Y)]

        for z in sorted(ring_zs, reverse=True):
            pts = [self.project(x, y, z)[:2] for x, y in corners]
            shade = 1.0 - clamp((z - 7) / 90, 0, 1)
            color = blend("#163151", "#43e4ff", shade)
            width = max(1, int(4 - z / 24))
            for i in range(4):
                x1, y1 = pts[i]
                x2, y2 = pts[(i + 1) % 4]
                self.canvas.create_line(x1, y1, x2, y2, fill=color, width=width)

        for x, y in corners:
            near = self.project(x, y, 6)[:2]
            far = self.project(x, y, 92)[:2]
            self.canvas.create_line(*near, *far, fill="#224467", width=1)

        for x in [-4.8, -2.4, 0, 2.4, 4.8]:
            near = self.project(x, -WORLD_Y, 6)[:2]
            far = self.project(x, -WORLD_Y, 92)[:2]
            self.canvas.create_line(*near, *far, fill="#142842", width=1)
            near = self.project(x, WORLD_Y, 6)[:2]
            far = self.project(x, WORLD_Y, 92)[:2]
            self.canvas.create_line(*near, *far, fill="#142842", width=1)

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
        color = blend("#43fff2", "#f9fdff", clamp((70 - obj.z) / 70, 0, 1))
        self.canvas.create_polygon(points, fill=color, outline="#0bd2ff", width=2)
        self.canvas.create_line(x, y - r * 1.5, x, y + r * 1.5, fill="#ffffff", width=1)
        self.canvas.create_oval(x - r * 1.8, y - r * 1.8, x + r * 1.8, y + r * 1.8, outline="#1a8dff")

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
