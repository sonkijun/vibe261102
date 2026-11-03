"""
S&P 500 데이터 분석 GUI (PyQt6)

sp500_analysis.py의 클렌징·분석·차트 함수를 그대로 사용하고, 화면만 PyQt6로 만든 버전입니다.

사용법:
    .venv/bin/python sp500_gui.py
"""

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QDateEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from sp500_analysis import (
    DEFAULT_CSV,
    OUT_DIR,
    analyze,
    draw_close_line,
    draw_dashboard,
    draw_monthly_heatmap,
    load_and_clean,
    save_charts,
)

RISE_COLOR = QColor("#d32f2f")  # 국내 관례: 상승 빨강
FALL_COLOR = QColor("#1565c0")  # 하락 파랑
DEFAULT_START = QDate(2000, 1, 1)
DEFAULT_END = QDate(2019, 12, 31)


class NumericItem(QTableWidgetItem):
    """표시는 포맷된 문자열, 정렬은 실제 숫자 크기로 하는 셀."""

    def __init__(self, text, value):
        super().__init__(text)
        self.value = value
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other):
        return self.value < other.value


class ChartTab(QWidget):
    """matplotlib Figure + 확대/이동 툴바를 담은 탭."""

    def __init__(self, figsize):
        super().__init__()
        self.figure = Figure(figsize=figsize)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(4, 4, 4, 4)
        self.layout_.addWidget(NavigationToolbar2QT(self.canvas, self))
        self.layout_.addWidget(self.canvas)

    def redraw(self, draw_func, *args):
        draw_func(self.figure, *args)
        self.canvas.draw_idle()


class KpiCard(QFrame):
    def __init__(self, title):
        super().__init__()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        self.title = QLabel(title)
        self.title.setStyleSheet("color: gray;")
        self.value = QLabel("-")
        self.value.setFont(QFont(self.value.font().family(), 15, QFont.Weight.Bold))
        layout.addWidget(self.title)
        layout.addWidget(self.value)

    def set(self, text, color=None):
        self.value.setText(text)
        self.value.setStyleSheet(f"color: {color.name()};" if color else "")


