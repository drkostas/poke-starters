// Optional visit counter (Vercel routing middleware).
//
// When COLLECTOR_URL and COLLECTOR_TOKEN are both set, each view of the page is posted to
// `${COLLECTOR_URL}/collect` after the response, so the page is never slower or different.
// Without both variables nothing is sent, which is the default for a fork or a local preview.
// COLLECTOR_PAGE names the site in the collector (default: the host).

export const config = { matcher: ["/"] };

export default function middleware(request, context) {
  const url = process.env.COLLECTOR_URL;
  const token = process.env.COLLECTOR_TOKEN;
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
