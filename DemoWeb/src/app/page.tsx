import Form from "next/form";
import Link from "next/link";
import { Suspense } from "react";
import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { listPosts } from "@/lib/posts";
import { formatDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export default function Home({ searchParams }: PageProps<"/">) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">게시판</CardTitle>
        <CardDescription>최신 글부터 보여 드립니다.</CardDescription>
      </CardHeader>
      <CardContent>
        <Suspense fallback={<p className="py-10 text-center text-sm text-muted-foreground">불러오는 중…</p>}>
          <PostList searchParams={searchParams} />
        </Suspense>
      </CardContent>
    </Card>
  );
}

async function PostList({ searchParams }: Pick<PageProps<"/">, "searchParams">) {
  const params = await searchParams;
  const query = typeof params.q === "string" ? params.q : "";
  const pageParam = Number(typeof params.page === "string" ? params.page : 1);
  const { posts, total, page, totalPages } = await listPosts({
    query,
    page: Number.isFinite(pageParam) ? pageParam : 1,
  });

  const pageHref = (p: number) => {
    const sp = new URLSearchParams();
    if (query) sp.set("q", query);
    if (p > 1) sp.set("page", String(p));
    const s = sp.toString();
    return s ? `/?${s}` : "/";
  };

  return (
    <div className="flex flex-col gap-4">
      <Form action="/" className="flex gap-2" key={query}>
        <Input
          name="q"
          defaultValue={query}
          placeholder="제목, 내용, 작성자 검색"
          aria-label="검색어"
          type="search"
        />
        <Button type="submit" variant="secondary">
          <Search /> <span className="hidden sm:inline">검색</span>
        </Button>
      </Form>

      <p className="text-sm text-muted-foreground">
        {query ? (
          <>
            &ldquo;{query}&rdquo; 검색 결과 {total}건 ·{" "}
            <Link href="/" className="underline underline-offset-4">
              전체 보기
            </Link>
          </>
        ) : (
          <>전체 {total}건</>
        )}
      </p>

      {posts.length === 0 ? (
        <div className="rounded-lg border border-dashed py-16 text-center text-sm text-muted-foreground">
          {query ? "검색 결과가 없습니다." : "아직 작성된 글이 없습니다. 첫 글을 작성해 보세요!"}
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="hidden w-16 text-center sm:table-cell">번호</TableHead>
              <TableHead>제목</TableHead>
              <TableHead className="hidden w-32 sm:table-cell">작성자</TableHead>
              <TableHead className="w-28 text-right">작성일</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {posts.map((post) => (
              <TableRow key={post.id}>
                <TableCell className="hidden text-center text-muted-foreground sm:table-cell">
                  {post.id}
                </TableCell>
                <TableCell className="max-w-0 whitespace-normal">
                  <Link
                    href={`/posts/${post.id}`}
                    className="block truncate font-medium hover:underline underline-offset-4"
                  >
                    {post.title}
                  </Link>
                  <span className="text-xs text-muted-foreground sm:hidden">{post.author}</span>
                </TableCell>
                <TableCell className="hidden truncate sm:table-cell">{post.author}</TableCell>
                <TableCell className="text-right text-muted-foreground">
                  {formatDate(post.createdAt)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {totalPages > 1 && (
        <nav className="flex items-center justify-center gap-1" aria-label="페이지 이동">
          <PageLink href={pageHref(page - 1)} disabled={page <= 1} label="이전 페이지">
            <ChevronLeft />
          </PageLink>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <Button key={p} size="icon-sm" variant={p === page ? "default" : "ghost"} asChild>
              <Link href={pageHref(p)} aria-current={p === page ? "page" : undefined}>
                {p}
              </Link>
            </Button>
          ))}
          <PageLink href={pageHref(page + 1)} disabled={page >= totalPages} label="다음 페이지">
            <ChevronRight />
          </PageLink>
        </nav>
      )}
    </div>
  );
}

function PageLink({
  href,
  disabled,
  label,
  children,
}: {
  href: string;
  disabled: boolean;
  label: string;
  children: React.ReactNode;
}) {
  if (disabled) {
    return (
      <Button size="icon-sm" variant="ghost" disabled aria-label={label}>
        {children}
      </Button>
    );
  }
  return (
    <Button size="icon-sm" variant="ghost" asChild>
      <Link href={href} aria-label={label}>
        {children}
      </Link>
    </Button>
  );
}
