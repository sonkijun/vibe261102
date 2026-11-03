"""
네이버 뉴스 검색기 (네이버 공식 검색 API + BeautifulSoup4 + PyQt6 GUI)

준비:
    1. https://developers.naver.com 에서 [Application → 애플리케이션 등록]
       - 사용 API: "검색" 선택, 환경: "WEB 설정"에 http://localhost 입력
    2. 발급된 Client ID / Client Secret 을 앱의 [🔑 API 키] 버튼에 입력
       (키는 이 컴퓨터의 앱 설정에만 저장되고, 코드나 git에는 들어가지 않습니다)

실행:
    python naver_news_crawler.py
    → 검색어를 넣고 [검색] 버튼을 누릅니다.
    → 표에서 기사를 더블클릭하면 브라우저로 기사가 열립니다.
    → [엑셀 저장] 버튼을 누르면 결과를 .xlsx 파일로 저장합니다.

다른 파일에서는 검색 함수만 이렇게 가져다 쓸 수 있습니다:
    from naver_news_crawler import crawl_naver_news
    articles = crawl_naver_news("반도체", client_id, client_secret)
"""

import os
import sys
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from PyQt6.QtCore import QSettings, Qt, QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QColor, QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# 네이버 공식 뉴스 검색 API 주소 (하루 25,000회까지 무료)
API_URL = "https://openapi.naver.com/v1/search/news.json"

# API는 언론사 이름을 주지 않아서, 기사 주소(도메인)로 이름을 찾습니다.
PRESS_BY_DOMAIN = {
    "yna.co.kr": "연합뉴스", "newsis.com": "뉴시스", "news1.kr": "뉴스1",
    "chosun.com": "조선일보", "biz.chosun.com": "조선비즈", "joongang.co.kr": "중앙일보",
    "donga.com": "동아일보", "hani.co.kr": "한겨레", "khan.co.kr": "경향신문",
    "hankyung.com": "한국경제", "mk.co.kr": "매일경제", "sedaily.com": "서울경제",
    "edaily.co.kr": "이데일리", "mt.co.kr": "머니투데이", "fnnews.com": "파이낸셜뉴스",
    "asiae.co.kr": "아시아경제", "heraldcorp.com": "헤럴드경제", "etnews.com": "전자신문",
    "dt.co.kr": "디지털타임스", "zdnet.co.kr": "지디넷코리아", "ohmynews.com": "오마이뉴스",
    "kbs.co.kr": "KBS", "imbc.com": "MBC", "sbs.co.kr": "SBS", "ytn.co.kr": "YTN",
    "jtbc.co.kr": "JTBC", "mbn.co.kr": "MBN", "hankookilbo.com": "한국일보",
    "seoul.co.kr": "서울신문", "kmib.co.kr": "국민일보", "munhwa.com": "문화일보",
    "segye.com": "세계일보", "nocutnews.co.kr": "노컷뉴스", "inews24.com": "아이뉴스24",
    "bizwatch.co.kr": "비즈워치", "ajunews.com": "아주경제", "newspim.com": "뉴스핌",
    "thelec.kr": "디일렉", "bloter.net": "블로터", "ddaily.co.kr": "디지털데일리",
}


class ApiError(Exception):
    """API 호출이 실패했을 때 사용자에게 보여 줄 메시지를 담는 오류"""


def strip_html(text):
    """API 결과의 <b>반도체</b>, &quot; 같은 HTML 표시를 일반 글자로 바꿉니다."""
    return " ".join(BeautifulSoup(text, "html.parser").get_text().split())


def press_from_url(url):
    """기사 주소에서 언론사 이름을 찾습니다. 모르는 곳이면 도메인을 그대로 씁니다."""
    host = urlparse(url).netloc.lower().removeprefix("www.").removeprefix("m.")
    # biz.chosun.com 처럼 하위 도메인이 따로 등록돼 있으면 먼저 찾고, 없으면 chosun.com 으로 찾기
    parts = host.split(".")
    for i in range(len(parts) - 1):
        name = PRESS_BY_DOMAIN.get(".".join(parts[i:]))
        if name:
            return name
    return host


