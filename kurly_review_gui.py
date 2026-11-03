"""
마켓컬리 상품 후기 감성 분석기 (컬리 후기 API + Pandas + matplotlib + PyQt6 GUI)

실행:
    python kurly_review_gui.py
    → 컬리 상품 주소(또는 상품번호)와 수집 개수를 넣고 [수집 & 분석] 버튼을 누릅니다.
    → 후기를 모아 긍정/부정/중립으로 나누고 파이차트로 보여줍니다.
    → [CSV 저장] 버튼을 누르면 분류 결과를 .csv 파일로 저장합니다.

감성 분류 방식:
    컬리 후기에는 별점이 없어서, 후기 문장에 들어 있는 긍정/부정 단어를 세어 점수를 매깁니다.
    (점수 > 0 → 긍정, 점수 < 0 → 부정, 0 → 중립)
    "맛있"처럼 앞에 "안 / 별로 / 못" 같은 부정어가 붙으면 반대로 계산합니다.

다른 파일에서는 함수만 이렇게 가져다 쓸 수 있습니다:
    from kurly_review_gui import crawl_kurly_reviews, analyze_reviews
    df = analyze_reviews(crawl_kurly_reviews("5041031", 300))
"""

import re
import sys
import time

import matplotlib
import pandas as pd
import requests
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# 한글이 네모(□)로 깨지지 않도록 운영체제별 한글 글꼴을 지정합니다.
if sys.platform == "darwin":
    matplotlib.rcParams["font.family"] = "AppleGothic"
elif sys.platform.startswith("win"):
    matplotlib.rcParams["font.family"] = "Malgun Gothic"
else:
    matplotlib.rcParams["font.family"] = "NanumGothic"
matplotlib.rcParams["axes.unicode_minus"] = False

DEFAULT_URL = "https://www.kurly.com/goods/5041031?collectionCode=market-sales-main1"

# 컬리 웹페이지가 후기를 불러올 때 쓰는 API (한 번에 최대 50개, 커서 방식으로 다음 페이지)
REVIEW_API = "https://api.kurly.com/product-review/v4/contents-products/{no}/reviews"
COUNT_API = "https://api.kurly.com/product-review/v1/contents-products/{no}/count"
HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.kurly.com/"}
PAGE_SIZE = 50

# 감성 사전: 후기에 자주 나오는 표현 위주로 골랐습니다. (단어가 들어 있으면 +1 / -1)
POSITIVE_WORDS = [
    "맛있", "맛나", "맛좋", "맛도리", "존맛", "꿀맛", "좋아", "좋네", "좋고", "좋은", "좋습", "좋았",
    "좋음", "좋더", "최고", "추천", "만족", "훌륭", "괜찮", "부드럽", "촉촉", "쫄깃", "고소", "든든",
    "간편", "편하", "편리", "신선", "푸짐", "넉넉", "저렴", "가성비", "재구매", "또 구매", "또 살",
    "또 주문", "쟁여", "단골", "잘 먹", "잘먹", "잘 샀", "잘샀", "감사", "굿", "짱", "대박", "인기",
    "사랑", "딱이", "딱 좋", "최애", "육즙", "풍미", "강추", "믿고", "행복", "알차", "조아", "맛잇", "마싯", "뚝딱", "아주 좋",
]
NEGATIVE_WORDS = [
    "별로", "실망", "아쉽", "아쉬", "짜요", "짜고", "짜서", "너무 짜", "짭짤", "느끼", "비리", "비린",
    "질기", "질겨", "딱딱", "퍽퍽", "뻑뻑", "냄새", "이상", "불만", "최악", "비싸", "비쌈", "작아",
    "작네", "적어", "적네", "탔", "상했", "상한", "녹아", "터져", "파손", "찌그러", "늦게", "누락",
    "환불", "반품", "교환", "갖다 버", "다 버렸", "못 먹", "못먹", "안 먹", "다신", "다시는", "글쎄",
    "그닥", "그다지", "그저 그", "애매", "밍밍", "싱거", "달아요", "너무 달", "기름지", "기름이 많", "기름이 너", "조미료", "후회", "비추",
]
# 긍정 단어 바로 앞에 이 단어들이 오면 부정으로 뒤집습니다. 예) "안 맛있어요", "별로 안 좋아요"
NEGATORS = ["안 ", "안", "못 ", "별로 ", "그닥 ", "전혀 "]
# 긍정 단어 뒤에 붙으면 부정이 되는 꼬리 표현. 예) "맛있진 않아요", "좋지 않아요"
NEGATIVE_TAILS = ["지 않", "진 않", "지않", "진않", "지는 않", "지 못", "진 못"]


