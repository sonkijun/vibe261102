import { randomUUID } from "crypto";
import { promises as fs } from "fs";
import path from "path";

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

const DATA_DIR = path.join(process.cwd(), "data");
const DATA_FILE = path.join(DATA_DIR, "posts.json");

// 동시 쓰기로 파일이 깨지지 않도록 쓰기 작업을 순서대로 실행합니다.
let writeQueue: Promise<unknown> = Promise.resolve();

function seedPosts(): Post[] {
  const now = new Date().toISOString();
  return [
    {
      id: 1,
      title: "DemoWeb 게시판에 오신 것을 환영합니다",
      author: "관리자",
      content:
        "Next.js App Router와 shadcn/ui로 만든 간단한 게시판입니다.\n\n글 작성, 수정, 삭제, 검색을 사용해 보세요. 데이터는 서버의 data/posts.json 파일에 저장됩니다.",
      createdAt: now,
      updatedAt: now,
    },
  ];
}

async function readAll(): Promise<Post[]> {
  try {
    const raw = await fs.readFile(DATA_FILE, "utf8");
    return JSON.parse(raw) as Post[];
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    const posts = seedPosts();
    await writeAll(posts);
    return posts;
  }
}

async function writeAll(posts: Post[]) {
  await fs.mkdir(DATA_DIR, { recursive: true });
  const tmp = `${DATA_FILE}.${randomUUID()}.tmp`;
  await fs.writeFile(tmp, JSON.stringify(posts, null, 2), "utf8");
  await fs.rename(tmp, DATA_FILE);
}

function mutate<T>(fn: (posts: Post[]) => { posts: Post[]; result: T }) {
  const run = writeQueue.then(async () => {
    const { posts, result } = fn(await readAll());
    await writeAll(posts);
    return result;
  });
  writeQueue = run.catch(() => {});
  return run;
}

export async function listPosts({ query = "", page = 1 }: { query?: string; page?: number }) {
  const q = query.trim().toLowerCase();
  const all = (await readAll())
    .filter(
      (p) =>
        !q ||
        p.title.toLowerCase().includes(q) ||
        p.content.toLowerCase().includes(q) ||
        p.author.toLowerCase().includes(q),
    )
    .sort((a, b) => b.id - a.id);

  const totalPages = Math.max(1, Math.ceil(all.length / PAGE_SIZE));
  const current = Math.min(Math.max(1, page), totalPages);
  return {
    posts: all.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE),
    total: all.length,
    page: current,
    totalPages,
  };
}

export async function getPost(id: number) {
  return (await readAll()).find((p) => p.id === id) ?? null;
}

export function createPost(input: PostInput) {
  return mutate((posts) => {
    const now = new Date().toISOString();
    const post: Post = {
      id: posts.reduce((max, p) => Math.max(max, p.id), 0) + 1,
      ...input,
      createdAt: now,
      updatedAt: now,
    };
    return { posts: [...posts, post], result: post };
  });
}

export function updatePost(id: number, input: PostInput) {
  return mutate((posts) => {
    const existing = posts.find((p) => p.id === id);
    if (!existing) return { posts, result: null };
    const updated = { ...existing, ...input, updatedAt: new Date().toISOString() };
    return { posts: posts.map((p) => (p.id === id ? updated : p)), result: updated };
  });
}

export function deletePost(id: number) {
  return mutate((posts) => {
    const next = posts.filter((p) => p.id !== id);
    return { posts: next, result: next.length !== posts.length };
  });
}
