import { Sidebar } from "@/components/layout/sidebar";
import { FetchingBar } from "@/components/ui/fetching-bar";

export const dynamic = "force-dynamic";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-dvh w-full overflow-hidden bg-background">
      <Sidebar />
      <div className="relative flex min-h-0 min-w-0 flex-1 flex-col bg-background">
        <FetchingBar />
        <main className="min-h-0 w-full max-w-none flex-1 overflow-y-auto px-6 py-8 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}