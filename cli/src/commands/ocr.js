/**
 * DocForge CLI — `ocr` command
 *
 * Extract text from an image or scanned PDF, then optionally
 * structurize it into release JSON.
 *
 * Usage:
 *   docforge ocr screenshot.png
 *   docforge ocr scan.pdf --structurize --out draft.json
 */

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve, basename } from "node:path";
import chalk from "chalk";
import ora from "ora";
import { healthCheck } from "../lib/apiClient.js";
import { getConfig } from "../lib/config.js";
import axios from "axios";
import FormData from "form-data";

export function registerOCRCommand(program) {
  program
    .command("ocr")
    .description("Extract text from an image or scanned PDF via OCR")
    .argument("<file>", "Path to image (png/jpg) or scanned PDF")
    .option("-s, --structurize", "Also convert extracted text to release JSON")
    .option("-o, --out <path>", "Save extracted text or JSON to file")
    .option("--json", "Output raw result as JSON")
    .action(async (file, opts) => {
      const filePath = resolve(file);

      if (!existsSync(filePath)) {
        console.error(chalk.red(`\n  File not found: ${filePath}\n`));
        process.exit(1);
      }

      const spinner = ora({
        text: `Running OCR on ${basename(filePath)}...`,
        color: "cyan",
      }).start();

      const healthy = await healthCheck();
      if (!healthy) {
        spinner.fail(chalk.red("Could not reach the DocForge backend."));
        process.exit(1);
      }

      try {
        const { backendUrl } = getConfig();
        const fileBuffer = readFileSync(filePath);
        const ext = filePath.toLowerCase().split(".").pop();
        const contentType = ext === "pdf" ? "application/pdf" : `image/${ext === "jpg" ? "jpeg" : ext}`;

        // Step 1: OCR extract
        const form = new FormData();
        form.append("file", fileBuffer, { filename: basename(filePath), contentType });

        const extractResp = await axios.post(`${backendUrl}/v1/ocr/extract`, form, {
          headers: form.getHeaders(),
          timeout: 60_000,
        });

        const ocrResult = extractResp.data;
        spinner.succeed(chalk.green(`OCR complete — ${ocrResult.page_count} page(s), confidence: ${(ocrResult.overall_confidence * 100).toFixed(0)}%`));

        if (!opts.structurize) {
          if (opts.json) {
            console.log(JSON.stringify(ocrResult, null, 2));
          } else {
            console.log();
            console.log(chalk.bold("  Extracted text:"));
            console.log(chalk.gray("  " + "─".repeat(50)));
            const lines = ocrResult.raw_text.split("\n").slice(0, 30);
            for (const line of lines) {
              console.log(chalk.white(`  ${line}`));
            }
            if (ocrResult.raw_text.split("\n").length > 30) {
              console.log(chalk.gray(`  ... (${ocrResult.raw_text.split("\\n").length - 30} more lines)`));
            }
            console.log();
            console.log(chalk.bold("  Confidence:"), chalk.cyan(`${(ocrResult.overall_confidence * 100).toFixed(0)}%`));
            console.log(chalk.bold("  Method:    "), chalk.cyan(ocrResult.method));
            console.log();
          }

          if (opts.out) {
            const outPath = resolve(opts.out);
            writeFileSync(outPath, ocrResult.raw_text, "utf-8");
            console.log(chalk.green(`  Saved extracted text to ${outPath}`));
            console.log();
          }
          return;
        }

        // Step 2: Structurize
        const structSpinner = ora({
          text: "Structurizing text into release JSON...",
          color: "cyan",
        }).start();

        const structResp = await axios.post(`${backendUrl}/v1/ocr/structurize`, {
          text: ocrResult.raw_text,
        }, { timeout: 30_000 });

        const structResult = structResp.data;
        structSpinner.succeed(
          chalk.green(`Structured — confidence: ${(structResult.confidence * 100).toFixed(0)}%`)
        );

        if (structResult.warnings.length > 0) {
          for (const w of structResult.warnings) {
            console.log(chalk.yellow(`  ⚠ ${w}`));
          }
        }

        if (structResult.needs_review) {
          console.log(chalk.yellow("\n  ⚠ Draft needs manual review before generation.\n"));
        }

        if (opts.json) {
          console.log(JSON.stringify(structResult, null, 2));
        } else {
          const d = structResult.draft_json;
          console.log();
          console.log(chalk.bold("  Draft Release JSON:"));
          console.log(chalk.bold("  Product:  "), chalk.cyan(d.product_name || "(not detected)"));
          console.log(chalk.bold("  Version:  "), chalk.cyan(d.version || "(not detected)"));
          console.log(chalk.bold("  Features: "), chalk.cyan(`${d.features?.length || 0} items`));
          console.log(chalk.bold("  Fixes:    "), chalk.cyan(`${d.fixes?.length || 0} items`));
          console.log(chalk.bold("  Breaking: "), chalk.cyan(`${d.breaking_changes?.length || 0} items`));
          console.log();
        }

        if (opts.out) {
          const outPath = resolve(opts.out);
          writeFileSync(outPath, JSON.stringify(structResult.draft_json, null, 2), "utf-8");
          console.log(chalk.green(`  Saved draft JSON to ${outPath}`));
          console.log(chalk.gray("  Review and edit, then: docforge generate " + opts.out));
          console.log();
        }
      } catch (err) {
        spinner.fail(chalk.red("OCR failed"));
        if (err.response) {
          console.error(chalk.red(`  Server: ${err.response.status} — ${err.response.data?.detail || ""}`));
        } else {
          console.error(chalk.red(`  ${err.message}`));
        }
        process.exit(1);
      }
    });
}
