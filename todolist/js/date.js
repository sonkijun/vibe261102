// 날짜 유틸: "오늘"은 항상 사용자 로컬 시간대 기준
(function () {
  const DAY_MS = 24 * 60 * 60 * 1000;
  const KEY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

  const formatter = new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  });

  /** Date → "YYYY-MM-DD" (로컬 기준) */
  function toKey(date = new Date()) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  /** "YYYY-MM-DD" → 로컬 자정 Date, 형식이 틀리면 null */
  function fromKey(key) {
    const match = KEY_PATTERN.exec(key);
    if (!match) return null;
    return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  }

  /** 두 날짜 키 사이의 일 수 (later - earlier). 서머타임 오차는 반올림으로 흡수 */
  function daysBetween(earlierKey, laterKey) {
    const a = fromKey(earlierKey);
    const b = fromKey(laterKey);
    if (!a || !b) return NaN;
    return Math.round((b - a) / DAY_MS);
  }

  /** 예: "2026년 11월 2일 월요일" */
  function formatLong(date = new Date()) {
    return formatter.format(date);
  }

  window.TodoDate = { toKey, fromKey, daysBetween, formatLong };
})();
