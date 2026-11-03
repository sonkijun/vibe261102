# DemoWeb 게시판

Next.js(App Router) + TypeScript + Tailwind CSS + shadcn/ui로 만든 간단한 웹 게시판입니다.
게시글은 [Neon](https://neon.tech) 서버리스 PostgreSQL 데이터베이스에 저장합니다.

## 기능

- 글 목록: 최신순 정렬, 페이지당 10개 페이지네이션
- 검색: 제목·내용·작성자 대상 (`/?q=검색어`)
- 글 상세 / 작성 / 수정 / 삭제(확인 다이얼로그)
- 입력값 검증(서버 측) 및 한국어 오류 메시지
- 반응형 레이아웃, 다크모드(라이트/다크/시스템 전환)

## 요구 사항

- Node.js 20.9 이상 (22 LTS 권장)
- Neon 데이터베이스 (무료 플랜으로 충분)

## 실행 방법

```bash
cd DemoWeb
npm install
cp .env.example .env.local   # DATABASE_URL에 Neon 연결 문자열 입력
npm run dev -- --port 3000
```

브라우저에서 http://localhost:3000 을 엽니다.

프로덕션 빌드와 실행:

```bash
npm run build
npm run start -- --port 3000
```

Claude 데스크톱 앱에서는 저장소 루트의 `.claude/launch.json`에 있는 `demoweb` 설정으로 미리보기를 띄울 수 있습니다(포트 3000).

## 데이터 저장

- 연결 정보는 `DATABASE_URL` 환경 변수로 받습니다. `.env.local`은 `.gitignore`에 포함되어 커밋되지 않습니다.
- `@neondatabase/serverless`의 HTTP 드라이버를 사용하므로 서버리스 환경(Vercel)에서도 그대로 동작합니다.
- 첫 요청 때 `posts` 테이블이 없으면 자동으로 만들고, 비어 있으면 환영 글 1개를 넣습니다.

```sql
CREATE TABLE posts (
  id         SERIAL PRIMARY KEY,
  title      VARCHAR(100) NOT NULL,
  author     VARCHAR(30)  NOT NULL,
  content    TEXT         NOT NULL,
  created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);
```

## Vercel 배포

1. Vercel에서 이 저장소를 Import하고 **Root Directory**를 `DemoWeb`으로 지정합니다.
2. Settings → Environment Variables에 `DATABASE_URL`(Neon pooled 연결 문자열)을 추가합니다.
   Vercel의 Neon 통합(Storage → Neon)을 연결하면 자동으로 추가됩니다.
3. Deploy. 빌드 명령과 출력 폴더는 기본값(Next.js)을 그대로 씁니다.

## 구조

```
src/
  app/
    actions.ts            # Server Actions: 작성·수정·삭제 + 검증
    page.tsx              # 목록 + 검색 + 페이지네이션
    posts/new/page.tsx    # 글쓰기
    posts/[id]/page.tsx   # 상세
    posts/[id]/edit/page.tsx  # 수정
  components/
    post-form.tsx         # 작성/수정 공용 폼 (useActionState)
    delete-post-button.tsx  # 삭제 확인 다이얼로그
    theme-toggle.tsx      # 다크모드 전환
    ui/                   # shadcn/ui 컴포넌트
  lib/
    posts.ts              # Neon(PostgreSQL) 저장소
```
