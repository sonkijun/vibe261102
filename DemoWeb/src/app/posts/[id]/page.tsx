import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { ArrowLeft, Pencil } from "lucide-react";
import { getPost } from "@/lib/posts";
import { formatDateTime } from "@/lib/format";
import { DeletePostButton } from "@/components/delete-post-button";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

export default function PostPage({ params }: PageProps<"/posts/[id]">) {
  return (
    <Suspense fallback={<p className="py-10 text-center text-sm text-muted-foreground">불러오는 중…</p>}>
      <PostDetail params={params} />
    </Suspense>
  );
}

async function PostDetail({ params }: Pick<PageProps<"/posts/[id]">, "params">) {
  const { id } = await params;
  const post = await getPost(Number(id));
  if (!post) notFound();

  const edited = post.updatedAt !== post.createdAt;

  return (
    <div className="flex flex-col gap-4">
      <Button variant="ghost" size="sm" className="self-start" asChild>
        <Link href="/">
          <ArrowLeft /> 목록으로
        </Link>
      </Button>
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl break-words">{post.title}</CardTitle>
          <CardDescription className="flex flex-wrap gap-x-3 gap-y-1">
            <span>{post.author}</span>
            <span>{formatDateTime(post.createdAt)}</span>
            {edited && <span>(수정됨 {formatDateTime(post.updatedAt)})</span>}
          </CardDescription>
        </CardHeader>
        <Separator />
        <CardContent>
          <div className="min-h-40 whitespace-pre-wrap break-words leading-relaxed">{post.content}</div>
        </CardContent>
        <Separator />
        <CardFooter className="justify-end gap-2">
          <Button variant="outline" asChild>
            <Link href={`/posts/${post.id}/edit`}>
              <Pencil /> 수정
            </Link>
          </Button>
          <DeletePostButton id={post.id} title={post.title} />
        </CardFooter>
      </Card>
    </div>
  );
}
