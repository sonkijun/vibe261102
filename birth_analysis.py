"""
대한민국 출생아수·합계출산율·자연증가 데이터 클렌징 + 다각도 분석 + 출생아수 라인그래프

사용법:
    python birth_analysis.py [엑셀 경로]
    (경로를 생략하면 같은 폴더의 "출생아수__합계출산율__자연증가_등.xlsx"를 사용)

결과물은 birth_output/ 폴더에 저장됩니다.
"""

import sys
import warnings
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_XLSX = BASE_DIR / "출생아수__합계출산율__자연증가_등.xlsx"
OUT_DIR = BASE_DIR / "birth_output"

# 한글 폰트 (macOS: AppleGothic, Windows: Malgun Gothic)
_installed = {f.name for f in font_manager.fontManager.ttflist}
plt.rcParams["font.family"] = next(
    (f for f in ["AppleGothic", "Malgun Gothic", "NanumGothic"] if f in _installed), "DejaVu Sans")
plt.rcParams["axes.unicode_minus"] = False

# KOSIS 원본 항목명 → 분석용 컬럼명
COLUMN_MAP = {
    "출생아수(명)": "출생아수",
    "자연증가건수(명)": "자연증가",
    "조출생률(천명당)": "조출생률",
    "자연증가율(천명당)": "자연증가율",
    "합계출산율(명)": "합계출산율",
    "출생성비(명)": "출생성비",
}


