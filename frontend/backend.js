// Talks to the ESG backend. The only file in the frontend that knows a backend
// exists. Everything else consumes the same shape it always did.
//
// Point API_BASE at the FastAPI service. Set it to null and the page falls back
// to the built-in demo data, which is what makes this safe to ship before the
// backend is reliable.

import { track, identify, reset } from "./analytics.js";

export const API_BASE = window.PROVISION_API_BASE ?? "http://localhost:8080";

export const backendEnabled = () => Boolean(API_BASE);

export const PILLARS = ["GOVERNANCE", "ENVIRONMENTAL", "SOCIAL"];

// The session token from signing in. Kept in localStorage so a refresh keeps you
// signed in; every request sends it as a bearer token.
const TOKEN_KEY = "provisionit.session";
let token = null;
try { token = localStorage.getItem(TOKEN_KEY); } catch (e) {}

export function signedIn() { return Boolean(token); }

function setToken(t) {
  token = t;
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch (e) {}
}

function withAuth(opts) {
  const o = Object.assign({}, opts || {});
  o.headers = Object.assign({}, o.headers || {}, token ? { Authorization: "Bearer " + token } : {});
  return o;
}

async function json(url, opts) {
  const res = await fetch(url, withAuth(opts));
  if (res.status === 401 && !/\/api\/auth\/(login|signup)$/.test(url)) {
    // Session expired or signed out elsewhere: tell the page to show sign-in.
    setToken(null);
    window.dispatchEvent(new CustomEvent("provision:signedout"));
  }
  if (!res.ok) {
    track("api_error", { status: res.status, path: new URL(url).pathname.replace(/\/[0-9a-f-]{8,}/gi, "/:id") });
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = (body.detail && body.detail.error && body.detail.error.message)
        || JSON.stringify(body);
    } catch (e) {}
    throw new Error(detail);
  }
  return res.json();
}

function post(url, body) {
  return json(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {})
  });
}

export async function signIn(email, password) {
  const out = await post(`${API_BASE}/api/auth/login`, { email, password });
  setToken(out.token);
  identify(out.user);
  track("signed_in");
  return out.user;
}

export async function signUp(name, email, password) {
  const out = await post(`${API_BASE}/api/auth/signup`, { name, email, password });
  setToken(out.token);
  identify(out.user);
  track("signed_up");
  return out.user;
}

export async function signOut() {
  try { await post(`${API_BASE}/api/auth/logout`, {}); } catch (e) {}
  setToken(null);
  track("signed_out");
  reset();
}

export async function me() {
  if (!token) return null;
  try { return (await json(`${API_BASE}/api/auth/me`)).user; } catch (e) { return null; }
}

export async function health() {
  return json(`${API_BASE}/api/health`);
}

export async function listCompanies() {
  const data = await json(`${API_BASE}/api/companies?all=true`);
  return data.matches || [];
}

// Add a private (unlisted) company by its website. Returns the stored company,
// or the existing one if that website is already on file.
export async function addCompany(name, website, contactEmail, sector, asxCode) {
  track("company_added", { listed: Boolean(asxCode) });
  return post(`${API_BASE}/api/companies`, { name, website, contactEmail, sector, asxCode });
}

// Contact addresses the company publishes on its own website. Nothing is
// guessed or stored; the analyst picks one.
export async function findContacts(code) {
  track("contacts_looked_up");
  return json(`${API_BASE}/api/companies/${encodeURIComponent(code)}/contacts`);
}

export async function searchCompanies(query) {
  const data = await json(`${API_BASE}/api/companies?q=${encodeURIComponent(query)}`);
  return data.matches || [];
}

// Polls a run until it completes. onProgress receives the running payload each
// poll, which is what drives the retrieval screen.
export async function pollRun(runId, onProgress, pollAfterMs) {
  const deadline = Date.now() + 15 * 60 * 1000;
  while (Date.now() < deadline) {
    await wait(pollAfterMs || 1500);
    const payload = await json(`${API_BASE}/api/assessments/${runId}`);
    if (payload.status === "COMPLETE") return payload;
    if (payload.status === "FAILED") throw new Error("Run failed on the backend");
    if (onProgress) onProgress(payload);
  }
  throw new Error("Run did not complete within fifteen minutes");
}

// Starts a run for the chosen pillars and polls until it completes.
export async function runAssessment(asxCode, onProgress, pillars) {
  const chosen = pillars && pillars.length ? pillars : ["GOVERNANCE"];
  const t0 = Date.now();
  track("assessment_started", { pillars: chosen, pillarCount: chosen.length });
  const start = await post(`${API_BASE}/api/assessments`, { asxCode, pillars: chosen });
  try {
    const payload = await pollRun(start.runId, onProgress, start.pollAfterMs);
    track("assessment_completed", assessmentSummary(payload, Date.now() - t0));
    return payload;
  } catch (e) {
    track("assessment_failed", { pillars: chosen, seconds: Math.round((Date.now() - t0) / 1000) });
    throw e;
  }
}

// Bands and counts only: enough to see whether people trust what they get,
// nothing that identifies the company's disclosures.
function assessmentSummary(payload, ms) {
  const out = { seconds: Math.round(ms / 1000), runId: payload.runId };
  (payload.pillars || []).forEach(p => {
    const k = String(p.pillar || "").toLowerCase();
    if (k && p.result) out[k + "_band"] = p.result.band || null;
  });
  return out;
}

