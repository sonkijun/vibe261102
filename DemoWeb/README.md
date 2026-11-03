# DemoWeb 게시판

Next.js(App Router) + TypeScript + Tailwind CSS + shadcn/ui로 만든 간단한 웹 게시판입니다.
별도 DB 없이 서버의 JSON 파일(`data/posts.json`)에 글을 저장합니다.

## 기능

- 글 목록: 최신순 정렬, 페이지당 10개 페이지네이션
- 검색: 제목·내용·작성자 대상 (`/?q=검색어`)
- 글 상세 / 작성 / 수정 / 삭제(확인 다이얼로그)
- 입력값 검증(서버 측) 및 한국어 오류 메시지
- 반응형 레이아웃, 다크모드(라이트/다크/시스템 전환)

## 요구 사항

- Node.js 20.9 이상 (22 LTS 권장)

## 실행 방법

```bash
cd DemoWeb
npm install
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

- 글은 `DemoWeb/data/posts.json`에 저장되며, 파일이 없으면 첫 요청 때 환영 글 1개로 자동 생성됩니다.
- `data/` 폴더는 `.gitignore`에 포함되어 커밋되지 않습니다. 초기화하려면 이 파일을 지우면 됩니다.
- 쓰기 작업은 서버 프로세스 안에서 순서대로 처리되고 임시 파일 → 이름 변경 방식으로 저장해 파일 손상을 막습니다.
  여러 서버 인스턴스나 서버리스 환경(예: Vercel)에서는 파일이 공유·보존되지 않으므로 실제 서비스에는 DB를 사용하세요.

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
    posts.ts              # JSON 파일 저장소
```
