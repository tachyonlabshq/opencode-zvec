import path from "node:path";
import { fileURLToPath } from "node:url";

import type { Plugin } from "@opencode-ai/plugin";

const SERVER_ID = "zvec-memory";

const DEFAULT_ENVIRONMENT: Record<string, string> = {
  ZVEC_MAX_STORAGE_MB: "5120",
  ZVEC_AUTO_PRUNE: "1",
  ZVEC_MAX_ITEMS: "250000",
};

function getPackageRoot(): string {
  const currentFile = fileURLToPath(import.meta.url);
  return path.resolve(path.dirname(currentFile), "..");
}

function createServerConfig() {
  const packageRoot = getPackageRoot();
  const launcher = path.join(packageRoot, "bin", "launch-server.cjs");
  return {
    type: "local" as const,
    command: [process.execPath, launcher],
    enabled: true,
    environment: { ...DEFAULT_ENVIRONMENT },
  };
}

export const plugin: Plugin = async () => {
  return {
    config: async (config) => {
      if (process.env.ZVEC_AUTO_REGISTER_MCP === "0") {
        return;
      }

      if (!config.mcp) {
        config.mcp = {};
      }

      if (config.mcp[SERVER_ID]) {
        return;
      }

      config.mcp[SERVER_ID] = createServerConfig();
    },
  };
};

export default plugin;
