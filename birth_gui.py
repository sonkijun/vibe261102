"""
대한민국 출생아수 데이터 분석 GUI (PyQt6)

birth_analysis.py의 클렌징·분석·차트 함수를 그대로 사용하고, 화면만 PyQt6로 만든 버전입니다.

사용법:
    .venv/bin/python birth_gui.py
"""

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
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
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from birth_analysis import (
    DEFAULT_XLSX,
    OUT_DIR,
    analyze,
    draw_births_line,
    draw_dashboard,
    load_and_clean,
    save_charts,
)

RISE_COLOR = QColor("#d32f2f")  # 국내 관례: 증가 빨강
FALL_COLOR = QColor("#1565c0")  # 감소 파랑
DEFAULT_START = 1970
DEFAULT_END = 2025


class NumericItem(QTableWidgetItem):
    """표시는 포맷된 문자열, 정렬은 실제 숫자 크기로 하는 셀."""

    def __init__(self, text, value):
        super().__init__(text)
        self.value = float("-inf") if pd.isna(value) else float(value)
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
    # (표시 이름, 컬럼, 포맷)
    TABLE_COLUMNS = [
        ("연도", None, None),
        ("출생아수(명)", "출생아수", "{:,.0f}"),
        ("전년 대비", "출생아수_증감률", "{:+.2%}"),
        ("사망자수(추정)", "사망자수", "{:,.0f}"),
        ("자연증가(명)", "자연증가", "{:,.0f}"),
        ("합계출산율", "합계출산율", "{:.2f}"),
        ("조출생률(천명당)", "조출생률", "{:.1f}"),
        ("자연증가율(천명당)", "자연증가율", "{:.1f}"),
        ("출생성비", "출생성비", "{:.1f}"),
    ]
    DECADE_COLUMNS = [
        ("평균출생아수", "{:,.0f}"),
        ("평균합계출산율", "{:.2f}"),
        ("평균출생성비", "{:.1f}"),
        ("자연증가합계", "{:,.0f}"),
        ("연대간_변화율", "{:+.1%}"),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("대한민국 출생아수 데이터 분석")
        self.resize(1400, 860)
        self.df = None
        self.result = None

        central = QWidget()
        root = QVBoxLayout(central)
        self.setCentralWidget(central)

        # --- 상단: 파일 선택 / 실행 / 저장 ---
        top = QHBoxLayout()
        self.path_edit = QLineEdit(str(DEFAULT_XLSX))
        open_btn = QPushButton("엑셀 열기...")
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
        for i, name in enumerate(["기간", "최근 출생아수", "전년 대비", "최근 합계출산율",
                                  "최저 출생아수", "자연감소 시작"]):
            self.cards[name] = KpiCard(name)
            kpi.addWidget(self.cards[name], 0, i)
        root.addLayout(kpi)

        # --- 탭 ---
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # (1) 출생아수 라인그래프 + 연도 범위 선택
        line_page = QWidget()
        line_layout = QVBoxLayout(line_page)
        line_layout.setContentsMargins(0, 0, 0, 0)
        range_bar = QHBoxLayout()
        self.start_spin = QSpinBox()
        self.end_spin = QSpinBox()
        for spin, value in ((self.start_spin, DEFAULT_START), (self.end_spin, DEFAULT_END)):
            spin.setRange(DEFAULT_START, DEFAULT_END)
            spin.setValue(value)
            spin.setSuffix("년")
        apply_btn = QPushButton("기간 적용")
        apply_btn.clicked.connect(self.update_line_chart)
        reset_btn = QPushButton("1970 ~ 2025")
        reset_btn.clicked.connect(self.reset_range)
        recent_btn = QPushButton("최근 20년")
        recent_btn.clicked.connect(self.recent_range)
        range_bar.addWidget(QLabel("시작 연도"))
        range_bar.addWidget(self.start_spin)
        range_bar.addWidget(QLabel("종료 연도"))
        range_bar.addWidget(self.end_spin)
        range_bar.addWidget(apply_btn)
        range_bar.addWidget(reset_btn)
        range_bar.addWidget(recent_btn)
        range_bar.addStretch()
        line_layout.addLayout(range_bar)
        self.line_tab = ChartTab((14, 6))
        line_layout.addWidget(self.line_tab)
        self.tabs.addTab(line_page, "출생아수 라인그래프")

        self.dashboard_tab = ChartTab((16, 10))
        self.tabs.addTab(self.dashboard_tab, "분석 대시보드")

        # (3) 연대별 요약 표
        self.decade_table = QTableWidget(0, len(self.DECADE_COLUMNS))
        self.decade_table.setHorizontalHeaderLabels([c for c, _ in self.DECADE_COLUMNS])
        self.decade_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.decade_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabs.addTab(self.decade_table, "연대별 요약")

        # (4) 텍스트 리포트
        self.report = QPlainTextEdit()
        self.report.setReadOnly(True)
        self.report.setFont(QFont("Menlo", 11))
        self.report.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.tabs.addTab(self.report, "분석 리포트")

        # (5) 클렌징된 데이터 표
        self.table = QTableWidget(0, len(self.TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels([c for c, _, _ in self.TABLE_COLUMNS])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.tabs.addTab(self.table, "클렌징 데이터")

        self.statusBar().showMessage("엑셀 파일을 선택한 뒤 [분석 실행]을 누르세요.")

        if DEFAULT_XLSX.exists():
            self.run_analysis()

    # ------------------------------------------------------------------
    def choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "KOSIS 출생아수 엑셀 선택",
                                              str(Path(self.path_edit.text()).parent),
                                              "엑셀 파일 (*.xlsx);;모든 파일 (*)")
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
        except Exception as e:  # 형식이 다른 엑셀 등
            QMessageBox.critical(self, "분석 실패", f"데이터를 분석하지 못했습니다.\n\n{e}")
            return

        self.df, self.result = df, result
        first, last = int(df.index.min()), int(df.index.max())
        for spin in (self.start_spin, self.end_spin):
            spin.setRange(first, last)
        self.start_spin.setValue(first)
        self.end_spin.setValue(last)

        self.report.setPlainText(log.getvalue())
        self.fill_kpis()
        self.fill_table()
        self.fill_decade_table()
        self.update_line_chart()
        self.dashboard_tab.redraw(draw_dashboard, df, result)
        self.save_btn.setEnabled(True)
        self.statusBar().showMessage(f"{path.name}: {len(df)}개 연도 분석 완료 ({first} ~ {last})")

    def fill_kpis(self):
        df = self.df
        births = df["출생아수"].astype(float)
        last = df.index[-1]
        chg = df.loc[last, "출생아수_증감률"]
        nat_loss = df.index[df["자연증가"] < 0]

        self.cards["기간"].set(f"{df.index[0]} ~ {last}")
        self.cards["최근 출생아수"].set(f"{births[last]:,.0f}명 ({last})")
        self.cards["전년 대비"].set(f"{chg:+.2%}", RISE_COLOR if chg > 0 else FALL_COLOR)
        self.cards["최근 합계출산율"].set(f"{df.loc[last, '합계출산율']:.2f}명")
        self.cards["최저 출생아수"].set(f"{births.min():,.0f}명 ({births.idxmin()})", FALL_COLOR)
        self.cards["자연감소 시작"].set(f"{nat_loss[0]}년" if len(nat_loss) else "없음",
                                     FALL_COLOR if len(nat_loss) else None)

    def fill_table(self):
        data = self.df.iloc[::-1]  # 최신 연도가 위로
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(data))
        for row, (year, rec) in enumerate(data.iterrows()):
            self.table.setItem(row, 0, NumericItem(str(year), year))
            for col, (_, key, fmt) in enumerate(self.TABLE_COLUMNS[1:], start=1):
                value = rec[key]
                item = NumericItem("-" if pd.isna(value) else fmt.format(value), value)
                if key in ("출생아수_증감률", "자연증가") and not pd.isna(value) and value != 0:
                    item.setForeground(RISE_COLOR if value > 0 else FALL_COLOR)
                self.table.setItem(row, col, item)
        self.table.setSortingEnabled(True)

    def fill_decade_table(self):
        decade = self.result["decade"]
        self.decade_table.setRowCount(len(decade))
        self.decade_table.setVerticalHeaderLabels(list(decade.index))
        for row, (_, rec) in enumerate(decade.iterrows()):
            for col, (key, fmt) in enumerate(self.DECADE_COLUMNS):
                value = rec[key]
                item = NumericItem("-" if pd.isna(value) else fmt.format(value), value)
                if key in ("연대간_변화율", "자연증가합계") and not pd.isna(value) and value != 0:
                    item.setForeground(RISE_COLOR if value > 0 else FALL_COLOR)
                self.decade_table.setItem(row, col, item)

    def update_line_chart(self):
        if self.df is None:
            return
        start, end = self.start_spin.value(), self.end_spin.value()
        if start >= end:
            QMessageBox.warning(self, "기간 오류", "시작 연도는 종료 연도보다 앞서야 합니다.")
            return
        self.line_tab.redraw(draw_births_line, self.df, start, end)

    def reset_range(self):
        self.start_spin.setValue(self.start_spin.minimum())
        self.end_spin.setValue(self.end_spin.maximum())
        self.update_line_chart()

    def recent_range(self):
        last = self.end_spin.maximum()
        self.start_spin.setValue(max(self.start_spin.minimum(), last - 19))
        self.end_spin.setValue(last)
        self.update_line_chart()

    def save_results(self):
        folder = QFileDialog.getExistingDirectory(self, "저장할 폴더 선택", str(OUT_DIR.parent))
        if not folder:
            return
        out_dir = Path(folder) / OUT_DIR.name
        paths = save_charts(self.df, self.result, out_dir,
                            self.start_spin.value(), self.end_spin.value())
        self.df.to_csv(out_dir / "births_cleaned.csv", encoding="utf-8-sig")
        (out_dir / "analysis_report.txt").write_text(self.report.toPlainText(), encoding="utf-8")
        QMessageBox.information(self, "저장 완료",
                                f"{out_dir}\n\n" + "\n".join(p.name for p in paths)
                                + "\nbirths_cleaned.csv\nanalysis_report.txt")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
