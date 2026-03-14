import { useEffect, useRef } from "react";

interface TerminalOutputProps {
  lines: string[];
  running: boolean;
}

function colorize(line: string): string {
  if (line.includes("✅") || line.includes("✓")) return "text-green-400";
  if (line.includes("❌") || line.includes("Error") || line.includes("error")) return "text-red-400";
  if (line.includes("⚠️") || line.includes("Warning")) return "text-yellow-400";
  if (line.startsWith("🔍") || line.startsWith("🚀") || line.startsWith("📊")) return "text-blue-400";
  if (line.includes("Sending request") || line.includes("AI Agent")) return "text-purple-300";
  return "text-gray-300";
}

export default function TerminalOutput({ lines, running }: TerminalOutputProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <div className="rounded-lg border border-border bg-[#0d0d0d] font-mono text-xs overflow-hidden">
      <div className="flex items-center gap-1.5 px-3 py-2 border-b border-border/50 bg-[#1a1a1a]">
        <span className="h-2.5 w-2.5 rounded-full bg-red-500/80" />
        <span className="h-2.5 w-2.5 rounded-full bg-yellow-500/80" />
        <span className="h-2.5 w-2.5 rounded-full bg-green-500/80" />
        <span className="ml-2 text-[10px] text-gray-500">hedge-fund-tracker — AI Agent</span>
      </div>
      <div className="p-4 max-h-[50vh] overflow-y-auto space-y-0.5">
        {lines.map((line, i) => (
          <div key={i} className={`leading-5 whitespace-pre ${colorize(line)}`}>
            {line}
          </div>
        ))}
        {running && (
          <div className="flex items-center gap-1 text-gray-500 mt-1">
            <span className="inline-block w-2 h-3.5 bg-gray-400 animate-pulse" />
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
