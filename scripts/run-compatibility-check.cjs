#!/usr/bin/env node
"use strict";

const path = require("node:path");
const { spawnSync } = require("node:child_process");

function commandExists(command, args) {
  const result = spawnSync(command, args, {
    stdio: "pipe",
    encoding: "utf8",
  });
  return !result.error && result.status === 0;
}

function detectPython() {
  const candidates = [
    { command: "python3", args: [] },
    { command: "python", args: [] },
    { command: "py", args: ["-3"] },
  ];

  for (const candidate of candidates) {
    if (commandExists(candidate.command, [...candidate.args, "--version"])) {
      return candidate;
    }
  }

  throw new Error("Python 3.10+ is required");
}

function main() {
  const python = detectPython();
  const scriptPath = path.resolve(__dirname, "compatibility_check.py");
  const result = spawnSync(
    python.command,
    [...python.args, scriptPath, "--skip-installed-check"],
    {
      stdio: "inherit",
      env: process.env,
    },
  );
  if (result.error) {
    throw result.error;
  }
  process.exit(result.status ?? 1);
}

main();
