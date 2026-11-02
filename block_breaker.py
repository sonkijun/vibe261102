import tkinter as tk


class BlockBreaker:
    WIDTH = 800
    HEIGHT = 600
    TOP = 70
    BALL_RADIUS = 8
    PADDLE_WIDTH = 110
    PADDLE_HEIGHT = 14
    PADDLE_Y = 540
    BRICK_ROWS = 5
    BRICK_COLUMNS = 10
    BRICK_WIDTH = 70
    BRICK_HEIGHT = 22
    BRICK_GAP = 6
    BRICK_LEFT = 22
    BRICK_TOP = 95

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("블럭깨기")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            root,
            width=self.WIDTH,
            height=self.HEIGHT,
            background="#101827",
            highlightthickness=0,
        )
        self.canvas.pack()

        self.paddle_x = self.WIDTH / 2
        self.ball_x = self.WIDTH / 2
        self.ball_y = self.PADDLE_Y - self.BALL_RADIUS - 2
        self.ball_dx = 0.0
        self.ball_dy = 0.0
        self.score = 0
        self.lives = 3
        self.keys_down: set[str] = set()
        self.state = "ready"
        self.bricks: list[dict[str, object]] = []
        self._create_bricks()

        self.root.bind("<KeyPress>", self._key_down)
        self.root.bind("<KeyRelease>", self._key_up)
        self.canvas.bind("<Motion>", self._move_paddle_to_mouse)

        self._draw()
        self.root.after(16, self._tick)

    def _create_bricks(self) -> None:
        colors = ["#ff6b6b", "#ff9f43", "#feca57", "#48dbfb", "#5f9df7"]
        self.bricks = []
        for row in range(self.BRICK_ROWS):
            for column in range(self.BRICK_COLUMNS):
                x1 = self.BRICK_LEFT + column * (self.BRICK_WIDTH + self.BRICK_GAP)
                y1 = self.BRICK_TOP + row * (self.BRICK_HEIGHT + self.BRICK_GAP)
                self.bricks.append(
                    {
                        "x1": x1,
                        "y1": y1,
                        "x2": x1 + self.BRICK_WIDTH,
                        "y2": y1 + self.BRICK_HEIGHT,
                        "color": colors[row],
                    }
                )

    def _key_down(self, event: tk.Event) -> None:
        key = event.keysym.lower()
        self.keys_down.add(key)

        if key == "space":
            if self.state in ("ready", "paused"):
                self.state = "playing"
                if self.ball_dx == 0 and self.ball_dy == 0:
                    self.ball_dx = 3.2
                    self.ball_dy = -4.8
            elif self.state == "playing":
                self.state = "paused"
        elif key == "r":
            self._restart()

    def _key_up(self, event: tk.Event) -> None:
        self.keys_down.discard(event.keysym.lower())

    def _move_paddle_to_mouse(self, event: tk.Event) -> None:
        self.paddle_x = self._clamp_paddle_x(event.x)
        if self.state == "ready":
            self.ball_x = self.paddle_x
        self._draw()

    def _clamp_paddle_x(self, x: float) -> float:
        half_width = self.PADDLE_WIDTH / 2
        return max(half_width, min(self.WIDTH - half_width, x))

    def _restart(self) -> None:
        self.paddle_x = self.WIDTH / 2
        self.ball_x = self.WIDTH / 2
        self.ball_y = self.PADDLE_Y - self.BALL_RADIUS - 2
        self.ball_dx = 0.0
        self.ball_dy = 0.0
        self.score = 0
        self.lives = 3
        self.state = "ready"
        self._create_bricks()
        self._draw()

    def _tick(self) -> None:
        if self.state == "playing":
            if "left" in self.keys_down or "a" in self.keys_down:
                self.paddle_x -= 7
            if "right" in self.keys_down or "d" in self.keys_down:
                self.paddle_x += 7
            self.paddle_x = self._clamp_paddle_x(self.paddle_x)
            self._move_ball()

        self._draw()
        self.root.after(16, self._tick)

    def _move_ball(self) -> None:
        previous_x = self.ball_x
        previous_y = self.ball_y
        self.ball_x += self.ball_dx
        self.ball_y += self.ball_dy

        if self.ball_x - self.BALL_RADIUS <= 0:
            self.ball_x = self.BALL_RADIUS
            self.ball_dx = abs(self.ball_dx)
        elif self.ball_x + self.BALL_RADIUS >= self.WIDTH:
            self.ball_x = self.WIDTH - self.BALL_RADIUS
            self.ball_dx = -abs(self.ball_dx)

        if self.ball_y - self.BALL_RADIUS <= self.TOP:
            self.ball_y = self.TOP + self.BALL_RADIUS
            self.ball_dy = abs(self.ball_dy)

        paddle_left = self.paddle_x - self.PADDLE_WIDTH / 2
        paddle_right = self.paddle_x + self.PADDLE_WIDTH / 2
        paddle_top = self.PADDLE_Y
        if (
            self.ball_dy > 0
            and previous_y + self.BALL_RADIUS <= paddle_top
            and self.ball_y + self.BALL_RADIUS >= paddle_top
            and paddle_left <= self.ball_x <= paddle_right
        ):
            hit_position = (self.ball_x - self.paddle_x) / (self.PADDLE_WIDTH / 2)
            self.ball_y = paddle_top - self.BALL_RADIUS
            self.ball_dx = hit_position * 5.5
            self.ball_dy = -max(3.2, 5.8 - abs(self.ball_dx) * 0.35)

        self._hit_brick(previous_x, previous_y)

        if self.ball_y - self.BALL_RADIUS > self.HEIGHT:
            self.lives -= 1
            if self.lives == 0:
                self.state = "game_over"
            else:
                self.ball_x = self.paddle_x
                self.ball_y = self.PADDLE_Y - self.BALL_RADIUS - 2
                self.ball_dx = 0.0
                self.ball_dy = 0.0
                self.state = "ready"

        if not self.bricks and self.state == "playing":
            self.state = "won"

    def _hit_brick(self, previous_x: float, previous_y: float) -> None:
        radius = self.BALL_RADIUS
        for brick in self.bricks:
            x1 = float(brick["x1"])
            y1 = float(brick["y1"])
            x2 = float(brick["x2"])
            y2 = float(brick["y2"])
            overlap_x = min(self.ball_x + radius, x2) - max(self.ball_x - radius, x1)
            overlap_y = min(self.ball_y + radius, y2) - max(self.ball_y - radius, y1)

            if overlap_x <= 0 or overlap_y <= 0:
                continue

            if previous_y + radius <= y1 or previous_y - radius >= y2:
                self.ball_dy *= -1
            elif previous_x + radius <= x1 or previous_x - radius >= x2:
                self.ball_dx *= -1
            elif overlap_x < overlap_y:
                self.ball_dx *= -1
            else:
                self.ball_dy *= -1

            self.bricks.remove(brick)
            self.score += 10
            break

    def _draw(self) -> None:
        self.canvas.delete("all")
        self.canvas.create_text(
            22,
            30,
            text=f"점수  {self.score}",
            fill="#f3f4f6",
            font=("맑은 고딕", 15, "bold"),
            anchor="w",
        )
        self.canvas.create_text(
            self.WIDTH - 22,
            30,
            text=f"목숨  {self.lives}",
            fill="#f3f4f6",
            font=("맑은 고딕", 15, "bold"),
            anchor="e",
        )
        self.canvas.create_line(0, 60, self.WIDTH, 60, fill="#344054", width=2)

        for brick in self.bricks:
            self.canvas.create_rectangle(
                brick["x1"],
                brick["y1"],
                brick["x2"],
                brick["y2"],
                fill=brick["color"],
                outline="",
            )

        half_width = self.PADDLE_WIDTH / 2
        self.canvas.create_rectangle(
            self.paddle_x - half_width,
            self.PADDLE_Y,
            self.paddle_x + half_width,
            self.PADDLE_Y + self.PADDLE_HEIGHT,
            fill="#e8eef7",
            outline="",
        )
        self.canvas.create_oval(
            self.ball_x - self.BALL_RADIUS,
            self.ball_y - self.BALL_RADIUS,
            self.ball_x + self.BALL_RADIUS,
            self.ball_y + self.BALL_RADIUS,
            fill="#ffffff",
            outline="",
        )

        messages = {
            "ready": "스페이스바를 눌러 시작",
            "paused": "일시정지  ·  스페이스바로 계속",
            "game_over": "게임 오버  ·  R 키로 다시 시작",
            "won": "승리!  ·  R 키로 다시 시작",
        }
        message = messages.get(self.state)
        if message:
            self.canvas.create_text(
                self.WIDTH / 2,
                390,
                text=message,
                fill="#ffffff",
                font=("맑은 고딕", 20, "bold"),
            )


def main() -> None:
    root = tk.Tk()
    BlockBreaker(root)
    root.mainloop()


if __name__ == "__main__":
    main()
