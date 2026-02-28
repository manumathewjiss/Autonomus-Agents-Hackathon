import React, { useState } from "react";
import "./release-notes.css";

const SUGGESTIONS = [
  "Show latest production releases only",
  "Summarize critical CVEs from last 7 days",
  "Generate executive-friendly monthly release digest"
];

const STATUS_COLORS = {
  answer: "status-answer",
  abstain: "status-abstain",
  error: "status-error"
};

export function ReleaseNotesApp() {
  const [darkMode, setDarkMode] = useState(true);

  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [answer, setAnswer] = useState("");
  const [status, setStatus] = useState("idle"); // "idle" | "answer" | "abstain" | "error"
  const [meta, setMeta] = useState({ vendor: "", version: "", source: "" });
  const [traceJson, setTraceJson] = useState("");
  const [debugOpen, setDebugOpen] = useState(false);

  const handleSuggestionClick = (text) => {
    setQuery(text);
  };

  const handleAsk = async () => {
    const trimmed = query.trim();
    if (!trimmed || loading) return;

    setLoading(true);
    setError("");
    setStatus("idle");

    const apiBase = import.meta.env.VITE_API_URL || "";
    try {
      const answerRes = await fetch(`${apiBase}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: trimmed })
      });

      if (answerRes.ok) {
        const data = await answerRes.json();

        setAnswer(data.answer ?? "");
        setStatus(
          data.status === "abstain"
            ? "abstain"
            : data.status === "error"
            ? "error"
            : "answer"
        );
        if (data.status === "error") {
          setError(data.answer ?? "Backend returned an error.");
        } else {
          setError("");
        }
        setMeta({
          vendor: data.vendor ?? "Unknown vendor",
          version: data.version ?? data.verified_version ?? "N/A",
          source: data.source ?? "Release Hub"
        });
        // Fetch trace by query_id from answer response
        const queryId = data.query_id;
        if (queryId) {
          const traceRes = await fetch(`${apiBase}/trace/${queryId}`);
          if (traceRes.ok) {
            const traceData = await traceRes.json();
            setTraceJson(JSON.stringify(traceData, null, 2));
          } else {
            setTraceJson("");
          }
        } else {
          setTraceJson("");
        }
      } else {
        setStatus("error");
        setAnswer("");
        setMeta({ vendor: "", version: "", source: "" });
        setError("Failed to fetch answer from /answer. Check backend.");
        setTraceJson("");
      }
    } catch (e) {
      setStatus("error");
      setError("Unexpected error contacting backend.");
      setAnswer("");
      setMeta({ vendor: "", version: "", source: "" });
    } finally {
      setLoading(false);
      setDebugOpen(true);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  };

  const statusClass = STATUS_COLORS[status] ?? "";
  const statusLabel =
    status === "answer"
      ? "Answered"
      : status === "abstain"
      ? "Abstained (no safe answer)"
      : status === "error"
      ? "Error"
      : "Idle";

  return (
    <div
      className={`rn-root rn-root-hero ${
        darkMode ? "rn-theme-dark" : "rn-theme-light"
      }`}
    >
      <div className="rn-hero-overlay" />

      <header className="rn-hero-header">
        <div className="rn-hero-title-group">
          <h1 className="rn-hero-title rn-hero-title-agent">
            <span className="rn-hero-gradient">ReleaseHub</span>
            <span className="rn-agent-badge">Agent</span>
          </h1>
        </div>

        <div className="rn-hero-header-actions">
          <div className="rn-hero-header-actions-right">
            <div className="rn-toggle-group">
              <button
                className={`rn-pill-btn ${
                  darkMode ? "rn-pill-active" : ""
                }`}
                onClick={() => setDarkMode(true)}
              >
                Dark
              </button>
              <button
                className={`rn-pill-btn ${
                  !darkMode ? "rn-pill-active" : ""
                }`}
                onClick={() => setDarkMode(false)}
              >
                Light
              </button>
            </div>
            <button className="rn-ghost-chip">Settings</button>
          </div>
        </div>
      </header>

      <main className="rn-hero-main">
        <div className="rn-chat-layout">
          <section className="rn-chat-column">
            <div className="rn-chat-card">
              <div className="rn-chat-header">
                <div className="rn-env-pill">Prod · EU-West</div>
                <div className={`rn-status-pill ${statusClass}`}>
                  {statusLabel}
                </div>
              </div>
              <div className="rn-chat-input-wrap">
                <textarea
                  className="rn-chat-textarea"
                  placeholder="Ask about latest versions, CVEs, patches… (vendors only)"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={3}
                />
                <div className="rn-chat-actions">
                  <div className="rn-suggestion-row">
                    {SUGGESTIONS.map((s) => (
                      <button
                        key={s}
                        type="button"
                        className="rn-suggestion-pill"
                        onClick={() => handleSuggestionClick(s)}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                  <button
                    type="button"
                    className="rn-primary-btn"
                    onClick={handleAsk}
                    disabled={loading}
                  >
                    {loading ? "Thinking…" : "Ask"}
                  </button>
                </div>
              </div>
            </div>
            <AnswerCard
              answer={answer}
              meta={meta}
              status={status}
              loading={loading}
              error={error}
            />
          </section>
          <section className="rn-side-column">
            <DebugPanel
              open={debugOpen}
              onToggle={() => setDebugOpen((o) => !o)}
              traceJson={traceJson}
            />
          </section>
        </div>
      </main>
    </div>
  );
}

function AnswerCard({ answer, meta, status, loading, error }) {
  return (
    <div className="rn-answer-card">
      <div className="rn-answer-header">
        <div>
          <div className="rn-answer-title">Answer</div>
          <div className="rn-answer-meta">
            {meta.vendor && <span>{meta.vendor}</span>}
            {meta.version && <span>· v{meta.version}</span>}
            {meta.source && <span>· {meta.source}</span>}
          </div>
        </div>
      </div>

      <div className="rn-answer-body">
        {loading && (
          <div className="rn-skeleton-lines">
            <div />
            <div />
            <div />
          </div>
        )}

        {!loading && error && (
          <div className="rn-answer-error">{error}</div>
        )}

        {!loading && !error && !answer && (
          <p className="rn-answer-placeholder">
            Ask a question to see a structured answer here, including when the
            system chooses to abstain.
          </p>
        )}

        {!loading && !error && answer && (
          <p className="rn-answer-text">{answer}</p>
        )}

        {status === "abstain" && !loading && !error && (
          <p className="rn-abstain-note">
            The system abstained because it could not find enough trustworthy
            data to answer safely.
          </p>
        )}
      </div>
    </div>
  );
}

function DebugPanel({ open, onToggle, traceJson }) {
  return (
    <div className="rn-debug-wrapper">
      <button className="rn-debug-toggle" onClick={onToggle}>
        <span className="rn-debug-chevron">{open ? "▾" : "▸"}</span>
        <span className="rn-debug-title">Debug / trace JSON</span>
        <span className="rn-debug-badge">Safe to share</span>
      </button>
      {open && (
        <div className="rn-debug-body">
          {traceJson ? (
            <pre className="rn-debug-pre">{traceJson}</pre>
          ) : (
            <p className="rn-debug-placeholder">
              Call `/trace` on the backend and return JSON here to see the full
              agent trace.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
