import type { Metadata } from "next";
import { createPostAction } from "@/app/actions";
import { PostForm } from "@/components/post-form";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = { title: "글쓰기" };

export default function NewPostPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">새 글 작성</CardTitle>
      </CardHeader>
      <CardContent>
        <PostForm action={createPostAction} submitLabel="등록" cancelHref="/" />
      </CardContent>
    </Card>
  );
}
