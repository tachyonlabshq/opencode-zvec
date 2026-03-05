#!/usr/bin/env node
"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawn, spawnSync } = require("node:child_process");

const PACKAGE_ROOT = path.resolve(__dirname, "..");
const PACKAGE_JSON_PATH = path.join(PACKAGE_ROOT, "package.json");
const SERVER_PATH = path.join(PACKAGE_ROOT, "zvec-memory", "mcp", "server.py");
const REQUIREMENTS = {
  minimal: path.join(PACKAGE_ROOT, "zvec-memory", "mcp", "requirements-minimal.txt"),
  full: path.join(PACKAGE_ROOT, "zvec-memory", "mcp", "requirements.txt"),
};

function log(message) {
  process.stderr.write(`[opencode-zvec] ${message}\n`);
}

function fail(message, code = 1) {
  log(message);
  process.exit(code);
}

function sha256File(filePath) {
  const buf = fs.readFileSync(filePath);
  return crypto.createHash("sha256").update(buf).digest("hex");
}

function readJSON(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return null;
  }
}

function runAndCapture(command, args, extraEnv = {}) {
  const result = spawnSync(command, args, {
    encoding: "utf8",
    stdio: "pipe",
    env: { ...process.env, ...extraEnv },
  });
  if (result.stdout) {
    process.stderr.write(result.stdout);
  }
  if (result.stderr) {
    process.stderr.write(result.stderr);
  }
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    throw new Error(`Command failed (${result.status}): ${command} ${args.join(" ")}`);
  }
  return result.stdout || "";
}

function commandExists(command, args) {
  const result = spawnSync(command, args, {
    encoding: "utf8",
    stdio: "pipe",
  });
  return !result.error && result.status === 0;
}

function detectPython() {
  const candidates = [];
  if (process.env.ZVEC_PYTHON && process.env.ZVEC_PYTHON.trim()) {
    candidates.push({ command: process.env.ZVEC_PYTHON.trim(), args: [] });
  }
  candidates.push(
    { command: "python3", args: [] },
    { command: "python", args: [] },
    { command: "py", args: ["-3"] },
  );

  for (const candidate of candidates) {
    if (commandExists(candidate.command, [...candidate.args, "--version"])) {
      return candidate;
    }
  }

  fail(
    "Python 3.10+ was not found. Install Python and restart OpenCode. Optionally set ZVEC_PYTHON.",
    2,
  );
}

function getProfile() {
  const profile = (process.env.ZVEC_INSTALL_PROFILE || "minimal").toLowerCase();
  if (!Object.prototype.hasOwnProperty.call(REQUIREMENTS, profile)) {
    fail(
      `Unsupported ZVEC_INSTALL_PROFILE='${profile}'. Use one of: ${Object.keys(REQUIREMENTS).join(", ")}`,
      2,
    );
  }
  return profile;
}

function cacheRoot() {
  if (process.env.ZVEC_CACHE_DIR && process.env.ZVEC_CACHE_DIR.trim()) {
    return path.resolve(process.env.ZVEC_CACHE_DIR.trim());
  }

  if (process.platform === "win32") {
    const base = process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local");
    return path.join(base, "opencode-zvec");
  }

  if (process.platform === "darwin") {
    return path.join(os.homedir(), "Library", "Caches", "opencode-zvec");
  }

  const base = process.env.XDG_CACHE_HOME || path.join(os.homedir(), ".cache");
  return path.join(base, "opencode-zvec");
}

function venvPython(venvPath) {
  return process.platform === "win32"
    ? path.join(venvPath, "Scripts", "python.exe")
    : path.join(venvPath, "bin", "python");
}

function ensureRuntime() {
  if (!fs.existsSync(SERVER_PATH)) {
    fail(`Missing server file: ${SERVER_PATH}`, 2);
  }

  const profile = getProfile();
  const requirementsPath = REQUIREMENTS[profile];
  if (!fs.existsSync(requirementsPath)) {
    fail(`Missing requirements file: ${requirementsPath}`, 2);
  }

  const python = detectPython();
  const runtimeRoot = cacheRoot();
  const venvPath = path.join(runtimeRoot, "venv");
  const markerPath = path.join(runtimeRoot, "install-state.json");

  fs.mkdirSync(runtimeRoot, { recursive: true });

  const venvPythonPath = venvPython(venvPath);
  if (!fs.existsSync(venvPythonPath)) {
    log(`Creating Python virtualenv: ${venvPath}`);
    runAndCapture(python.command, [...python.args, "-m", "venv", venvPath]);
  }

  const pkg = readJSON(PACKAGE_JSON_PATH) || {};
  const desiredState = {
    packageVersion: String(pkg.version || "0.0.0"),
    profile,
    requirementsSha256: sha256File(requirementsPath),
  };
  const currentState = readJSON(markerPath);
  const forceReinstall = process.env.ZVEC_FORCE_REINSTALL === "1";
  const needsInstall =
    forceReinstall ||
    !currentState ||
    currentState.packageVersion !== desiredState.packageVersion ||
    currentState.profile !== desiredState.profile ||
    currentState.requirementsSha256 !== desiredState.requirementsSha256;

  if (needsInstall) {
    log(`Installing Python dependencies (${profile} profile)`);
    if (process.env.ZVEC_SKIP_PIP_UPGRADE !== "1") {
      runAndCapture(venvPythonPath, ["-m", "pip", "install", "--upgrade", "pip"]);
    }
    runAndCapture(venvPythonPath, [
      "-m",
      "pip",
      "install",
      "--disable-pip-version-check",
      "--requirement",
      requirementsPath,
    ]);
    fs.writeFileSync(markerPath, `${JSON.stringify(desiredState, null, 2)}\n`, "utf8");
  }

  return venvPythonPath;
}

function runHealthCheck(pythonPath) {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "opencode-zvec-health-"));
  try {
    const output = runAndCapture(
      pythonPath,
      [SERVER_PATH, "health", "--workspace-path", tempRoot],
      {
        ZVEC_MEMORY_MODE: "cli",
        ZVEC_FORCE_JSON_BACKEND: "1",
        OPENCODE_WORKSPACE: tempRoot,
        PYTHONUTF8: "1",
        PYTHONIOENCODING: "utf-8",
      },
    );
    const parsed = JSON.parse(output || "{}");
    if (!parsed || parsed.ok !== true) {
      throw new Error("health payload missing ok=true");
    }
    log("Health check passed");
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
}

function startServer(pythonPath) {
  const child = spawn(pythonPath, [SERVER_PATH], {
    stdio: ["inherit", "inherit", "inherit"],
    env: {
      ...process.env,
      PYTHONUTF8: "1",
      PYTHONIOENCODING: "utf-8",
    },
  });

  child.on("error", (error) => {
    fail(`Failed to start server: ${error.message}`, 2);
  });

  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 0);
  });
}

function main() {
  const pythonPath = ensureRuntime();
  if (process.argv.includes("--healthcheck")) {
    runHealthCheck(pythonPath);
    return;
  }
  startServer(pythonPath);
}

main();
