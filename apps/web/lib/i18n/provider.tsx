"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { apiFetch } from "@/lib/api";
import { getToken } from "@/lib/session";
import {
  DEFAULT_LOCALE,
  LOCALE_COOKIE,
  LOCALE_STORAGE_KEY,
  type Locale,
  parseLocale,
  translate,
} from "@/lib/i18n/config";
import { en, es } from "@/lib/i18n/messages";
import type { User } from "@/types/api";

const catalogs = { es, en } as const;

type Translate = (key: string, vars?: Record<string, string | number>) => string;

type I18nValue = {
  locale: Locale;
  t: Translate;
  setLocale: (locale: Locale) => void;
  applyLocale: (locale: Locale) => void;
};

const I18nContext = createContext<I18nValue>({
  locale: DEFAULT_LOCALE,
  t: (key) => key,
  setLocale: () => undefined,
  applyLocale: () => undefined,
});

function readStoredLocale(): Locale {
  if (typeof window === "undefined") return DEFAULT_LOCALE;
  const stored = localStorage.getItem(LOCALE_STORAGE_KEY);
  if (stored === "en" || stored === "es") return stored;
  const match = document.cookie.split("; ").find((row) => row.startsWith(`${LOCALE_COOKIE}=`));
  return parseLocale(match?.split("=")[1]);
}

function persistLocale(locale: Locale) {
  localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  document.cookie = `${LOCALE_COOKIE}=${locale}; Path=/; Max-Age=31536000; SameSite=Lax`;
  document.documentElement.lang = locale;
}

export function I18nProvider({
  children,
  initialLocale = DEFAULT_LOCALE,
}: {
  children: React.ReactNode;
  initialLocale?: Locale;
}) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);
  const queryClient = useQueryClient();

  useEffect(() => {
    const stored = readStoredLocale();
    if (stored !== locale) setLocaleState(stored);
    document.documentElement.lang = stored;
    // Hydrate from storage once; locale is the cookie-backed SSR value.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const applyLocale = useCallback((next: Locale) => {
    persistLocale(next);
    setLocaleState(next);
  }, []);

  const setLocale = useCallback(
    (next: Locale) => {
      applyLocale(next);
      if (!getToken()) return;
      void apiFetch<User>("/api/v1/auth/me", { method: "PATCH", body: { locale: next } })
        .then(() => queryClient.invalidateQueries({ queryKey: ["me"] }))
        .catch(() => undefined);
    },
    [applyLocale, queryClient],
  );

  const value = useMemo<I18nValue>(
    () => ({
      locale,
      t: (key, vars) => translate(catalogs[locale] as never, key, vars),
      setLocale,
      applyLocale,
    }),
    [locale, setLocale, applyLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}

export function useT() {
  return useI18n().t;
}

export function syncLocaleFromUser(user: { locale?: string } | null | undefined) {
  if (!user?.locale) return;
  persistLocale(parseLocale(user.locale));
}

export function useSyncUserLocale(user?: { locale?: string } | null) {
  const { locale, applyLocale } = useI18n();
  useEffect(() => {
    if (!user?.locale) return;
    const next = parseLocale(user.locale);
    if (next !== locale) applyLocale(next);
  }, [user?.locale, locale, applyLocale]);
}
