import { NextResponse } from "next/server";

const COOKIE = "qd_token";
const MAX_AGE = 60 * 60 * 24 * 7;

function applySessionCookie(response: NextResponse, value: string | null) {
  const secure = process.env.NODE_ENV === "production";
  if (value) {
    response.cookies.set({
      name: COOKIE,
      value,
      path: "/",
      maxAge: MAX_AGE,
      sameSite: "lax",
      httpOnly: true,
      secure,
    });
  } else {
    response.cookies.set({
      name: COOKIE,
      value: "",
      path: "/",
      maxAge: 0,
      sameSite: "lax",
      httpOnly: true,
      secure,
    });
  }
  return response;
}

export async function POST() {
  return applySessionCookie(NextResponse.json({ ok: true }), "1");
}

export async function DELETE() {
  return applySessionCookie(NextResponse.json({ ok: true }), null);
}
