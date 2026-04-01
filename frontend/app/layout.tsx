import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Async Document Processing",
  description: "FastAPI + Celery + Next.js demo"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "1.5rem" }}>
          <header style={{ marginBottom: "1rem" }}>
            <h1 style={{ marginBottom: 4 }}>Async Document Processing</h1>
            <p style={{ margin: 0, color: "#555" }}>
              Upload documents, track background processing, review, finalize, and export.
            </p>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}

