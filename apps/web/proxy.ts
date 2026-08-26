import { NextRequest, NextResponse } from "next/server";

const protectedPrefixes = ["/overview", "/documents", "/exams", "/flashcards", "/team"];

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isProtected = protectedPrefixes.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  if (!isProtected) return NextResponse.next();

  const hasSession = Boolean(request.cookies.get("qd_token")?.value);
  if (!hasSession) {
    const login = new URL("/login", request.url);
    login.searchParams.set("next", pathname);
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/overview",
    "/documents",
    "/exams",
    "/exams/:path*",
    "/flashcards",
    "/flashcards/:path*",
    "/team",
    "/team/:path*",
  ],
};
