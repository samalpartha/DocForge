#!/usr/bin/env node

/**
 * DocForge CLI v2
 *
 * Generate Release Notes PDFs from GitHub-style release JSON.
 * Powered by Foxit Document Generation + PDF Services APIs.
 *
 * Usage:
 *   docforge generate examples/release.json --out output.pdf
 *   docforge generate examples/release.json --engine latex --verify --open
 *   docforge templates
 *   docforge --help
 */

import { Command } from "commander";
import chalk from "chalk";
import axios from "axios";
import { registerGenerateCommand } from "./commands/generate.js";
import { registerVerifyCommand } from "./commands/verify.js";
import { registerOCRCommand } from "./commands/ocr.js";
import { getConfig } from "./lib/config.js";

const program = new Command();

program
  .name("docforge")
  .description(
    "Generate polished Release Notes PDFs from JSON — powered by Foxit APIs"
  )
  .version("2.0.0");

registerGenerateCommand(program);
registerVerifyCommand(program);
registerOCRCommand(program);

// ---- templates command ----
program
  .command("templates")
  .description("List available PDF templates")
  .action(async () => {
    const { backendUrl } = getConfig();
    try {
      const resp = await axios.get(`${backendUrl}/v1/templates`, { timeout: 5_000 });
      console.log();
      console.log(chalk.bold("  Available Templates:"));
      console.log();
      for (const t of resp.data) {
        console.log(chalk.bold(`  ${chalk.cyan(t.id)}`), chalk.gray(`— ${t.name}`));
        console.log(chalk.gray(`    ${t.description}`));
        console.log(chalk.gray(`    Engines: ${t.engines.join(", ")}  |  Watermark: ${t.default_watermark}`));
        console.log();
      }
    } catch {
      console.error(chalk.red("  Could not fetch templates. Is the backend running?"));
      process.exit(1);
    }
  });

program.parse();
