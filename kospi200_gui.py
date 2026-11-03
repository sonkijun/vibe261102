"""
코스피200 크롤러 GUI (PyQt6)

kospi200_crawler.py의 수집 함수를 그대로 사용하고, 화면만 PyQt6로 만든 버전입니다.

사용법:
    .venv/bin/python3.15 -m pip install requests PyQt6 openpyxl
    .venv/bin/python3.15 kospi200_gui.py
"""

import sys
from datetime import datetime

from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from kospi200_crawler import fetch_constituents, fetch_daily_prices, fetch_index_summary, save_csv, save_xlsx

RISE_COLOR = QColor("#d32f2f")  # 국내 관례: 상승 빨강
FALL_COLOR = QColor("#1565c0")  # 하락 파랑
AUTO_REFRESH_MS = 60_000


def to_number(text):
    """'1,388,000' / '-4.15' 같은 문자열을 정렬용 숫자로 변환."""
    try:
        return float(str(text).replace(",", ""))
    except ValueError:
        return float("-inf")


class NumericItem(QTableWidgetItem):
    """콤마가 들어간 숫자도 숫자 크기대로 정렬되는 셀."""

    def __lt__(self, other):
        return to_number(self.text()) < to_number(other.text())


class FetchWorker(QObject):
    """네트워크 요청을 UI 스레드 밖에서 실행."""

    finished = pyqtSignal(dict, list, list)
    failed = pyqtSignal(str)

    def run(self):
        try:
            summary = fetch_index_summary()
            daily = fetch_daily_prices(20)
            stocks = fetch_constituents()
        except Exception as e:  # 네트워크/응답 형식 오류를 화면에 표시
            self.failed.emit(str(e))
            return
        self.finished.emit(summary, daily, stocks)


