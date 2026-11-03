# PRD: DemoPort — 개발자 프로필 웹사이트

| 항목 | 내용 |
|---|---|
| 문서 버전 | v0.1 (초안) |
| 작성일 | 2026-11-03 |
| 소유자 | cesareborza@gmail.com |
| 상태 | Draft |

---

## 1. 개요

**DemoPort**는 개발자 개인의 기술 역량, 프로젝트, 경력을 한눈에 보여주는 포트폴리오형 프로필 웹사이트입니다.
주력 분야인 **Python**, **HTML5(웹 프론트엔드)**, **iOS 앱 개발**을 중심으로 결과물과 데모를 소개하고, 방문자가 쉽게 연락할 수 있도록 하는 것이 목적입니다.

## 2. 목표 (Goals)

1. 채용 담당자·클라이언트가 **30초 안에** 주력 기술과 대표 프로젝트를 파악할 수 있다.
2. 각 프로젝트의 **데모(라이브 링크, 스크린샷, 영상, App Store 링크)** 를 바로 확인할 수 있다.
3. 방문자가 **이메일로 손쉽게 연락**할 수 있다.
4. 모바일·데스크톱 모두에서 빠르고 보기 좋게 동작한다.

### 비목표 (Non-Goals)

- 블로그 CMS, 회원가입/로그인 기능
- 관리자 대시보드 (v1에서는 정적 데이터 파일로 콘텐츠 관리)
- 다국어 자동 번역 (v1은 한국어 기본, 영어는 추후 검토)

## 3. 대상 사용자 (Target Users)

| 페르소나 | 니즈 |
|---|---|
| 채용 담당자 / 테크 리드 | 기술 스택, 경력, 코드 품질(GitHub) 빠르게 확인 |
| 프리랜서 클라이언트 | 유사 프로젝트 사례, 앱/웹 데모, 연락 방법 |
| 동료 개발자 | 오픈소스 프로젝트, 기술 글, 협업 가능성 |

## 4. 핵심 기술 분야 (Profile Focus)

| 분야 | 소개 포인트 | 예시 키워드 |
|---|---|---|
| **Python** | 백엔드, 자동화, 데이터 처리 | FastAPI / Django / Flask, 스크립팅, 크롤링, 데이터 분석 |
| **HTML5 / Web** | 반응형 웹, 인터랙티브 UI | HTML5, CSS3, JavaScript, Canvas, 웹 표준·접근성 |
| **iOS 앱 개발** | 네이티브 앱 설계·출시 | Swift, SwiftUI, UIKit, Xcode, App Store 배포 |

## 5. 기능 요구사항 (Functional Requirements)

### 5.1 페이지 구성 (싱글 페이지 + 섹션 스크롤)

| # | 섹션 | 내용 | 우선순위 |
|---|---|---|---|
| F1 | **Hero** | 이름, 한 줄 소개("Python · Web · iOS Developer"), CTA 버튼(프로젝트 보기 / 연락하기) | P0 |
| F2 | **About** | 자기소개, 개발 철학, 프로필 사진 | P0 |
| F3 | **Skills** | 3대 주력 분야 카드 + 세부 기술 태그, 숙련도 표시 | P0 |
| F4 | **Projects** | 프로젝트 카드 그리드, 분야별 필터(All / Python / Web / iOS) | P0 |
| F5 | **Project Detail** | 모달 또는 상세 페이지: 설명, 역할, 기술 스택, 스크린샷, 데모·GitHub·App Store 링크 | P0 |
| F6 | **Experience** | 경력·교육 타임라인 | P1 |
| F7 | **Contact** | 이메일 `cesareborza@gmail.com` (mailto 링크 + 복사 버튼), GitHub 등 SNS 링크 | P0 |
| F8 | **Footer** | 저작권, 소셜 링크 | P1 |

### 5.2 부가 기능

