"use client";

/**
 * Renders Mermaid source in the browser.
 *
 * Client-side on purpose: rendering server-side would mean a headless browser
 * in the backend, and the same source text is what gets committed to the
 * generated repository, where GitHub renders it natively. One representation,
 * three places it works.
 */

import { AlertTriangle, Loader2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

let initialised = false;

export function Mermaid({ source, id }: { source: string; id: string }) {
  const container = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      const mermaid = (await import("mermaid")).default;
      if (!initialised) {
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          fontFamily: "var(--font-sans), system-ui, sans-serif",
          theme: window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "default",
        });
        initialised = true;
      }
      try {
        const { svg } = await mermaid.render(`m-${id}`, source);
        if (!cancelled && container.current) {
          container.current.innerHTML = svg;
          setError(null);
          setReady(true);
        }
      } catch (caught) {
        if (!cancelled) {
          setError(caught instanceof Error ? caught.message : String(caught));
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [source, id]);

  if (error) {
    return (
      <div className="rounded-lg border border-failed/25 bg-failed-soft p-4 text-sm">
        <p className="flex items-center gap-2 font-medium text-failed">
          <AlertTriangle className="size-4" strokeWidth={2.25} />
          This diagram did not render
        </p>
        <pre className="mt-2 overflow-x-auto rounded-md bg-surface/60 p-2.5 text-xs whitespace-pre-wrap text-failed">
          {error}
        </pre>
        <details className="mt-2">
          <summary className="cursor-pointer text-xs text-muted">Show the source</summary>
          <pre className="mt-2 overflow-x-auto rounded-md bg-surface/60 p-2.5 text-xs">{source}</pre>
        </details>
      </div>
    );
  }

  return (
    <div className="relative overflow-x-auto rounded-lg border border-border bg-surface-2/60 p-4">
      {!ready ? (
        <div className="flex h-32 items-center justify-center text-muted-2">
          <Loader2 className="size-5 animate-spin" strokeWidth={2} />
        </div>
      ) : null}
      <div
        ref={container}
        className={`[&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full ${ready ? "" : "hidden"}`}
      />
    </div>
  );
}