# ---------------------------------------------------------------------------
# 1. 데이터 클렌징
# ---------------------------------------------------------------------------
def load_and_clean(xlsx_path: Path) -> pd.DataFrame:
    # openpyxl의 "no default style" 경고는 KOSIS 파일 특성이라 무시
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        raw = pd.read_excel(xlsx_path, sheet_name="데이터", header=None, dtype=str)
    print(f"[원본] {raw.shape[0]}행 x {raw.shape[1]}열 (항목이 행, 연도가 열인 wide 형태)")

    # 첫 열 = 항목명, 첫 행 = 연도 → 전치(transpose)해서 연도를 행으로
    raw[0] = raw[0].str.strip()
    raw = raw.set_index(0)
    df = raw.iloc[1:].T
    df.index = raw.iloc[0].values
    df.index.name = "연도"
    df.columns.name = None

    unknown = set(df.columns) - set(COLUMN_MAP)
    if unknown:
        print(f"[클렌징] 알 수 없는 항목 제외: {unknown}")
    df = df[[c for c in COLUMN_MAP if c in df.columns]].rename(columns=COLUMN_MAP)

    # 연도: "1970.0" 같은 문자열 → 정수
    df.index = pd.to_numeric(df.index.str.strip(), errors="coerce")
    df = df[df.index.notna()]
    df.index = df.index.astype(int)

    # 값: 공백·콤마 제거, KOSIS 결측 기호("-", "…", "x")는 NaN 처리 후 숫자 변환
    for col in df.columns:
        s = df[col].str.strip().str.replace(",", "", regex=False)
        df[col] = pd.to_numeric(s.replace({"-": np.nan, "…": np.nan, "x": np.nan, "": np.nan}),
                                errors="coerce")
    for col in ["출생아수", "자연증가"]:
        df[col] = df[col].round().astype("Int64")

    # 중복 연도 / 정렬 / 누락 연도 확인
    before = len(df)
    df = df[~df.index.duplicated(keep="first")].sort_index()
    print(f"[클렌징] 중복 연도 제거: {before - len(df)}행")
    missing_years = sorted(set(range(df.index.min(), df.index.max() + 1)) - set(df.index))
    print(f"[검증] 누락된 연도: {missing_years or '없음'}")

    # 범위 검증: 음수 출생아수, 비정상 출산율·성비
    checks = {
        "출생아수 <= 0": df["출생아수"] <= 0,
        "합계출산율 범위(0~10) 밖": ~df["합계출산율"].between(0, 10),
        "출생성비 범위(90~130) 밖": ~df["출생성비"].between(90, 130),
    }
    for name, mask in checks.items():
        print(f"[검증] {name}: {int(mask.sum())}건")

    # 파생 변수: 사망자수 = 출생아수 - 자연증가 (자연증가 = 출생 - 사망)
    df["사망자수"] = df["출생아수"] - df["자연증가"]
    # 조출생률(천명당) = 출생아수 / 인구 * 1000 → 인구 추정
    df["추정인구"] = (df["출생아수"] / df["조출생률"] * 1000).round(-3).astype("Int64")
    df["출생아수_증감률"] = df["출생아수"].astype(float).pct_change()

    print(f"[결과] {len(df)}행, 기간 {df.index.min()} ~ {df.index.max()}")
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
    births = df["출생아수"].astype(float)
    result = {}

    section("① 기술 통계")
    cols = ["출생아수", "사망자수", "자연증가", "합계출산율", "조출생률", "출생성비"]
    print(df[cols].astype(float).describe().round(2).to_string())

    section("② 전체 기간 변화")
    first, last = df.index[0], df.index[-1]
    cagr = (births[last] / births[first]) ** (1 / (last - first)) - 1
    print(f"{first}년 출생아수 : {births[first]:,.0f}명")
    print(f"{last}년 출생아수 : {births[last]:,.0f}명")
    print(f"누적 변화율      : {births[last] / births[first] - 1:+.2%}")
    print(f"연평균 증감률    : {cagr:+.2%}")
    print(f"최대 출생아수    : {births.max():,.0f}명 ({births.idxmax()}년)")
    print(f"최소 출생아수    : {births.min():,.0f}명 ({births.idxmin()}년)")
    tfr = df["합계출산율"]
    print(f"합계출산율       : {tfr[first]:.2f} → {tfr[last]:.2f}명 "
          f"(최저 {tfr.min():.2f}명, {tfr.idxmin()}년)")

    section("③ 10년 단위(연대별) 요약")
    decade = df.groupby((df.index // 10) * 10).agg(
        평균출생아수=("출생아수", "mean"),
        평균합계출산율=("합계출산율", "mean"),
        평균출생성비=("출생성비", "mean"),
        자연증가합계=("자연증가", "sum"),
    )
    decade = decade.astype(float)  # Int64 합계의 <NA> 출력 방지
    decade.index = [f"{d}년대" for d in decade.index]
    decade["연대간_변화율"] = decade["평균출생아수"].pct_change()
    print(decade.to_string(na_rep="-", formatters={
        "평균출생아수": "{:,.0f}".format, "평균합계출산율": "{:.2f}".format,
        "평균출생성비": "{:.1f}".format, "자연증가합계": "{:,.0f}".format,
        "연대간_변화율": lambda v: "-" if pd.isna(v) else f"{v:+.1%}",
    }))
    result["decade"] = decade

    section("④ 전년 대비 증감 극단값")
    chg = df["출생아수_증감률"].dropna()
    print("[전년 대비 최대 증가 TOP 5]")
    print(chg.nlargest(5).map("{:+.2%}".format).to_string())
    print("[전년 대비 최대 감소 TOP 5]")
    print(chg.nsmallest(5).map("{:+.2%}".format).to_string())
    print(f"\n증가한 해 {(chg > 0).sum()}개 / 감소한 해 {(chg < 0).sum()}개")
    # 가장 긴 연속 감소 구간
    down = (chg < 0).astype(int)
    runs = down.groupby((down != down.shift()).cumsum()).agg(["sum", lambda s: s.index[0]])
    runs.columns = ["길이", "시작"]
    best = runs[runs["길이"] > 0].sort_values("길이").iloc[-1]
    print(f"최장 연속 감소: {best['시작']}~{best['시작'] + best['길이'] - 1}년 ({best['길이']}년 연속)")

    section("⑤ 출산율 임계선 돌파 시점")
    for label, th in [("대체출산율 2.1명", 2.1), ("저출산 1.3명", 1.3), ("1.0명", 1.0)]:
        below = tfr[tfr < th]
        print(f"{label} 미만 첫 해: {below.index[0] if not below.empty else '없음'}")
    print(f"출생아수 50만명 미만 첫 해: {births[births < 500_000].index[0]}")
    print(f"출생아수 30만명 미만 첫 해: {births[births < 300_000].index[0]}")

    section("⑥ 자연증가 (출생 - 사망) / 인구 데드크로스")
    nat = df["자연증가"]
    cross = nat[nat < 0]
    print(f"자연감소(사망 > 출생) 시작: {cross.index[0] if not cross.empty else '없음'}년")
    print(f"자연감소 누적({cross.index[0]}~{last}): {cross.sum():,}명")
    print(df.loc[2015:, ["출생아수", "사망자수", "자연증가", "추정인구"]].to_string(
        formatters={c: "{:,}".format for c in ["출생아수", "사망자수", "자연증가", "추정인구"]}))

    section("⑦ 출생성비 추이 (정상 범위 103~107)")
    sr = df["출생성비"]
    abnormal = sr[sr > 107]
    print(f"정상 범위 초과(>107) 연도 수: {len(abnormal)}개 "
          f"({abnormal.index.min()}~{abnormal.index.max()})")
    print(f"최고 출생성비: {sr.max():.1f} ({sr.idxmax()}년)")
    print(f"최근 5년 평균: {sr.iloc[-5:].mean():.1f}")

    section("⑧ 지표 간 상관관계")
    corr = df[["출생아수", "합계출산율", "조출생률", "자연증가", "출생성비"]].astype(float).corr()
    print(corr.round(3).to_string())
    result["corr"] = corr

    section("⑨ 최근 반등 여부 (2023 → 2025)")
    for y in [2023, 2024, 2025]:
        if y in df.index:
            print(f"{y}년: 출생아수 {births[y]:,.0f}명 ({df.loc[y, '출생아수_증감률']:+.2%}), "
                  f"합계출산율 {tfr[y]:.2f}명")

    return result


# ---------------------------------------------------------------------------
# 3. 시각화
# ---------------------------------------------------------------------------
def draw_births_line(fig, df: pd.DataFrame, start=1970, end=2025) -> None:
    """출생아수 라인그래프 (기본: 1970년 ~ 2025년)"""
    data = df.loc[start:end, "출생아수"].astype(float)
    fig.clear()
    ax = fig.add_subplot()

    ax.plot(data.index, data.values, color="#1f77b4", linewidth=2, marker="o", markersize=3.5,
            label="출생아수")
    ax.fill_between(data.index, data.values, 0, color="#1f77b4", alpha=0.08)

    # 최고/최저점 표시
    for idx, color, offset in [(data.idxmax(), "red", (10, 8)), (data.idxmin(), "green", (-10, -22))]:
        ax.scatter(idx, data[idx], color=color, s=50, zorder=5)
        ax.annotate(f"{data[idx]:,.0f}명 ({idx}년)", (idx, data[idx]), textcoords="offset points",
                    xytext=offset, ha="left" if offset[0] > 0 else "right", fontsize=10,
                    color=color, fontweight="bold")

    # 주요 사건
    events = {1983: "합계출산율 2.1 붕괴", 2002: "초저출산(1.3 미만)",
              2018: "합계출산율 1.0 붕괴", 2020: "자연감소 시작"}
    for year, text in events.items():
        if start <= year <= end:
            ax.axvline(year, color="gray", linestyle=":", linewidth=1)
            ax.text(year + 0.3, data.max() * 1.02, text, rotation=90, va="top", fontsize=9,
                    color="dimgray")

    ax.set_title(f"대한민국 연도별 출생아수 추이 ({start}~{end})", fontsize=15, fontweight="bold")
    ax.set_xlabel("연도")
    ax.set_ylabel("출생아수 (명)")
    ax.set_xlim(start - 1, end + 1)
    ax.set_ylim(0, data.max() * 1.1)
    ax.set_xticks(range(start, end + 1, 5))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v / 10000:,.0f}만"))
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right")
    fig.tight_layout()


