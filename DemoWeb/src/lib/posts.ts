import { neon, type NeonQueryFunction } from "@neondatabase/serverless";

export type Post = {
  id: number;
  title: string;
  author: string;
  content: string;
  createdAt: string;
  updatedAt: string;
};

export type PostInput = Pick<Post, "title" | "author" | "content">;

export const PAGE_SIZE = 10;

let client: NeonQueryFunction<false, false> | null = null;

function db() {
  if (!client) {
    const url = process.env.DATABASE_URL;
    if (!url) throw new Error("DATABASE_URL 환경 변수가 설정되지 않았습니다.");
    client = neon(url);
  }
  return client;
}

// 테이블이 없으면 만들고, 비어 있으면 환영 글을 넣습니다. 프로세스당 한 번만 실행됩니다.
let schemaReady: Promise<void> | null = null;

function ensureSchema() {
  schemaReady ??= (async () => {
    const sql = db();
    await sql`
      CREATE TABLE IF NOT EXISTS posts (
        id         SERIAL PRIMARY KEY,
        title      VARCHAR(100) NOT NULL,
        author     VARCHAR(30)  NOT NULL,
        content    TEXT         NOT NULL,
        created_at TIMESTAMPTZ  NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ  NOT NULL DEFAULT now()
      )`;
    await sql`
      INSERT INTO posts (title, author, content)
      SELECT
        'DemoWeb 게시판에 오신 것을 환영합니다',
        '관리자',
        E'Next.js App Router와 shadcn/ui로 만든 간단한 게시판입니다.\n\n글 작성, 수정, 삭제, 검색을 사용해 보세요. 데이터는 Neon(PostgreSQL) 데이터베이스에 저장됩니다.'
      WHERE NOT EXISTS (SELECT 1 FROM posts)`;
  })().catch((error) => {
    schemaReady = null;
    throw error;
  });
  return schemaReady;
}

type Row = Record<string, unknown>;

function toPost(row: Row): Post {
  return {
    id: Number(row.id),
    title: String(row.title),
    author: String(row.author),
    content: String(row.content),
    createdAt: String(row.created_at),
    updatedAt: String(row.updated_at),
  };
}

// 타임스탬프를 드라이버 설정과 상관없이 ISO 문자열(UTC)로 받습니다.
const ISO = 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"';

export async function listPosts({ query = "", page = 1 }: { query?: string; page?: number }) {
  await ensureSchema();
  const sql = db();
  const q = query.trim();
  const pattern = `%${q.replace(/[\\%_]/g, "\\$&")}%`;

  const [{ count }] = await sql`
    SELECT count(*)::int AS count FROM posts
    WHERE ${q} = '' OR title ILIKE ${pattern} OR content ILIKE ${pattern} OR author ILIKE ${pattern}`;
  const total = Number(count);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const current = Math.min(Math.max(1, page), totalPages);

  const rows = await sql`
    SELECT id, title, author, content,
           to_char(created_at AT TIME ZONE 'UTC', ${ISO}) AS created_at,
           to_char(updated_at AT TIME ZONE 'UTC', ${ISO}) AS updated_at
    FROM posts
    WHERE ${q} = '' OR title ILIKE ${pattern} OR content ILIKE ${pattern} OR author ILIKE ${pattern}
    ORDER BY id DESC
    LIMIT ${PAGE_SIZE} OFFSET ${(current - 1) * PAGE_SIZE}`;

  return { posts: rows.map(toPost), total, page: current, totalPages };
}

export async function getPost(id: number) {
  if (!Number.isSafeInteger(id) || id < 1) return null;
  await ensureSchema();
  const rows = await db()`
    SELECT id, title, author, content,
           to_char(created_at AT TIME ZONE 'UTC', ${ISO}) AS created_at,
           to_char(updated_at AT TIME ZONE 'UTC', ${ISO}) AS updated_at
    FROM posts WHERE id = ${id}`;
  return rows[0] ? toPost(rows[0]) : null;
}

export async function createPost(input: PostInput) {
  await ensureSchema();
  const rows = await db()`
    INSERT INTO posts (title, author, content)
    VALUES (${input.title}, ${input.author}, ${input.content})
    RETURNING id, title, author, content,
              to_char(created_at AT TIME ZONE 'UTC', ${ISO}) AS created_at,
              to_char(updated_at AT TIME ZONE 'UTC', ${ISO}) AS updated_at`;
  return toPost(rows[0]);
}

export async function updatePost(id: number, input: PostInput) {
  await ensureSchema();
  const rows = await db()`
    UPDATE posts
    SET title = ${input.title}, author = ${input.author}, content = ${input.content}, updated_at = now()
    WHERE id = ${id}
    RETURNING id, title, author, content,
              to_char(created_at AT TIME ZONE 'UTC', ${ISO}) AS created_at,
              to_char(updated_at AT TIME ZONE 'UTC', ${ISO}) AS updated_at`;
  return rows[0] ? toPost(rows[0]) : null;
}

export async function deletePost(id: number) {
  await ensureSchema();
  const rows = await db()`DELETE FROM posts WHERE id = ${id} RETURNING id`;
  return rows.length > 0;
}
