"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  FileText,
  LayoutDashboard,
  Layers,
  LogOut,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";

import { Logo } from "@/components/layout/logo";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import { ApiError, apiFetch } from "@/lib/api";
import { Loader, Skeleton, Spinner } from "@/components/ui/loader";
import { redirectToLogin, getOrgId, switchOrganization } from "@/lib/session";
import { cn } from "@/lib/utils";
import type { User } from "@/types/api";

const nav = [
  { href: "/overview", label: "Resumen", icon: LayoutDashboard },
  { href: "/documents", label: "Documentos", icon: FileText },
  { href: "/exams", label: "Exámenes", icon: BookOpen },
  { href: "/flashcards", label: "Flashcards", icon: Layers },
  {
    href: "/team/members",
    label: "Equipo",
    icon: Users,
    children: [
      { href: "/team/members", label: "Miembros" },
      { href: "/team/groups", label: "Grupos" },
      { href: "/team/invite", label: "Invitar" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<User>("/api/v1/auth/me"),
    refetchOnMount: "always",
  });

  const [orgId, setOrgId] = useState<string | null>(null);

  useEffect(() => {
    setOrgId(getOrgId());
  }, [me.data]);

  useEffect(() => {
    if (me.error instanceof ApiError && (me.error.status === 401 || me.error.message === "Invalid token")) {
      void redirectToLogin();
    }
  }, [me.error]);

  async function logout() {
    await redirectToLogin("/login");
  }

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground">
      <div className="px-5 py-5">
        <Logo inverted />
        {me.isLoading ? (
          <Loader label="Cargando workspace…" className="mt-4 text-sidebar-muted" />
        ) : me.data?.memberships.length ? (
          <label className="mt-4 block">
            <span className="mb-1 block text-[11px] font-medium uppercase tracking-wide text-sidebar-muted">
              Workspace
            </span>
            <select
              aria-label="Workspace"
              className="h-9 w-full rounded-md border border-sidebar-border bg-sidebar-hover px-2 text-xs text-sidebar-foreground"
              value={orgId ?? me.data.personal_organization_id ?? me.data.memberships[0].organization_id}
              onChange={(event) => switchOrganization(event.target.value)}
            >
              {me.data.memberships.map((membership) => (
                <option key={membership.organization_id} value={membership.organization_id}>
                  {membership.organization.name}
                  {membership.organization.is_personal ? " (personal)" : " (empresa)"}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <Link
          href="/team/invite"
          className="mt-2 block text-xs text-sidebar-muted hover:text-sidebar-foreground hover:underline"
        >
          {me.data && me.data.memberships.length < 2 ? "Crear equipo e invitar →" : "Invitar al equipo →"}
        </Link>
      </div>
      <nav className="flex flex-1 flex-col gap-1 px-3">
        {nav.map((item) => {
          const Icon = item.icon;
          const children = "children" in item ? item.children : undefined;
          const sectionActive = Boolean(children) && (pathname === "/team" || pathname.startsWith("/team/"));
          const itemActive =
            !children && (pathname === item.href || pathname.startsWith(`${item.href}/`));
          return (
            <div key={item.href}>
              <Link
                href={item.href}
                className={cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-foreground",
                  itemActive &&
                    "bg-accent font-medium text-accent-foreground hover:bg-accent hover:text-accent-foreground",
                  children && sectionActive && "text-sidebar-foreground",
                )}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </Link>
              {children ? (
                <div className="mb-1 ml-4 mt-0.5 flex flex-col gap-0.5 border-l border-sidebar-border pl-3">
                  {children.map((child) => {
                    const childActive = pathname === child.href;
                    return (
                      <Link
                        key={child.href}
                        href={child.href}
                        className={cn(
                          "rounded-md px-3 py-1.5 text-sm text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-foreground",
                          childActive &&
                            "bg-accent font-medium text-accent-foreground hover:bg-accent hover:text-accent-foreground",
                        )}
                      >
                        {child.label}
                      </Link>
                    );
                  })}
                </div>
              ) : null}
            </div>
          );
        })}
      </nav>
      <div className="border-t border-sidebar-border p-3">
        <div className="flex items-center justify-between gap-2 px-2 pb-2">
          <div className="min-w-0">
            <p className="flex items-center gap-2 truncate text-sm font-medium text-sidebar-foreground">
              {me.isLoading ? (
                <>
                  <Spinner className="h-3.5 w-3.5 shrink-0 text-sidebar-muted" />
                  Cargando…
                </>
              ) : (
                (me.data?.full_name ?? "Usuario")
              )}
            </p>
            {me.isLoading ? (
              <Skeleton className="mt-1 h-3 w-24 bg-sidebar-hover" />
            ) : (
              <p className="truncate text-xs text-sidebar-muted">{me.data?.email}</p>
            )}
          </div>
          <ThemeToggle className="text-sidebar-foreground hover:bg-sidebar-hover hover:text-sidebar-foreground" />
        </div>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-start text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-foreground"
          onClick={logout}
        >
          <LogOut className="h-4 w-4" />
          Cerrar sesión
        </Button>
      </div>
    </aside>
  );
}