| # | 기능 | 우선순위 |
|---|---|---|
| F9 | 다크/라이트 모드 토글 (시스템 설정 기본) | P1 |
| F10 | 스크롤 시 부드러운 섹션 이동 및 등장 애니메이션 | P1 |
| F11 | 이력서 PDF 다운로드 버튼 | P2 |
| F12 | 연락 폼 (Formspree 등 외부 서비스 연동) | P2 |
| F13 | 한/영 언어 전환 | P2 |

## 6. 비기능 요구사항 (Non-Functional Requirements)

- **성능**: Lighthouse Performance 90점 이상, 첫 화면 로드 2초 이내
- **반응형**: 모바일(≥360px), 태블릿, 데스크톱 대응
- **접근성**: 시맨틱 HTML5 태그 사용, 이미지 alt, 키보드 내비게이션, 명도 대비 WCAG AA
- **SEO**: 메타 태그, Open Graph(공유 미리보기), sitemap
- **유지보수성**: 프로젝트·스킬 데이터는 `data/*.json`으로 분리하여 코드 수정 없이 콘텐츠 갱신

## 7. 기술 스택 (제안)

| 영역 | 선택 | 비고 |
|---|---|---|
| 마크업/스타일 | HTML5 + CSS3 (CSS 변수, Flex/Grid) | 주력 분야인 HTML5 역량을 직접 보여줌 |
| 스크립트 | Vanilla JavaScript (ES Modules) | 프레임워크 없이 가볍게 |
| 콘텐츠 데이터 | JSON 파일 | `projects.json`, `skills.json` |
| 로컬 개발 서버 | `python -m http.server` | Python 활용 |
| 배포 | GitHub Pages 또는 Netlify / Vercel | 정적 호스팅, 무료 |

> 추후 확장 시 Python(FastAPI) 백엔드로 연락 폼 처리나 방문 통계를 붙일 수 있음.

## 8. 디렉터리 구조 (초안)

```
DemoPort/
├── prd.md
├── index.html
├── assets/
│   ├── css/style.css
│   ├── js/main.js
│   └── images/
├── data/
│   ├── projects.json
│   └── skills.json
└── README.md
```

## 9. 콘텐츠 데이터 스키마 (예시)

```json
{
  "id": "weather-ios",
  "title": "날씨 알림 iOS 앱",
  "category": "ios",
  "summary": "SwiftUI 기반 위치 기반 날씨 알림 앱",
  "stack": ["Swift", "SwiftUI", "CoreLocation"],
  "thumbnail": "assets/images/weather.png",
  "links": {
    "demo": "",
    "github": "",
    "appstore": ""
  }
}
```

`category` 값: `python` | `web` | `ios`

## 10. 마일스톤

| 단계 | 내용 | 산출물 |
|---|---|---|
| M1 | PRD 확정, 디자인 방향(컬러·폰트) 결정 | prd.md, 무드보드 |
| M2 | 레이아웃 & 정적 섹션 구현 (Hero, About, Skills, Contact) | index.html, style.css |
| M3 | 프로젝트 섹션 + JSON 데이터 연동 + 필터 | main.js, projects.json |
| M4 | 반응형·다크모드·애니메이션·접근성 보완 | QA 체크리스트 |
| M5 | SEO 설정 및 배포 | 배포 URL |

## 11. 성공 지표

- Lighthouse: Performance / Accessibility / SEO 모두 90+
- 모든 프로젝트 카드에 최소 1개 이상의 데모 또는 코드 링크
- 연락 버튼 클릭 → 메일 앱 정상 연결

## 12. 미정 사항 (Open Questions)

- [ ] 사이트에 표시할 이름 / 닉네임
- [ ] GitHub, LinkedIn 등 소셜 계정 링크
- [ ] 소개할 대표 프로젝트 목록 (분야별 2~3개 권장)
- [ ] 선호 컬러·디자인 톤 (미니멀 / 다크 테크 / 컬러풀 등)
- [ ] 커스텀 도메인 사용 여부
