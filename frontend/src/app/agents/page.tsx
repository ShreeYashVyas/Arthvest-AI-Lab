"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  Activity, ArrowUpRight, CheckCircle2, CircleAlert, Clock3, ExternalLink,
  LoaderCircle, ShieldCheck, Sparkles, TrendingUp, WifiOff,
} from "lucide-react";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

type AgentStatus = {
  provider: string;
  provider_key: string;
  configured: boolean;
  model: string;
  agents: { name: string; role: string }[];
  note: string;
};
type Finding = { title: string; explanation: string; evidence_keys: string[] };
type SpecialistReport = {
  summary: string;
  findings: Finding[];
  watch_items: string[];
  data_gaps: string[];
  confidence: "low" | "moderate" | "high";
};
type Brief = {
  headline: string;
  executive_summary: string;
  key_findings: Finding[];
  watch_items: string[];
  limitations: string[];
  confidence: "low" | "moderate" | "high";
};
type MacroEvidence = {
  key: string; status: string; indicator: string; series_id: string; value?: number;
  unit: string; observation_date?: string; retrieved_at?: string; freshness_status?: string;
  source: string; source_url: string; reason?: string;
};
type Quote = {
  key: string; name: string; status: string; last_price: number | null;
  change_percent: number | null; timestamp?: string | null;
};
type ResearchResponse = {
  status: string; generated_at: string; question: string; model: string;
  agents: { name: string; status: string }[];
  brief: Brief;
  specialist_reports: { macro: SpecialistReport; market: SpecialistReport; geopolitical_risk: SpecialistReport; cross_asset: SpecialistReport; scenario: SpecialistReport; sector_transmission: SpecialistReport; contrarian: SpecialistReport; risk_evidence_audit: SpecialistReport; };
  evidence_validation: { allowed_keys: string[]; invalid_reference_count: number };
  evidence: {
    generated_at: string;
    macro_observations: MacroEvidence[];
    market_snapshot: {
      status: string; provider?: string; source_url?: string; data_as_of?: string | null;
      reason?: string; quotes: Quote[];
    };
  };
  disclaimer: string;
};

const suggestedQuestion =
  "Give me a source-grounded macro and Indian market risk brief. Highlight notable readings, possible connections, data gaps, and what to monitor next.";

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-IN", { maximumFractionDigits: 3 }).format(value);
}
function formatDate(value?: string | null): string {
  if (!value) return "Date not supplied";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" });
}

