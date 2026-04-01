"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type JobStatus = "queued" | "processing" | "completed" | "failed";

interface JobDetail {
  id: string;
  document_id: string;
  status: JobStatus;
  stage?: string | null;
  progress_percent: number;
  attempt: number;
  error_message?: string | null;
  extracted_json?: any;
  reviewed_json?: any;
  final_json?: any;
  document?: {
    id: string;
    original_filename: string;
    mime_type?: string | null;
    size_bytes: number;
  } | null;
}

interface ProgressEvent {
  type: string;
  job_id: string;
  stage?: string | null;
  progress_percent?: number | null;
  timestamp_utc: string;
  payload?: any;
}

function pretty(obj: any) {
  try {
    return JSON.stringify(obj, null, 2);
  } catch {
    return String(obj ?? "");
  }
}

export default function JobDetailPage({ params }: { params: { jobId: string } }) {
  const { jobId } = params;

  const [job, setJob] = useState<JobDetail | null>(null);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const [reviewJsonDraft, setReviewJsonDraft] = useState("");
  const [isSavingReview, setIsSavingReview] = useState(false);
  const [isFinalizing, setIsFinalizing] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [expandedJson, setExpandedJson] = useState(false);
  const [showExtracted, setShowExtracted] = useState(false);
  const [showReviewed, setShowReviewed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isTerminal = job?.status === "completed" || job?.status === "failed";

  async function loadJob() {
    try {
      const res = await fetch(`${API_URL}/api/jobs/${jobId}`);
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail ?? `Failed to load job (${res.status})`);
      }
      const data = await res.json();
      setJob(data);
      if (!reviewJsonDraft && (data.reviewed_json || data.extracted_json)) {
        setReviewJsonDraft(pretty(data.reviewed_json ?? data.extracted_json));
      }
    } catch (err: any) {
      setError(err.message ?? "Failed to load job.");
    }
  }

  useEffect(() => {
    loadJob();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  useEffect(() => {
    const es = new EventSource(`${API_URL}/api/jobs/${jobId}/events`);
    es.onmessage = (ev) => {
      try {
        const data: ProgressEvent = JSON.parse(ev.data);
        setEvents((prev) => [...prev, data]);
        setJob((prev) =>
          prev
            ? {
                ...prev,
                stage: data.stage ?? prev.stage,
                progress_percent: data.progress_percent ?? prev.progress_percent,
                status:
                  data.type === "job_failed"
                    ? "failed"
                    : data.type === "job_completed"
                    ? "completed"
                    : prev.status
              }
            : prev
        );
      } catch {
        // ignore
      }
    };
    es.onerror = () => {
      es.close();
    };
    return () => {
      es.close();
    };
  }, [jobId]);

  async function handleRetry() {
    setIsRetrying(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/jobs/${jobId}/retry`, { method: "POST" });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail ?? `Retry failed (${res.status})`);
      }
      const data = await res.json();
      setJob(data);
      setEvents([]);
      setReviewJsonDraft("");
    } catch (err: any) {
      setError(err.message ?? "Retry failed.");
    } finally {
      setIsRetrying(false);
    }
  }

  async function handleSaveReview() {
    if (!reviewJsonDraft.trim()) return;
    setIsSavingReview(true);
    setError(null);
    try {
      let parsed: any;
      try {
        parsed = JSON.parse(reviewJsonDraft);
      } catch {
        throw new Error("Reviewed JSON is not valid JSON.");
      }
      const res = await fetch(`${API_URL}/api/jobs/${jobId}/reviewed`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reviewed_json: parsed })
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail ?? `Failed to save review (${res.status})`);
      }
      const data = await res.json();
      setJob(data);
    } catch (err: any) {
      setError(err.message ?? "Failed to save review.");
    } finally {
      setIsSavingReview(false);
    }
  }

  async function handleFinalize() {
    setIsFinalizing(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/jobs/${jobId}/finalize`, {
        method: "POST"
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail ?? `Finalize failed (${res.status})`);
      }
      const data = await res.json();
      setJob(data);
    } catch (err: any) {
      setError(err.message ?? "Finalize failed.");
    } finally {
      setIsFinalizing(false);
    }
  }

  const exportJsonUrl = useMemo(() => `${API_URL}/api/jobs/${jobId}/export?format=json`, [jobId]);
  const exportCsvUrl = useMemo(() => `${API_URL}/api/jobs/${jobId}/export?format=csv`, [jobId]);

  return (
    <main>
      <nav style={{ display: "flex", gap: "0.75rem", marginBottom: "1.25rem" }}>
        <Link href="/">Home</Link>
        <Link href="/upload">Upload</Link>
        <Link href="/jobs">Jobs dashboard</Link>
      </nav>

      <h2>Job Detail</h2>
      {error && <p style={{ color: "red" }}>{error}</p>}

      {!job && <p>Loading job...</p>}
      {job && (
        <>
          <section style={{ marginBottom: "1rem" }}>
            <h3>Overview</h3>
            <p>
              <strong>Job ID:</strong> <code>{job.id}</code>
            </p>
            <p>
              <strong>Status:</strong> {job.status} {job.error_message && <>({job.error_message})</>}
            </p>
            <p>
              <strong>Stage:</strong> {job.stage}
            </p>
            <p>
              <strong>Progress:</strong> {job.progress_percent}%
            </p>
            {job.document && (
              <p>
                <strong>Document:</strong> {job.document.original_filename} ({job.document.mime_type ?? "unknown"},{" "}
                {job.document.size_bytes} bytes)
              </p>
            )}
            <div style={{ display: "flex", gap: "0.75rem", marginTop: "0.5rem", flexWrap: "wrap" }}>
              {job.status === "failed" && (
                <button type="button" onClick={handleRetry} disabled={isRetrying}>
                  {isRetrying ? "Retrying..." : "Retry"}
                </button>
              )}
              <button type="button" onClick={loadJob}>
                Refresh
              </button>
              {job.status === "completed" && (
                <>
                  <button type="button" onClick={handleFinalize} disabled={isFinalizing}>
                    {isFinalizing ? "Finalizing..." : "Finalize"}
                  </button>
                  {job.final_json && (
                    <>
                      <a href={exportJsonUrl} target="_blank" rel="noreferrer">
                        Export JSON
                      </a>
                      <a href={exportCsvUrl} target="_blank" rel="noreferrer">
                        Export CSV
                      </a>
                    </>
                  )}
                </>
              )}
            </div>
          </section>

          <section style={{ marginBottom: "1.25rem" }}>
            <h3>Live Progress Events</h3>
            <div
              style={{
                maxHeight: 220,
                overflowY: "auto",
                background: "#fff",
                border: "1px solid #eee",
                padding: "0.5rem",
                fontFamily: "monospace",
                fontSize: "0.8rem"
              }}
            >
              {events.map((e, idx) => (
                <div key={idx} style={{ marginBottom: 4 }}>
                  <strong>{e.type}</strong> [{new Date(e.timestamp_utc).toLocaleTimeString()}]{" "}
                  {e.stage && <span>stage={e.stage} </span>}
                  {typeof e.progress_percent === "number" && <span>progress={e.progress_percent}%</span>}
                </div>
              ))}
              {events.length === 0 && <div>No live events yet. They will appear here as the worker runs.</div>}
            </div>
          </section>

          <section style={{ display: "grid", gridTemplateColumns: "1fr", gap: "0.8rem" }}>
            <div>
              <button
                type="button"
                onClick={() => setShowExtracted((v) => !v)}
                style={{ marginBottom: "0.35rem" }}
              >
                {showExtracted ? "Hide" : "Show"} Extracted Output (read-only)
              </button>
              {showExtracted && (
                <pre
                  style={{
                    background: "#fff",
                    border: "1px solid #eee",
                    padding: "0.5rem",
                    fontSize: "0.8rem",
                    maxHeight: expandedJson ? 420 : 180,
                    overflow: "auto"
                  }}
                >
                  {job.extracted_json ? pretty(job.extracted_json) : "Waiting for extraction..."}
                </pre>
              )}
            </div>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <button type="button" onClick={() => setShowReviewed((v) => !v)}>
                  {showReviewed ? "Hide" : "Show"} Reviewed Output (editable)
                </button>
                <button type="button" onClick={() => setExpandedJson((v) => !v)}>
                  {expandedJson ? "Compact View" : "Expand View"}
                </button>
              </div>
              {showReviewed && (
                <>
                  <textarea
                    value={reviewJsonDraft}
                    onChange={(e) => setReviewJsonDraft(e.target.value)}
                    rows={expandedJson ? 16 : 8}
                    style={{ width: "100%", fontFamily: "monospace", fontSize: "0.8rem" }}
                    placeholder='Paste or edit JSON here, e.g. {"title": "..."}'
                  />
                  <div style={{ marginTop: "0.5rem" }}>
                    <button type="button" onClick={handleSaveReview} disabled={isSavingReview || !job.extracted_json}>
                      {isSavingReview ? "Saving..." : "Save Reviewed JSON"}
                    </button>
                  </div>
                </>
              )}
            </div>
          </section>
        </>
      )}
    </main>
  );
}

