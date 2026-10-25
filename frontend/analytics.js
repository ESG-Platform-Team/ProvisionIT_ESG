// Product analytics for user acceptance testing, via PostHog.
//
// Off unless analytics.config.js holds a project key, or when the page is
// opened with ?ph=off. What it records:
//   - page views, clicks (autocapture) and session replays, with every input
//     field masked, so passwords, email addresses and notes never leave the page
//   - a handful of named events at the API seam (see backend.js) carrying ids,
//     counts and timings only, never company contact details or report text
//   - in-app surveys, which are configured in PostHog, not here
// The company response page (/respond) is served by the API, not this page,
// so companies answering a request are never tracked.

const VERSION = "1.435.5";
const cfg = window.PROVISION_ANALYTICS || {};
const optedOut = new URLSearchParams(location.search).get("ph") === "off";

const EMAIL = /[^\s@<>"']+@[^\s@<>"']+\.[a-z]{2,}/gi;

let loading = null;

export function enabled() {
  return Boolean(cfg.key) && !optedOut;
}

function load() {
  if (!enabled()) return Promise.resolve(null);
  if (!loading) {
    loading = import(`./vendor/posthog-${VERSION}.module.js`)
      .then(({ default: posthog }) => {
        posthog.init(cfg.key, {
          api_host: cfg.host || "https://us.i.posthog.com",
          person_profiles: "identified_only",
          capture_pageview: true,
          autocapture: true,
          persistence: "localStorage",
          session_recording: {
            // Every input is masked. On-screen text stays readable, except
            // anything shaped like an email address (contacts, recipients).
            maskAllInputs: true,
            maskTextSelector: "*",
            maskTextFn: text => text.replace(EMAIL, "\u2022\u2022\u2022@\u2022\u2022\u2022")
          }
        });
        posthog.register({ app: "provisionit-esg", environment: cfg.environment || "local" });
        if (cfg.debug) { posthog.debug(); window.posthog = posthog; }
        return posthog;
      })
      .catch(err => {
        // Offline or blocked by an ad blocker: the platform carries on without it.
        console.info("[provision] analytics unavailable", err && err.message);
        return null;
      });
  }
  return loading;
}

export function track(event, properties) {
  if (!enabled()) return;
  load().then(ph => ph && ph.capture(event, properties || {}));
}

// Signed-in analysts are identified by their account id only: no name, no email.
export function identify(user) {
  if (!enabled() || !user || user.userId == null) return;
  load().then(ph => ph && ph.identify(String(user.userId), { role: user.role || "analyst" }));
}

export function reset() {
  if (!enabled()) return;
  load().then(ph => ph && ph.reset());
}

// Start PostHog as soon as the page loads, so page views and replays begin
// before the first API call.
load();
