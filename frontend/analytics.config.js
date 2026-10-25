// PostHog settings for user acceptance testing.
//
// Leave key empty and nothing is loaded or sent: the local demo and the test
// suite run exactly as before. To turn it on, paste the project API key from
// PostHog (Project settings > Project API key, it starts with phc_). That key
// is designed to be public; it can send events but cannot read anything.
window.PROVISION_ANALYTICS = {
  key: "",
  host: "https://us.i.posthog.com",   // or https://eu.i.posthog.com for an EU project
  environment: "uat"                  // tags every event, so demo runs can be filtered out
};
