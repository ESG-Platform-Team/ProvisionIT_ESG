# User acceptance testing with PostHog

Automated tests prove the rules hold. PostHog shows whether people can use the
platform: where they hesitate, where they give up, and what they think.

## Turn it on

1. Create a free project at posthog.com. Choose the US or EU region; note which.
2. Project settings > Project API key. Copy the key (it starts with `phc_`).
   This key is designed to be public: it can send events but cannot read data.
3. Put it in `frontend/analytics.config.js`:

   ```js
   window.PROVISION_ANALYTICS = {
     key: "phc_...",
     host: "https://us.i.posthog.com",   // https://eu.i.posthog.com for an EU project
     environment: "uat"
   };
   ```

4. Project settings > Session replay: switch it on.
5. Reload the platform. Open it with `?ph=off` on the end of the address to
   use it without being recorded (rehearsals, our own testing).

Leave `key` empty and nothing loads: the offline demo and the tests behave
exactly as before.

## What is recorded

| Event | Fired when | Properties |
|---|---|---|
| `$pageview`, `$autocapture` | Page loads and clicks | PostHog defaults |
| `signed_up`, `signed_in`, `signed_out` | Account actions | none (the person is identified by account id only) |
| `assessment_started` | A search is run | `pillars`, `pillarCount` |
| `assessment_completed` | The run finishes | `seconds`, `runId`, one `<pillar>_band` per pillar |
| `assessment_failed` | The run errors | `pillars`, `seconds` |
| `evidence_opened` | The evidence for a criterion is fetched | `runId`, `criterionCode` |
| `report_downloaded` | PDF downloaded | `runId` |
| `report_emailed` | Report emailed | `runId`, `withNote` |
| `disclosure_request_sent` | A request is sent | `source`, document and item counts, `dueDays` |
| `disclosure_request_closed`, `reassessed_after_request` | Request lifecycle | none |
| `company_added`, `contacts_looked_up` | Composer actions | `listed` |
| `api_error` | Any API call fails | `status`, `path` (ids removed) |

Never recorded: names, email addresses, passwords, notes, report text,
contact details. Session replays mask every input field and anything shaped
like an email address. The company response page is served by the API, not
by this frontend, so companies answering a request are never tracked.

## Set up for the client sessions

- **Funnel** (Product analytics > New insight > Funnel): `$pageview` >
  `assessment_started` > `assessment_completed` > `report_downloaded`.
  Shows where people drop out between searching and getting a report.
- **Survey** (Surveys > New survey, popover): show after `report_downloaded`.
  Suggested questions: "How confident are you in this assessment?" (1 to 5),
  "Was anything hard to find?" (free text), "Would you use this instead of
  doing it by hand?" (yes / no / not yet).
- **Replays**: filter by `environment = uat` and watch the first session of
  each tester before reading their survey answers.
- Filter out our own team with the `?ph=off` link, or by excluding our
  account ids.

## Headless browsers

PostHog drops events from browsers that look automated (Playwright, CI).
That is intended: test runs never pollute the client's data.
