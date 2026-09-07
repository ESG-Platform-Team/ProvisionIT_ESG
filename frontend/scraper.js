// Governance scraper: attempts a real cross-origin text fetch, falls back to the
// stored capture when the browser (or the site) refuses. Keyword matching over the
// recovered text is what marks criteria as evidenced.

const READER = "https://r.jina.ai/";

export const KEYWORDS = {
  "G1.1": ["board charter", "roles and responsibilities"],
  "G1.5": ["gender diversity", "measurable objective"],
  "G1.7": ["performance evaluation", "senior executives"],
  "G2.1": ["nomination committee"],
  "G2.4": ["independent director", "independence"],
  "G2.6": ["induction", "professional development"],
  "G3.1": ["values", "code of conduct"],
  "G3.3": ["whistleblower"],
  "G3.4": ["anti-bribery", "corruption"],
  "G4.1": ["audit committee"],
  "G4.3": ["integrity of", "periodic report"],
  "G5.1": ["continuous disclosure"],
  "G5.2": ["market announcement", "asx announcement"],
  "G6.1": ["investor", "governance information"],
  "G6.4": ["poll", "show of hands"],
  "G7.2": ["risk management framework"],
  "G7.4": ["environmental and social risk", "climate"],
  "G8.1": ["remuneration committee"],
  "G8.2": ["remuneration policy", "non-executive director remuneration"]
};

export async function fetchSource(src, { live }) {
  const t0 = performance.now();
  if (!live || !src.url) {
    await wait(src.delay ?? 260);
    return { ...src, ms: Math.round(src.delay ?? 260), mode: "stored capture" };
  }
  try {
    const res = await fetch(READER + src.url, { headers: { Accept: "text/plain" } });
    const text = await res.text();
    const ms = Math.round(performance.now() - t0);
    if (!res.ok || text.length < 400) {
      return { ...src, status: "notfound", http: res.status, ms, mode: "live fetch", text: "" };
    }
    return { ...src, status: "retrieved", http: res.status, ms, bytes: text.length, mode: "live fetch", text };
  } catch (err) {
    const ms = Math.round(performance.now() - t0);
    return { ...src, status: "blocked", ms, mode: "live fetch", note: "blocked by the browser", text: "" };
  }
}

// Which criterion IDs the recovered text actually supports.
export function evidencedFrom(texts) {
  const hay = texts.join("\n").toLowerCase();
  const hits = {};
  for (const [id, terms] of Object.entries(KEYWORDS)) {
    const n = terms.filter(t => hay.includes(t)).length;
    if (n) hits[id] = n / terms.length;
  }
  return hits;
}

export function wait(ms) {
  return new Promise(r => setTimeout(r, ms));
}