class MainWindow(QMainWindow):
    STOCK_COLUMNS = ["종목코드", "종목명", "현재가", "전일대비", "등락률(%)", "거래량", "거래대금(백만)", "시가총액(억)"]
    DAILY_COLUMNS = ["날짜", "종가", "전일대비", "등락률(%)", "시가", "고가", "저가"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("코스피200 시세")
        self.resize(1320, 760)
        self.stocks = []
        self.thread = None

        # 상단: 지수 요약
        self.index_label = QLabel("코스피 200  -")
        self.index_label.setFont(QFont(self.font().family(), 20, QFont.Weight.Bold))
        self.change_label = QLabel("")
        self.change_label.setFont(QFont(self.font().family(), 14))
        self.time_label = QLabel("")
        self.time_label.setStyleSheet("color: gray;")

        summary_box = QHBoxLayout()
        summary_box.addWidget(self.index_label)
        summary_box.addSpacing(12)
        summary_box.addWidget(self.change_label)
        summary_box.addStretch()
        summary_box.addWidget(self.time_label)

        # 툴바: 검색 / 새로고침 / 자동 새로고침 / CSV 저장
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("종목명 또는 종목코드 검색")
        self.search_edit.textChanged.connect(self.apply_filter)
        self.refresh_button = QPushButton("새로고침")
        self.refresh_button.clicked.connect(self.refresh)
        self.auto_check = QCheckBox("1분마다 자동 새로고침")
        self.auto_check.toggled.connect(self.toggle_auto_refresh)
        self.save_button = QPushButton("CSV 저장")
        self.save_button.clicked.connect(lambda: self.save("csv"))
        self.save_button.setEnabled(False)
        self.excel_button = QPushButton("엑셀 저장")
        self.excel_button.clicked.connect(lambda: self.save("xlsx"))
        self.excel_button.setEnabled(False)

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.search_edit, 1)
        toolbar.addWidget(self.auto_check)
        toolbar.addWidget(self.refresh_button)
        toolbar.addWidget(self.save_button)
        toolbar.addWidget(self.excel_button)

        # 본문: 편입종목(왼쪽) + 일별 시세(오른쪽)
        self.stock_table = self.make_table(self.STOCK_COLUMNS)
        self.daily_table = self.make_table(self.DAILY_COLUMNS)
        self.stock_title = QLabel("편입종목")
        daily_title = QLabel("일별 시세")

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(self.stock_title)
        left_layout.addWidget(self.stock_table)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(daily_title)
        right_layout.addWidget(self.daily_table)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([860, 460])

        layout = QVBoxLayout()
        layout.addLayout(summary_box)
        layout.addLayout(toolbar)
        layout.addWidget(splitter, 1)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.timer = QTimer(self)
        self.timer.setInterval(AUTO_REFRESH_MS)
        self.timer.timeout.connect(self.refresh)

        self.refresh()

    def make_table(self, columns):
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        # 기본 정렬 표시(0번 열)를 지워서 처음에는 API가 준 순서(시가총액 순) 그대로 보여줌
        table.horizontalHeader().setSortIndicator(-1, Qt.SortOrder.AscendingOrder)
        return table

    def fill_table(self, table, columns, rows, text_columns):
        table.setSortingEnabled(False)  # 채우는 동안 정렬이 끼어들지 않게
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            color = None
            ratio = to_number(row.get("등락률(%)", 0))
            if ratio > 0:
                color = RISE_COLOR
            elif ratio < 0:
                color = FALL_COLOR
            for c, key in enumerate(columns):
                value = str(row[key])
                if key in text_columns:
                    item = QTableWidgetItem(value)
                else:
                    item = NumericItem(value)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if color and key in ("현재가", "종가", "전일대비", "등락률(%)"):
                        item.setForeground(color)
                table.setItem(r, c, item)
        table.setSortingEnabled(True)

    def refresh(self):
        if self.thread is not None:  # 이미 수집 중
            return
        self.refresh_button.setEnabled(False)
        self.statusBar().showMessage("데이터를 가져오는 중...")

        self.thread = QThread(self)
        self.worker = FetchWorker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_loaded)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.on_thread_done)
        self.thread.start()

    def on_thread_done(self):
        self.thread.deleteLater()
        self.worker.deleteLater()
        self.thread = None
        self.refresh_button.setEnabled(True)

    def on_loaded(self, summary, daily, stocks):
        self.stocks = stocks

        ratio = to_number(summary["등락률(%)"])
        color = RISE_COLOR.name() if ratio > 0 else FALL_COLOR.name() if ratio < 0 else "black"
        arrow = "▲" if ratio > 0 else "▼" if ratio < 0 else ""
        self.index_label.setText(f"{summary['지수명']}  {summary['현재가']}")
        self.index_label.setStyleSheet(f"color: {color};")
        self.change_label.setText(f"{arrow} {summary['전일대비']}  ({summary['등락률(%)']}%)")
        self.change_label.setStyleSheet(f"color: {color};")
        self.time_label.setText(f"{summary['장상태']} · 기준 {summary['기준시각']}")

        self.fill_table(self.stock_table, self.STOCK_COLUMNS, stocks, {"종목코드", "종목명"})
        self.fill_table(self.daily_table, self.DAILY_COLUMNS, daily, {"날짜"})
        self.apply_filter(self.search_edit.text())
        self.save_button.setEnabled(bool(stocks))
        self.excel_button.setEnabled(bool(stocks))
        self.statusBar().showMessage(f"편입종목 {len(stocks)}개 수집 완료 ({datetime.now():%H:%M:%S})")

    def on_failed(self, message):
        self.statusBar().showMessage("수집 실패")
        QMessageBox.warning(self, "수집 실패", f"데이터를 가져오지 못했습니다.\n\n{message}")

    def apply_filter(self, text):
        text = text.strip().lower()
        visible = 0
        for r in range(self.stock_table.rowCount()):
            code = self.stock_table.item(r, 0).text().lower()
            name = self.stock_table.item(r, 1).text().lower()
            hidden = bool(text) and text not in code and text not in name
            self.stock_table.setRowHidden(r, hidden)
            visible += not hidden
        total = self.stock_table.rowCount()
        self.stock_title.setText(f"편입종목 {total}개" if visible == total else f"편입종목 {visible} / {total}개")

    def toggle_auto_refresh(self, on):
        if on:
            self.timer.start()
        else:
            self.timer.stop()

    def save(self, fmt):
        title, file_filter, writer = {
            "csv": ("CSV 저장", "CSV 파일 (*.csv)", save_csv),
            "xlsx": ("엑셀 저장", "Excel 파일 (*.xlsx)", save_xlsx),
        }[fmt]
        default = f"kospi200_{datetime.now():%Y%m%d}.{fmt}"
        path, _ = QFileDialog.getSaveFileName(self, title, default, file_filter)
        if not path:
            return
        if not path.lower().endswith(f".{fmt}"):
            path += f".{fmt}"
        try:
            writer(self.stocks, path)
        except Exception as e:  # 파일이 엑셀에서 열려 있는 경우 등
            QMessageBox.warning(self, "저장 실패", f"파일을 저장하지 못했습니다.\n\n{e}")
            return
        self.statusBar().showMessage(f"{path} 에 {len(self.stocks)}개 종목을 저장했습니다.")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
