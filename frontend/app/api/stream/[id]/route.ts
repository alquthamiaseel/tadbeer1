/**
 * Proxies the backend's server-sent event stream to the browser.
 *
 * The browser cannot call the backend directly without being handed the
 * dashboard password, so the stream is relayed here: this route attaches the
 * password server-side and passes the upstream body through untouched.
 */

import { apiHeaders, apiUrl } from "@/lib/api";
import { authEnabled, COOKIE, tokenMatches } from "@/lib/session";

export const dynamic = "force-dynamic";

export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  if (authEnabled()) {
    const cookie = request.headers
      .get("cookie")
      ?.split("; ")
      .find((entry) => entry.startsWith(`${COOKIE}=`))
      ?.slice(COOKIE.length + 1);
    if (!tokenMatches(cookie)) {
      return new Response("Not authorised", { status: 401 });
    }
  }

  const { id } = await params;
  const upstream = await fetch(apiUrl(`/api/runs/${id}/events`), {
    headers: { ...apiHeaders(), Accept: "text/event-stream" },
    cache: "no-store",
    signal: request.signal,
  });

  if (!upstream.ok || !upstream.body) {
    return new Response("Upstream stream unavailable", { status: 502 });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
