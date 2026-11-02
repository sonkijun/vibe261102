"""
shooting.py - 종스크롤 슈팅 게임 (pygame)

공중의 적은 기관포로, 지상의 목표물은 폭탄으로 공격하는 2단 공격 방식의 슈팅 게임.

조작
  방향키 / WASD : 이동
  Z / Space    : 공중 사격 (누르고 있으면 연사)
  X            : 지상 폭탄 (조준점 위치에 낙하)
  P            : 일시정지
  M            : 음향효과 켜기/끄기

파란 "P" 아이템을 먹으면 기관포가 2 → 4 → 8 → 16발로 강화된다. (격추되면 한 단계 하락)
음향효과는 외부 파일 없이 코드에서 직접 합성한다.
  Enter        : 시작 / 재시작
  ESC          : 종료
"""
import math
import random
import sys
from array import array

import pygame

WIDTH, HEIGHT = 480, 720
FPS = 60
TILE = 40
COLS = WIDTH // TILE
ROWS = HEIGHT // TILE + 2
SCROLL = 1.2          # 지면 스크롤 속도 (px/frame)
BOMB_RANGE = 170      # 기체로부터 폭탄 조준점까지의 거리
EXTEND_EVERY = 20000  # 이 점수마다 잔기 +1
MAX_POWER = 3         # 파워 단계 0~3 → 탄 수 2, 4, 8, 16
SHOT_SPREAD = {2: 0.0, 4: 0.3, 8: 0.7, 16: 1.1}   # 탄 수별 전체 부채꼴 각도 (rad)
SAMPLE_RATE = 22050

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def dist2(ax, ay, bx, by):
    return (ax - bx) ** 2 + (ay - by) ** 2


def aim(x, y, tx, ty, speed, spread=0.0):
    """(x, y)에서 (tx, ty)를 향하는 탄 [x, y, vx, vy]를 만든다."""
    ang = math.atan2(ty - y, tx - x) + spread
    return [x, y, math.cos(ang) * speed, math.sin(ang) * speed]


def rotate_poly(points, ang, cx, cy):
    c, s = math.cos(ang), math.sin(ang)
    return [(cx + px * c - py * s, cy + px * s + py * c) for px, py in points]


# ---------------------------------------------------------------- 음향효과

class Sfx:
    """파형을 직접 합성해 만든 효과음. 오디오 장치가 없으면 조용히 비활성화된다."""

    def __init__(self):
        self.sounds = {}
        self.enabled = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)
            self.rate, _, self.channels = pygame.mixer.get_init()
            pygame.mixer.set_num_channels(24)
            self._build()
            self.enabled = True
        except pygame.error:
            pass

    def _wave(self, dur, f0, f1, wave="square", vol=0.5):
        """f0 → f1로 주파수가 변하며 감쇠하는 한 음의 샘플."""
        n = int(self.rate * dur)
        out = array("h")
        rnd = random.Random(int(f0 * 7 + f1))
        phase, level = 0.0, 0.0
        for i in range(n):
            k = i / n
            prev = phase
            phase += (f0 + (f1 - f0) * k) / self.rate
            p = phase % 1.0
            if wave == "square":
                v = 1.0 if p < 0.5 else -1.0
            elif wave == "tri":
                v = 4.0 * abs(p - 0.5) - 1.0
            else:  # noise: 주파수마다 값을 바꾸는 샘플&홀드 잡음 (레트로 폭발음)
                if int(phase) != int(prev) or i == 0:
                    level = rnd.uniform(-1.0, 1.0)
                v = level
            env = min(1.0, i / 60) * (1.0 - k) ** 2
            out.extend([int(v * env * vol * 32767)] * self.channels)
        return out

    def _seq(self, notes, dur, wave="square", vol=0.3):
        out = array("h")
        for f in notes:
            out.extend(self._wave(dur, f, f, wave, vol))
        return out

    def _build(self):
        specs = {
            "shot": self._wave(0.06, 1500, 700, "square", 0.12),
            "hit": self._wave(0.04, 700, 450, "square", 0.2),
            "explode": self._wave(0.35, 1800, 250, "noise", 0.45),
            "bomb": self._wave(0.40, 1300, 450, "tri", 0.3),
            "boom": self._wave(0.50, 900, 100, "noise", 0.6),
            "die": self._wave(1.00, 1300, 60, "noise", 0.7),
            "bigboom": self._wave(1.60, 700, 40, "noise", 0.8),
            "power": self._seq([523, 659, 784, 1047, 1319], 0.06, "square", 0.25),
            "extend": self._seq([784, 988, 1175, 1568, 1175, 1568], 0.08, "square", 0.25),
            "warning": self._seq([440, 330] * 3, 0.18, "square", 0.25),
            "start": self._seq([392, 523, 659, 784], 0.09, "tri", 0.4),
        }
        for name, buf in specs.items():
            self.sounds[name] = pygame.mixer.Sound(buffer=buf.tobytes())

    def play(self, name):
        if self.enabled:
            self.sounds[name].play()

    def toggle(self):
        if self.sounds:
            self.enabled = not self.enabled


# ---------------------------------------------------------------- 지형

