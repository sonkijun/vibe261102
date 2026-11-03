"""
S&P 500 과거 데이터 클렌징 + 다각도 분석 + 종가 라인그래프

사용법:
    python sp500_analysis.py [CSV 경로]
    (경로를 생략하면 같은 폴더의 "S&P 500 과거 데이터.csv"를 사용)

결과물은 sp500_output/ 폴더에 저장됩니다.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = BASE_DIR / "S&P 500 과거 데이터.csv"
if getattr(sys, "frozen", False):
    # PyInstaller 실행파일: 번들 내부는 쓰기용이 아니므로 결과는 문서 폴더에 저장
    OUT_DIR = Path.home() / "Documents" / "sp500_output"
else:
    OUT_DIR = BASE_DIR / "sp500_output"

# 한글 폰트 (macOS: AppleGothic, Windows: Malgun Gothic)
_installed = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = next(
    (f for f in ["AppleGothic", "Malgun Gothic", "NanumGothic"] if f in _installed), "DejaVu Sans")
plt.rcParams["axes.unicode_minus"] = False


# ---------------------------------------------------------------------------
# 1. 데이터 클렌징
# ---------------------------------------------------------------------------
def load_and_clean(csv_path: Path) -> pd.DataFrame:
    # utf-8-sig: 첫 컬럼명 앞의 BOM(﻿) 제거
    raw = pd.read_csv(csv_path, encoding="utf-8-sig", dtype=str)
    print(f"[원본] {raw.shape[0]:,}행 x {raw.shape[1]}열")
    print(f"[원본 컬럼] {list(raw.columns)}")

    df = raw.rename(columns={
        "날짜": "Date", "종가": "Close", "시가": "Open", "고가": "High",
        "저가": "Low", "거래량": "Volume", "변동 %": "Change",
    })

    # 날짜: "2019- 11- 14" 처럼 공백이 섞여 있음 → 공백 제거 후 변환
    df["Date"] = pd.to_datetime(df["Date"].str.replace(" ", "", regex=False),
                                format="%Y-%m-%d", errors="coerce")

    # 가격: 천 단위 콤마 제거 후 float 변환
    for col in ["Close", "Open", "High", "Low"]:
        df[col] = pd.to_numeric(df[col].str.replace(",", "", regex=False), errors="coerce")

    # 변동률: "%" 제거 후 소수(0.0008)로 변환
    df["Change"] = pd.to_numeric(df["Change"].str.replace("%", "", regex=False),
                                 errors="coerce") / 100

    # 거래량: 전부 비어 있으면 분석 의미가 없으므로 컬럼 삭제
    if df["Volume"].replace("", np.nan).isna().all():
        print("[클렌징] 거래량 컬럼이 전부 비어 있어 삭제")
        df = df.drop(columns="Volume")

    # 결측치 / 중복 처리
    before = len(df)
    df = df.dropna(subset=["Date", "Close"])
    df = df.drop_duplicates(subset="Date", keep="first")
    print(f"[클렌징] 날짜/종가 결측 또는 중복 제거: {before - len(df)}행")

    # 날짜 오름차순 정렬 후 인덱스로 지정
    df = df.sort_values("Date").set_index("Date")

    # 가격 논리 검증: 고가 >= max(시가, 종가, 저가), 저가 <= min(...)
    bad = df[(df["High"] < df[["Open", "Close", "Low"]].max(axis=1)) |
             (df["Low"] > df[["Open", "Close", "High"]].min(axis=1))]
    print(f"[검증] 고가/저가 논리 위반 행: {len(bad)}개")
    if not bad.empty:
        print(bad.head())

    # 변동률 재계산 후 원본과 비교 (데이터 누락일 검출용)
    df["Return"] = df["Close"].pct_change()
    diff = (df["Return"] - df["Change"]).abs()
    mismatch = df[diff > 0.0005]
    print(f"[검증] 재계산 수익률과 원본 변동%가 0.05%p 이상 차이나는 행: {len(mismatch)}개")

    print(f"[결과] {len(df):,}행, 기간 {df.index.min().date()} ~ {df.index.max().date()}")
    print(f"[결측치]\n{df.isna().sum().to_string()}\n")
    return df


# ---------------------------------------------------------------------------
# 2. 다각도 분석
# ---------------------------------------------------------------------------
def section(title: str) -> None:
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def analyze(df: pd.DataFrame) -> dict:
    close = df["Close"]
    ret = df["Return"].dropna()
    result = {}

    section("① 기술 통계")
    print(df[["Open", "High", "Low", "Close"]].describe().round(2).to_string())

    section("② 전체 기간 성과")
    years = (close.index[-1] - close.index[0]).days / 365.25
    total = close.iloc[-1] / close.iloc[0] - 1
    cagr = (close.iloc[-1] / close.iloc[0]) ** (1 / years) - 1
    vol = ret.std() * np.sqrt(252)
    print(f"시작 종가     : {close.iloc[0]:,.2f} ({close.index[0].date()})")
    print(f"마지막 종가   : {close.iloc[-1]:,.2f} ({close.index[-1].date()})")
    print(f"누적 수익률   : {total:.2%}")
    print(f"연평균(CAGR)  : {cagr:.2%}")
    print(f"연환산 변동성 : {vol:.2%}")
    print(f"샤프지수(무위험 0%): {ret.mean() * 252 / vol:.2f}")
    print(f"최고 종가     : {close.max():,.2f} ({close.idxmax().date()})")
    print(f"최저 종가     : {close.min():,.2f} ({close.idxmin().date()})")

    section("③ 연도별 수익률 / 변동성")
    yearly = pd.DataFrame({
        "시작": close.resample("YE").first(),
        "종료": close.resample("YE").last(),
        "수익률": close.resample("YE").last().pct_change(),
        "변동성": ret.resample("YE").std() * np.sqrt(252),
        "거래일": close.resample("YE").count(),
    })
    # 첫 해는 전년 말 데이터가 없으므로 그 해 첫 종가 대비로 계산
    yearly.iloc[0, yearly.columns.get_loc("수익률")] = yearly["종료"].iloc[0] / yearly["시작"].iloc[0] - 1
    yearly.index = yearly.index.year
    fmt = yearly.copy()
    fmt["수익률"] = fmt["수익률"].map("{:+.2%}".format)
    fmt["변동성"] = fmt["변동성"].map("{:.2%}".format)
    print(fmt.to_string(float_format="{:,.2f}".format))
    print(f"\n상승 연도 {(yearly['수익률'] > 0).sum()}개 / 하락 연도 {(yearly['수익률'] <= 0).sum()}개")
    result["yearly"] = yearly

    section("④ 최대 낙폭(MDD)")
    peak = close.cummax()
    drawdown = close / peak - 1
    mdd_date = drawdown.idxmin()
    peak_date = close[:mdd_date].idxmax()
    recovered = close[mdd_date:][close[mdd_date:] >= close[peak_date]]
    print(f"MDD          : {drawdown.min():.2%}")
    print(f"고점         : {peak_date.date()} ({close[peak_date]:,.2f})")
    print(f"저점         : {mdd_date.date()} ({close[mdd_date]:,.2f})")
    print(f"고점 회복일  : {recovered.index[0].date() if not recovered.empty else '미회복'}")
    result["drawdown"] = drawdown

    section("⑤ 일간 수익률 극단값")
    print("[하루 최대 상승 TOP 5]")
    print(ret.nlargest(5).map("{:+.2%}".format).to_string())
    print("[하루 최대 하락 TOP 5]")
    print(ret.nsmallest(5).map("{:+.2%}".format).to_string())
    print(f"\n상승일 비율: {(ret > 0).mean():.2%}")
    print(f"왜도(skew): {ret.skew():.3f}, 첨도(kurtosis): {ret.kurt():.3f}  (정규분포는 0, 0)")
    print(f"±3σ 초과 일수: {(ret.abs() > 3 * ret.std()).sum()}일 "
          f"(정규분포 기대값 약 {len(ret) * 0.0027:.0f}일)")

    section("⑥ 요일별 / 월별 평균 수익률 (계절성)")
    weekday_names = ["월", "화", "수", "목", "금"]
    by_wd = ret.groupby(ret.index.dayofweek).agg(["mean", "std", "count"])
    by_wd.index = [weekday_names[i] for i in by_wd.index]
    print(by_wd.to_string(formatters={"mean": "{:+.4%}".format, "std": "{:.4%}".format}))

    monthly_ret = close.resample("ME").last().pct_change().dropna()
    by_month = monthly_ret.groupby(monthly_ret.index.month).agg(["mean", lambda s: (s > 0).mean()])
    by_month.columns = ["평균수익률", "상승확률"]
    by_month.index = [f"{m}월" for m in by_month.index]
    print()
    print(by_month.to_string(formatters={"평균수익률": "{:+.2%}".format, "상승확률": "{:.0%}".format}))
    result["monthly_ret"] = monthly_ret

    section("⑦ 이동평균 / 추세")
    df["MA50"] = close.rolling(50).mean()
    df["MA200"] = close.rolling(200).mean()
    above = (close > df["MA200"])[df["MA200"].notna()]
    print(f"200일 이동평균 위에 있던 비율: {above.mean():.2%}")
    signal = np.sign(df["MA50"] - df["MA200"]).dropna()
    cross = signal.diff().dropna()
    golden = cross[cross > 0].index
    dead = cross[cross < 0].index
    print(f"골든크로스 {len(golden)}회 / 데드크로스 {len(dead)}회")
    print("최근 골든크로스:", ", ".join(d.strftime("%Y-%m-%d") for d in golden[-3:]))
    print("최근 데드크로스:", ", ".join(d.strftime("%Y-%m-%d") for d in dead[-3:]))

    section("⑧ 주요 위기 구간")
    periods = {
        "닷컴 버블 붕괴": ("2000-03-01", "2002-10-31"),
        "글로벌 금융위기": ("2007-10-01", "2009-03-31"),
        "유럽 재정위기": ("2011-04-01", "2011-10-31"),
        "2018 4분기 급락": ("2018-09-01", "2018-12-31"),
    }
    rows = []
    for name, (s, e) in periods.items():
        seg = close[s:e]
        rows.append({
            "구간": name,
            "고점일": seg.idxmax().date(), "고점": seg.max(),
            "저점일": seg[seg.idxmax():].idxmin().date(), "저점": seg[seg.idxmax():].min(),
        })
    crisis = pd.DataFrame(rows).set_index("구간")
    crisis["낙폭"] = (crisis["저점"] / crisis["고점"] - 1).map("{:.2%}".format)
    print(crisis.to_string(float_format="{:,.2f}".format))

    return result


# ---------------------------------------------------------------------------
# 3. 시각화
#    draw_* 함수는 전달받은 Figure에 그리기만 하므로 GUI(PyQt6)에서도 재사용합니다.
# ---------------------------------------------------------------------------
def draw_close_line(fig, df: pd.DataFrame, start="2000-01-01", end="2019-12-31") -> None:
    """종가 기준 라인그래프 (기본: 2000년 1월 ~ 2019년 12월)"""
    data = df.loc[start:end, "Close"]
    fig.clear()
    ax = fig.add_subplot()
    if data.empty:
        ax.text(0.5, 0.5, "선택한 기간에 데이터가 없습니다", ha="center", va="center",
                transform=ax.transAxes)
        return

    ax.plot(data.index, data.values, color="#1f77b4", linewidth=1.2, label="종가")
    ax.fill_between(data.index, data.values, data.min() * 0.95, color="#1f77b4", alpha=0.08)

    # 최고/최저점 표시
    for idx, color, va in [(data.idxmax(), "red", "bottom"), (data.idxmin(), "green", "top")]:
        ax.scatter(idx, data[idx], color=color, zorder=5)
        ax.annotate(f"{data[idx]:,.0f}\n({idx:%Y-%m-%d})", (idx, data[idx]),
                    textcoords="offset points", xytext=(-8, 0) if va == "bottom" else (0, -12),
                    ha="right" if va == "bottom" else "center",
                    va="center" if va == "bottom" else va, fontsize=9, color=color)

    ax.set_title(f"S&P 500 종가 추이 ({data.index.min():%Y.%m} ~ {data.index.max():%Y.%m})",
                 fontsize=15, fontweight="bold")
    ax.set_xlabel("연도")
    ax.set_ylabel("종가 (포인트)")
    locator = mdates.AutoDateLocator()
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    ax.set_xlim(pd.Timestamp(start), pd.Timestamp(end))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left")
    fig.tight_layout()


def draw_dashboard(fig, df: pd.DataFrame, result: dict) -> None:
    """보조 분석 차트 4종"""
    fig.clear()
    axes = fig.subplots(2, 2)

    # (1) 종가 + 이동평균 (로그 스케일)
    ax = axes[0, 0]
    ax.plot(df.index, df["Close"], label="종가", linewidth=1)
    ax.plot(df.index, df["MA50"], label="50일 이평", linewidth=1)
    ax.plot(df.index, df["MA200"], label="200일 이평", linewidth=1)
    ax.set_yscale("log")
    ax.set_title("종가와 이동평균 (로그 스케일)")
    ax.legend()
    ax.grid(alpha=0.3)

    # (2) 낙폭(Drawdown)
    ax = axes[0, 1]
    dd = result["drawdown"] * 100
    ax.fill_between(dd.index, dd, 0, color="crimson", alpha=0.4)
    ax.set_title("고점 대비 낙폭 (%)")
    ax.grid(alpha=0.3)

    # (3) 연도별 수익률
    ax = axes[1, 0]
    yr = result["yearly"]["수익률"] * 100
    ax.bar(yr.index, yr, color=np.where(yr >= 0, "tab:red", "tab:blue"))
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("연도별 수익률 (%)")
    ax.set_xticks(yr.index)
    ax.tick_params(axis="x", rotation=45)
    ax.grid(alpha=0.3, axis="y")

    # (4) 일간 수익률 분포
    ax = axes[1, 1]
    r = df["Return"].dropna() * 100
    ax.hist(r, bins=120, color="gray", alpha=0.7, density=True)
    x = np.linspace(r.min(), r.max(), 400)
    ax.plot(x, np.exp(-((x - r.mean()) ** 2) / (2 * r.std() ** 2)) / (r.std() * np.sqrt(2 * np.pi)),
            color="red", label="정규분포")
    ax.set_title("일간 수익률 분포 (%) — 꼬리가 두꺼움(Fat tail)")
    ax.set_xlim(-6, 6)
    ax.legend()
    ax.grid(alpha=0.3)

    fig.tight_layout()


def draw_monthly_heatmap(fig, monthly_ret: pd.Series) -> None:
    """연도 x 월 수익률 히트맵"""
    table = (monthly_ret * 100).to_frame("r")
    table = table.pivot_table(index=table.index.year, columns=table.index.month, values="r")

    fig.clear()
    ax = fig.add_subplot()
    lim = np.nanmax(np.abs(table.values))
    im = ax.imshow(table.values, cmap="RdBu_r", vmin=-lim, vmax=lim, aspect="auto")
    ax.set_xticks(range(len(table.columns)), [f"{m}월" for m in table.columns])
    ax.set_yticks(range(len(table.index)), table.index)
    for i in range(table.shape[0]):
        for j in range(table.shape[1]):
            v = table.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=8)
    ax.set_title("월별 수익률 히트맵 (%)", fontsize=14)
    fig.colorbar(im, ax=ax)
    fig.tight_layout()


def save_charts(df: pd.DataFrame, result: dict, out_dir: Path = OUT_DIR,
                start="2000-01-01", end="2019-12-31") -> list[Path]:
    """차트 3종을 PNG로 저장하고 경로 목록을 반환"""
    out_dir.mkdir(exist_ok=True)
    jobs = [
        ("1_close_line_2000_2019.png", (14, 6), 150, lambda f: draw_close_line(f, df, start, end)),
        ("2_analysis_dashboard.png", (16, 10), 130, lambda f: draw_dashboard(f, df, result)),
        ("3_monthly_heatmap.png", (12, 8), 130, lambda f: draw_monthly_heatmap(f, result["monthly_ret"])),
    ]
    paths = []
    for name, size, dpi, draw in jobs:
        fig = plt.figure(figsize=size)
        draw(fig)
        fig.savefig(out_dir / name, dpi=dpi)
        plt.close(fig)
        paths.append(out_dir / name)
    return paths


def main() -> None:
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV
    OUT_DIR.mkdir(exist_ok=True)

    section("데이터 클렌징")
    df = load_and_clean(csv_path)
    df.to_csv(OUT_DIR / "sp500_cleaned.csv", encoding="utf-8-sig")

    result = analyze(df)

    section("차트 저장")
    for p in save_charts(df, result):
        print(f"저장: {p}")


if __name__ == "__main__":
    main()
