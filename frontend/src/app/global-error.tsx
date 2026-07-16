"use client";

import { useEffect } from "react";

type GlobalErrorProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function GlobalError({ error, reset }: GlobalErrorProps) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "system-ui, sans-serif",
          background: "#f4f1ea",
          color: "#15161a",
          padding: "1.5rem",
        }}
      >
        <div style={{ maxWidth: "28rem", textAlign: "center" }}>
          <p style={{ fontSize: "0.75rem", fontWeight: 600, letterSpacing: "0.06em", color: "#6b7280" }}>
            SOMETHING WENT WRONG
          </p>
          <h1 style={{ margin: "0.5rem 0 0", fontSize: "1.5rem" }}>Rob&apos;s Finance could not load</h1>
          <p style={{ marginTop: "0.75rem", fontSize: "0.875rem", color: "#6b7280" }}>
            A critical error stopped the app. Try again, or reload the page.
          </p>
          {error.digest ? (
            <p style={{ marginTop: "0.75rem", fontFamily: "ui-monospace, monospace", fontSize: "0.75rem", color: "#6b7280" }}>
              Ref: {error.digest}
            </p>
          ) : null}
          <button
            type="button"
            onClick={() => reset()}
            style={{
              marginTop: "1.5rem",
              border: "none",
              borderRadius: "0.75rem",
              background: "#059669",
              color: "#fff",
              padding: "0.625rem 1.25rem",
              fontSize: "0.875rem",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      </body>
    </html>
  );
}
