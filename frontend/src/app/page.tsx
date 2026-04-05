"use client"

import { useEffect, useState } from "react"
import { api, createWebSocketHook } from "@/lib/api"
import { TerminalCard } from "@/components/terminal-card"
import { DitherCard } from "@/components/dither-card"
import { MetricsCard } from "@/components/metrics-card"
import { StatusCard } from "@/components/status-card"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { AlertTriangle, Power } from "lucide-react"

export default function AyuqDashboard() {
  const [patientId, setPatientId] = useState("P001")
  const [historicalData, setHistoricalData] = useState<any[]>([])
  const [currentRisk, setCurrentRisk] = useState<any>(null)
  const [latestExplanation, setLatestExplanation] = useState("")
  const [isSimulating, setIsSimulating] = useState(false)
  const [terminalLogs, setTerminalLogs] = useState<string[]>([
    "> SYSTEM INITIALIZED",
    "> AWAITING DATA STREAM..."
  ])
  
  const [glucose, setGlucose] = useState("---")
  const [trend, setTrend] = useState("---")
  const [riskScore, setRiskScore] = useState("--")

  const usePatientWS = createWebSocketHook(patientId)
  
  usePatientWS((data: any) => {
    // Determine message type
    if (data.type === 'initial_history') {
      setHistoricalData(data.data);
      setTerminalLogs(prev => [...prev, "> Historical baseline loaded."])
    } 
    else if (data.type === 'new_reading') {
      const { reading, risk_assessment } = data.data;
      
      setHistoricalData(prev => [...prev, reading].slice(-100)); // Keep last 100
      
      setGlucose(String(Math.round(reading.glucose_mgdl)));
      setTrend(reading.glucose_trend > 0 ? `+${reading.glucose_trend.toFixed(1)}` : reading.glucose_trend.toFixed(1));
      setRiskScore(String(Math.round(risk_assessment.risk_score)));
      setCurrentRisk(risk_assessment);

      let logMsg = `> INPUT: Glucose ${Math.round(reading.glucose_mgdl)} mg/dL | Risk Pipeline Output: ${Math.round(risk_assessment.risk_score)} (${risk_assessment.risk_level})`;
      
      if (risk_assessment.alert_generated) {
        logMsg = `> [WARN] HYPOGLYCEMIA ALERT: ${risk_assessment.explanation}`;
        setLatestExplanation(risk_assessment.explanation);
      }
      
      setTerminalLogs(prev => [...prev.slice(-15), logMsg]);
    }
  });

  const toggleSimulator = async () => {
    if (isSimulating) {
      await api.stopSimulator();
      setIsSimulating(false);
      setTerminalLogs(prev => [...prev, "> SIMULATOR: HALTED"]);
    } else {
      await api.startSimulator(5, 2);
      setIsSimulating(true);
      setTerminalLogs(prev => [...prev, "> SIMULATOR: ENGAGED [Speed 5x]"]);
    }
  };

  return (
    <div className="min-h-screen dot-grid-bg p-4 lg:p-8 flex flex-col gap-6">
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-border pb-4">
        <div>
          <h1 className="text-2xl font-mono font-bold tracking-tight uppercase">
            Ayuq <span className="text-[--color-accent]">System.Int</span>
          </h1>
          <p className="text-sm text-muted-foreground font-mono">Real-time Hypoglycemia Neurometric Tracking</p>
        </div>
        
        <div className="flex gap-4">
          <select 
            value={patientId}
            onChange={(e) => {
                setPatientId(e.target.value);
                setTerminalLogs(prev => [...prev, `> Switching context to ${e.target.value}`]);
            }}
            className="bg-card text-foreground font-mono text-sm border border-border p-2 outline-none"
          >
            <option value="P001">ID: P001 (Arjun)</option>
            <option value="P002">ID: P002 (Fatima)</option>
            <option value="P003">ID: P003 (Carlos)</option>
          </select>

          <Button 
            variant={isSimulating ? "destructive" : "outline"}
            className="font-mono rounded-none tracking-widest"
            onClick={toggleSimulator}
          >
            <Power className="mr-2 h-4 w-4" />
            {isSimulating ? "HALT SIMULATION" : "START SIMULATION"}
          </Button>
        </div>
      </header>

      {latestExplanation && currentRisk?.alert_generated && (
        <Alert variant="destructive" className="rounded-none border-2 animate-glitch bg-black/50">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle className="uppercase tracking-widest font-mono">Critical Protocol Engaged</AlertTitle>
          <AlertDescription className="font-mono">
           {latestExplanation}
          </AlertDescription>
        </Alert>
      )}

      <main className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column - Core Metrics */}
        <div className="lg:col-span-4 flex flex-col gap-6">
            <MetricsCard dynamicTarget1={glucose} dynamicTarget2={trend} dynamicTarget3={riskScore} />
            <div className="h-[240px]">
                <DitherCard />
            </div>
        </div>

        {/* Right Column - Terminals & Status */}
        <div className="lg:col-span-8 flex flex-col gap-6">
            <div className="h-[300px]">
                <TerminalCard logLines={terminalLogs} />
            </div>
            <div className="h-[200px]">
                <StatusCard glucoseLevel={glucose} riskLevel={currentRisk?.risk_level || "UNKNOWN"} />
            </div>
        </div>
      </main>
    </div>
  )
}
