/**
 * DocForge CLI — Configuration
 *
 * Reads the backend URL from the environment or falls back to localhost.
 */

const DEFAULTS = {
  backendUrl: "http://localhost:8000",
};

export function getConfig() {
  return {
    backendUrl: process.env.DOCFORGE_API_URL || DEFAULTS.backendUrl,
  };
}
