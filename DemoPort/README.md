# DemoPort

Python · HTML5 · iOS 개발자 프로필 웹사이트 (정적 사이트, 빌드 불필요).

## 실행

JSON 데이터를 `fetch`로 불러오므로 파일을 직접 열지 말고 로컬 서버로 실행합니다.

```bash
cd DemoPort
python3 -m http.server 5180
```

브라우저에서 http://localhost:5180 접속.

## 콘텐츠 수정

코드 수정 없이 `data/` 폴더의 JSON만 고치면 됩니다.

| 파일 | 내용 |
|---|---|
| `data/profile.json` | 이름, 소개, 이메일, GitHub/LinkedIn 링크, 경력 |
| `data/skills.json` | 주력 분야 카드, 숙련도, 기술 태그 |
| `data/projects.json` | 프로젝트 목록 (`category`: `python` / `web` / `ios`), 데모·GitHub·App Store 링크 |

링크 값이 비어 있으면 해당 버튼은 표시되지 않습니다.

## 구조

```
DemoPort/
├── index.html
├── assets/css/style.css
├── assets/js/main.js
├── data/{profile,skills,projects}.json
└── prd.md
```
