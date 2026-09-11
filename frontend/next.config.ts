import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import type { NextConfig } from "next";

/**
 * Load the repository-root .env.
 *
 * Next.js only reads .env files inside the frontend directory, but every
 * credential for this project lives in one file at the root — that is where the
 * backend, the Slack listener and `make check` all read from. Keeping a second
 * copy here would mean two files to update and one of them being wrong on demo
 * day. Values already in the environment win, so the shell can still override.
 */
function loadRootEnv(): void {
  let contents: string;
  try {
    contents = readFileSync(resolve(process.cwd(), "..", ".env"), "utf8");
  } catch {
    return; // No .env yet — the dashboard still runs against defaults.
  }

  for (const line of contents.split("\n")) {
    const match = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/.exec(line);
    if (!match) continue;
    const [, key, rawValue] = match;
    if (process.env[key] !== undefined) continue;
    process.env[key] = rawValue.trim().replace(/^["'](.*)["']$/, "$1");
  }
}

loadRootEnv();

const nextConfig: NextConfig = {};

export default nextConfig;
