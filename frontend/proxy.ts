import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const API_INTERNAL_URL =
  process.env.API_INTERNAL_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

async function hasValidSession(request: NextRequest): Promise<boolean> {
  const cookie = request.headers.get("cookie");
  if (!cookie) return false;

  try {
    const response = await fetch(`${API_INTERNAL_URL}/auth/me`, {
      cache: "no-store",
      headers: { cookie },
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function proxy(request: NextRequest) {
  const authenticated = await hasValidSession(request);

  if (request.nextUrl.pathname === "/") {
    return NextResponse.redirect(
      new URL(authenticated ? "/app" : "/login", request.url),
    );
  }

  if (!authenticated) {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/app/:path*"],
};