def parse_product_no(text):
    """'https://www.kurly.com/goods/5041031?...' 또는 '5041031' 에서 상품번호만 꺼냅니다."""
    match = re.search(r"goods/(\d+)", text) or re.fullmatch(r"\s*(\d+)\s*", text)
    if not match:
        raise ValueError("컬리 상품 주소나 상품번호를 입력해 주세요.\n예) https://www.kurly.com/goods/5041031")
    return match.group(1)


def fetch_review_count(product_no):
    """상품의 전체 후기 개수를 가져옵니다. (실패해도 수집에는 지장이 없으니 None 반환)"""
    try:
        res = requests.get(COUNT_API.format(no=product_no), headers=HEADERS, timeout=10)
        return res.json()["data"]["count"]
    except (requests.RequestException, KeyError, ValueError):
        return None


def crawl_kurly_reviews(product_no, limit=300, sort="RECENTLY", progress=None):
    """컬리 후기를 limit 개까지 모아 [{작성일, 작성자, 후기, 좋아요}, ...] 로 돌려줍니다.

    sort: "RECENTLY"(최근 등록순) 또는 "RECOMMEND"(추천순)
    progress: 지금까지 모은 개수를 받는 함수 (GUI 진행바 갱신용)
    """
    reviews, after = [], None
    while len(reviews) < limit:
        params = {"sortType": sort, "size": min(PAGE_SIZE, limit - len(reviews)), "onlyImage": "false"}
        if after:
            params["after"] = after
        res = requests.get(REVIEW_API.format(no=product_no), params=params, headers=HEADERS, timeout=10)
        res.raise_for_status()
        data = res.json().get("data") or {}

        for r in data.get("reviews", []):
            reviews.append({
                "작성일": r.get("registeredAt", "")[:10],
                "작성자": r.get("ownerName", ""),
                "후기": (r.get("contents") or "").strip(),
                "좋아요": r.get("likeCount", 0),
            })
        if progress:
            progress(len(reviews))

        after = (data.get("nextCursor") or {}).get("after")
        if not data.get("reviews") or not after:
            break  # 더 이상 후기가 없음
        time.sleep(0.2)  # 서버에 부담을 주지 않도록 잠깐 쉬어 갑니다.
    return reviews[:limit]


def sentiment_score(text):
    """후기 한 개의 감성 점수와, 점수에 쓰인 단어 목록을 돌려줍니다."""
    score, hits = 0, []
    for word in POSITIVE_WORDS:
        for m in re.finditer(re.escape(word), text):
            before = text[max(0, m.start() - 3):m.start()]
            after = text[m.end():m.end() + 5]
            if any(before.endswith(n) for n in NEGATORS) or any(after.startswith(t) or t in after for t in NEGATIVE_TAILS):
                score -= 1
                hits.append(f"-{word}")
            else:
                score += 1
                hits.append(f"+{word}")
    for word in NEGATIVE_WORDS:
        count = text.count(word)
        if count:
            score -= count
            hits.append(f"-{word}")
    return score, hits


