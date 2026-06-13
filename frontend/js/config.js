/**
 * API base URL
 * - In production: set RENDER_URL below to your Render service URL
 *   e.g. "https://api-pulse-backend.onrender.com"
 * - In local dev: leave RENDER_URL as "" and it falls back to localhost
 */
const RENDER_URL = "https://api-pulse-backend-or06.onrender.com";

const API_BASE = RENDER_URL
  ? RENDER_URL.replace(/\/$/, "")          // strip trailing slash if present
  : `http://127.0.0.1:8080`;
