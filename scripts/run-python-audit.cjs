#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function run(command, args) {
  const result = spawnSync(command, args, {
    stdio: "inherit",
    env: process.env,
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`Command failed (${result.status}): ${command} ${args.join(" ")}`);
  }
}

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

  throw new Error("Python 3.10+ is required for pip-audit");
}

function main() {
  const reqPath = path.resolve(__dirname, "..", "zvec-memory", "mcp", "requirements-minimal.txt");
  const python = detectPython();
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "opencode-zvec-audit-"));
  const venvPath = path.join(tempRoot, "venv");

  try {
    run(python.command, [...python.args, "-m", "venv", venvPath]);
    const venvPython =
      process.platform === "win32"
        ? path.join(venvPath, "Scripts", "python.exe")
        : path.join(venvPath, "bin", "python");
    run(venvPython, ["-m", "pip", "install", "--disable-pip-version-check", "--upgrade", "pip"]);
    run(venvPython, ["-m", "pip", "install", "--disable-pip-version-check", "pip-audit"]);
    run(venvPython, ["-m", "pip_audit", "-r", reqPath, "--progress-spinner", "off"]);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
}

main();
