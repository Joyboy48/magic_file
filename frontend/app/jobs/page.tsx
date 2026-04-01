"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type JobStatus = "queued" | "processing" | "completed" | "failed";

interface JobListItem {
  job: {
    id: string;
    status: JobStatus;
    stage?: string | null;
    progress_percent: number;
    attempt: number;
    error_message?: string | null;
    created_at: string;
  };
  filename: string;
  size_bytes: number;
  mime_type?: string | null;
  created_at: string;
}

export default function JobsDashboardPage() {
  const [jobs, setJobs] = useState<JobListItem[]>([]);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<JobStatus | "">("");
  const [sort, setSort] = useState("created_at_desc");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (status) params.set("status", status);
      if (sort) params.set("sort", sort);
      const res = await fetch(`${API_URL}/api/jobs?${params.toString()}`);
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail ?? `Failed to load jobs (${res.status})`);
      }
      const data = await res.json();
      setJobs(data ?? []);
    } catch (err: any) {
      setError(err.message ?? "Failed to load jobs.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    load();
    const id = setInterval(load, 4000);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, status, sort]);

  return (
    <main>
      <nav style={{ display: "flex", gap: "0.75rem", marginBottom: "1.25rem" }}>
        <Link href="/">Home</Link>
        <Link href="/upload">Upload</Link>
      </nav>

      <h2>Jobs Dashboard</h2>

      <section style={{ marginBottom: "1rem", display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        <input
          type="search"
          placeholder="Search filename / text..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select value={status} onChange={(e) => setStatus(e.target.value as any)}>
          <option value="">All statuses</option>
          <option value="queued">Queued</option>
          <option value="processing">Processing</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="created_at_desc">Newest first</option>
          <option value="created_at_asc">Oldest first</option>
          <option value="filename_asc">Filename A-Z</option>
          <option value="filename_desc">Filename Z-A</option>
          <option value="status_asc">Status A-Z</option>
          <option value="status_desc">Status Z-A</option>
          <option value="progress_desc">Progress high-low</option>
          <option value="progress_asc">Progress low-high</option>
        </select>
        <button type="button" onClick={load} disabled={isLoading}>
          Refresh
        </button>
      </section>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <table style={{ width: "100%", background: "white", borderRadius: 4 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid #ddd" }}>
            <th>Filename</th>
            <th>Status</th>
            <th>Stage</th>
            <th>Progress</th>
            <th>Attempt</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((row) => (
            <tr key={row.job.id} style={{ borderBottom: "1px solid #f0f0f0" }}>
              <td>{row.filename}</td>
              <td>{row.job.status}</td>
              <td>{row.job.stage}</td>
              <td>
                <div style={{ width: 100, background: "#eee", borderRadius: 4 }}>
                  <div
                    style={{
                      width: `${row.job.progress_percent}%`,
                      background: row.job.status === "failed" ? "#d33" : "#4caf50",
                      height: 8,
                      borderRadius: 4
                    }}
                  />
                </div>
                <span style={{ fontSize: "0.8rem" }}>{row.job.progress_percent}%</span>
              </td>
              <td>{row.job.attempt}</td>
              <td>{new Date(row.created_at).toLocaleString()}</td>
              <td>
                <Link href={`/jobs/${row.job.id}`}>Open</Link>
              </td>
            </tr>
          ))}
          {jobs.length === 0 && (
            <tr>
              <td colSpan={7} style={{ padding: "0.75rem 0.5rem" }}>
                {isLoading ? "Loading jobs..." : "No jobs yet. Try uploading a document."}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </main>
  );
}

