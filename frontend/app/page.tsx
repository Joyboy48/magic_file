import Link from "next/link";

export default function HomePage() {
  return (
    <main>
      <nav style={{ display: "flex", gap: "0.75rem", marginBottom: "1.25rem" }}>
        <Link href="/upload">Upload</Link>
        <Link href="/jobs">Jobs dashboard</Link>
      </nav>
      <section>
        <p>Use the navigation above to upload documents and view processing jobs.</p>
      </section>
    </main>
  );
}