def analyze_reviews(reviews):
    """후기 리스트를 Pandas DataFrame 으로 바꾸고 감성(긍정/부정/중립)을 붙입니다."""
    df = pd.DataFrame(reviews, columns=["작성일", "작성자", "후기", "좋아요"])
    df = df[df["후기"].str.len() > 0].drop_duplicates(subset=["작성자", "후기"]).reset_index(drop=True)
    scored = df["후기"].apply(sentiment_score)
    df["점수"] = scored.str[0]
    df["근거 단어"] = scored.str[1].apply(", ".join)
    df["감성"] = pd.cut(df["점수"], bins=[-float("inf"), -0.5, 0.5, float("inf")], labels=["부정", "중립", "긍정"])
    df["글자수"] = df["후기"].str.len()
    return df


class CrawlThread(QThread):
    """후기 수집은 시간이 걸리므로 별도 스레드에서 돌려 창이 멈추지 않게 합니다."""

    progressed = pyqtSignal(int)
    finished_ok = pyqtSignal(object, object)  # (DataFrame, 전체 후기 수)
    failed = pyqtSignal(str)

    def __init__(self, product_no, limit, sort):
        super().__init__()
        self.product_no = product_no
        self.limit = limit
        self.sort = sort

    def run(self):
        try:
            total = fetch_review_count(self.product_no)
            reviews = crawl_kurly_reviews(self.product_no, self.limit, self.sort, self.progressed.emit)
            if not reviews:
                raise RuntimeError("후기를 하나도 가져오지 못했습니다. 상품번호를 확인해 주세요.")
            self.finished_ok.emit(analyze_reviews(reviews), total)
        except Exception as e:  # 네트워크 오류 등은 메시지로 보여 줍니다.
            self.failed.emit(str(e))