export default function AgentsPage() {
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [question, setQuestion] = useState(suggestedQuestion);
  const [research, setResearch] = useState<ResearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(API_BASE_URL + "/api/agents/status", { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        const payload: unknown = await response.json().catch(() => null);
        if (!response.ok || typeof payload !== "object" || payload === null) {
          throw new Error("The AI agent status endpoint is unavailable.");
        }
        const value = payload as AgentStatus;
        if (typeof value.configured !== "boolean" || typeof value.model !== "string") {
          throw new Error("The AI agent status endpoint returned an unexpected response.");
        }
        setAgentStatus(value);
        setStatusError(null);
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setStatusError(reason instanceof Error ? reason.message : "Unable to check AI agent status.");
      });
    return () => controller.abort();
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setResearch(null);
    try {
      const response = await fetch(API_BASE_URL + "/api/agents/research", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim() }),
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        const detail =
          typeof payload === "object" && payload !== null && "detail" in payload &&
          typeof (payload as { detail?: unknown }).detail === "string"
            ? (payload as { detail: string }).detail
            : "The research agents could not complete this run.";
        throw new Error(detail);
      }
      setResearch(payload as ResearchResponse);
    } catch (reason: unknown) {
      setError(reason instanceof Error ? reason.message : "The research agents could not complete this run.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen px-4 pb-12 pt-5 sm:px-7 lg:px-10">
      <div className="mx-auto max-w-[1200px]">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-line pb-5">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl border border-accent/30 bg-accent/10 text-accent">
              <Sparkles size={21} strokeWidth={1.8} />
            </div>
            <div>
              <div className="text-lg font-semibold tracking-[0.18em] text-white">ARTHVEST</div>
              <div className="mt-0.5 text-[10px] uppercase tracking-[0.24em] text-muted">AI research council</div>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <Link href="/" className="rounded-lg border border-line px-3 py-2 text-muted transition hover:border-accent/40 hover:text-white">Dashboard</Link>
            <Link href="/markets" className="rounded-lg border border-line px-3 py-2 text-muted transition hover:border-accent/40 hover:text-white">Market Pulse</Link>
          </div>
        </header>

        <section className="grid gap-8 py-9 lg:grid-cols-[1.15fr_0.85fr] lg:items-end lg:py-12">
          <div>
            <div className="mb-4 flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.2em] text-accent">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" />
              Nine-agent council. One evidence-led brief.
            </div>
            <h1 className="max-w-3xl text-4xl font-semibold leading-[1.08] tracking-tight text-white sm:text-5xl">
              Research with a <span className="text-accent">second opinion.</span>
            </h1>
            <p className="mt-5 max-w-2xl text-sm leading-7 text-muted">
              Seven specialists review macro data, Indian market snapshots, geopolitical transmission channels, cross-asset context,
              conditional scenarios, Indian sector transmission mechanisms, and alternative interpretations. A Risk &amp; Evidence
              Auditor challenges weak claims before the Lead Research Analyst synthesizes the brief. Missing data stays missing—no fabricated quotes or automatic trading.
            </p>
          </div>
          <div className="rounded-2xl border border-line bg-panel p-5">
            <div className="mb-4 flex items-center gap-2 text-[11px] uppercase tracking-[0.18em] text-muted">
              <ShieldCheck size={14} className="text-accent" /> Agent runtime
            </div>
            {statusError ? (
              <div className="flex items-start gap-3 text-sm text-amber-200">
                <WifiOff size={17} className="mt-0.5 shrink-0" /><span>{statusError}</span>
              </div>
            ) : !agentStatus ? (
              <div className="flex items-center gap-2 text-sm text-muted"><LoaderCircle size={16} className="animate-spin" /> Checking backend configuration…</div>
            ) : (
              <>
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm text-white">{agentStatus.provider}</span>
                  <span className={agentStatus.configured ? "rounded-full border border-accent/30 px-2.5 py-1 text-[10px] uppercase tracking-wider text-accent" : "rounded-full border border-amber-300/30 px-2.5 py-1 text-[10px] uppercase tracking-wider text-amber-200"}>
                    {agentStatus.configured ? "Configured" : "Setup required"}
                  </span>
                </div>
                <div className="mt-2 text-xs text-muted">Model: {agentStatus.model}</div>
                <p className="mt-3 text-xs leading-5 text-muted">{agentStatus.note}</p>
                <div className="mt-4 space-y-3 border-t border-line pt-4">
                  <p className="text-[11px] leading-5 text-muted">Registered roles, not a live health check. Per-run completion appears below after the council executes.</p>
                  {agentStatus.agents.map((agent) => (
                    <div key={agent.name} className="flex items-start gap-2.5">
                      <div className="mt-0.5 text-accent"><Sparkles size={14} /></div>
                      <div><div className="text-xs font-medium text-white">{agent.name}</div><div className="mt-1 text-[11px] leading-5 text-muted">{agent.role}</div></div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </section>

        <section className="rounded-2xl border border-line bg-panel p-5 sm:p-7">
          <div className="mb-5 flex items-center gap-2 text-xs uppercase tracking-[0.17em] text-muted">
            <Activity size={15} className="text-accent" /> Research request
          </div>
          <form onSubmit={handleSubmit} className="space-y-4">
            <label htmlFor="research-question" className="block text-sm font-medium text-white">What should the council investigate?</label>
            <textarea
              id="research-question" value={question} onChange={(event) => setQuestion(event.target.value)}
              rows={4} maxLength={600} minLength={4} required
              className="w-full resize-y rounded-xl border border-line bg-[#0b1017] px-4 py-3 text-sm leading-6 text-white outline-none transition placeholder:text-muted focus:border-accent/60"
            />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span className="text-[11px] text-muted">{question.length}/600 characters · Nine model runs per brief</span>
              <button type="submit" disabled={loading || !agentStatus?.configured || question.trim().length < 4}
                className="inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[#10140b] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40">
                {loading ? <LoaderCircle size={15} className="animate-spin" /> : <Sparkles size={15} />}
                {loading ? "Agents researching…" : "Run research council"}
                {!loading && <ArrowUpRight size={14} />}
              </button>
            </div>
          </form>
          {!agentStatus?.configured && !statusError && agentStatus && (
            <div className="mt-5 flex items-start gap-3 rounded-xl border border-amber-300/20 bg-amber-200/5 p-4 text-sm text-amber-100">
              <CircleAlert size={17} className="mt-0.5 shrink-0" />
              <div><div className="font-medium">AI provider setup needed</div>{agentStatus.provider_key === "ollama" ? (<p className="mt-1 leading-6 text-amber-100/75">Install <a href="https://ollama.com/download/windows" target="_blank" rel="noreferrer" className="underline">Ollama for Windows</a>, start the Ollama app, then run <code>ollama pull qwen3:4b</code> in PowerShell. Keep ARTHVEST_LLM_PROVIDER=ollama and restart FastAPI.</p>) : (<p className="mt-1 leading-6 text-amber-100/75">To use paid cloud inference, set ARTHVEST_LLM_PROVIDER=openai and add OPENAI_API_KEY to the private backend/.env file. Never place the key in the frontend.</p>)}</div>
            </div>
          )}
          {error && <div role="alert" className="mt-5 rounded-xl border border-red-400/25 bg-red-400/5 p-4 text-sm leading-6 text-red-200">{error}</div>}
        </section>

        {loading && <div className="mt-6 flex items-center gap-3 rounded-2xl border border-line bg-panel p-5 text-sm text-muted"><LoaderCircle size={18} className="animate-spin text-accent" /> Collecting evidence, running seven specialists with local-resource concurrency limits, auditing their reports, and synthesizing the brief…</div>}

        {research && (
          <section className="mt-8 space-y-6">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <div className="mb-2 flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] text-accent"><CheckCircle2 size={13} /> Research run complete</div>
                <h2 className="text-2xl font-semibold tracking-tight text-white">{research.brief.headline}</h2>
                <p className="mt-2 text-xs text-muted">{research.model} · Generated {formatDate(research.generated_at)}</p>
              </div>
              <span className="rounded-full border border-line px-3 py-2 text-[10px] uppercase tracking-wider text-muted">{research.brief.confidence.toUpperCase()} CONFIDENCE</span>
            </div>

            <article className="rounded-2xl border border-line bg-panel p-5 sm:p-6">
              <div className="mb-2 flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-muted"><ShieldCheck size={14} className="text-accent" /> Nine-agent execution status</div>
              <p className="text-xs leading-5 text-muted">Statuses from this research run. Source limitations are distinguished from a fully completed stage.</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {research.agents.map((agent) => {
                  const limited = agent.status !== "completed";
                  return (
                    <div key={agent.name} className="rounded-xl border border-line bg-[#0b1017] p-3">
                      <div className="text-xs font-medium text-white">{agent.name}</div>
                      <div className={limited ? "mt-2 text-[10px] uppercase tracking-wide text-amber-200" : "mt-2 text-[10px] uppercase tracking-wide text-accent"}>
                        {agent.status.replaceAll("_", " ")}
                      </div>
                    </div>
                  );
                })}
              </div>
            </article>

            <div className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
              <article className="rounded-2xl border border-accent/20 bg-panel p-5 sm:p-7">
                <div className="mb-3 flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-accent"><Sparkles size={14} /> Lead analyst brief</div>
                <p className="text-sm leading-7 text-white/90">{research.brief.executive_summary}</p>
                {research.brief.key_findings.length > 0 && <div className="mt-6 space-y-4 border-t border-line pt-5">
                  {research.brief.key_findings.map((finding, index) => <div key={finding.title + "-" + index}>
                    <h3 className="text-sm font-semibold text-white">{finding.title}</h3>
                    <p className="mt-1.5 text-sm leading-6 text-muted">{finding.explanation}</p>
                    {finding.evidence_keys.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{finding.evidence_keys.map((key) => <span key={key} className="rounded-md border border-line px-2 py-1 text-[10px] text-accent">{key}</span>)}</div>}
                  </div>)}
                </div>}
              </article>

              <article className="rounded-2xl border border-line bg-panel p-5 sm:p-6">
                <div className="mb-4 flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-muted"><Clock3 size={14} className="text-accent" /> What to monitor</div>
                {research.brief.watch_items.length > 0 ? <div className="space-y-3">{research.brief.watch_items.map((item, index) => <div key={item + "-" + index} className="flex gap-3 text-sm leading-6 text-white/85"><span className="mt-0.5 text-accent">{String(index + 1).padStart(2, "0")}</span><span>{item}</span></div>)}</div> : <p className="text-sm text-muted">No additional watch items were returned.</p>}
                {research.brief.limitations.length > 0 && <div className="mt-6 border-t border-line pt-4"><div className="mb-2 text-[10px] uppercase tracking-[0.16em] text-muted">Caveats</div><ul className="space-y-2">{research.brief.limitations.map((item, index) => <li key={item + "-" + index} className="text-xs leading-5 text-muted">• {item}</li>)}</ul></div>}
              </article>
            </div>

            {research.evidence_validation.invalid_reference_count > 0 && (
              <div role="status" className="rounded-xl border border-amber-300/25 bg-amber-200/5 p-4 text-sm leading-6 text-amber-100">
                Evidence validation removed {research.evidence_validation.invalid_reference_count} unsupported evidence reference(s).
                Review the affected report caveats before relying on those findings.
              </div>
            )}

            <div className="grid gap-5 lg:grid-cols-2">
              {[
                { title: "Macro Analyst", report: research.specialist_reports.macro, icon: Activity },
                { title: "India Market Analyst", report: research.specialist_reports.market, icon: TrendingUp },
                { title: "Geopolitical Risk Analyst", report: research.specialist_reports.geopolitical_risk, icon: ShieldCheck },
                { title: "Cross-Asset Analyst", report: research.specialist_reports.cross_asset, icon: Activity },
                { title: "Scenario Analyst", report: research.specialist_reports.scenario, icon: Activity },
                { title: "India Sector Transmission Analyst", report: research.specialist_reports.sector_transmission, icon: TrendingUp },
                { title: "Contrarian Analyst", report: research.specialist_reports.contrarian, icon: ShieldCheck },
                { title: "Risk & Evidence Auditor", report: research.specialist_reports.risk_evidence_audit, icon: ShieldCheck },
              ].map(({ title, report, icon: Icon }) => <article key={title} className="rounded-2xl border border-line bg-panel p-5">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.16em] text-muted"><Icon size={15} className="text-accent" /> {title}</div>
                  <span className="rounded-full border border-line px-2 py-1 text-[10px] uppercase tracking-wide text-muted">{report.confidence} confidence</span>
                </div>
                <p className="text-sm leading-6 text-white/85">{report.summary}</p>
                {report.findings.length > 0 && <div className="mt-4 space-y-3 border-t border-line pt-4">{report.findings.map((finding, index) => <div key={finding.title + "-" + index}>
                  <div className="text-xs font-semibold text-white">{finding.title}</div>
                  <p className="mt-1 text-xs leading-5 text-muted">{finding.explanation}</p>
                  {finding.evidence_keys.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{finding.evidence_keys.map((key) => <span key={key} className="rounded-md border border-line px-2 py-1 text-[10px] text-accent">{key}</span>)}</div>}
                </div>)}</div>}
                {report.watch_items.length > 0 && <div className="mt-4 border-t border-line pt-3">
                  <div className="mb-2 text-[10px] uppercase tracking-[0.16em] text-muted">Watch items</div>
                  <ul className="space-y-1.5">{report.watch_items.map((item, index) => <li key={item + "-" + index} className="text-xs leading-5 text-white/80">• {item}</li>)}</ul>
                </div>}
                {report.data_gaps.length > 0 && <div className="mt-4 border-t border-line pt-3 text-xs leading-5 text-amber-100/80">Data gaps: {report.data_gaps.join(" · ")}</div>}
              </article>)}
            </div>

            <article className="rounded-2xl border border-line bg-panel p-5 sm:p-6">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div><h3 className="text-sm font-semibold text-white">Evidence used in this run</h3><p className="mt-1 text-xs text-muted">Source observations are shown separately from AI interpretation.</p></div>
                <span className="text-[10px] uppercase tracking-wider text-muted">{research.evidence.macro_observations.filter((item) => item.status === "available").length}/{research.evidence.macro_observations.length} macro feeds</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-left text-xs">
                  <thead className="border-b border-line text-[10px] uppercase tracking-wider text-muted"><tr><th className="pb-3 pr-4 font-medium">Indicator</th><th className="pb-3 pr-4 font-medium">Latest value</th><th className="pb-3 pr-4 font-medium">Observation date</th><th className="pb-3 pr-4 font-medium">Freshness</th><th className="pb-3 font-medium">Source</th></tr></thead>
                  <tbody>{research.evidence.macro_observations.map((item) => <tr key={item.key} className="border-b border-line/70 last:border-0">
                    <td className="py-3 pr-4"><div className="font-medium text-white">{item.indicator}</div><div className="mt-1 text-[10px] text-muted">{item.key}</div></td>
                    <td className="py-3 pr-4 text-white">{item.status === "available" ? formatNumber(item.value) + " " + item.unit : "Unavailable"}</td>
                    <td className="py-3 pr-4 text-muted">{formatDate(item.observation_date)}</td>
                    <td className="py-3 pr-4"><span className={item.freshness_status === "fresh" ? "text-accent" : "text-amber-200"}>{item.freshness_status || item.status}</span></td>
                    <td className="py-3"><a href={item.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-accent hover:underline">{item.source} <ExternalLink size={11} /></a></td>
                  </tr>)}</tbody>
                </table>
              </div>
              <div className="mt-5 border-t border-line pt-5">
                <div className="mb-3 text-[10px] uppercase tracking-[0.16em] text-muted">Upstox market snapshot</div>
                {research.evidence.market_snapshot.status === "available" ? <div className="grid gap-3 sm:grid-cols-3">{research.evidence.market_snapshot.quotes.map((quote) => <div key={quote.key} className="rounded-xl border border-line bg-[#0b1017] p-4">
                  <div className="text-xs text-muted">{quote.name}</div><div className="mt-2 text-lg font-semibold text-white">{formatNumber(quote.last_price)}</div>
                  <div className={quote.change_percent !== null && quote.change_percent > 0 ? "mt-1 text-xs text-accent" : "mt-1 text-xs text-muted"}>{quote.change_percent === null ? "Change unavailable" : (quote.change_percent > 0 ? "+" : "") + formatNumber(quote.change_percent) + "%"}</div>
                  {quote.timestamp && <div className="mt-2 text-[10px] text-muted">{formatDate(quote.timestamp)}</div>}
                </div>)}</div> : <div className="flex items-start gap-2 text-sm leading-6 text-amber-100/80"><CircleAlert size={15} className="mt-1 shrink-0" /><span>{research.evidence.market_snapshot.reason || "No usable Upstox index quotes were available during this run."} <Link href="/markets" className="text-accent hover:underline">Check Market Pulse</Link></span></div>}
                {research.evidence.market_snapshot.source_url && <a href={research.evidence.market_snapshot.source_url} target="_blank" rel="noreferrer" className="mt-3 inline-flex items-center gap-1 text-xs text-accent hover:underline">Upstox source <ExternalLink size={11} /></a>}
              </div>
              <p className="mt-5 border-t border-line pt-4 text-[11px] leading-5 text-muted">{research.disclaimer}</p>
            </article>
          </section>
        )}
      </div>
    </main>
  );
}