def make_tiles():
    rng = random.Random(7)

    def base(color):
        s = pygame.Surface((TILE, TILE))
        s.fill(color)
        return s

    grass = []
    for _ in range(3):
        s = base((62, 120, 58))
        for _ in range(12):
            pygame.draw.rect(s, (74, 138, 66), (rng.randrange(TILE), rng.randrange(TILE), 3, 2))
        grass.append(s)

    forest = []
    for _ in range(3):
        s = base((40, 90, 44))
        for _ in range(5):
            x, y = rng.randrange(6, TILE - 6), rng.randrange(6, TILE - 6)
            pygame.draw.circle(s, (26, 62, 30), (x + 2, y + 2), 8)
            pygame.draw.circle(s, (48, 112, 52), (x, y), 8)
            pygame.draw.circle(s, (70, 146, 72), (x - 2, y - 2), 3)
        forest.append(s)

    water = []
    for _ in range(3):
        s = base((36, 82, 140))
        for _ in range(4):
            x, y = rng.randrange(0, TILE - 14), rng.randrange(4, TILE - 4)
            pygame.draw.line(s, (78, 126, 186), (x, y), (x + 12, y), 1)
        water.append(s)

    sand = []
    for _ in range(3):
        s = base((168, 150, 100))
        for _ in range(14):
            pygame.draw.rect(s, (148, 130, 86), (rng.randrange(TILE), rng.randrange(TILE), 2, 2))
        sand.append(s)

    road = base((88, 88, 92))
    pygame.draw.line(road, (210, 196, 120), (6, TILE // 2), (TILE - 14, TILE // 2), 2)
    bridge = base((122, 94, 62))
    for x in range(0, TILE, 8):
        pygame.draw.line(bridge, (88, 64, 40), (x, 0), (x, TILE), 1)
    pygame.draw.line(bridge, (60, 44, 28), (0, 1), (TILE, 1), 2)
    pygame.draw.line(bridge, (60, 44, 28), (0, TILE - 2), (TILE, TILE - 2), 2)

    return {"grass": grass, "forest": forest, "water": water, "sand": sand,
            "road": [road], "bridge": [bridge]}


class Terrain:
    """타일 행을 무한히 생성하며 아래로 스크롤되는 지면."""

    def __init__(self):
        self.tiles = make_tiles()
        self.offset = 0.0
        self.n = 0
        self.river_x = COLS / 2
        self.river_dir = 0.0
        self.rows = []
        for _ in range(ROWS):
            self.rows.insert(0, self._gen_row())

    def _gen_row(self):
        self.n += 1
        self.river_dir = clamp(self.river_dir + random.uniform(-0.12, 0.12), -0.35, 0.35)
        self.river_x += self.river_dir
        if not 2 <= self.river_x <= COLS - 2:
            self.river_x = clamp(self.river_x, 2, COLS - 2)
            self.river_dir = -self.river_dir
        half = 1.1 + 0.6 * math.sin(self.n * 0.05)
        is_road = self.n % 29 == 0
        row = []
        for c in range(COLS):
            d = abs(c + 0.5 - self.river_x)
            if is_road:
                kind = "bridge" if d < half else "road"
            elif d < half:
                kind = "water"
            elif d < half + 0.9:
                kind = "sand"
            elif math.sin(c * 0.8 + self.n * 0.11) + math.sin(c * 0.35 - self.n * 0.06) > 0.8:
                kind = "forest"
            else:
                kind = "grass"
            row.append((kind, random.randrange(len(self.tiles[kind]))))
        return row

    def update(self, speed):
        self.offset += speed
        while self.offset >= TILE:
            self.offset -= TILE
            self.rows.pop()
            self.rows.insert(0, self._gen_row())

    def kind_at(self, x, y):
        i = clamp(int((y - self.offset) // TILE) + 1, 0, ROWS - 1)
        c = clamp(int(x // TILE), 0, COLS - 1)
        return self.rows[i][c][0]

    def draw(self, surf):
        for i, row in enumerate(self.rows):
            y = (i - 1) * TILE + self.offset
            if y > HEIGHT:
                break
            for c, (kind, var) in enumerate(row):
                surf.blit(self.tiles[kind][var], (c * TILE, y))


# ---------------------------------------------------------------- 플레이어

class Player:
    RADIUS = 5      # 피격 판정 (작게)
    SPEED = 4.6

    def __init__(self):
        self.power = 0    # 0~MAX_POWER, 재출격(reset)해도 유지
        self.reset()

    @property
    def shot_count(self):
        return 2 << self.power

    def reset(self):
        self.x = WIDTH / 2
        self.y = HEIGHT - 110
        self.shot_cd = 0
        self.invuln = 150
        self.alive = True

    @property
    def sight(self):
        return self.x, self.y - BOMB_RANGE

    def update(self, keys, game):
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        speed = self.SPEED * (0.7071 if dx and dy else 1.0)
        self.x = clamp(self.x + dx * speed, 18, WIDTH - 18)
        self.y = clamp(self.y + dy * speed, BOMB_RANGE + 20, HEIGHT - 30)

        if self.invuln > 0:
            self.invuln -= 1
        if self.shot_cd > 0:
            self.shot_cd -= 1
        if (keys[pygame.K_z] or keys[pygame.K_SPACE]) and self.shot_cd == 0:
            self.fire(game)
            self.shot_cd = 6
        if keys[pygame.K_x] and game.bomb is None:
            game.bomb = Bomb(self.x, self.y)
            game.sfx.play("bomb")

    def fire(self, game):
        """탄 수만큼 부채꼴로 발사. 탄은 [x, y, vx, vy]."""
        n = self.shot_count
        step = SHOT_SPREAD[n] / (n - 1)
        gap = 14 if n == 2 else 4
        for i in range(n):
            off = i - (n - 1) / 2
            ang = off * step
            game.shots.append([self.x + off * gap, self.y - 14, math.sin(ang) * 12, -math.cos(ang) * 12])
        game.sfx.play("shot")

    def draw(self, surf, frame):
        if self.invuln and (frame // 4) % 2:
            return
        x, y = self.x, self.y
        # 그림자
        shadow = [(x + 14 + px * 0.6, y + 26 + py * 0.6) for px, py in self._shape()]
        pygame.draw.polygon(surf, (20, 40, 20), shadow)
        # 엔진 불꽃
        flame = random.randint(6, 13)
        pygame.draw.polygon(surf, (255, 150, 40), [(x - 4, y + 15), (x + 4, y + 15), (x, y + 15 + flame)])
        pygame.draw.polygon(surf, (255, 240, 160), [(x - 2, y + 15), (x + 2, y + 15), (x, y + 15 + flame * 0.5)])
        body = [(x + px, y + py) for px, py in self._shape()]
        pygame.draw.polygon(surf, (212, 216, 226), body)
        pygame.draw.polygon(surf, (90, 96, 112), body, 2)
        pygame.draw.line(surf, (150, 156, 170), (x, y - 14), (x, y + 12), 2)
        pygame.draw.circle(surf, (230, 50, 70), (int(x), int(y - 2)), 4)
        pygame.draw.circle(surf, (255, 170, 180), (int(x - 1), int(y - 3)), 1)

    @staticmethod
    def _shape():
        return [(0, -20), (6, -6), (18, 8), (18, 13), (6, 10), (4, 16),
                (-4, 16), (-6, 10), (-18, 13), (-18, 8), (-6, -6)]


class Bomb:
    """조준점을 향해 포물선처럼 작아지며 떨어지는 지상 공격용 폭탄."""
    DURATION = 26

    def __init__(self, x, y):
        self.sx, self.sy = x, y
        self.tx, self.ty = x, y - BOMB_RANGE
        self.t = 0

    def update(self, scroll):
        self.ty += scroll   # 목표 지점은 지면과 함께 움직인다
        self.t += 1
        return self.t >= self.DURATION

    def draw(self, surf):
        k = self.t / self.DURATION
        x = self.sx + (self.tx - self.sx) * k
        y = self.sy + (self.ty - self.sy) * k
        r = max(2, int(6 * (1 - k * 0.6)))
        pygame.draw.circle(surf, (60, 60, 60), (int(x), int(y)), r + 1)
        pygame.draw.circle(surf, (250, 210, 90), (int(x), int(y)), r)


class PowerItem:
    """먹으면 기관포 탄 수가 두 배가 되는 파워업 캡슐."""
    RADIUS = 16

    def __init__(self, x, y):
        self.base_x, self.x, self.y = x, x, y
        self.t = 0
        self.alive = True

    def update(self):
        self.t += 1
        self.y += 1.4
        self.x = clamp(self.base_x + math.sin(self.t * 0.06) * 24, 14, WIDTH - 14)
        if self.y > HEIGHT + 20:
            self.alive = False

    def draw(self, surf, font):
        x, y = int(self.x), int(self.y)
        glow = 3 + int(2 * math.sin(self.t * 0.25))
        pygame.draw.circle(surf, (120, 200, 255), (x, y), 12 + glow, 2)
        pygame.draw.circle(surf, (30, 90, 200), (x, y), 12)
        pygame.draw.circle(surf, WHITE, (x, y), 12, 2)
        img = font.render("P", True, WHITE)
        surf.blit(img, (x - img.get_width() // 2, y - img.get_height() // 2 + 1))


# ---------------------------------------------------------------- 공중 적

class AirEnemy:
    def __init__(self, kind, x, y, diff):
        self.kind = kind
        self.x, self.y = x, y
        self.t = 0
        self.diff = diff
        self.alive = True
        self.flash = 0
        if kind == "drifter":      # 사인파로 흔들리며 내려오는 원반
            self.hp, self.r, self.score = 1, 13, 100
            self.base_x = x
            self.amp = random.uniform(40, 90)
            self.vy = random.uniform(2.0, 2.8)
            self.phase = random.uniform(0, math.tau)
        elif kind == "diver":      # 멈췄다가 플레이어를 향해 돌진
            self.hp, self.r, self.score = 1, 12, 150
            self.stop_y = random.uniform(110, 260)
            self.state = 0
            self.vx, self.vy = 0.0, 3.0
        else:                      # spinner: 옆에서 등장해 부채꼴 탄을 쏘는 중형기
            self.hp, self.r, self.score = 4, 17, 400
            self.vx = 1.8 if x < 0 else -1.8
            self.vy = 0.25

    def hit(self):
        self.hp -= 1
        self.flash = 4
        return self.hp <= 0

    def update(self, game):
        self.t += 1
        if self.flash:
            self.flash -= 1
        fire_rate = max(35, int(120 / self.diff))
        if self.kind == "drifter":
            self.y += self.vy
            self.x = self.base_x + self.amp * math.sin(self.t * 0.05 + self.phase)
            if self.t % fire_rate == 30:
                game.enemy_fire(self.x, self.y, 3.2)
        elif self.kind == "diver":
            if self.state == 0:
                self.y += (self.stop_y - self.y) * 0.06 + 0.5
                if self.y >= self.stop_y - 2:
                    self.state, self.t = 1, 0
            elif self.state == 1:
                if self.t == 20:
                    game.enemy_fire(self.x, self.y, 3.6)
                if self.t >= 35:
                    px, py = game.player.x, game.player.y
                    _, _, self.vx, self.vy = aim(self.x, self.y, px, py, 6.5 + self.diff)
                    self.state = 2
            else:
                self.x += self.vx
                self.y += self.vy
        else:
            self.x += self.vx
            self.y += self.vy
            if self.t % max(45, int(100 / self.diff)) == 20:
                for i in range(-2, 3):
                    game.enemy_fire(self.x, self.y, 2.8, spread=i * 0.22)

        if self.t > 30 and (self.y > HEIGHT + 40 or self.y < -80 or self.x < -60 or self.x > WIDTH + 60):
            self.alive = False

    def draw(self, surf):
        x, y = int(self.x), int(self.y)
        flash = self.flash > 0
        pygame.draw.circle(surf, (20, 40, 20), (x + 12, y + 20), self.r - 3)   # 그림자
        if self.kind == "drifter":
            pygame.draw.circle(surf, WHITE if flash else (160, 168, 182), (x, y), 13)
            pygame.draw.circle(surf, (86, 94, 112), (x, y), 13, 2)
            pygame.draw.circle(surf, (40, 200, 220), (x, y), 6)
            a = self.t * 0.2
            for k in range(3):
                ang = a + k * math.tau / 3
                pygame.draw.line(surf, (60, 66, 80), (x + math.cos(ang) * 7, y + math.sin(ang) * 7),
                                 (x + math.cos(ang) * 12, y + math.sin(ang) * 12), 2)
        elif self.kind == "diver":
            ang = math.atan2(self.vy, self.vx) - math.pi / 2
            pts = rotate_poly([(0, 16), (11, -8), (0, -3), (-11, -8)], ang, x, y)
            pygame.draw.polygon(surf, WHITE if flash else (200, 60, 50), pts)
            pygame.draw.polygon(surf, (90, 20, 20), pts, 2)
            pygame.draw.circle(surf, (255, 220, 90), (x, y), 3)
        else:
            pts = rotate_poly([(math.cos(i * math.tau / 6) * 17, math.sin(i * math.tau / 6) * 17)
                               for i in range(6)], self.t * 0.05, x, y)
            pygame.draw.polygon(surf, WHITE if flash else (130, 80, 170), pts)
            pygame.draw.polygon(surf, (60, 30, 90), pts, 2)
            pygame.draw.circle(surf, (240, 120, 230), (x, y), 7)
            pygame.draw.circle(surf, (60, 30, 90), (x, y), 7, 2)


# ---------------------------------------------------------------- 지상 목표물

class GroundObj:
    def __init__(self, kind, x, y):
        self.kind = kind
        self.x, self.y = x, y
        self.t = random.randrange(100)
        self.alive = True
        self.cd = random.randint(60, 140)
        self.vx = random.choice((-0.6, 0.6))
        self.score = {"turret": 300, "radar": 1000, "tank": 500}[kind]

    def update(self, game, scroll):
        self.t += 1
        self.y += scroll
        if self.kind == "tank":
            self.x += self.vx
            if not 20 < self.x < WIDTH - 20:
                self.vx = -self.vx
        if self.kind != "radar":
            self.cd -= 1
            if self.cd <= 0:
                if 20 < self.y < game.player.y - 60:
                    game.enemy_fire(self.x, self.y, 2.6 + game.difficulty * 0.4)
                self.cd = max(45, int(random.randint(110, 170) / game.difficulty))
        if self.y > HEIGHT + 40:
            self.alive = False

    def draw(self, surf, target):
        x, y = int(self.x), int(self.y)
        ang = math.atan2(target[1] - y, target[0] - x)
        if self.kind == "turret":
            pygame.draw.rect(surf, (96, 98, 104), (x - 14, y - 14, 28, 28))
            pygame.draw.rect(surf, (54, 56, 62), (x - 14, y - 14, 28, 28), 2)
            pygame.draw.line(surf, (40, 40, 46), (x, y), (x + math.cos(ang) * 16, y + math.sin(ang) * 16), 4)
            pygame.draw.circle(surf, (150, 152, 160), (x, y), 8)
            pygame.draw.circle(surf, (220, 70, 60), (x, y), 3)
        elif self.kind == "radar":
            pygame.draw.circle(surf, (120, 120, 128), (x, y), 16)
            pygame.draw.circle(surf, (70, 70, 78), (x, y), 16, 2)
            a = self.t * 0.08
            ex, ey = math.cos(a) * 13, math.sin(a) * 13
            pygame.draw.line(surf, (220, 224, 232), (x - ex, y - ey), (x + ex, y + ey), 5)
            pygame.draw.circle(surf, (250, 200, 60), (x, y), 4)
        else:
            body = rotate_poly([(-13, -9), (13, -9), (13, 9), (-13, 9)], 0 if self.vx > 0 else math.pi, x, y)
            pygame.draw.rect(surf, (40, 44, 34), (x - 15, y - 12, 30, 5))
            pygame.draw.rect(surf, (40, 44, 34), (x - 15, y + 7, 30, 5))
            pygame.draw.polygon(surf, (110, 120, 70), body)
            pygame.draw.line(surf, (50, 56, 36), (x, y), (x + math.cos(ang) * 15, y + math.sin(ang) * 15), 3)
            pygame.draw.circle(surf, (130, 140, 84), (x, y), 6)
            pygame.draw.circle(surf, (60, 66, 40), (x, y), 6, 1)


class Fortress:
    """일정 거리마다 등장하는 대형 지상 요새. 폭탄으로만 파괴 가능."""

    def __init__(self):
        self.x, self.y = WIDTH / 2, -130
        self.t = 0
        self.state = "enter"
        self.hold = 0
        self.core_hp = 6
        self.flash = 0
        self.alive = True
        self.destroyed = False
        # [dx, dy, alive, cooldown]
        self.turrets = [[-58, -40, True, 60], [58, -40, True, 90],
                        [-58, 40, True, 120], [58, 40, True, 150]]

    def parts(self):
        """폭탄 판정용 (x, y, 반경) 목록."""
        out = [(self.x + dx, self.y + dy, 16) for dx, dy, alive, _ in self.turrets if alive]
        out.append((self.x, self.y, 22))
        return out

    def update(self, game, scroll):
        self.t += 1
        if self.flash:
            self.flash -= 1
        if self.state == "enter":
            self.y += scroll
            if self.y >= 190:
                self.state = "hold"
        elif self.state == "hold":
            self.hold += 1
            self.x = WIDTH / 2 + math.sin(self.hold * 0.012) * 70
            if self.hold > FPS * 35:
                self.state = "leave"
        else:
            self.y += scroll * 2
            if self.y > HEIGHT + 160:
                self.alive = False
                return

        if self.state != "hold":
            return
        for tur in self.turrets:
            if not tur[2]:
                continue
            tur[3] -= 1
            if tur[3] <= 0:
                game.enemy_fire(self.x + tur[0], self.y + tur[1], 3.0 + game.difficulty * 0.3)
                tur[3] = max(50, int(random.randint(90, 130) / game.difficulty))
        if self.hold % 150 == 75:
            n = 12
            for i in range(n):
                ang = i * math.tau / n + self.hold * 0.01
                game.ebullets.append([self.x, self.y, math.cos(ang) * 2.4, math.sin(ang) * 2.4])

    def bomb_hit(self, bx, by, game):
        """폭탄 착탄 처리. 획득 점수를 돌려준다."""
        gained = 0
        for tur in self.turrets:
            tx, ty = self.x + tur[0], self.y + tur[1]
            if tur[2] and dist2(bx, by, tx, ty) < 26 ** 2:
                tur[2] = False
                gained += 500
                game.explode(tx, ty, 22, ground=True)
        if dist2(bx, by, self.x, self.y) < 30 ** 2:
            self.core_hp -= 1
            self.flash = 6
            game.sfx.play("hit")
            if self.core_hp <= 0:
                game.sfx.play("bigboom")
                self.destroyed = True
                self.alive = False
                gained += 10000
                for tur in self.turrets:
                    if tur[2]:
                        gained += 500
                        game.explode(self.x + tur[0], self.y + tur[1], 18, ground=True)
                for _ in range(6):
                    game.explode(self.x + random.uniform(-70, 70), self.y + random.uniform(-50, 50),
                                 30, ground=True, power=5)
                game.craters.append([self.x, self.y, 40])
                game.shake = 30
        return gained

    def draw(self, surf):
        x, y = self.x, self.y
        oct_pts = [(x + math.cos(i * math.tau / 8 + math.pi / 8) * 92,
                    y + math.sin(i * math.tau / 8 + math.pi / 8) * 70) for i in range(8)]
        shadow = [(px + 10, py + 14) for px, py in oct_pts]
        pygame.draw.polygon(surf, (24, 40, 26), shadow)
        pygame.draw.polygon(surf, (118, 122, 132), oct_pts)
        pygame.draw.polygon(surf, (60, 62, 72), oct_pts, 3)
        pygame.draw.rect(surf, (96, 100, 110), (x - 70, y - 8, 140, 16))
        pygame.draw.rect(surf, (96, 100, 110), (x - 8, y - 56, 16, 112))
        for dx, dy, alive, _ in self.turrets:
            tx, ty = int(x + dx), int(y + dy)
            if alive:
                pygame.draw.circle(surf, (70, 72, 80), (tx, ty), 14)
                pygame.draw.circle(surf, (170, 172, 182), (tx, ty), 9)
                pygame.draw.circle(surf, (220, 70, 60), (tx, ty), 3)
            else:
                pygame.draw.circle(surf, (40, 36, 34), (tx, ty), 13)
        pulse = 0.5 + 0.5 * math.sin(self.t * 0.15)
        core = WHITE if self.flash else (200 + int(55 * pulse), 40, 60)
        pygame.draw.circle(surf, (50, 50, 58), (int(x), int(y)), 24)
        pygame.draw.circle(surf, core, (int(x), int(y)), 17)
        pygame.draw.circle(surf, (255, 200, 200), (int(x - 5), int(y - 5)), 4)


# ---------------------------------------------------------------- 게임 본체

class Game:
    def __init__(self):
        pygame.mixer.pre_init(SAMPLE_RATE, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("Sky Raider - 종스크롤 슈팅")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.sfx = Sfx()
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 26)
        self.font_big = pygame.font.Font(None, 64)
        self.font_mid = pygame.font.Font(None, 36)
        self.hiscore = 0
        self.state = "title"
        self.paused = False
        self.new_game()

    # ---------- 초기화 / 상태

    def new_game(self):
        self.terrain = Terrain()
        self.player = Player()
        self.shots = []
        self.ebullets = []
        self.air = []
        self.ground = []
        self.craters = []
        self.particles = []
        self.items = []
        self.bomb = None
        self.boss = None
        self.score = 0
        self.lives = 2            # 남은 예비 기체
        self.next_extend = EXTEND_EVERY
        self.frame = 0
        self.air_timer = 90
        self.ground_timer = 60
        self.next_boss = FPS * 50
        self.respawn_timer = 0
        self.over_timer = 0
        self.shake = 0
        self.message = ""
        self.message_timer = 0

    @property
    def difficulty(self):
        return 1.0 + self.frame / (FPS * 90)

    def show_message(self, text, frames=120):
        self.message, self.message_timer = text, frames

    # ---------- 생성

    def enemy_fire(self, x, y, speed, spread=0.0):
        if self.player.alive:
            self.ebullets.append(aim(x, y, self.player.x, self.player.y, speed, spread))
        else:
            self.ebullets.append(aim(x, y, x, y + 1, speed, spread))

    def explode(self, x, y, n=18, ground=False, power=3.0):
        colors = [(255, 230, 120), (255, 160, 50), (240, 80, 40), (120, 110, 100)]
        for _ in range(n):
            ang = random.uniform(0, math.tau)
            spd = random.uniform(0.5, power)
            life = random.randint(18, 36)
            self.particles.append([x, y, math.cos(ang) * spd, math.sin(ang) * spd, life, life,
                                   random.choice(colors), random.uniform(2, 5), ground])

    def spawn(self):
        d = self.difficulty
        boss_active = self.boss is not None

        self.air_timer -= 1
        if self.air_timer <= 0:
            if boss_active:
                wave = "drifter"
            else:
                wave = random.choices(("drifter", "diver", "spinner"), (5, 4, 2 + d))[0]
            if wave == "drifter":
                bx = random.uniform(80, WIDTH - 80)
                for i in range(random.randint(3, 5)):
                    e = AirEnemy("drifter", bx, -20 - i * 42, d)
                    e.phase = i * 0.5
                    self.air.append(e)
            elif wave == "diver":
                for _ in range(random.randint(2, 2 + int(d))):
                    self.air.append(AirEnemy("diver", random.uniform(30, WIDTH - 30),
                                             random.uniform(-80, -20), d))
            else:
                left = random.random() < 0.5
                self.air.append(AirEnemy("spinner", -30 if left else WIDTH + 30,
                                         random.uniform(80, 220), d))
            base = random.randint(110, 170) * (2.0 if boss_active else 1.0)
            self.air_timer = int(base / math.sqrt(d))

        if not boss_active:
            self.ground_timer -= 1
            if self.ground_timer <= 0:
                kind = random.choices(("turret", "tank", "radar"), (6, 3, 1))[0]
                for _ in range(8):
                    x = random.randrange(COLS) * TILE + TILE / 2
                    if self.terrain.kind_at(x, -20) not in ("water", "bridge"):
                        self.ground.append(GroundObj(kind, x, -20))
                        break
                self.ground_timer = int(random.randint(70, 140) / d)

            if self.frame >= self.next_boss:
                self.boss = Fortress()
                self.show_message("WARNING : FORTRESS APPROACHING", 150)
                self.sfx.play("warning")

    # ---------- 진행

    def update(self, keys):
        if self.message_timer:
            self.message_timer -= 1
        if self.shake:
            self.shake -= 1
        if self.state == "title":
            self.terrain.update(SCROLL)
        elif self.state == "gameover":
            self.over_timer += 1
            self.terrain.update(SCROLL)
            self.update_particles(SCROLL)
        elif not self.paused:
            self.step(keys)

    def step(self, keys):
        self.frame += 1
        scroll = SCROLL
        self.terrain.update(scroll)

        if self.player.alive:
            self.player.update(keys, self)
        else:
            self.respawn_timer -= 1
            if self.respawn_timer <= 0:
                if self.lives > 0:
                    self.lives -= 1
                    self.player.reset()
                else:
                    self.state = "gameover"
                    self.over_timer = 0
                    self.hiscore = max(self.hiscore, self.score)

        for s in self.shots:
            s[0] += s[2]
            s[1] += s[3]
        self.shots = [s for s in self.shots if s[1] > -20 and -20 < s[0] < WIDTH + 20]

        for it in self.items:
            it.update()
            p = self.player
            if p.alive and dist2(it.x, it.y, p.x, p.y) < (it.RADIUS + 10) ** 2:
                it.alive = False
                self.collect_power()
        self.items = [it for it in self.items if it.alive]

        if self.bomb and self.bomb.update(scroll):
            self.bomb_explode(self.bomb.tx, self.bomb.ty)
            self.bomb = None

        for g in self.ground:
            g.update(self, scroll)
        for c in self.craters:
            c[1] += scroll
        self.craters = [c for c in self.craters if c[1] < HEIGHT + 50]

        if self.boss:
            self.boss.update(self, scroll)
            if not self.boss.alive:
                if self.boss.destroyed:
                    self.show_message("FORTRESS DESTROYED!  +10000", 150)
                    self.maybe_drop(self.boss.x, self.boss.y, 1.0)
                self.boss = None
                self.next_boss = self.frame + FPS * 60

        for e in self.air:
            e.update(self)
        for b in self.ebullets:
            b[0] += b[2]
            b[1] += b[3]
        self.ebullets = [b for b in self.ebullets if -20 < b[0] < WIDTH + 20 and -20 < b[1] < HEIGHT + 20]

        self.collide()

        self.ground = [g for g in self.ground if g.alive]
        self.air = [e for e in self.air if e.alive]
        self.update_particles(scroll)
        self.spawn()

        if self.score >= self.next_extend:
            self.lives += 1
            self.next_extend += EXTEND_EVERY
            self.show_message("EXTEND!  1UP", 90)
            self.sfx.play("extend")

    def collect_power(self):
        p = self.player
        if p.power < MAX_POWER:
            p.power += 1
            self.show_message(f"POWER UP!  SHOT x{p.shot_count}", 90)
        else:
            self.score += 1000
            self.show_message("MAX POWER  +1000", 90)
        self.sfx.play("power")

    def maybe_drop(self, x, y, chance):
        if random.random() < chance:
            self.items.append(PowerItem(x, y))

    def update_particles(self, scroll):
        for p in self.particles:
            p[0] += p[2]
            p[1] += p[3] + (scroll if p[8] else 0)
            p[2] *= 0.93
            p[3] *= 0.93
            p[4] -= 1
        self.particles = [p for p in self.particles if p[4] > 0]

    def bomb_explode(self, x, y):
        self.explode(x, y, 14, ground=True, power=2.2)
        self.sfx.play("boom")
        for g in self.ground:
            if g.alive and dist2(x, y, g.x, g.y) < 26 ** 2:
                g.alive = False
                self.score += g.score
                self.explode(g.x, g.y, 26, ground=True, power=3.5)
                self.craters.append([g.x, g.y, 14])
                self.maybe_drop(g.x, g.y, 1.0 if g.kind == "radar" else 0.05)
        if self.boss:
            self.score += self.boss.bomb_hit(x, y, self)

    def collide(self):
        # 기관포 vs 공중 적
        for e in self.air:
            for s in self.shots:
                if dist2(s[0], s[1], e.x, e.y) < (e.r + 4) ** 2:
                    s[1] = -100
                    if e.hit():
                        e.alive = False
                        self.score += e.score
                        self.explode(e.x, e.y, 20 if e.r < 15 else 34)
                        self.sfx.play("explode")
                        self.maybe_drop(e.x, e.y, 1.0 if e.kind == "spinner" else 0.06)
                        break
                    self.sfx.play("hit")

        p = self.player
        if not p.alive or p.invuln:
            return
        for b in self.ebullets:
            if dist2(b[0], b[1], p.x, p.y) < (p.RADIUS + 3) ** 2:
                self.kill_player()
                return
        for e in self.air:
            if dist2(e.x, e.y, p.x, p.y) < (e.r + p.RADIUS + 2) ** 2:
                e.alive = False
                self.explode(e.x, e.y, 20)
                self.kill_player()
                return

    def kill_player(self):
        p = self.player
        p.alive = False
        p.power = max(0, p.power - 1)
        self.explode(p.x, p.y, 50, power=5)
        self.sfx.play("die")
        self.shake = 20
        self.respawn_timer = 100
        self.bomb = None
        self.ebullets.clear()

    # ---------- 그리기

    def draw(self):
        surf = self.canvas
        self.terrain.draw(surf)
        for x, y, r in self.craters:
            pygame.draw.circle(surf, (44, 38, 30), (int(x), int(y)), r)
            pygame.draw.circle(surf, (28, 24, 20), (int(x), int(y)), int(r * 0.6))

        if self.state == "title":
            self.draw_title(surf)
        else:
            self.draw_world(surf)
            self.draw_hud(surf)
            if self.state == "gameover":
                self.draw_gameover(surf)
            elif self.paused:
                self.center_text(surf, "PAUSED", self.font_big, HEIGHT // 2, WHITE)

        sx = random.randint(-4, 4) if self.shake else 0
        sy = random.randint(-4, 4) if self.shake else 0
        self.screen.fill(BLACK)
        self.screen.blit(surf, (sx, sy))

    def draw_world(self, surf):
        p = self.player
        target = (p.x, p.y)
        for g in self.ground:
            g.draw(surf, target)
        if self.boss:
            self.boss.draw(surf)
        for q in self.particles:
            if q[8]:
                self.draw_particle(surf, q)

        if p.alive:
            sx, sy = p.sight
            locked = any(dist2(sx, sy, g.x, g.y) < 22 ** 2 for g in self.ground)
            if self.boss:
                locked = locked or any(dist2(sx, sy, bx, by) < (r + 6) ** 2 for bx, by, r in self.boss.parts())
            color = (255, 60, 60) if locked else (230, 230, 240)
            sx, sy = int(sx), int(sy)
            pygame.draw.circle(surf, color, (sx, sy), 11, 2)
            for ddx, ddy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                pygame.draw.line(surf, color, (sx + ddx * 6, sy + ddy * 6), (sx + ddx * 16, sy + ddy * 16), 2)

        if self.bomb:
            self.bomb.draw(surf)
        for e in self.air:
            e.draw(surf)
        for it in self.items:
            it.draw(surf, self.font)
        for s in self.shots:
            tail = (s[0] - s[2], s[1] - s[3])
            pygame.draw.line(surf, (255, 250, 170), (s[0], s[1]), tail, 4)
            pygame.draw.line(surf, (255, 200, 60), (s[0], s[1]), tail, 2)
        if p.alive:
            p.draw(surf, self.frame)
        for b in self.ebullets:
            pygame.draw.circle(surf, (255, 90, 160), (int(b[0]), int(b[1])), 5)
            pygame.draw.circle(surf, (255, 235, 245), (int(b[0]), int(b[1])), 2)
        for q in self.particles:
            if not q[8]:
                self.draw_particle(surf, q)

    @staticmethod
    def draw_particle(surf, q):
        r = max(1, int(q[7] * q[4] / q[5]))
        pygame.draw.circle(surf, q[6], (int(q[0]), int(q[1])), r)

    def draw_hud(self, surf):
        bar = pygame.Surface((WIDTH, 30), pygame.SRCALPHA)
        bar.fill((0, 0, 0, 130))
        surf.blit(bar, (0, 0))
        surf.blit(self.font.render(f"SCORE {self.score:07d}", True, WHITE), (10, 7))
        hi = self.font.render(f"HI {max(self.hiscore, self.score):07d}", True, (255, 220, 120))
        surf.blit(hi, (WIDTH - hi.get_width() - 10, 7))
        for i in range(self.lives):
            x, y = 20 + i * 24, HEIGHT - 20
            pts = [(x + px * 0.5, y + py * 0.5) for px, py in Player._shape()]
            pygame.draw.polygon(surf, (212, 216, 226), pts)
        pw = self.font.render(f"SHOT x{self.player.shot_count}", True, (140, 210, 255))
        surf.blit(pw, (WIDTH - pw.get_width() - 10, HEIGHT - 28))
        if not self.sfx.enabled:
            surf.blit(self.font.render("MUTE", True, (200, 200, 200)), (10, 34))
        if self.message_timer and (self.message_timer // 8) % 2 == 0:
            self.center_text(surf, self.message, self.font_mid, HEIGHT // 2 - 60, (255, 230, 90))

    def draw_title(self, surf):
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 20, 120))
        surf.blit(shade, (0, 0))
        self.center_text(surf, "SKY RAIDER", self.font_big, 200, (255, 230, 120))
        self.center_text(surf, "vertical scrolling shooter", self.font, 250, (200, 210, 230))
        lines = ["ARROWS / WASD : MOVE",
                 "Z / SPACE : AIR CANNON",
                 "X : GROUND BOMB",
                 "P : PAUSE    M : SOUND    ESC : QUIT",
                 "GET [P] ITEM : SHOT x2 > x4 > x8 > x16"]
        for i, line in enumerate(lines):
            self.center_text(surf, line, self.font, 340 + i * 30, WHITE)
        if (pygame.time.get_ticks() // 500) % 2 == 0:
            self.center_text(surf, "PRESS ENTER TO START", self.font_mid, 540, (255, 120, 120))
        if self.hiscore:
            self.center_text(surf, f"HI SCORE {self.hiscore:07d}", self.font, 600, (255, 220, 120))

    def draw_gameover(self, surf):
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 140))
        surf.blit(shade, (0, 0))
        self.center_text(surf, "GAME OVER", self.font_big, 280, (255, 90, 90))
        self.center_text(surf, f"SCORE {self.score:07d}", self.font_mid, 340, WHITE)
        if self.over_timer > 60:
            self.center_text(surf, "PRESS ENTER TO RESTART", self.font, 400, (220, 220, 230))

    @staticmethod
    def center_text(surf, text, font, y, color):
        img = font.render(text, True, color)
        surf.blit(img, (WIDTH // 2 - img.get_width() // 2, y - img.get_height() // 2))

    # ---------- 루프

    def on_key(self, key):
        if key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit()
        if key == pygame.K_m:
            self.sfx.toggle()
        elif self.state == "title" and key in (pygame.K_RETURN, pygame.K_SPACE):
            self.new_game()
            self.state = "playing"
            self.sfx.play("start")
        elif self.state == "gameover" and key == pygame.K_RETURN and self.over_timer > 60:
            self.new_game()
            self.state = "playing"
            self.sfx.play("start")
        elif self.state == "playing" and key == pygame.K_p:
            self.paused = not self.paused

    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    self.on_key(event.key)
            self.update(pygame.key.get_pressed())
            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)


if __name__ == "__main__":
    Game().run()
