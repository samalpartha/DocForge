/**
 * DocForge CLI — Configuration
 *
 * Reads the backend URL from the environment or falls back to localhost.
 */

const DEFAULTS = {
  backendUrl: "https://docforge-monolith-108816008638.us-central1.run.app",
};

export function getConfig() {
  return {
    backendUrl: process.env.DOCFORGE_API_URL || DEFAULTS.backendUrl,
  };
}
