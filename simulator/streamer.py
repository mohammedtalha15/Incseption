"""
Ayuq — Real-Time Data Streamer

Reads generated patient data and POSTs readings to the backend API
every 3-5 seconds, simulating a real CGM data stream.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

import aiohttp


DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_DATA_FILE = Path(__file__).parent / "simulated_data.json"


class DataStreamer:
    """Streams simulated patient data to the backend API."""
    
    def __init__(
        self,
        api_url: str = DEFAULT_API_URL,
        data_file: str = str(DEFAULT_DATA_FILE),
        speed_multiplier: float = 1.0,
        interval_seconds: float = 4.0,
    ):
        self.api_url = api_url.rstrip("/")
        self.data_file = data_file
        self.speed_multiplier = speed_multiplier
        self.base_interval = interval_seconds
        self.running = False
        self._data = None
        self._cursors = {}  # Track position per patient
    
    def load_data(self):
        """Load the generated dataset."""
        with open(self.data_file) as f:
            self._data = json.load(f)
        
        for patient_id in self._data:
            self._cursors[patient_id] = 0
        
        total = sum(len(v) for v in self._data.values())
        print(f"Loaded {total} readings for {len(self._data)} patients")
    
    @property
    def interval(self) -> float:
        """Effective interval considering speed multiplier."""
        return max(0.5, self.base_interval / self.speed_multiplier)
    
    async def stream_reading(self, session: aiohttp.ClientSession, patient_id: str) -> dict:
        """Send a single reading to the API."""
        readings = self._data[patient_id]
        cursor = self._cursors[patient_id]
        
        if cursor >= len(readings):
            return None  # No more data
        
        reading = readings[cursor]
        self._cursors[patient_id] = cursor + 1
        
        try:
            async with session.post(
                f"{self.api_url}/reading",
                json=reading,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result
                else:
                    error = await resp.text()
                    print(f"  ⚠ API error for {patient_id}: {resp.status} - {error}")
                    return None
        except Exception as e:
            print(f"  ⚠ Connection error for {patient_id}: {e}")
            return None
    
    async def run(self):
        """Main streaming loop — cycles through patients."""
        if not self._data:
            self.load_data()
        
        self.running = True
        patient_ids = list(self._data.keys())
        patient_idx = 0
        total_sent = 0
        
        print(f"\n{'='*60}")
        print(f"  Ayuq Data Streamer")
        print(f"  API: {self.api_url}")
        print(f"  Speed: {self.speed_multiplier}x")
        print(f"  Interval: {self.interval:.1f}s")
        print(f"  Patients: {', '.join(patient_ids)}")
        print(f"{'='*60}\n")
        
        async with aiohttp.ClientSession() as session:
            while self.running:
                patient_id = patient_ids[patient_idx % len(patient_ids)]
                cursor = self._cursors.get(patient_id, 0)
                total_for_patient = len(self._data.get(patient_id, []))
                
                # Check if all patients are exhausted
                if all(
                    self._cursors[pid] >= len(self._data[pid])
                    for pid in patient_ids
                ):
                    print("\n✓ All patient data has been streamed.")
                    break
                
                # Skip exhausted patients
                if cursor >= total_for_patient:
                    patient_idx += 1
                    continue
                
                result = await self.stream_reading(session, patient_id)
                total_sent += 1
                
                if result:
                    risk = result.get("risk_assessment", {})
                    risk_score = risk.get("risk_score", 0)
                    risk_level = risk.get("risk_level", "?")
                    glucose = result.get("reading", {}).get("glucose_mgdl", 0)
                    
                    # Color-code the output
                    indicator = "🟢" if risk_level == "LOW" else "🟡" if risk_level == "MEDIUM" else "🔴"
                    
                    print(
                        f"  {indicator} [{patient_id}] "
                        f"Glucose: {glucose:>6.1f} mg/dL | "
                        f"Risk: {risk_score:>5.1f} ({risk_level:>6}) | "
                        f"#{cursor + 1}/{total_for_patient}"
                    )
                    
                    # Show alert if triggered
                    if risk.get("alert_generated"):
                        explanation = risk.get("explanation", "")
                        print(f"         ⚠  ALERT: {explanation[:100]}...")
                
                patient_idx += 1
                await asyncio.sleep(self.interval)
        
        print(f"\nTotal readings sent: {total_sent}")
    
    def stop(self):
        """Stop the streamer."""
        self.running = False


async def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ayuq Data Streamer")
    parser.add_argument("--api", default=DEFAULT_API_URL, help="Backend API URL")
    parser.add_argument("--data", default=str(DEFAULT_DATA_FILE), help="Data file path")
    parser.add_argument("--speed", type=float, default=1.0, help="Speed multiplier")
    parser.add_argument("--interval", type=float, default=4.0, help="Base interval (seconds)")
    
    args = parser.parse_args()
    
    streamer = DataStreamer(
        api_url=args.api,
        data_file=args.data,
        speed_multiplier=args.speed,
        interval_seconds=args.interval,
    )
    
    try:
        await streamer.run()
    except KeyboardInterrupt:
        print("\nStreamer stopped by user.")
        streamer.stop()


if __name__ == "__main__":
    asyncio.run(main())
