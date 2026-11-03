"""
코스피200 크롤러 (네이버페이 증권)

https://stock.naver.com/market/stock/kr 페이지는 Next.js로 만든 클라이언트 렌더링 페이지라서,
requests로 받은 HTML에는 지수/종목 데이터가 들어있지 않습니다 (BeautifulSoup으로 파싱해도 빈 껍데기).
또한 예전 finance.naver.com/sise/entryJongmok.naver 페이지는 "더 이상 제공되지 않습니다"로 바뀌었습니다.

그래서 이 페이지가 브라우저에서 실제로 호출하는 JSON API(m.stock.naver.com/api)를 직접 요청합니다.

사용법:
    pip install requests openpyxl
    python kospi200_crawler.py            # 화면 출력 + kospi200_YYYYMMDD.csv / .xlsx 저장
"""

import csv
from datetime import datetime

import requests

BASE_URL = "https://m.stock.naver.com/api/index/KPI200"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    ),
    "Referer": "https://stock.naver.com/",
}
PAGE_SIZE = 50


def get_json(path, params=None):
    resp = requests.get(f"{BASE_URL}/{path}", headers=HEADERS, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


def fetch_index_summary():
    """코스피200 지수 현재가/등락."""
    data = get_json("basic")
    return {
        "지수명": data["stockName"],
        "현재가": data["closePrice"],
        "전일대비": data["compareToPreviousClosePrice"],
        "등락률(%)": data["fluctuationsRatio"],
        "장상태": data["marketStatus"],
        "기준시각": data["localTradedAt"],
    }


def fetch_daily_prices(count=10):
    """최근 일별 시세 (시가/고가/저가/종가)."""
    rows = get_json("price", {"page": 1, "pageSize": count})
    return [
        {
            "날짜": r["localTradedAt"],
            "종가": r["closePrice"],
            "전일대비": r["compareToPreviousClosePrice"],
            "등락률(%)": r["fluctuationsRatio"],
            "시가": r["openPrice"],
            "고가": r["highPrice"],
            "저가": r["lowPrice"],
        }
        for r in rows
    ]


def fetch_constituents():
    """코스피200 편입종목 전체 (시가총액 순)."""
    stocks = []
    page = 1
    while True:
        rows = get_json("enrollStocks", {"page": page, "pageSize": PAGE_SIZE})
        if not rows:
            break
        for r in rows:
            stocks.append(
                {
                    "종목코드": r["itemCode"],
                    "종목명": r["stockName"],
                    "현재가": r["closePrice"],
                    "전일대비": r["compareToPreviousClosePrice"],
                    "등락률(%)": r["fluctuationsRatio"],
                    "거래량": r["accumulatedTradingVolume"],
                    "거래대금(백만)": r["accumulatedTradingValue"],
                    "시가총액(억)": r["marketValue"],
                }
            )
        if len(rows) < PAGE_SIZE:
            break
        page += 1
    return stocks


def save_csv(rows, filename):
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:  # 엑셀 한글 깨짐 방지
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


# 엑셀에서 문자열이 아닌 숫자로 저장할 열과 표시 형식
EXCEL_NUMBER_FORMATS = {
    "현재가": "#,##0",
    "전일대비": "#,##0",
    "등락률(%)": "0.00",
    "거래량": "#,##0",
    "거래대금(백만)": "#,##0",
    "시가총액(억)": "#,##0",
}


def to_excel_value(key, value):
    if key not in EXCEL_NUMBER_FORMATS:
        return value
    try:
        return float(str(value).replace(",", ""))
    except ValueError:  # "N/A" 같은 값은 그대로
        return value


def save_xlsx(rows, filename, sheet_title="코스피200 편입종목"):
    from openpyxl import Workbook  # 엑셀 저장할 때만 필요
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title
    headers = list(rows[0].keys())
    ws.append(headers)
    for row in rows:
        ws.append([to_excel_value(k, row[k]) for k in headers])

    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DDEBF7")
        cell.alignment = Alignment(horizontal="center")
    for col, key in enumerate(headers, start=1):
        letter = get_column_letter(col)
        ws.column_dimensions[letter].width = max(12, len(key) * 2 + 2)
        if key in EXCEL_NUMBER_FORMATS:
            for (cell,) in ws.iter_rows(min_row=2, min_col=col, max_col=col):
                cell.number_format = EXCEL_NUMBER_FORMATS[key]
    ws.freeze_panes = "A2"  # 머리글 고정
    ws.auto_filter.ref = ws.dimensions
    wb.save(filename)


def main():
    summary = fetch_index_summary()
    print("=== 코스피200 지수 ===")
    for k, v in summary.items():
        print(f"{k}: {v}")

    print("\n=== 최근 일별 시세 ===")
    for r in fetch_daily_prices(5):
        print(f"{r['날짜']}  종가 {r['종가']:>8}  ({r['등락률(%)']}%)  시 {r['시가']} 고 {r['고가']} 저 {r['저가']}")

    stocks = fetch_constituents()
    print(f"\n=== 편입종목 {len(stocks)}개 (상위 10개) ===")
    for s in stocks[:10]:
        print(f"{s['종목명']:<12} {s['현재가']:>10}  {s['등락률(%)']:>6}%  시총 {s['시가총액(억)']}억")

    basename = f"kospi200_{datetime.now():%Y%m%d}"
    save_csv(stocks, f"{basename}.csv")
    save_xlsx(stocks, f"{basename}.xlsx")
    print(f"\n편입종목 전체를 {basename}.csv, {basename}.xlsx 에 저장했습니다.")


if __name__ == "__main__":
    main()
