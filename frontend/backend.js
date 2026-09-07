// Talks to the governance backend. The only file in the frontend that knows a
// backend exists. Everything else consumes the same shape it always did.
//
// Point API_BASE at the FastAPI service. Set it to null and the page falls back
// to the built-in demo data, which is what makes this safe to ship before the
// backend is reliable.

export const API_BASE = window.PROVISION_API_BASE ?? "http://localhost:8080";

export const backendEnabled = () => Boolean(API_BASE);

async function json(url, opts) {
  const res = await fetch(url, opts);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = JSON.stringify(await res.json()); } catch (e) {}
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json();
}

export async function health() {
  return json(`${API_BASE}/api/health`);
}

export async function searchCompanies(query) {
  const data = await json(`${API_BASE}/api/companies?q=${encodeURIComponent(query)}`);
  return data.matches || [];
}

// Starts a run and polls until it completes. onProgress receives the running
// payload each poll, which is what drives the retrieval screen.
export async function runAssessment(asxCode, onProgress) {
  const start = await json(`${API_BASE}/api/assessments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ asxCode, pillar: "GOVERNANCE" })
  });

  const runId = start.runId;
  const deadline = Date.now() + 10 * 60 * 1000;

  while (Date.now() < deadline) {
    await wait(start.pollAfterMs || 1500);
    const payload = await json(`${API_BASE}/api/assessments/${runId}`);
    if (payload.status === "COMPLETE") return payload;
    if (payload.status === "FAILED") throw new Error("Run failed on the backend");
    if (onProgress) onProgress(payload);
  }
  throw new Error("Run did not complete within ten minutes");
}

export async function evidenceFor(runId, criterionCode) {
  return json(`${API_BASE}/api/assessments/${runId}/criteria/${criterionCode}/evidence`);
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
    mode: "live fetch",
    grade: d.sourceGrade,
    note: d.note
  }));
}

function wait(ms) {
  return new Promise(r => setTimeout(r, ms));
}
