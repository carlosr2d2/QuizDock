"use client";

import Link from "next/link";

import { LocaleSwitcher } from "@/components/layout/locale-switcher";
import { Logo } from "@/components/layout/logo";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n/provider";

export function HomeLanding() {
  const t = useT();
  const features = [
    { title: t("home.ingestTitle"), body: t("home.ingestBody") },
    { title: t("home.examsTitle"), body: t("home.examsBody") },
    { title: t("home.teamsTitle"), body: t("home.teamsBody") },
  ];

  return (
    <div className="flex min-h-full flex-col bg-background">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6">
        <Logo />
        <nav className="flex items-center gap-2">
          <LocaleSwitcher />
          <ThemeToggle />
          <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground">
            {t("home.login")}
          </Link>
          <Link href="/register">
            <Button size="sm">{t("home.start")}</Button>
          </Link>
        </nav>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 pb-24 pt-12">
        <p className="text-sm font-medium text-accent">{t("home.tagline")}</p>
        <h1 className="mt-4 max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          {t("home.headline")}
        </h1>
        <p className="mt-5 max-w-2xl text-base leading-relaxed text-muted-foreground">{t("home.body")}</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/register">
            <Button size="lg">{t("home.createFree")}</Button>
          </Link>
          <Link href="/login">
            <Button size="lg" variant="outline">
              {t("home.haveAccount")}
            </Button>
          </Link>
        </div>

        <section className="mt-24 grid gap-6 sm:grid-cols-3">
          {features.map((feature) => (
            <article
              key={feature.title}
              className="rounded-xl border border-border bg-card p-6 shadow-sm"
            >
              <h2 className="text-sm font-semibold">{feature.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{feature.body}</p>
            </article>
          ))}
        </section>
      </main>

      <footer className="border-t border-border">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6 text-xs text-muted-foreground">
          <span>QuizDock</span>
          <span>{t("home.footer")}</span>
        </div>
      </footer>
    </div>
  );
}
