import { useEffect, useRef } from "react";

import { Panel } from "@/components/ui/Panel";

interface TerminalOutputProps {
  lines: string[];
  running: boolean;
}

function colorize(line: string): string {
  if (line.includes("✅") || line.includes("✓")) return "text-positive";
  if (line.includes("❌") || line.includes("Error") || line.includes("error"))
    return "text-negative";
  if (line.includes("⚠️") || line.includes("Warning")) return "text-warning";
  return "text-muted-foreground";
}

export default function TerminalOutput({ lines, running }: TerminalOutputProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <Panel title="Output" className="min-w-0 bg-background">
      {/* Monospace belongs to the log body only: these are command lines. */}
      <div
        className="min-w-0 p-3 max-h-[32vh] overflow-y-auto space-y-0.5 font-mono text-xs"
        role="log"
        aria-live="polite"
        aria-label="Process output"
      >
        {lines.map((line, i) => (
          <div
            // append-only log buffer; index is a stable identity
            key={i}
            className={`leading-5 whitespace-pre-wrap break-words [overflow-wrap:anywhere] ${colorize(line)}`}
          >
            {line}
          </div>
        ))}
        {running ? (
          <div className="text-muted-foreground mt-1" aria-label="Running">
            Running…
          </div>
        ) : (
          lines.length > 0 && <div className="text-muted-foreground mt-1">Done</div>
        )}
        <div ref={bottomRef} />
      </div>
    </Panel>
  );
}