export async function getRun(runId) {
  return json(`${API_BASE}/api/assessments/${runId}`);
}

export async function listRuns(asxCode) {
  const q = asxCode ? `?asxCode=${encodeURIComponent(asxCode)}` : "";
  const data = await json(`${API_BASE}/api/assessments${q}`);
  return data.runs || [];
}

export async function evidenceFor(runId, criterionCode) {
  track("evidence_opened", { runId, criterionCode });
  return json(`${API_BASE}/api/assessments/${runId}/criteria/${criterionCode}/evidence`);
}

export function reportUrl(runId, download) {
  return `${API_BASE}/api/assessments/${runId}/report.pdf${download ? "?download=true" : ""}`;
}

// The PDF needs the session header, so it is fetched and handed to the browser
// as a file rather than opened as a bare link.
export async function openReport(runId, filename) {
  const res = await fetch(reportUrl(runId, true), withAuth());
  if (!res.ok) throw new Error(res.status === 401 ? "Sign in again to download the report" : res.statusText);
  track("report_downloaded", { runId });
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url; a.download = filename || "esg-assessment.pdf";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

export async function emailReport(runId, to, message) {
  track("report_emailed", { runId, withNote: Boolean(message) });
  return post(`${API_BASE}/api/assessments/${runId}/email`, { to, message, includeJson: true });
}

export async function createRequest(runId, contactEmail, requestedBy, pillars) {
  track("disclosure_request_sent", { source: "assessment", runId });
  return post(`${API_BASE}/api/assessments/${runId}/disclosure-requests`,
    { contactEmail, requestedBy, pillars });
}

export async function requestCatalogue() {
  return json(`${API_BASE}/api/disclosure-requests/catalogue`);
}

// The exact email the request form would send, without sending it.
export async function previewRequest(form) {
  return post(`${API_BASE}/api/disclosure-requests/preview`, form);
}

export async function sendRequestForm(form) {
  track("disclosure_request_sent", {
    source: "composer",
    documents: (form.documents || []).length,
    customItems: (form.custom || []).length,
    includeGaps: Boolean(form.includeGaps),
    dueDays: form.dueDays || null
  });
  return post(`${API_BASE}/api/disclosure-requests`, form);
}

export async function getRequest(requestId) {
  return json(`${API_BASE}/api/disclosure-requests/${requestId}`);
}

// Open a document a company supplied, in a new tab. Fetched with the session
// header, then handed to the browser.
export async function openRequestDocument(requestId, index, download) {
  const url = `${API_BASE}/api/disclosure-requests/${requestId}/documents/${index}${download ? "?download=true" : ""}`;
  const tab = download ? null : window.open("", "_blank");
  const res = await fetch(url, withAuth());
  if (!res.ok) { if (tab) tab.close(); throw new Error(res.status === 401 ? "Sign in again to open the document" : "Document not available"); }
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  if (tab) { tab.location.href = objectUrl; }
  else {
    const name = (res.headers.get("content-disposition") || "").match(/filename="([^"]+)"/);
    const a = document.createElement("a");
    a.href = objectUrl; a.download = name ? name[1] : "document";
    document.body.appendChild(a); a.click(); a.remove();
  }
  setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
}

export async function listRequests(asxCode) {
  const q = asxCode ? `?asxCode=${encodeURIComponent(asxCode)}` : "";
  const data = await json(`${API_BASE}/api/disclosure-requests${q}`);
  return data.requests || [];
}

export async function closeRequest(requestId) {
  track("disclosure_request_closed");
  return post(`${API_BASE}/api/disclosure-requests/${requestId}/close`, {});
}

export async function reassess(requestId, onProgress) {
  track("reassessed_after_request");
  const start = await post(`${API_BASE}/api/disclosure-requests/${requestId}/reassess`, {});
  return pollRun(start.runId, onProgress, start.pollAfterMs);
}

// Backend enum to the label the UI already renders.
export const STATE_LABEL = {
  DISCLOSED: "Evidenced",
  NOT_DISCLOSED: "Not disclosed",
  NOT_DISCLOSED_EXPLAINED: "Departs, explained",
  NOT_APPLICABLE: "Not required",
  EVIDENCE_GAP: "Not retrieved"
};

export const BAND_LABEL = {
  LEADING: "Leading",
  ESTABLISHED: "Established",
  DEVELOPING: "Developing",
  MINIMAL: "Minimal",
  NOT_EVIDENCED: "Not evidenced",
  INSUFFICIENT_EVIDENCE: "Not rated",
  DEPARTS_EXPLAINED: "Departs, explained"
};

// Source log outcome to the four states the retrieval screen draws.
export const OUTCOME = {
  RETRIEVED: "retrieved",
  NOT_FOUND: "notfound",
  BLOCKED: "notfound",
  UNREADABLE: "unreadable",
  PENDING: "retrieved"
};

export function retrievalRows(sourceLog) {
  return (sourceLog || []).map(d => ({
    name: d.title,
    loc: d.location,
    url: d.url,
    status: d.extractionMethod === "ocr" ? "scan" : (OUTCOME[d.outcome] || "notfound"),
    ms: d.elapsedMs || 0,
    mode: d.provenance === "PROVIDED_ON_REQUEST" ? "provided on request" : "live fetch",
    grade: d.sourceGrade,
    note: d.note
  }));
}

function wait(ms) {
  return new Promise(r => setTimeout(r, ms));
}
