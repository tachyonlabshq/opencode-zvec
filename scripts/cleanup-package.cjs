#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const TARGETS = [path.join(ROOT, "zvec-memory"), path.join(ROOT, "scripts"), path.join(ROOT, "bin")];

function walk(currentPath) {
  const entries = fs.readdirSync(currentPath, { withFileTypes: true });
  for (const entry of entries) {
    const nextPath = path.join(currentPath, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "__pycache__") {
        fs.rmSync(nextPath, { recursive: true, force: true });
        continue;
      }
      walk(nextPath);
      continue;
    }

    if (entry.name === ".DS_Store" || entry.name.endsWith(".pyc") || entry.name.endsWith(".pyo")) {
      fs.rmSync(nextPath, { force: true });
    }
  }
}

for (const target of TARGETS) {
  if (fs.existsSync(target)) {
    walk(target);
  }
}
