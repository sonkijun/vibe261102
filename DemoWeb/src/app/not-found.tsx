import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center gap-4 py-20 text-center">
      <h1 className="text-2xl font-semibold">글을 찾을 수 없습니다</h1>
      <p className="text-sm text-muted-foreground">삭제되었거나 존재하지 않는 페이지입니다.</p>
      <Button asChild>
        <Link href="/">목록으로 돌아가기</Link>
      </Button>
    </div>
  );
}
