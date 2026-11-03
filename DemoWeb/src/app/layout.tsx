import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { MessagesSquare, PenSquare } from "lucide-react";
import { ThemeProvider } from "@/components/theme-provider";
import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: { default: "DemoWeb 게시판", template: "%s | DemoWeb 게시판" },
  description: "Next.js와 shadcn/ui로 만든 간단한 게시판",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="ko"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur">
            <div className="mx-auto flex h-14 w-full max-w-4xl items-center justify-between px-4">
              <Link href="/" className="flex items-center gap-2 font-semibold">
                <MessagesSquare className="size-5" />
                DemoWeb 게시판
              </Link>
              <div className="flex items-center gap-1">
                <Button size="sm" asChild>
                  <Link href="/posts/new">
                    <PenSquare /> <span className="hidden sm:inline">글쓰기</span>
                  </Link>
                </Button>
                <ThemeToggle />
              </div>
            </div>
          </header>
          <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-6 sm:py-10">{children}</main>
          <footer className="border-t py-6 text-center text-xs text-muted-foreground">
            DemoWeb · Next.js + shadcn/ui
          </footer>
        </ThemeProvider>
      </body>
    </html>
  );
}