def fetch_news(query, client_id, client_secret, sort="date", display=50):
    """네이버 뉴스 검색 API를 호출해 JSON 결과를 받아 옵니다.
    sort: 'date'(최신순) 또는 'sim'(관련도순), display: 가져올 개수(최대 100)"""
    headers = {"X-Naver-Client-Id": client_id, "X-Naver-Client-Secret": client_secret}
    params = {"query": query, "display": display, "sort": sort}
    response = requests.get(API_URL, params=params, headers=headers, timeout=10)

    if response.status_code == 401:
        raise ApiError("API 키가 올바르지 않습니다. [🔑 API 키]에서 Client ID/Secret을 확인하세요.")
    if response.status_code == 403:
        raise ApiError("이 애플리케이션에 '검색' API 사용 권한이 없습니다. 개발자센터에서 '검색'을 추가하세요.")
    if response.status_code == 429:
        raise ApiError("오늘 사용할 수 있는 검색 횟수를 모두 썼습니다. 내일 다시 시도하세요.")
    response.raise_for_status()
    return response.json()


def parse_articles(data):
    """API 결과(JSON)를 기사 dict 리스트로 바꿉니다."""
    articles = []
    for item in data.get("items", []):
        original = item.get("originallink") or item.get("link", "")
        naver = item.get("link", "")
        written_at = ""
        if item.get("pubDate"):
            written_at = parsedate_to_datetime(item["pubDate"]).strftime("%Y-%m-%d %H:%M")

        articles.append({
            "title": strip_html(item.get("title", "")),
            "press": press_from_url(original),
            "summary": strip_html(item.get("description", "")),
            "link": original,
            "naver_link": naver if "news.naver.com" in naver else "",
            "written_at": written_at,
        })
    return articles


def crawl_naver_news(query, client_id, client_secret, sort="date", display=50):
    """검색어로 네이버 뉴스를 검색해 기사 dict 리스트를 반환합니다."""
    return parse_articles(fetch_news(query, client_id, client_secret, sort, display))



# 엑셀 열 순서: (머리글, dict 키, 열 너비)
EXCEL_COLUMNS = [
    ("제목", "title", 50),
    ("언론사", "press", 14),
    ("작성 시각", "written_at", 12),
    ("요약", "summary", 80),
    ("기사 링크", "link", 40),
    ("네이버뉴스 링크", "naver_link", 40),
]


