// Optional visit counter and error reports (Vercel routing middleware).
//
// When COLLECTOR_URL and COLLECTOR_TOKEN are both set, each view of the page is posted to
// `${COLLECTOR_URL}/collect` after the response, so the page is never slower or different, and an
// error the page reports to /api/client-error is forwarded there as `kind: "error"`. The token
// never reaches the browser. Without both variables nothing is sent, which is the default for a
// fork or a local preview. COLLECTOR_PAGE names the site in the collector (default: the host).

export const config = { matcher: ["/", "/api/client-error"] };

async function forwardError(request, url, token) {
  try {
    const body = await request.json();
    const message = String(body.message || "").slice(0, 300);
    if (url && token && message) {
      await fetch(`${url.replace(/\/$/, "")}/collect`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`,
                   "User-Agent": "estate-collector-client/1.0" },
        body: JSON.stringify({ kind: "error", page: process.env.COLLECTOR_PAGE || new URL(request.url).host,
                               message, source: String(body.source || "").slice(0, 250),
                               agent: request.headers.get("user-agent") || "" }),
        signal: AbortSignal.timeout(1500),
      });
    }
  } catch {
    // a report that cannot be read or sent is dropped; the page never sees it
  }
  return new Response(null, { status: 204 });
}

export default function middleware(request, context) {
  const url = process.env.COLLECTOR_URL;
  const token = process.env.COLLECTOR_TOKEN;
  if (new URL(request.url).pathname === "/api/client-error") {
    return request.method === "POST" ? forwardError(request, url, token) : new Response(null, { status: 405 });
  }
  if (!url || !token || request.method !== "GET") return;
  if (!(request.headers.get("accept") || "").includes("text/html")) return;
  const body = JSON.stringify({
    page: process.env.COLLECTOR_PAGE || new URL(request.url).host,
    ref: request.headers.get("referer") || "Unknown",
    agent: request.headers.get("user-agent") || "",
    ip: (request.headers.get("x-forwarded-for") || "").split(",")[0].trim(),
    domain: "",
  });
  const sent = fetch(`${url.replace(/\/$/, "")}/collect`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      // some edges refuse a request with no user agent of its own
      "User-Agent": "estate-collector-client/1.0",
    },
    body,
    signal: AbortSignal.timeout(1500),
  }).catch(() => undefined);
  context?.waitUntil?.(sent);
}
