import { useEffect, useRef } from "react";

import { PanelTitle } from "@/components/ui/PanelTitle";

interface TerminalOutputProps {
  lines: string[];
  running: boolean;
}

function colorize(line: string): string {
  if (line.includes("✅") || line.includes("✓")) return "text-positive";
  if (line.includes("❌") || line.includes("Error") || line.includes("error"))
    return "text-negative";
  if (line.includes("⚠️") || line.includes("Warning")) return "text-warning";
  if (line.startsWith("🔍") || line.startsWith("🚀") || line.startsWith("📊"))
    return "text-muted-foreground";
  if (line.includes("Sending request") || line.includes("AI Agent")) return "text-magenta";
  return "text-foreground";
}

export default function TerminalOutput({ lines, running }: TerminalOutputProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <div className="frame bg-background overflow-hidden">
      <div className="frame-title">
        <PanelTitle>Output</PanelTitle>
      </div>
      {/* Monospace belongs to the log body only: these are command lines. */}
      <div
        className="p-3 max-h-[50vh] overflow-y-auto space-y-0.5 font-mono text-xs"
        role="log"
        aria-live="polite"
        aria-label="Process output"
      >
        {lines.map((line, i) => (
          <div
            // append-only log buffer; index is a stable identity
            key={i}
            className={`leading-5 whitespace-pre ${colorize(line)}`}
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
    </div>
  );
}
