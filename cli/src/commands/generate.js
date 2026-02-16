/**
 * DocForge CLI — `generate` command
 *
 * Usage:
 *   docforge generate <input.json> --out output.pdf [--watermark DRAFT] [--password secret]
 */

import { readFileSync, writeFileSync } from "node:fs";
import { resolve, basename } from "node:path";
import chalk from "chalk";
import ora from "ora";
import { generatePDF } from "../lib/apiClient.js";

/**
 * Register the `generate` command on a Commander program.
 */
export function registerGenerateCommand(program) {
  program
    .command("generate")
    .description("Generate a Release Notes PDF from a JSON file")
    .argument("<input>", "Path to the release JSON file")
    .option("-o, --out <path>", "Output PDF path", "release-notes.pdf")
    .option("-w, --watermark <text>", "Watermark text", "INTERNAL")
    .option("-p, --password <pwd>", "Password-protect the PDF")
    .option("-t, --template <id>", "Template ID", "release-notes-v1")
    .action(async (input, opts) => {
      const inputPath = resolve(input);
      const outputPath = resolve(opts.out);

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
      if (!releaseData.product_name) {
        console.error(
          chalk.red("\n  Missing required field: product_name")
        );
        process.exit(1);
      }
      if (!releaseData.version) {
        console.error(chalk.red("\n  Missing required field: version"));
        process.exit(1);
      }

      // --- Call backend ---
      console.log();
      console.log(
        chalk.bold("  DocForge CLI"),
        chalk.gray("— Release Notes Generator")
      );
      console.log(
        chalk.gray(`  Input:     ${inputPath}`)
      );
      console.log(
        chalk.gray(`  Output:    ${outputPath}`)
      );
      console.log(
        chalk.gray(`  Watermark: ${opts.watermark}`)
      );
      if (opts.password) {
        console.log(chalk.gray(`  Password:  ****`));
      }
      console.log();

      const spinner = ora({
        text: "Generating PDF via Foxit APIs...",
        color: "cyan",
      }).start();

      try {
        const { pdf, durationMs } = await generatePDF(releaseData, {
          watermark: opts.watermark,
          password: opts.password,
          templateId: opts.template,
        });

        writeFileSync(outputPath, pdf);

        spinner.succeed(chalk.green("PDF generated successfully!"));
        console.log();
        console.log(chalk.bold("  Output:   "), chalk.cyan(outputPath));
        console.log(
          chalk.bold("  Size:     "),
          chalk.cyan(`${(pdf.length / 1024).toFixed(1)} KB`)
        );
        if (durationMs) {
          console.log(
            chalk.bold("  Pipeline: "),
            chalk.cyan(`${durationMs.toFixed(0)} ms`)
          );
        }
        console.log();
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
