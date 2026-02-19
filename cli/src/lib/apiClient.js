/**
 * DocForge CLI — API Client
 *
 * Sends the release JSON to the backend and returns the PDF buffer.
 */

import axios from "axios";
import { getConfig } from "./config.js";

/**
 * Quick health check against the backend.
 * Returns true if reachable, false otherwise.
 */
export async function healthCheck() {
  const { backendUrl } = getConfig();
  try {
    const resp = await axios.get(`${backendUrl}/health`, { timeout: 5_000 });
    return resp.status === 200;
  } catch {
    return false;
  }
}

/**
 * Call POST /v1/generate on the DocForge backend.
 *
 * @param {object} releaseData  - Parsed release JSON
 * @param {object} options      - { watermark, password, templateId }
 * @returns {Promise<{pdf: Buffer, durationMs: number|null}>}
 */
export async function generatePDF(releaseData, options = {}) {
  const { backendUrl } = getConfig();
  const url = `${backendUrl}/v1/generate`;

  const body = {
    data: releaseData,
    template_id: options.templateId || "product-release",
    watermark: options.watermark || "INTERNAL",
    password: options.password || null,
    engine: options.engine || "docgen",
    verify: options.verify || false,
  };

  const response = await axios.post(url, body, {
    responseType: "arraybuffer",
    timeout: 180_000,
    headers: { "Content-Type": "application/json" },
  });

  const durationMs = response.headers["x-pipeline-duration-ms"];

  // Parse job metadata from base64 header
  let jobResult = null;
  const jobHeader = response.headers["x-docforge-job"];
  if (jobHeader) {
    try {
      jobResult = JSON.parse(Buffer.from(jobHeader, "base64").toString("utf-8"));
    } catch { /* ignore parse errors */ }
  }

  return {
    pdf: Buffer.from(response.data),
    durationMs: durationMs ? Number(durationMs) : null,
    jobResult,
  };
}
