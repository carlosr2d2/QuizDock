import { Suspense } from "react";

import { PageLoader } from "@/components/ui/loader";

import { FlashcardsView } from "./flashcards-view";

export default function FlashcardsPage() {
  return (
    <Suspense fallback={<PageLoader />}>
      <FlashcardsView />
    </Suspense>
  );
}
