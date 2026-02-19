/**
 * DocForge CLI — `generate` command
 *
 * Usage:
 *   docforge generate <input.json> --out output.pdf [--watermark DRAFT] [--password secret]
 */

import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve, basename } from "node:path";
import chalk from "chalk";
import ora from "ora";
import { generatePDF, healthCheck } from "../lib/apiClient.js";

/**
 * Register the `generate` command on a Commander program.
 */
export function registerGenerateCommand(program) {
  program
    .command("generate")
    .description("Generate a Release Notes PDF from a JSON file")
    .argument("<input>", "Path to the release JSON file")
    .option("-o, --out <path>", "Output PDF path (default: <product>-<version>-release-notes.pdf)")
    .option("-w, --watermark <text>", "Watermark text", "INTERNAL")
    .option("-p, --password <pwd>", "Password-protect the PDF")
    .option("-t, --template <id>", "Template ID", "release-notes-v1")
    .option("-e, --engine <type>", "Rendering engine: docgen or latex", "docgen")
    .option("-v, --verify", "Run post-processing verification checks")
    .option("--open", "Open PDF in system reader after generation")
    .option("--json", "Output job metadata as JSON to stdout")
    .action(async (input, opts) => {
      const inputPath = resolve(input);

      // --- Check file exists ---
      if (!existsSync(inputPath)) {
        console.error(chalk.red(`\n  File not found: ${inputPath}\n`));
        process.exit(1);
      }

      // --- Read & parse JSON ---
      let releaseData;
      try {
        const raw = readFileSync(inputPath, "utf-8");
        releaseData = JSON.parse(raw);
      } catch (err) {
        console.error(
          chalk.red(`\n  Error reading ${basename(inputPath)}:`),
          err.message
        );
        process.exit(1);
      }

      // --- Quick local validation ---
      const missing = [];
      if (!releaseData.product_name) missing.push("product_name");
      if (!releaseData.version) missing.push("version");
      if (missing.length) {
        console.error(
          chalk.red(`\n  Missing required field(s): ${missing.join(", ")}`)
        );
        console.error(
          chalk.gray("  See examples/release.json for the expected format.\n")
        );
        process.exit(1);
      }

      // --- Derive smart default output path ---
      const slug = releaseData.product_name.toLowerCase().replace(/\s+/g, "-");
      const defaultOut = `${slug}-v${releaseData.version}-release-notes.pdf`;
      const outputPath = resolve(opts.out || defaultOut);

      const productLabel = `${releaseData.product_name} v${releaseData.version}`;

      // --- Print header ---
      console.log();
      console.log(
        chalk.bold("  DocForge CLI"),
        chalk.gray("— Release Notes Generator")
      );
      console.log(
        chalk.bold("  Product: "),
        chalk.white(productLabel)
      );
      console.log(chalk.gray(`  Input:     ${inputPath}`));
      console.log(chalk.gray(`  Output:    ${outputPath}`));
      console.log(chalk.gray(`  Watermark: ${opts.watermark}`));
      console.log(chalk.gray(`  Engine:    ${opts.engine}`));
      if (opts.password) {
        console.log(chalk.gray("  Password:  ****"));
      }
      if (opts.verify) {
        console.log(chalk.gray("  Verify:    enabled"));
      }
      console.log();

      // --- Health-check the backend first ---
      const spinner = ora({
        text: "Connecting to DocForge backend...",
        color: "cyan",
      }).start();

      const healthy = await healthCheck();
      if (!healthy) {
        spinner.fail(chalk.red("Could not reach the DocForge backend."));
        console.error();
        console.error(
          chalk.gray("  Make sure it is running:\n") +
          chalk.white("    cd backend && uvicorn app.main:app --reload\n")
        );
        process.exit(1);
      }

      spinner.text = `Generating PDF for ${productLabel} via Foxit APIs...`;

      try {
        const { pdf, durationMs, jobResult } = await generatePDF(releaseData, {
          watermark: opts.watermark,
          password: opts.password,
          templateId: opts.template,
          engine: opts.engine,
          verify: !!opts.verify,
        });

        writeFileSync(outputPath, pdf);

        spinner.succeed(
          chalk.green(`PDF generated for ${chalk.bold(productLabel)}`)
        );
        console.log();
        console.log(chalk.bold("  Output:   "), chalk.cyan(outputPath));
        console.log(
          chalk.bold("  Size:     "),
          chalk.cyan(`${(pdf.length / 1024).toFixed(1)} KB`)
        );
        console.log(
          chalk.bold("  Engine:   "),
          chalk.cyan(opts.engine)
        );
        if (durationMs) {
          console.log(
            chalk.bold("  Pipeline: "),
            chalk.cyan(`${durationMs.toFixed(0)} ms`)
          );
        }

        // Show verification results
        if (jobResult && jobResult.verification) {
          const v = jobResult.verification;
          const status = v.passed
            ? chalk.green(`✓ ${v.checks_passed}/${v.checks_total} checks passed`)
            : chalk.red(`✗ ${v.checks_passed}/${v.checks_total} checks passed`);
          console.log(chalk.bold("  Verify:   "), status);
          console.log(chalk.bold("  Pages:    "), chalk.cyan(v.page_count));
          console.log(chalk.bold("  Hash:     "), chalk.gray(jobResult.artifact?.content_hash?.slice(0, 24) + "..."));
        }

        // Show timings
        if (jobResult && jobResult.timings) {
          console.log();
          console.log(chalk.bold("  Step Timings:"));
          for (const t of jobResult.timings) {
            const icon = t.status === "ok" ? chalk.green("✓") : t.status === "skipped" ? chalk.gray("⊘") : chalk.red("✗");
            console.log(`    ${icon} ${t.step.padEnd(18)} ${chalk.cyan(t.duration_ms + "ms")} ${chalk.gray(t.detail || "")}`);
          }
        }

        // JSON output mode
        if (opts.json && jobResult) {
          console.log();
          console.log(JSON.stringify(jobResult, null, 2));
        }

        console.log();

        // Open in system reader
        if (opts.open) {
          const { exec } = await import("node:child_process");
          const cmd = process.platform === "darwin" ? "open" : process.platform === "win32" ? "start" : "xdg-open";
          exec(`${cmd} "${outputPath}"`);
        }
      } catch (err) {
        spinner.fail(chalk.red("Failed to generate PDF"));
        console.error();

        if (err.response) {
          const status = err.response.status;
          let detail = "";
          try {
            const body = JSON.parse(
              Buffer.from(err.response.data).toString("utf-8")
            );
            detail = body.detail
              ? typeof body.detail === "string"
                ? body.detail
                : JSON.stringify(body.detail, null, 2)
              : "";
          } catch {
            detail = err.message;
          }
          console.error(
            chalk.red(`  Server responded with ${status}:`),
            detail
          );
        } else if (err.code === "ECONNREFUSED") {
          console.error(
            chalk.red("  Could not connect to the DocForge backend.")
          );
          console.error(
            chalk.gray(
              "  Make sure the backend is running: cd backend && uvicorn app.main:app --reload"
            )
          );
        } else {
          console.error(chalk.red(`  ${err.message}`));
        }
        console.log();
        process.exit(1);
      }
    });
}
