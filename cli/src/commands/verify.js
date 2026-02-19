/**
 * DocForge CLI — `verify` command
 *
 * Run 7-check verification on an existing PDF file.
 *
 * Usage:
 *   docforge verify output.pdf --watermark INTERNAL
 */

import { existsSync, readFileSync } from "node:fs";
import { resolve, basename } from "node:path";
import chalk from "chalk";
import ora from "ora";
import { healthCheck } from "../lib/apiClient.js";
import { getConfig } from "../lib/config.js";
import axios from "axios";
import FormData from "form-data";

export function registerVerifyCommand(program) {
  program
    .command("verify")
    .description("Run verification checks on an existing PDF")
    .argument("<pdf>", "Path to the PDF file to verify")
    .option("-w, --watermark <text>", "Expected watermark text", "INTERNAL")
    .option("--encrypted", "Expect the PDF to be encrypted")
    .option("--json", "Output verification result as JSON")
    .action(async (pdf, opts) => {
      const pdfPath = resolve(pdf);

      if (!existsSync(pdfPath)) {
        console.error(chalk.red(`\n  File not found: ${pdfPath}\n`));
        process.exit(1);
      }

      const spinner = ora({
        text: `Verifying ${basename(pdfPath)}...`,
        color: "cyan",
      }).start();

      const healthy = await healthCheck();
      if (!healthy) {
        spinner.fail(chalk.red("Could not reach the DocForge backend."));
        process.exit(1);
      }

      try {
        const { backendUrl } = getConfig();
        const pdfBuffer = readFileSync(pdfPath);
        const form = new FormData();
        form.append("file", pdfBuffer, { filename: basename(pdfPath), contentType: "application/pdf" });
        form.append("watermark_text", opts.watermark);
        form.append("should_be_encrypted", opts.encrypted ? "true" : "false");

        const resp = await axios.post(`${backendUrl}/v1/verify`, form, {
          headers: form.getHeaders(),
          timeout: 30_000,
        });

        const v = resp.data;
        spinner.succeed(
          v.passed
            ? chalk.green(`Verification passed: ${v.checks_passed}/${v.checks_total} checks`)
            : chalk.red(`Verification failed: ${v.checks_passed}/${v.checks_total} checks`)
        );

        if (opts.json) {
          console.log(JSON.stringify(v, null, 2));
        } else {
          console.log();
          const check = (label, value) => {
            const icon = value ? chalk.green("✓") : chalk.red("✗");
            console.log(`    ${icon}  ${label}`);
          };
          check("Opens & parses", v.page_count > 0);
          check("Has text content", v.has_text);
          check("Watermark detected", v.watermark_detected);
          check("Watermark on all pages", v.watermark_on_all_pages);
          check("Encryption matches", !opts.encrypted || v.is_encrypted);
          check("Flattening signals", v.flattening_signals);
          check("Content hash", !!v.content_hash);
          console.log();
          console.log(chalk.bold("  Pages:  "), chalk.cyan(v.page_count));
          console.log(chalk.bold("  Size:   "), chalk.cyan(`${(v.file_size / 1024).toFixed(1)} KB`));
          console.log(chalk.bold("  Hash:   "), chalk.gray(v.content_hash?.slice(0, 24) + "..."));
          console.log();
        }
      } catch (err) {
        spinner.fail(chalk.red("Verification failed"));
        if (err.response) {
          console.error(chalk.red(`  Server: ${err.response.status}`));
        } else {
          console.error(chalk.red(`  ${err.message}`));
        }
        process.exit(1);
      }
    });
}
