// Routes requests: the API and the company response pages go to the
// container, everything else is the static website.
import { Container, getContainer } from "@cloudflare/containers";

// Worker settings and secrets handed to the API as environment variables.
// Anything not set is left out, so the API's own defaults apply.
const PASS_THROUGH = [
  "DATABASE_URL", "JWT_SECRET", "JWT_EXPIRE_MINUTES", "SIGNUP_DOMAINS",
  "PUBLIC_BASE_URL", "GEMINI_API_KEY", "GEMINI_MODEL",
  "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM", "SMTP_REPLY_TO",
  "SMTP_SSL", "SMTP_STARTTLS",
];

export class EsgApi extends Container {
  defaultPort = 8080;
  // Sleeps after 30 idle minutes and wakes on the next request (a few seconds).
  sleepAfter = "30m";

  constructor(ctx, env) {
    super(ctx, env);
    this.envVars = Object.fromEntries(
      PASS_THROUGH.filter((k) => env[k]).map((k) => [k, String(env[k])]));
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/respond/")) {
      // The container sees plain http, so say what the browser used. The API
      // builds the links in request emails from this when PUBLIC_BASE_URL is
      // not set. Set here, never taken from the client.
      const headers = new Headers(request.headers);
      headers.set("X-Forwarded-Proto", url.protocol.replace(":", ""));
      headers.set("X-Forwarded-Host", url.host);
      return getContainer(env.ESG_API).fetch(new Request(request, { headers }));
    }
    return env.ASSETS.fetch(request);
  },
};
