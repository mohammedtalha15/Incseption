"use client"

import { useEffect, useState } from "react"

interface ScrambleNumberProps {
  target: string
  label: string
  delay?: number
}

function ScrambleNumber({ target, label, delay = 0 }: ScrambleNumberProps) {
  const [display, setDisplay] = useState(target.replace(/[0-9]/g, "0"))
  const [scrambling, setScrambling] = useState(false)

  useEffect(() => {
    const timeout = setTimeout(() => {
      setScrambling(true)
      let iterations = 0
      const maxIterations = 20

      const interval = setInterval(() => {
        if (iterations >= maxIterations) {
          setDisplay(target)
          setScrambling(false)
          clearInterval(interval)
          return
        }

        setDisplay(
          target
            .split("")
            .map((char, i) => {
              if (!/[0-9]/.test(char)) return char
              if (iterations > maxIterations - 5 && i < iterations - (maxIterations - 5)) return char
              return String(Math.floor(Math.random() * 10))
            })
            .join("")
        )
        iterations++
      }, 50)

      return () => clearInterval(interval)
    }, delay)

    return () => clearTimeout(timeout)
  }, [target, delay])

  return (
    <div className="flex flex-col gap-1">
      <span
        className="text-4xl lg:text-5xl font-mono font-bold tracking-tight text-foreground"
        style={{ fontVariantNumeric: "tabular-nums" }}
      >
        {display}
      </span>
      <span className="text-[10px] tracking-[0.2em] uppercase text-muted-foreground">
        {label}
      </span>
    </div>
  )
}

export function MetricsCard({ dynamicTarget1 = "---", dynamicTarget2 = "---", dynamicTarget3 = "---" }: { dynamicTarget1?: string, dynamicTarget2?: string, dynamicTarget3?: string }) {
  return (
    <div className="flex flex-col h-full border border-border bg-card">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <span className="text-[10px] tracking-widest text-muted-foreground uppercase">
          inference.metrics
        </span>
        <span className="inline-block h-2 w-2 bg-[--color-accent]" />
      </div>
      <div className="flex-1 flex flex-col justify-center gap-6 p-6">
        <ScrambleNumber target={dynamicTarget1} label="Current Glucose (mg/dL)" delay={100} />
        <ScrambleNumber target={dynamicTarget2} label="Trend Rate (5min)" delay={300} />
        <ScrambleNumber target={dynamicTarget3} label="Risk Score (0-100)" delay={500} />
        <ScrambleNumber target="99.97%" label="Uptime" delay={1100} />
      </div>
    </div>
  )
}
