import type { BlocklistRow, ChallengeStats, Campaign, CheckResult, FeedbackRow, PartnerInfo, PartnerSummary, ReportRow, ResultsPayload, Stats } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  } catch {
    throw new ApiError(0, "Serverə qoşulmaq mümkün olmadı.");
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : "";
    } catch {}
    throw new ApiError(res.status, detail || `Server xətası (${res.status}).`);
  }
  return res.json() as Promise<T>;
}

export const checkMessage = (text: string, imageBase64: string | null) =>
  request<CheckResult>("/check", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: text.trim() || null, image_base64: imageBase64 }),
  });

export const getStats = () => request<Stats>("/stats");
export const getCampaigns = (brand?: string) =>
  request<Campaign[]>(`/campaigns?limit=50${brand ? `&brand=${encodeURIComponent(brand)}` : ""}`);
export const getRecent = (limit = 20) => request<ReportRow[]>(`/reports/recent?limit=${limit}`);
export const getResults = () => request<ResultsPayload>("/results");
export const getBlocklist = (brand?: string) =>
  request<BlocklistRow[]>(`/blocklist?limit=200${brand ? `&brand=${encodeURIComponent(brand)}` : ""}`);
export const blocklistCsvUrl = (brand?: string) =>
  `${API_URL}/blocklist?format=csv${brand ? `&brand=${encodeURIComponent(brand)}` : ""}`;
export const sendChallenge = (text: string) =>
  request<CheckResult>("/challenge", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
export const getChallengeStats = () => request<ChallengeStats>("/challenge/stats");
export const getFeedback = () => request<FeedbackRow[]>("/feedback/recent?limit=10");
export const sendFeedback = (reportId: number, agrees: boolean, suggested?: "scam" | "safe") =>
  request<{ ok: boolean }>("/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ report_id: reportId, agrees, suggested: agrees ? null : suggested }),
  });

/** Friendly Azerbaijani text for an error from checkMessage. */
export function checkErrorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 0) return "Serverə qoşulmaq mümkün olmadı. İnternetinizi yoxlayın və bir az sonra yenidən cəhd edin.";
    if (e.status === 413) return "Şəkil çox böyükdür (5 MB-dan az olmalıdır).";
    if (e.status === 422) return "Mətn yazın və ya şəkil əlavə edin.";
    if (e.status === 400) return "Şəkil oxuna bilmədi. Başqa şəkil yoxlayın.";
  }
  return "Yoxlama zamanı xəta baş verdi. Bir az sonra yenidən cəhd edin.";
}

// ---- partner API (needs the company's X-API-Key)
const withKey = (key: string): RequestInit => ({ headers: { "X-API-Key": key } });
export const partnerMe = (key: string) => request<PartnerInfo>("/partner/me", withKey(key));
export const partnerSummary = (key: string) => request<PartnerSummary>("/partner/summary", withKey(key));
export const partnerCampaigns = (key: string) => request<Campaign[]>("/partner/campaigns?limit=50", withKey(key));
export const partnerBlocklist = (key: string) => request<BlocklistRow[]>("/partner/blocklist", withKey(key));

/** The CSV needs the key header, so it is fetched and saved from the page instead of being a plain link. */
export async function downloadPartnerCsv(key: string): Promise<void> {
  const res = await fetch(`${API_URL}/partner/blocklist?format=csv`, withKey(key));
  if (!res.ok) throw new ApiError(res.status, "CSV yüklənmədi");
  const url = URL.createObjectURL(await res.blob());
  const a = Object.assign(document.createElement("a"), { href: url, download: "unhook-blocklist.csv" });
  a.click();
  URL.revokeObjectURL(url);
}
