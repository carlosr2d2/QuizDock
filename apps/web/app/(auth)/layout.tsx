import Link from "next/link";

import { Logo } from "@/components/layout/logo";
import { ThemeToggle } from "@/components/layout/theme-toggle";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-full flex-col bg-background">
      <header className="flex items-center justify-between px-6 py-5">
        <Link href="/">
          <Logo />
        </Link>
        <ThemeToggle />
      </header>
      <main className="flex flex-1 items-start justify-center px-6 py-16">{children}</main>
    </div>
  );
}