class MainWindow(QMainWindow):
    TABLE_COLUMNS = ["날짜", "종가", "시가", "고가", "저가", "변동 %"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("S&P 500 데이터 분석")
        self.resize(1400, 860)
        self.df = None
        self.result = None

        central = QWidget()
        root = QVBoxLayout(central)
        self.setCentralWidget(central)

        # --- 상단: 파일 선택 / 실행 / 저장 ---
        top = QHBoxLayout()
        self.path_edit = QLineEdit(str(DEFAULT_CSV))
        open_btn = QPushButton("CSV 열기...")
        open_btn.clicked.connect(self.choose_file)
        self.run_btn = QPushButton("분석 실행")
        self.run_btn.setDefault(True)
        self.run_btn.clicked.connect(self.run_analysis)
        self.save_btn = QPushButton("결과 저장...")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_results)
        top.addWidget(QLabel("데이터 파일:"))
        top.addWidget(self.path_edit, 1)
        top.addWidget(open_btn)
        top.addWidget(self.run_btn)
        top.addWidget(self.save_btn)
        root.addLayout(top)

        # --- KPI 카드 ---
        kpi = QGridLayout()
        self.cards = {}
        for i, name in enumerate(["기간", "마지막 종가", "누적 수익률", "연평균(CAGR)", "연환산 변동성", "최대 낙폭(MDD)"]):
            self.cards[name] = KpiCard(name)
            kpi.addWidget(self.cards[name], 0, i)
        root.addLayout(kpi)

        # --- 탭 ---
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # (1) 종가 라인그래프 + 기간 선택
        line_page = QWidget()
        line_layout = QVBoxLayout(line_page)
        line_layout.setContentsMargins(0, 0, 0, 0)
        range_bar = QHBoxLayout()
        self.start_edit = QDateEdit(DEFAULT_START)
        self.end_edit = QDateEdit(DEFAULT_END)
        for edit in (self.start_edit, self.end_edit):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("yyyy-MM-dd")
        apply_btn = QPushButton("기간 적용")
        apply_btn.clicked.connect(self.update_line_chart)
        reset_btn = QPushButton("2000.01 ~ 2019.12")
        reset_btn.clicked.connect(self.reset_range)
        all_btn = QPushButton("전체 기간")
        all_btn.clicked.connect(self.full_range)
        range_bar.addWidget(QLabel("시작일"))
        range_bar.addWidget(self.start_edit)
        range_bar.addWidget(QLabel("종료일"))
        range_bar.addWidget(self.end_edit)
        range_bar.addWidget(apply_btn)
        range_bar.addWidget(reset_btn)
        range_bar.addWidget(all_btn)
        range_bar.addStretch()
        line_layout.addLayout(range_bar)
        self.line_tab = ChartTab((14, 6))
        line_layout.addWidget(self.line_tab)
        self.tabs.addTab(line_page, "종가 라인그래프")

        self.dashboard_tab = ChartTab((16, 10))
        self.tabs.addTab(self.dashboard_tab, "분석 대시보드")
        self.heatmap_tab = ChartTab((12, 8))
        self.tabs.addTab(self.heatmap_tab, "월별 히트맵")

        # (4) 텍스트 리포트
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setFont(QFont("Menlo", 11))
        self.report.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.tabs.addTab(self.report, "분석 리포트")

        # (5) 클렌징된 데이터 표
        self.table = QTableWidget(0, len(self.TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels(self.TABLE_COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.tabs.addTab(self.table, "클렌징 데이터")

        self.statusBar().showMessage("CSV 파일을 선택한 뒤 [분석 실행]을 누르세요.")

        if DEFAULT_CSV.exists():
            self.run_analysis()

    # ------------------------------------------------------------------
    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "S&P 500 CSV 선택", str(Path(self.path_edit.text()).parent),
                                              "CSV 파일 (*.csv);;모든 파일 (*)")
        if path:
            self.path_edit.setText(path)
            self.run_analysis()

    def run_analysis(self):
        path = Path(self.path_edit.text().strip())
        if not path.exists():
            QMessageBox.warning(self, "파일 없음", f"파일을 찾을 수 없습니다:\n{path}")
            return

        log = io.StringIO()
        try:
            # 기존 분석 함수의 print 출력을 그대로 리포트 탭에 표시
            with redirect_stdout(log):
                df = load_and_clean(path)
                result = analyze(df)
        except Exception as e:  # 형식이 다른 CSV 등
            QMessageBox.critical(self, "분석 실패", f"데이터를 분석하지 못했습니다.\n\n{e}")
            return

        self.df, self.result = df, result
        self.report.setPlainText(log.getvalue())
        self.fill_kpis()
        self.fill_table()
        self.update_line_chart()
        self.dashboard_tab.redraw(draw_dashboard, df, result)
        self.heatmap_tab.redraw(draw_monthly_heatmap, result["monthly_ret"])
        self.save_btn.setEnabled(True)
        self.statusBar().showMessage(
            f"{path.name}: {len(df):,}행 분석 완료 ({df.index.min():%Y-%m-%d} ~ {df.index.max():%Y-%m-%d})")

    def fill_kpis(self):
        close = self.df["Close"]
        ret = self.df["Return"].dropna()
        years = (close.index[-1] - close.index[0]).days / 365.25
        total = close.iloc[-1] / close.iloc[0] - 1
        cagr = (close.iloc[-1] / close.iloc[0]) ** (1 / years) - 1
        mdd = self.result["drawdown"].min()

        def color(v):
            return RISE_COLOR if v > 0 else FALL_COLOR

        self.cards["기간"].set(f"{close.index[0]:%Y.%m.%d} ~ {close.index[-1]:%Y.%m.%d}")
        self.cards["마지막 종가"].set(f"{close.iloc[-1]:,.2f}")
        self.cards["누적 수익률"].set(f"{total:+.2%}", color(total))
        self.cards["연평균(CAGR)"].set(f"{cagr:+.2%}", color(cagr))
        self.cards["연환산 변동성"].set(f"{ret.std() * np.sqrt(252):.2%}")
        self.cards["최대 낙폭(MDD)"].set(f"{mdd:.2%}", FALL_COLOR)

    def fill_table(self):
        data = self.df.iloc[::-1]  # 최신 날짜가 위로
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(data))
        for row, (date, rec) in enumerate(data.iterrows()):
            self.table.setItem(row, 0, QTableWidgetItem(date.strftime("%Y-%m-%d")))
            for col, key in enumerate(["Close", "Open", "High", "Low"], start=1):
                self.table.setItem(row, col, NumericItem(f"{rec[key]:,.2f}", rec[key]))
            change = NumericItem(f"{rec['Change']:+.2%}", rec["Change"])
            if rec["Change"] != 0:
                change.setForeground(RISE_COLOR if rec["Change"] > 0 else FALL_COLOR)
            self.table.setItem(row, 5, change)
        self.table.setSortingEnabled(True)

    def update_line_chart(self):
        if self.df is None:
            return
        start = self.start_edit.date().toString("yyyy-MM-dd")
        end = self.end_edit.date().toString("yyyy-MM-dd")
        if start > end:
            QMessageBox.warning(self, "기간 오류", "시작일이 종료일보다 늦습니다.")
            return
        self.line_tab.redraw(draw_close_line, self.df, start, end)

    def reset_range(self):
        self.start_edit.setDate(DEFAULT_START)
        self.end_edit.setDate(DEFAULT_END)
        self.update_line_chart()

    def full_range(self):
        if self.df is None:
            return
        first, last = self.df.index.min(), self.df.index.max()
        self.start_edit.setDate(QDate(first.year, first.month, first.day))
        self.end_edit.setDate(QDate(last.year, last.month, last.day))
        self.update_line_chart()

    def save_results(self):
        folder = QFileDialog.getExistingDirectory(self, "저장할 폴더 선택", str(OUT_DIR.parent))
        if not folder:
            return
        out_dir = Path(folder) / OUT_DIR.name
        start = self.start_edit.date().toString("yyyy-MM-dd")
        end = self.end_edit.date().toString("yyyy-MM-dd")
        paths = save_charts(self.df, self.result, out_dir, start, end)
        self.df.to_csv(out_dir / "sp500_cleaned.csv", encoding="utf-8-sig")
        (out_dir / "analysis_report.txt").write_text(self.report.toPlainText(), encoding="utf-8")
        QMessageBox.information(self, "저장 완료",
                                f"{out_dir}\n\n" + "\n".join(p.name for p in paths)
                                + "\nsp500_cleaned.csv\nanalysis_report.txt")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
