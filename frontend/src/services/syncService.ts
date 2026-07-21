import { db } from '@/lib/db';

const MOCK_PROCEDURES = [
  {
    title: "Emergency Shut-down: Compressor C-101",
    content: "1. Turn off main power feed. 2. Close isolation valve V-12 immediately to prevent gas backflow. 3. Engage manual brake override. 4. Evacuate 50ft radius.",
    asset_tag: "C-101",
    lastSync: Date.now()
  },
  {
    title: "Cooling Tower T-04 Overflow Mitigation",
    content: "If cooling tower basin overflows: 1. Throttle inlet valve 50%. 2. Start auxiliary pump P-05. 3. Check blowdown valve for obstruction. 4. Notify control room.",
    asset_tag: "T-04",
    lastSync: Date.now()
  },
  {
    title: "Boiler B-2 Overpressure Response",
    content: "Critical overpressure detected: 1. Confirm safety relief valve is venting. 2. Shut off fuel gas supply. 3. Maintain boiler feedwater flow to prevent overheating. 4. Do NOT attempt to manually lift relief valves.",
    asset_tag: "B-2",
    lastSync: Date.now()
  }
];

export async function syncProceduresToLocal() {
  if (typeof window === 'undefined' || !db) return;

  try {
    // In a real app, this would fetch from /api/v1/sync/procedures
    // For this demonstration, we use the robust mock data above.
    
    // Clear existing cache to prevent duplicates on demo loads
    await db.safetyProcedures.clear();
    
    // Bulk insert the mock procedures
    await db.safetyProcedures.bulkPut(MOCK_PROCEDURES);
    
    console.log("Successfully synced safety procedures to IndexedDB.");
  } catch (error) {
    console.error("Failed to sync procedures to local cache:", error);
  }
}
