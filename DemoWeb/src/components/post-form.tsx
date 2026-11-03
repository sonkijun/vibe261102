"use client";

import Link from "next/link";
import { useActionState } from "react";
import type { FormState } from "@/app/actions";
import type { PostInput } from "@/lib/posts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

type Props = {
  action: (prev: FormState, formData: FormData) => Promise<FormState>;
  initial?: PostInput;
  submitLabel: string;
  cancelHref: string;
};

export function PostForm({ action, initial, submitLabel, cancelHref }: Props) {
  const [state, formAction, pending] = useActionState(action, { values: initial });
  const values = state.values ?? initial;
  const errors = state.errors ?? {};

  return (
    <form action={formAction} className="flex flex-col gap-5" noValidate>
      {state.message && (
        <p role="alert" className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {state.message}
        </p>
      )}

      <div className="grid gap-2">
        <Label htmlFor="title">제목</Label>
        <Input
          id="title"
          name="title"
          placeholder="제목을 입력하세요"
          maxLength={100}
          defaultValue={values?.title}
          aria-invalid={!!errors.title}
        />
        {errors.title && <p className="text-sm text-destructive">{errors.title}</p>}
      </div>

      <div className="grid gap-2">
        <Label htmlFor="author">작성자</Label>
        <Input
          id="author"
          name="author"
          placeholder="이름 또는 닉네임"
          maxLength={30}
          defaultValue={values?.author}
          aria-invalid={!!errors.author}
          className="sm:max-w-xs"
        />
        {errors.author && <p className="text-sm text-destructive">{errors.author}</p>}
      </div>

      <div className="grid gap-2">
        <Label htmlFor="content">내용</Label>
        <Textarea
          id="content"
          name="content"
          placeholder="내용을 입력하세요"
          rows={12}
          defaultValue={values?.content}
          aria-invalid={!!errors.content}
          className="min-h-60"
        />
        {errors.content && <p className="text-sm text-destructive">{errors.content}</p>}
      </div>

      <div className="flex justify-end gap-2">
        <Button variant="outline" asChild>
          <Link href={cancelHref}>취소</Link>
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? "저장 중…" : submitLabel}
        </Button>
      </div>
    </form>
  );
}
