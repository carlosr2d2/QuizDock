import type { Metadata } from "next";

import { HomeLanding } from "@/components/home-landing";

export const metadata: Metadata = {
  title: "QuizDock — Documentos a evaluaciones",
};

export default function HomePage() {
  return <HomeLanding />;
}
