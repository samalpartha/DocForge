#!/usr/bin/env node

/**
 * DocForge CLI
 *
 * Generate Release Notes PDFs from GitHub-style release JSON.
 * Powered by Foxit Document Generation + PDF Services APIs.
 *
 * Usage:
 *   docforge generate examples/release.json --out output.pdf
 *   docforge --help
 */

import { Command } from "commander";
import { registerGenerateCommand } from "./commands/generate.js";

const program = new Command();

program
  .name("docforge")
  .description(
    "Generate polished Release Notes PDFs from JSON — powered by Foxit APIs"
  )
  .version("1.0.0");

registerGenerateCommand(program);

program.parse();
