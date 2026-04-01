/* eslint-disable @next/next/no-img-element */
"use client";

import { useState } from "react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function UploadPage() {
  const [files, setFiles] = useState<FileList | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdJobIds, setCreatedJobIds] = useState<string[]>([]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setCreatedJobIds([]);
    if (!files || files.length === 0) {
      setError("Please select at least one file.");
      return;
    }

    const form = new FormData();
    Array.from(files).forEach((f) => form.append("files", f));

    setIsUploading(true);
    try {
      const res = await fetch(`${API_URL}/api/upload`, {
        method: "POST",
        body: form
      });
      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail ?? `Upload failed with status ${res.status}`);
      }
      const data = await res.json();
      const ids: string[] = (data.jobs ?? []).map((j: any) => j.job.id ?? j.job?.id ?? j.id);
      setCreatedJobIds(ids);
    } catch (err: any) {
      setError(err.message ?? "Upload failed.");
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <main>
      <nav style={{ display: "flex", gap: "0.75rem", marginBottom: "1.25rem" }}>
        <Link href="/">Home</Link>
        <Link href="/jobs">Jobs dashboard</Link>
      </nav>

      <h2>Upload Documents</h2>
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <input
          type="file"
          multiple
          onChange={(e) => setFiles(e.target.files)}
          style={{ maxWidth: 400 }}
        />
        <button type="submit" disabled={isUploading}>
          {isUploading ? "Uploading..." : "Upload & Start Processing"}
        </button>
      </form>

      {error && <p style={{ color: "red", marginTop: "1rem" }}>{error}</p>}

      {createdJobIds.length > 0 && (
        <section style={{ marginTop: "1.5rem" }}>
          <h3>Created Jobs</h3>
          <ul>
            {createdJobIds.map((id) => (
              <li key={id}>
                Job <code>{id}</code> -{" "}
                <Link href={`/jobs/${id}`}>View detail</Link>
              </li>
            ))}
          </ul>
          <p style={{ marginTop: "0.5rem" }}>
            Or go to the{" "}
            <Link href="/jobs">
              jobs dashboard
            </Link>
            .
          </p>
        </section>
      )}
    </main>
  );
}