def save_to_excel(articles, path, query=""):
    """기사 dict 리스트를 엑셀(.xlsx) 파일로 저장합니다."""
    wb = Workbook()
    ws = wb.active
    ws.title = "뉴스"

    # 1행: 머리글 (굵은 글씨 + 연한 파란 배경)
    ws.append(["번호"] + [name for name, _, _ in EXCEL_COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DDEBF7")
        cell.alignment = Alignment(horizontal="center")

    # 2행부터: 기사 한 건이 한 줄
    for number, article in enumerate(articles, start=1):
        ws.append([number] + [article[key] for _, key, _ in EXCEL_COLUMNS])

    # 링크 칸은 클릭하면 열리도록 하이퍼링크로 만듭니다.
    for row in ws.iter_rows(min_row=2):
        for cell in row[5:7]:
            if cell.value:
                cell.hyperlink = cell.value
                cell.style = "Hyperlink"

    # 열 너비 정하기 (A열은 번호)
    ws.column_dimensions["A"].width = 6
    for index, (_, _, width) in enumerate(EXCEL_COLUMNS):
        ws.column_dimensions[chr(ord("B") + index)].width = width

    ws.freeze_panes = "A2"  # 스크롤해도 머리글이 보이게 고정

    # 두 번째 시트: 언제, 무엇을 검색했는지 기록
    info = wb.create_sheet("검색 정보")
    info.append(["검색어", query])
    info.append(["저장 시각", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    info.append(["기사 수", len(articles)])

    wb.save(path)


# ----------------------------------------------------------------------
# 여기부터 PyQt6 GUI
# ----------------------------------------------------------------------

# 표의 열 순서: (제목, dict 키)
COLUMNS = [("제목", "title"), ("언론사", "press"), ("작성 시각", "written_at"), ("요약", "summary")]

# 콤보박스에 보일 이름 → API sort 값
SORT_OPTIONS = {"최신순": "date", "관련도순": "sim"}

# 가져올 기사 수 (API는 한 번에 최대 100건)
COUNT_OPTIONS = ["30건", "50건", "100건"]

# 언론사 이름마다 다른 색을 주기 위한 팔레트
PRESS_COLORS = ["#4ADE80", "#38BDF8", "#F472B6", "#FBBF24", "#A78BFA", "#FB923C", "#2DD4BF", "#F87171"]

# 상태 표시줄 색: 종류별 (글자색, 배경색)
STATUS_COLORS = {
    "info": ("#CBD5E1", "#1E293B"),
    "busy": ("#FDE68A", "#3B2F0B"),
    "ok": ("#86EFAC", "#0F3D2A"),
    "error": ("#FCA5A5", "#451A1A"),
}

# 화면 전체 디자인 (Qt 스타일시트, CSS와 비슷한 문법)
STYLE = """
QMainWindow { background: #0B1120; }
QWidget { color: #E2E8F0; font-size: 14px; }

#banner {
    border-radius: 18px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #03C75A, stop:0.55 #0EA5A4, stop:1 #6366F1);
}
#bannerTitle { color: white; font-size: 28px; font-weight: 800; background: transparent; }
#bannerSub { color: rgba(255,255,255,0.85); font-size: 14px; background: transparent; }
#countChip {
    color: white; font-size: 15px; font-weight: 700;
    background: rgba(255,255,255,0.18);
    border: 1px solid rgba(255,255,255,0.35);
    border-radius: 16px; padding: 6px 16px;
}

#card { background: #111A2E; border: 1px solid #1F2A44; border-radius: 16px; }
#fieldLabel { color: #94A3B8; font-weight: 700; background: transparent; }

QLineEdit, QComboBox {
    background: #0B1324; border: 2px solid #23304D; border-radius: 12px;
    padding: 9px 14px; font-size: 15px; color: #F1F5F9;
}
QLineEdit:focus, QComboBox:focus { border: 2px solid #03C75A; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView {
    background: #111A2E; border: 1px solid #23304D;
    selection-background-color: #03C75A; selection-color: #04130A;
}

QPushButton {
    border: none; border-radius: 12px; padding: 10px 22px;
    font-size: 15px; font-weight: 800; color: white;
}
QPushButton:disabled { background: #273449; color: #64748B; }
#searchButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #03C75A, stop:1 #10B981);
}
#searchButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #22E07A, stop:1 #34D399); }
#saveButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #8B5CF6, stop:1 #EC4899);
}
#saveButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #A78BFA, stop:1 #F472B6); }
#keyButton { background: #1E293B; border: 2px solid #334155; color: #FBBF24; }
#keyButton:hover { border: 2px solid #FBBF24; }

QDialog { background: #111A2E; }
QDialogButtonBox QPushButton { background: #03C75A; min-width: 70px; }
#hint { color: #94A3B8; font-size: 13px; }

QTableWidget {
    background: #0E1729; alternate-background-color: #121D33;
    border: none; border-radius: 12px; gridline-color: transparent;
    selection-background-color: #14532D; selection-color: #ECFDF5;
}
QTableWidget::item { padding: 6px 10px; border-bottom: 1px solid #1A253D; }
QTableWidget::item:hover { background: #1B2A47; }
QHeaderView::section {
    background: #16223B; color: #4ADE80; font-weight: 800;
    padding: 10px; border: none; border-bottom: 2px solid #03C75A;
}
QHeaderView { background: #0E1729; }
QTableCornerButton::section { background: #16223B; border: none; }
QHeaderView::section:vertical {
    background: #0E1729; color: #475569; border: none; border-bottom: none; font-weight: 600;
}

QScrollBar:vertical { background: transparent; width: 10px; margin: 4px; }
QScrollBar::handle:vertical { background: #334155; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #03C75A; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar:horizontal { height: 0; }

QToolTip { background: #1E293B; color: #F1F5F9; border: 1px solid #03C75A; padding: 6px; }
"""


def add_shadow(widget, color="#000000", blur=30):
    """위젯 아래에 은은한 그림자를 넣어 떠 있는 느낌을 줍니다."""
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, 6)
    shadow.setColor(QColor(color))
    widget.setGraphicsEffect(shadow)


class ApiKeyDialog(QDialog):
    """네이버 API의 Client ID / Client Secret 을 입력받는 작은 창"""

    def __init__(self, client_id, client_secret, parent=None):
        super().__init__(parent)
        self.setWindowTitle("네이버 API 키 설정")
        self.setMinimumWidth(460)

        hint = QLabel(
            "developers.naver.com → Application → 애플리케이션 등록에서\n"
            "'검색' API를 선택하면 Client ID와 Client Secret을 받을 수 있습니다."
        )
        hint.setObjectName("hint")

        self.id_input = QLineEdit(client_id)
        self.secret_input = QLineEdit(client_secret)
        self.secret_input.setEchoMode(QLineEdit.EchoMode.Password)  # 비밀번호처럼 가리기

        form = QFormLayout()
        form.addRow("Client ID", self.id_input)
        form.addRow("Client Secret", self.secret_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self):
        return self.id_input.text().strip(), self.secret_input.text().strip()


class CrawlThread(QThread):
    """API 호출은 시간이 걸리므로 별도 스레드에서 돌려 창이 멈추지 않게 합니다."""

    finished_ok = pyqtSignal(list)  # 성공하면 기사 리스트를 보냄
    failed = pyqtSignal(str)        # 실패하면 오류 메시지를 보냄

    def __init__(self, query, client_id, client_secret, sort, display):
        super().__init__()
        self.query = query
        self.client_id = client_id
        self.client_secret = client_secret
        self.sort = sort
        self.display = display

    def run(self):
        try:
            articles = crawl_naver_news(self.query, self.client_id, self.client_secret, self.sort, self.display)
            self.finished_ok.emit(articles)
        except ApiError as error:
            self.failed.emit(str(error))
        except requests.RequestException:
            self.failed.emit("네이버에 연결하지 못했습니다. 인터넷 연결을 확인하세요.")
        except Exception as error:
            self.failed.emit(str(error))


class NewsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("네이버 뉴스 크롤러")
        self.resize(1150, 720)
        self.setStyleSheet(STYLE)
        self.articles = []
        self.last_query = ""
        self.thread = None

        # API 키는 이 컴퓨터의 앱 설정(QSettings)에 저장합니다. 코드에는 넣지 않습니다.
        self.settings = QSettings("VibeCodingClass", "NaverNewsCrawler")
        self.client_id = self.settings.value("client_id", "")
        self.client_secret = self.settings.value("client_secret", "")

        # ── 맨 위: 그라데이션 배너 (제목 + 기사 수 표시) ──
        banner = QFrame()
        banner.setObjectName("banner")
        title = QLabel("📰  NAVER NEWS CRAWLER")
        title.setObjectName("bannerTitle")
        subtitle = QLabel("네이버 뉴스를 한 번에 모아 보고, 엑셀로 저장하세요")
        subtitle.setObjectName("bannerSub")
        self.count_chip = QLabel("✨ 준비 완료")
        self.count_chip.setObjectName("countChip")

        title_box = QVBoxLayout()
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(28, 22, 28, 22)
        banner_layout.addLayout(title_box, stretch=1)
        banner_layout.addWidget(self.count_chip)
        add_shadow(banner, "#03C75A", 40)

        # ── 검색 카드: 검색어 입력칸 + 검색 위치 + 버튼들 ──
        self.query_input = QLineEdit("반도체")
        self.query_input.setPlaceholderText("🔍  검색어를 입력하세요")
        self.query_input.returnPressed.connect(self.start_search)  # 엔터로도 검색

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(SORT_OPTIONS.keys())

        self.count_combo = QComboBox()
        self.count_combo.addItems(COUNT_OPTIONS)
        self.count_combo.setCurrentIndex(1)  # 기본 50건

        self.key_button = QPushButton("🔑  API 키")
        self.key_button.setObjectName("keyButton")
        self.key_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.key_button.clicked.connect(self.edit_api_key)

        self.search_button = QPushButton("🔍  검색")
        self.search_button.setObjectName("searchButton")
        self.search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.search_button.clicked.connect(self.start_search)

        self.save_button = QPushButton("📊  엑셀 저장")
        self.save_button.setObjectName("saveButton")
        self.save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_button.setEnabled(False)  # 검색 결과가 생기면 켜짐
        self.save_button.clicked.connect(self.save_excel)

        label = QLabel("검색어")
        label.setObjectName("fieldLabel")

        search_card = QFrame()
        search_card.setObjectName("card")
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(20, 16, 20, 16)
        search_layout.setSpacing(12)
        search_layout.addWidget(label)
        search_layout.addWidget(self.query_input, stretch=1)
        search_layout.addWidget(self.sort_combo)
        search_layout.addWidget(self.count_combo)
        search_layout.addWidget(self.search_button)
        search_layout.addWidget(self.save_button)
        search_layout.addWidget(self.key_button)
        add_shadow(search_card)

        # ── 결과 카드: 기사 표 ──
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels([name for name, _ in COLUMNS])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)  # 읽기 전용
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)  # 줄마다 배경색을 번갈아
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setMouseTracking(True)
        self.table.verticalHeader().setDefaultSectionSize(44)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 420)
        self.table.cellDoubleClicked.connect(self.open_article)

        table_card = QFrame()
        table_card.setObjectName("card")
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(10, 10, 10, 10)
        table_layout.addWidget(self.table)
        add_shadow(table_card)

        # ── 맨 아래: 상태 표시줄 ──
        self.status_label = QLabel()
        if self.client_id and self.client_secret:
            self.set_status("검색어를 넣고 [검색]을 누르세요. 기사를 더블클릭하면 브라우저로 열립니다.", "info")
        else:
            self.set_status("처음 사용하시나요? 오른쪽 위 [🔑 API 키]에 네이버 API 키를 먼저 입력하세요.", "info")

        layout = QVBoxLayout()
        layout.setContentsMargins(22, 22, 22, 18)
        layout.setSpacing(16)
        layout.addWidget(banner)
        layout.addWidget(search_card)
        layout.addWidget(table_card, stretch=1)
        layout.addWidget(self.status_label)

        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    def set_status(self, text, kind="info"):
        """상태 표시줄의 글자와 색을 바꿉니다. kind: info / busy / ok / error"""
        icons = {"info": "💡", "busy": "⏳", "ok": "✅", "error": "⚠️"}
        color, background = STATUS_COLORS[kind]
        self.status_label.setText(f"{icons[kind]}  {text}")
        self.status_label.setStyleSheet(
            f"color: {color}; background: {background}; border-radius: 10px;"
            f"padding: 10px 16px; font-weight: 600;"
        )

    def start_search(self):
        query = self.query_input.text().strip()
        if not query:
            self.set_status("검색어를 입력하세요.", "error")
            return
        if not (self.client_id and self.client_secret):
            self.edit_api_key()
            if not (self.client_id and self.client_secret):
                self.set_status("API 키가 있어야 검색할 수 있습니다.", "error")
                return
        sort = SORT_OPTIONS[self.sort_combo.currentText()]
        display = int(self.count_combo.currentText().removesuffix("건"))

        self.search_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self.search_button.setText("⏳  검색 중")
        self.set_status(f"'{query}' 검색 중...", "busy")
        self.last_query = query

        self.thread = CrawlThread(query, self.client_id, self.client_secret, sort, display)
        self.thread.finished_ok.connect(self.show_articles)
        self.thread.failed.connect(self.show_error)
        self.thread.start()

    def show_articles(self, articles):
        self.articles = articles
        self.table.setRowCount(len(articles))
        bold = QFont()
        bold.setBold(True)
        for row, article in enumerate(articles):
            for col, (_, key) in enumerate(COLUMNS):
                item = QTableWidgetItem(article[key])
                item.setToolTip(article[key])  # 마우스를 올리면 전체 내용 표시
                if key == "title":
                    item.setFont(bold)
                    item.setForeground(QColor("#F8FAFC"))
                elif key == "press":
                    # 같은 언론사는 항상 같은 색이 되도록 이름으로 색을 고릅니다.
                    color = PRESS_COLORS[sum(map(ord, article[key])) % len(PRESS_COLORS)]
                    item.setForeground(QColor(color))
                    item.setFont(bold)
                elif key == "written_at":
                    item.setForeground(QColor("#FBBF24"))
                else:
                    item.setForeground(QColor("#94A3B8"))
                self.table.setItem(row, col, item)

        self.search_button.setEnabled(True)
        self.search_button.setText("🔍  검색")
        self.save_button.setEnabled(len(articles) > 0)
        self.count_chip.setText(f"📰 {len(articles)}건")
        self.set_status(f"'{self.last_query}' 기사 {len(articles)}건을 가져왔습니다. 더블클릭하면 기사가 열립니다.", "ok")

    def save_excel(self):
        """저장할 위치를 물어본 뒤 현재 결과를 엑셀 파일로 저장합니다."""
        default_name = f"네이버뉴스_{self.last_query}_{datetime.now():%Y%m%d_%H%M}.xlsx"
        default_path = os.path.join(os.path.expanduser("~/Desktop"), default_name)
        path, _ = QFileDialog.getSaveFileName(self, "엑셀로 저장", default_path, "엑셀 파일 (*.xlsx)")
        if not path:  # 취소를 누른 경우
            return
        if not path.endswith(".xlsx"):
            path += ".xlsx"

        try:
            save_to_excel(self.articles, path, self.last_query)
        except Exception as error:
            # 같은 파일이 엑셀에서 열려 있으면 저장이 안 될 수 있습니다.
            self.set_status(f"저장 실패: {error}", "error")
            return
        self.set_status(f"엑셀로 저장했습니다: {path}", "ok")

    def show_error(self, message):
        self.search_button.setEnabled(True)
        self.search_button.setText("🔍  검색")
        self.set_status(f"오류가 났습니다: {message}", "error")

    def edit_api_key(self):
        """API 키 입력 창을 띄우고, 입력한 키를 앱 설정에 저장합니다."""
        dialog = ApiKeyDialog(self.client_id, self.client_secret, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.client_id, self.client_secret = dialog.values()
        self.settings.setValue("client_id", self.client_id)
        self.settings.setValue("client_secret", self.client_secret)
        self.set_status("API 키를 저장했습니다. 이제 [검색]을 누르세요.", "ok")

    def open_article(self, row, column):
        """더블클릭한 기사를 기본 브라우저로 엽니다."""
        QDesktopServices.openUrl(QUrl(self.articles[row]["link"]))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 운영체제 기본 모양 대신 스타일시트가 잘 먹는 Fusion 스타일
    window = NewsWindow()
    window.show()
    sys.exit(app.exec())
