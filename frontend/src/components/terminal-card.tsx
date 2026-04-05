"use client"

import { useEffect, useState } from "react"

export function TerminalCard({ logLines = [] }: { logLines?: string[] }) {
  const [lines, setLines] = useState<string[]>([])
  
  // Use passed in logs or fallback to a dummy feed
  const DEFAULT_LOGS = [
    "> Initializing AI pipeline...",
    "> Loading model weights: 2.4GB",
    "> Connecting to data stream...",
    "> Analyzing codebase...",
    "> Running inference: batch_01",
    "> Optimization pass: 1/3",
    "> Optimization pass: 2/3",
    "> Optimization pass: 3/3",
    "> 98% Optimized",
    "> Deploying to edge nodes...",
    "> Status: OPERATIONAL",
    "> Latency: 12ms p99",
    "> Throughput: 14.2k req/s",
    "> Memory: 847MB / 2048MB",
    "> --------- CYCLE COMPLETE ---------",
  ];

  const streamData = logLines && logLines.length > 0 ? logLines : DEFAULT_LOGS;

  useEffect(() => {
    // If we're provided external loglines, just show them exactly as they are.
    if (logLines && logLines.length > 0) {
      setLines(logLines.slice(-8));
      return;
    }
    
    // Fallback animation logic
    let index = 0;
    const interval = setInterval(() => {
        setLines(prev => {
            const next = Array.from(prev);
            next.push(DEFAULT_LOGS[index]);
            if (next.length > 8) next.shift();
            return next;
        });
        index = (index + 1) % DEFAULT_LOGS.length;
    }, 600);
    return () => clearInterval(interval)
  }, [logLines])

  return (
    <div className="flex flex-col h-full border border-border">
      <div className="flex items-center gap-2 border-b border-border bg-card px-4 py-2">
        <span className="h-2 w-2 bg-[--color-accent]" />
        <span className="h-2 w-2 bg-foreground" />
        <span className="h-2 w-2 border border-foreground" />
        <span className="ml-auto text-[10px] tracking-widest text-muted-foreground uppercase">
          terminal.sys
        </span>
      </div>
      <div className="flex-1 bg-foreground p-4 overflow-hidden relative">
        <div className="flex flex-col gap-1">
          {lines.map((line, i) => (
            <span
              key={`${line}-${i}`}
              className="text-xs text-background font-mono block"
              style={{ opacity: i === lines.length - 1 ? 1 : 0.6 }}
            >
              {line}
            </span>
          ))}
          <span className="text-xs text-[--color-accent] font-mono animate-blink">{"_"}</span>
        </div>
      </div>
    </div>
  )
}
