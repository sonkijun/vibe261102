"""터미널 뱀게임: 사람 vs AI 대결 (표준 라이브러리 curses 사용, 별도 설치 불필요)

실행: python3 snake.py
조작: 방향키 또는 WASD 이동, P 일시정지, Q 종료

규칙
- 사과(@)를 먹으면 10점, 몸이 한 칸 길어짐
- 벽, 자기 몸, 상대 몸에 부딪히면 패배
- 머리끼리 정면으로 부딪히면 점수가 높은 쪽이 승리
- 먼저 WIN_SCORE점을 얻으면 승리
"""
import curses
import random
from collections import deque

WIN_SCORE = 150     # 이 점수에 먼저 도달하면 승리
AI_MISTAKE = 0.08   # AI가 최적이 아닌 수를 둘 확률 (높을수록 AI가 약해짐)
START_SPEED = 130   # ms, 작을수록 빠름

UP, DOWN, LEFT, RIGHT = (-1, 0), (1, 0), (0, -1), (0, 1)
DIRS = [UP, DOWN, LEFT, RIGHT]
KEYS = {
    curses.KEY_UP: UP, ord("w"): UP,
    curses.KEY_DOWN: DOWN, ord("s"): DOWN,
    curses.KEY_LEFT: LEFT, ord("a"): LEFT,
    curses.KEY_RIGHT: RIGHT, ord("d"): RIGHT,
}


def add(p, d):
    return (p[0] + d[0], p[1] + d[1])


class Board:
    def __init__(self, h, w):
        self.h, self.w = h, w

    def inside(self, p):
        return 0 < p[0] < self.h - 1 and 0 < p[1] < self.w - 1


def place_food(board, blocked):
    while True:
        food = (random.randint(1, board.h - 2), random.randint(1, board.w - 2))
        if food not in blocked:
            return food


# ---------------- AI ----------------
def flood_area(board, start, blocked, limit=200):
    """start에서 갈 수 있는 빈 칸 수 (막다른 길을 피하려고 사용)"""
    seen = {start}
    q = deque([start])
    while q and len(seen) < limit:
        cur = q.popleft()
        for d in DIRS:
            nxt = add(cur, d)
            if board.inside(nxt) and nxt not in blocked and nxt not in seen:
                seen.add(nxt)
                q.append(nxt)
    return len(seen)


def bfs_first_step(board, start, goal, blocked):
    """start에서 goal까지 최단 경로의 첫 방향. 길이 없으면 None"""
    prev = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur == goal:
            while prev[cur] != start:
                cur = prev[cur]
            return (cur[0] - start[0], cur[1] - start[1])
        for d in DIRS:
            nxt = add(cur, d)
            if board.inside(nxt) and nxt not in blocked and nxt not in prev:
                prev[nxt] = cur
                q.append(nxt)
    return None


def ai_move(board, ai, human, food):
    head = ai[0]
    # 꼬리는 다음 턴에 비켜나므로 장애물에서 제외
    blocked = set(ai[:-1]) | set(human[:-1])
    # 사람 뱀 머리가 다음에 갈 수 있는 칸은 위험하니 피함
    danger = {add(human[0], d) for d in DIRS}

    safe = [d for d in DIRS if board.inside(add(head, d)) and add(head, d) not in blocked]
    if not safe:
        return RIGHT  # 어디로 가도 죽음

    # 가끔 한눈팔기 (게임 밸런스) - 막다른 길로는 가지 않음
    if random.random() < AI_MISTAKE:
        roomy = [d for d in safe if flood_area(board, add(head, d), blocked | {head}) > len(ai)]
        if roomy:
            return random.choice(roomy)

    step = bfs_first_step(board, head, food, blocked | danger)
    if step:
        nxt = add(head, step)
        # 먹이로 가는 길이 막다른 길이 아니면 그 길로
        if flood_area(board, nxt, blocked | {head}) > len(ai):
            return step

    # 먹이로 못 가면 가장 넓은 공간 쪽으로 (위험 칸은 후순위)
    return max(safe, key=lambda d: (add(head, d) not in danger,
                                    flood_area(board, add(head, d), blocked | {head})))


