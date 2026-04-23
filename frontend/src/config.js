// The base URL for your backend server (Member 2's job)
export const API_BASE = "http://localhost:5000/api";

// How often the map should "check" the server for new alerts (8 seconds)
export const POLL_MS = 8000;
export const RAG_API_BASE = "http://localhost:5001/api";

// IRC:67 Standard Classifications & Styling

export const STATUS_CONFIG = {
  Good: {
    hex: "#22c55e", // Green
    label: "Compliant",
    icon: "✓",
    desc: "Retroreflectivity meets IRC:67 Class I requirements.",
  },
  Warning: {
    hex: "#f59e0b", // Yellow/Amber
    label: "Degraded",
    icon: "⚠",
    desc: "Retroreflectivity below optimal. Schedule inspection.",
  },
  Critical: {
    hex: "#ef4444", // Red
    label: "Critical",
    icon: "✕",
    desc: "Below minimum threshold. Immediate replacement required.",
  },
};