import type { Metadata } from "next";
import Link from "next/link";

import { Logo } from "@/components/layout/logo";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "QuizDock — Documentos a evaluaciones",
};

const features = [
  {
    title: "Ingesta de documentos",
    body: "Sube PDFs técnicos, normativas o material académico. El procesamiento corre en segundo plano.",
  },
  {
    title: "Exámenes y flashcards",
    body: "Genera cuestionarios dinámicos y tarjetas de estudio con repetición espaciada.",
  },
  {
    title: "Equipos e instituciones",
    body: "Workspaces, roles y asignación de evaluaciones para capacitación y cumplimiento.",
  },
];

export default function HomePage() {
  return (
    <div className="flex min-h-full flex-col bg-background">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6">
        <Logo />
        <nav className="flex items-center gap-2">
          <ThemeToggle />
          <Link href="/login" className="text-sm text-muted-foreground hover:text-foreground">
            Entrar
          </Link>
          <Link href="/register">
            <Button size="sm">Empezar</Button>
          </Link>
        </nav>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-6 pb-24 pt-12">
        <p className="text-sm font-medium text-accent">SaaS B2B / B2C</p>
        <h1 className="mt-4 max-w-3xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          Convierte documentos técnicos en evaluaciones listas para usar.
        </h1>
        <p className="mt-5 max-w-2xl text-base leading-relaxed text-muted-foreground">
          Sube normativas, guías o material de estudio. QuizDock genera cuestionarios, exámenes y
          flashcards para estudio individual o capacitación de equipos.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/register">
            <Button size="lg">Crear cuenta gratuita</Button>
          </Link>
          <Link href="/login">
            <Button size="lg" variant="outline">
              Ya tengo cuenta
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
          <span>Evaluación inteligente de documentos</span>
        </div>
      </footer>
    </div>
  );
}