# ---------------- 게임 ----------------
def play(stdscr, use_color):
    curses.curs_set(0)
    stdscr.keypad(True)

    sh, sw = stdscr.getmaxyx()
    h, w = min(sh - 1, 25), min(sw, 60)  # 맨 아래 줄은 점수 표시용
    if h < 12 or w < 30:
        return None
    board = Board(h, w)

    human = [(h // 3, 5 - i) for i in range(3)]
    ai = [(2 * h // 3, w - 6 + i) for i in range(3)]
    human_dir, ai_dir = RIGHT, LEFT
    food = place_food(board, set(human) | set(ai))
    scores = {"human": 0, "ai": 0}
    speed = START_SPEED
    paused = False

    def color(n):
        return curses.color_pair(n) | curses.A_BOLD if use_color else 0

    while True:
        stdscr.timeout(speed)
        key = stdscr.getch()
        if key in (ord("q"), ord("Q")):
            return "quit", scores
        if key in (ord("p"), ord("P")):
            paused = not paused
        new_dir = KEYS.get(key)
        if new_dir and add(new_dir, human_dir) != (0, 0):  # 반대 방향 금지
            human_dir = new_dir

        if not paused:
            ai_dir = ai_move(board, ai, human, food)
            h_head, a_head = add(human[0], human_dir), add(ai[0], ai_dir)
            h_eat, a_eat = h_head == food, a_head == food

            human = [h_head] + (human if h_eat else human[:-1])
            ai = [a_head] + (ai if a_eat else ai[:-1])

            h_dead = not board.inside(h_head) or h_head in human[1:] or h_head in ai[1:]
            a_dead = not board.inside(a_head) or a_head in ai[1:] or a_head in human[1:]
            if h_head == a_head:  # 정면 충돌
                h_dead = a_dead = True

            if h_dead or a_dead:
                if h_dead and a_dead:
                    if scores["human"] > scores["ai"]:
                        result = "win"
                    elif scores["human"] < scores["ai"]:
                        result = "lose"
                    else:
                        result = "draw"
                else:
                    result = "lose" if h_dead else "win"
                return result, scores

            if h_eat:
                scores["human"] += 10
            if a_eat:
                scores["ai"] += 10
            if h_eat or a_eat:
                speed = max(60, speed - 3)
                food = place_food(board, set(human) | set(ai))

            if scores["human"] >= WIN_SCORE:
                return "win", scores
            if scores["ai"] >= WIN_SCORE:
                return "lose", scores

        # 그리기
        stdscr.erase()
        win = stdscr.derwin(h, w, 0, 0)
        win.border()
        win.addch(food[0], food[1], "@", color(3))
        for i, (y, x) in enumerate(human):
            win.addch(y, x, "O" if i == 0 else "o", color(1))
        for i, (y, x) in enumerate(ai):
            win.addch(y, x, "X" if i == 0 else "x", color(2))
        status = f" 나(O): {scores['human']}  AI(X): {scores['ai']}  목표 {WIN_SCORE}점  P:정지 Q:종료"
        if paused:
            status += " [일시정지]"
        stdscr.addstr(h, 0, status[: sw - 1])
        stdscr.refresh()


def main(stdscr):
    use_color = curses.has_colors()
    if use_color:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)   # 사람
        curses.init_pair(2, curses.COLOR_RED, -1)     # AI
        curses.init_pair(3, curses.COLOR_YELLOW, -1)  # 사과

    messages = {"win": "당신이 이겼습니다!", "lose": "AI가 이겼습니다...", "draw": "무승부!"}
    while True:
        outcome = play(stdscr, use_color)
        if outcome is None:
            stdscr.erase()
            stdscr.addstr(0, 0, "터미널 창이 너무 작아요. 창을 키우고 아무 키나 누르세요.")
            stdscr.timeout(-1)
            stdscr.getch()
            continue
        result, scores = outcome
        if result == "quit":
            break
        stdscr.timeout(-1)
        stdscr.erase()
        stdscr.addstr(2, 2, "게임 오버!")
        stdscr.addstr(3, 2, messages[result])
        stdscr.addstr(4, 2, f"나: {scores['human']}점   AI: {scores['ai']}점")
        stdscr.addstr(6, 2, "R: 다시 하기   아무 키: 종료")
        stdscr.refresh()
        if stdscr.getch() not in (ord("r"), ord("R")):
            break


if __name__ == "__main__":
    curses.wrapper(main)
