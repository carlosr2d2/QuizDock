import { NextRequest } from "next/server";

const API = process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function proxyCover(request: NextRequest, documentId: string) {
  const auth = request.headers.get("authorization") ?? "";
  const org = request.headers.get("x-organization-id") ?? "";
  const upstream = await fetch(`${API}/api/v1/documents/${documentId}/cover`, {
    headers: {
      ...(auth ? { Authorization: auth } : {}),
      ...(org ? { "X-Organization-Id": org } : {}),
    },
    cache: "no-store",
  });
  if (upstream.status === 404 || upstream.status === 204) {
    return new Response(null, { status: 404 });
  }
  if (!upstream.ok) {
    return new Response(null, { status: upstream.status });
  }
  const buffer = await upstream.arrayBuffer();
  return new Response(buffer, {
    status: 200,
    headers: {
      "Content-Type": upstream.headers.get("content-type") ?? "image/jpeg",
      "Cache-Control": "private, max-age=86400",
    },
  });
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ documentId: string }> },
) {
  const { documentId } = await context.params;
  return proxyCover(request, documentId);
}