SENTIMENT_COLORS = {"긍정": "#4C9F70", "부정": "#E0605E", "중립": "#B8B8B8"}


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("마켓컬리 후기 감성 분석기")
        self.resize(1200, 760)
        self.df = None
        self.thread = None

        # ── 상단 입력줄 ──
        self.url_edit = QLineEdit(DEFAULT_URL)
        self.url_edit.setPlaceholderText("컬리 상품 주소 또는 상품번호")
        self.count_spin = QSpinBox()
        self.count_spin.setRange(10, 3000)
        self.count_spin.setSingleStep(50)
        self.count_spin.setValue(300)
        self.count_spin.setSuffix(" 개")
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("최근 등록순", "RECENTLY")
        self.sort_combo.addItem("추천순", "RECOMMEND")
        self.run_btn = QPushButton("수집 && 분석")  # Qt 버튼에서 &는 단축키 표시라 &&로 써야 보입니다
        self.run_btn.setStyleSheet("background:#5f0080; color:white; font-weight:bold; padding:6px 14px;")
        self.run_btn.clicked.connect(self.start_crawl)
        self.save_btn = QPushButton("CSV 저장")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_csv)

        top = QHBoxLayout()
        top.addWidget(QLabel("상품"))
        top.addWidget(self.url_edit, 1)
        top.addWidget(QLabel("수집"))
        top.addWidget(self.count_spin)
        top.addWidget(self.sort_combo)
        top.addWidget(self.run_btn)
        top.addWidget(self.save_btn)

        self.progress = QProgressBar()
        self.progress.setFormat("%v / %m 개")
        self.status = QLabel("상품 주소를 확인하고 [수집 & 분석]을 눌러 주세요.")
        self.status.setStyleSheet("color: gray;")

        # ── 왼쪽: 파이차트 ──
        self.figure = Figure(figsize=(5, 5), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.summary = QLabel()
        self.summary.setFont(QFont(self.summary.font().family(), 13))
        self.summary.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left = QWidget()
        left_box = QVBoxLayout(left)
        left_box.addWidget(self.canvas, 1)
        left_box.addWidget(self.summary)

        # ── 오른쪽: 필터 + 후기 표 ──
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["전체", "긍정", "부정", "중립"])
        self.filter_combo.currentTextChanged.connect(self.fill_table)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["감성", "점수", "후기", "근거 단어", "작성일"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(3, 150)
        self.table.setWordWrap(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        right = QWidget()
        right_box = QVBoxLayout(right)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("보기"))
        filter_row.addWidget(self.filter_combo)
        filter_row.addStretch()
        right_box.addLayout(filter_row)
        right_box.addWidget(self.table)

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([480, 720])

        root = QWidget()
        layout = QVBoxLayout(root)
        layout.addLayout(top)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(root)
        self.draw_pie()

    def start_crawl(self):
        try:
            product_no = parse_product_no(self.url_edit.text())
        except ValueError as e:
            QMessageBox.warning(self, "입력 확인", str(e))
            return
        self.run_btn.setEnabled(False)
        self.save_btn.setEnabled(False)
        self.progress.setRange(0, self.count_spin.value())
        self.progress.setValue(0)
        self.status.setText(f"상품 {product_no} 후기 수집 중...")

        self.thread = CrawlThread(product_no, self.count_spin.value(), self.sort_combo.currentData())
        self.thread.progressed.connect(self.progress.setValue)
        self.thread.finished_ok.connect(self.on_done)
        self.thread.failed.connect(self.on_failed)
        self.thread.start()

    def on_done(self, df, total):
        self.df = df
        self.run_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.progress.setValue(self.progress.maximum())
        total_text = f" (전체 후기 {total:,}개 중)" if total else ""
        self.status.setText(f"후기 {len(df)}개 분석 완료{total_text}")
        self.draw_pie()
        self.fill_table()

    def on_failed(self, message):
        self.run_btn.setEnabled(True)
        self.status.setText("수집 실패")
        QMessageBox.critical(self, "오류", message)

    def draw_pie(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        if self.df is None or self.df.empty:
            ax.text(0.5, 0.5, "분석 결과가 여기에 표시됩니다", ha="center", va="center", color="gray")
            ax.axis("off")
            self.summary.setText("")
            self.canvas.draw()
            return

        counts = self.df["감성"].value_counts().reindex(["긍정", "부정", "중립"], fill_value=0)
        counts = counts[counts > 0]
        ax.pie(
            counts.values,
            labels=[f"{k}\n{v}개" for k, v in counts.items()],
            colors=[SENTIMENT_COLORS[k] for k in counts.index],
            autopct="%1.1f%%",
            pctdistance=0.75,
            explode=[0.08 if v / counts.sum() < 0.05 else 0 for v in counts.values],  # 작은 조각은 살짝 띄워 글자 겹침 방지
            startangle=90,
            counterclock=False,
            wedgeprops={"edgecolor": "white", "linewidth": 2},
            textprops={"fontsize": 12},
        )
        ax.set_title(f"후기 감성 분석 (총 {len(self.df)}개)", fontsize=15, fontweight="bold")
        ax.axis("equal")
        self.canvas.draw()

        pos, neg = counts.get("긍정", 0), counts.get("부정", 0)
        ratio = pos / (pos + neg) * 100 if pos + neg else 0
        self.summary.setText(
            f"<b style='color:{SENTIMENT_COLORS['긍정']}'>긍정 {pos}</b> · "
            f"<b style='color:{SENTIMENT_COLORS['부정']}'>부정 {neg}</b> · "
            f"중립 {counts.get('중립', 0)}<br>긍정 비율(중립 제외) <b>{ratio:.1f}%</b>"
        )

    def fill_table(self):
        if self.df is None:
            return
        choice = self.filter_combo.currentText()
        view = self.df if choice == "전체" else self.df[self.df["감성"] == choice]
        self.table.setRowCount(len(view))
        for row, (_, r) in enumerate(view.iterrows()):
            values = [r["감성"], str(r["점수"]), r["후기"], r["근거 단어"], r["작성일"]]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col == 0:
                    item.setForeground(QColor(SENTIMENT_COLORS[r["감성"]]))
                    item.setFont(QFont(item.font().family(), weight=QFont.Weight.Bold))
                self.table.setItem(row, col, item)
        self.table.resizeRowsToContents()

    def save_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "CSV 저장", "kurly_reviews.csv", "CSV (*.csv)")
        if path:
            # utf-8-sig: 엑셀에서 열어도 한글이 깨지지 않습니다.
            self.df.to_csv(path, index=False, encoding="utf-8-sig")
            self.status.setText(f"저장 완료: {path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
