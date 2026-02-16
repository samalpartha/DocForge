/**
 * DocForge CLI — API Client
 *
 * Sends the release JSON to the backend and returns the PDF buffer.
 */

import axios from "axios";
import { getConfig } from "./config.js";

/**
 * Call POST /v1/generate on the DocForge backend.
 *
 * @param {object} releaseData  - Parsed release JSON
 * @param {object} options      - { watermark, password, templateId }
 * @returns {Promise<Buffer>}   - PDF file bytes
 */
export async function generatePDF(releaseData, options = {}) {
  const { backendUrl } = getConfig();
  const url = `${backendUrl}/v1/generate`;

  const body = {
    data: releaseData,
    template_id: options.templateId || "release-notes-v1",
    watermark: options.watermark || "INTERNAL",
    password: options.password || null,
  };

  const response = await axios.post(url, body, {
    responseType: "arraybuffer",
    timeout: 180_000,
    headers: { "Content-Type": "application/json" },
  });

  const durationMs = response.headers["x-pipeline-duration-ms"];
  return {
    pdf: Buffer.from(response.data),
    durationMs: durationMs ? Number(durationMs) : null,
  };
}