def draw_dashboard(fig, df: pd.DataFrame, result: dict) -> None:
    """보조 분석 차트 4종"""
    fig.clear()
    axes = fig.subplots(2, 2)
    years = df.index

    # (1) 출생아수 vs 합계출산율 (이중축)
    ax = axes[0, 0]
    ax.bar(years, df["출생아수"].astype(float) / 10000, color="tab:blue", alpha=0.5, label="출생아수(만명)")
    ax.set_ylabel("출생아수 (만명)")
    ax2 = ax.twinx()
    ax2.plot(years, df["합계출산율"], color="tab:red", linewidth=2, label="합계출산율")
    ax2.axhline(2.1, color="tab:red", linestyle="--", linewidth=0.8)
    ax2.text(years[-1], 2.15, "대체출산율 2.1", ha="right", fontsize=8, color="tab:red")
    ax2.set_ylabel("합계출산율 (명)")
    ax.set_title("출생아수와 합계출산율")
    ax.grid(alpha=0.3)

    # (2) 출생 vs 사망 (자연증가)
    ax = axes[0, 1]
    b = df["출생아수"].astype(float) / 10000
    d = df["사망자수"].astype(float) / 10000
    ax.plot(years, b, label="출생아수", color="tab:blue")
    ax.plot(years, d, label="사망자수(추정)", color="black")
    ax.fill_between(years, b, d, where=b >= d, color="tab:blue", alpha=0.2, label="자연증가")
    ax.fill_between(years, b, d, where=b < d, color="tab:red", alpha=0.3, label="자연감소")
    ax.set_title("출생 vs 사망 (만명)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    # (3) 전년 대비 증감률
    ax = axes[1, 0]
    chg = df["출생아수_증감률"].dropna() * 100
    ax.bar(chg.index, chg, color=np.where(chg >= 0, "tab:red", "tab:blue"))
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("출생아수 전년 대비 증감률 (%)")
    ax.grid(alpha=0.3, axis="y")

    # (4) 출생성비
    ax = axes[1, 1]
    ax.plot(years, df["출생성비"], color="purple", marker="o", markersize=3)
    ax.axhspan(103, 107, color="green", alpha=0.15, label="정상 범위(103~107)")
    ax.set_title("출생성비 (여아 100명당 남아)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)

    fig.tight_layout()


def save_charts(df: pd.DataFrame, result: dict, out_dir: Path = OUT_DIR,
                start=1970, end=2025) -> list[Path]:
    """차트를 PNG로 저장하고 경로 목록을 반환"""
    out_dir.mkdir(exist_ok=True)
    jobs = [
        (f"1_births_line_{start}_{end}.png", (14, 6), 150, lambda f: draw_births_line(f, df, start, end)),
        ("2_analysis_dashboard.png", (16, 10), 130, lambda f: draw_dashboard(f, df, result)),
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
    xlsx_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_XLSX
    OUT_DIR.mkdir(exist_ok=True)

    section("데이터 클렌징")
    df = load_and_clean(xlsx_path)
    df.to_csv(OUT_DIR / "births_cleaned.csv", encoding="utf-8-sig")

    result = analyze(df)

    section("차트 저장")
    for p in save_charts(df, result):
        print(f"저장: {p}")


if __name__ == "__main__":
    main()
