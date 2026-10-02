#!/usr/bin/env node
/**
 * Fleet portability gate: reject machine-local absolute paths in repository text.
 * Usage: node scripts/check-portability.mjs [--root /path/to/repo]
 */
import { readFileSync, readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DEFAULT_ROOT = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const rootArgIndex = process.argv.indexOf("--root");
const root =
  rootArgIndex >= 0 && process.argv[rootArgIndex + 1]
    ? path.resolve(process.argv[rootArgIndex + 1])
    : DEFAULT_ROOT;

const POLICY_PATH = path.join(root, "portability.policy.yaml");

const DEFAULT_SKIP_DIRS = new Set([
  ".git",
  "node_modules",
  "target",
  ".venv",
  ".mise",
  ".pnpm-store",
  "megalinter-reports",
  "dist",
  "build",
  ".next",
  ".turbo",
  "coverage",
  "actions-runner",
  ".migration-backups",
  // Scratch worktrees are deliberately NOT listed -- `shouldSkipDir` matches on
  // basename alone, so a `worktrees` entry would also skip an authored
  // `docs/worktrees/`. They are git-ignored, and `gitIgnored` already excludes
  // them by the authority that actually knows.
  //
  // `.build` was listed here for Xcode derived data and has been removed for
  // exactly the reason stated above: a tracked `docs/.build/notes.md` naming
  // somebody's machine passed the gate. The rule this file already documents
  // was written down and then broken one entry later. Derived data is
  // git-ignored, so the authority that actually knows still excludes it.
]);

const TEXT_EXTENSIONS = new Set([
  ".md",
  ".mdc",
  ".txt",
  ".json",
  ".jsonc",
  ".yaml",
  ".yml",
  ".toml",
  ".js",
  ".mjs",
  ".cjs",
  ".ts",
  ".tsx",
  ".jsx",
  ".py",
  ".rs",
  ".sh",
  ".bash",
  ".zsh",
  ".sql",
  ".env.example",
  ".gitlab-ci.yml",
  ".mega-linter.yml",
]);

const MACHINE_LOCAL_PATH_PATTERNS = [
  {
    label: "Unix machine-local absolute path",
    // Each alternative carries its own trailing separator. Factoring the `/`
    // out to the end silently broke the two alternatives that need a lookahead
    // *after* it: `tmp\/(?!lint\b)` then required a literal `/tmp//`, and
    // `Volumes\/(?!TARDIS\/)` required a literal doubled separator, so neither ever matched.
    regex:
      /(^|[\s"'`(=])\/(?:Users\/|home\/|private\/|var\/folders\/|Volumes\/)[^\s"'`),;|&<>]+/g,
  },
  {
    label: "Windows drive absolute path",
    regex: /(^|[\s"'`(=])[A-Za-z]:\\[^\s"'`),;]+/g,
    // `C:\fakepath\` is a sentinel the HTML spec requires browsers to report
    // for `input[type=file].value`; it appears in any bundle touching file
    // inputs and names nobody's machine. Excluding it keeps the guard usable
    // on repositories that commit build output.
    // Tolerates the escaped form too: minified bundles carry the sentinel
    // inside a JS string literal, where each backslash is doubled.
    ignore: /^[A-Za-z]:\\{1,2}fakepath\\{1,2}/i,
  },
  {
    label: "file URL",
    regex: /file:\/\/[^\s"'`),;]+/g,
    // `file://${...}` is runtime path construction, not a machine-local path
    // -- and it is the standard Node entry-point idiom, so flagging it makes
    // the guard unusable on most Node repositories. The policy recommends
    // exactly this construction, so detecting it would contradict the rule.
    ignore: /^file:\/\/\$\{/,
  },
];

function loadPolicy() {
  try {
    const raw = readFileSync(POLICY_PATH, "utf8");
    const allowedPaths = [];
    const skipDirs = new Set(DEFAULT_SKIP_DIRS);
    const skipPaths = new Set();

    // Track which key a `- item` belongs to. The previous scan treated every
    // list item anywhere in the file as an allowed path, so a policy carrying a
    // second list silently mixed the two -- a repository skipping `legacy` was
    // instead exempting a file called `legacy`.
    const sink = { allowedPaths, skipDirs, skipPaths };
    let current = null;

    for (const line of raw.split("\n")) {
      const key = line.match(/^([A-Za-z][A-Za-z0-9_]*):\s*(.*)$/);
      if (key) {
        const [, name, inline] = key;
        // Singular inline forms: `skipDir: node_modules`, `skipPath: .trunk/out`.
        if (name === "skipDir" && inline.trim()) skipDirs.add(inline.trim());
        else if (name === "skipPath" && inline.trim())
          skipPaths.add(inline.trim());
        current =
          name === "allowedPaths"
            ? "allowedPaths"
            : name === "skipDirs"
              ? "skipDirs"
              : name === "skipPaths"
                ? "skipPaths"
                : null;
        continue;
      }
      const item = line.match(/^\s*-\s+(.+)$/);
      if (item && current) {
        const value = item[1].trim();
        if (current === "allowedPaths") allowedPaths.push(value);
        else sink[current].add(value);
      }
    }
    return { allowedPaths: new Set(allowedPaths), skipDirs, skipPaths };
  } catch {
    return {
      allowedPaths: new Set([
        "portability.policy.yaml",
        "scripts/check-portability.mjs",
        "fleet-tooling/scripts/check-portability.mjs",
      ]),
      skipDirs: DEFAULT_SKIP_DIRS,
      skipPaths: new Set(),
    };
  }
}

function shouldSkipDir(absolutePath, rootDir, skipDirs, skipPaths) {
  const relativePath = path
    .relative(rootDir, absolutePath)
    .split(path.sep)
    .join("/");
  return (
    skipDirs.has(path.basename(absolutePath)) || skipPaths.has(relativePath)
  );
}

function walkTextFiles(dir, rootDir, skipDirs, skipPaths, files = []) {
  let entries;
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch {
    return files;
  }
  for (const entry of entries) {
    const absolutePath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (!shouldSkipDir(absolutePath, rootDir, skipDirs, skipPaths)) {
        walkTextFiles(absolutePath, rootDir, skipDirs, skipPaths, files);
      }
      continue;
    }
    const ext = path.extname(entry.name);
    if (
      TEXT_EXTENSIONS.has(ext) ||
      entry.name === ".gitlab-ci.yml" ||
      entry.name === ".mega-linter.yml"
    ) {
      files.push(absolutePath);
    }
  }
  return files;
}

/**
 * Paths git ignores, which are by definition not repository text.
 *
 * The walk reads the filesystem, so without this it reports local runtime
 * state, caches and scratch output as repository violations -- files the
 * repository does not contain and a reviewer cannot fix. Degrades to scanning
 * everything when the root is not a git checkout (which is how the contract
 * suite runs it) or when git is unavailable.
 */
function gitIgnored(rootDir, relativePaths) {
  if (relativePaths.length === 0) return new Set();
  // `-z` on both sides. Without it git applies `core.quotePath` and returns a
  // non-ASCII name in escaped form, which no longer equals the path we asked
  // about -- so an ignored `runtime/e\u0301.md` was scanned anyway. NUL framing
  // also makes tabs and newlines in names unable to change path identity.
  // Asked in bounded batches. `spawnSync` buffers the child's whole output and
  // defaults to about 1 MiB; a repository with a large ignored tree exceeds
  // that, the child dies with ENOBUFS and a null status, and the "not a repo"
  // fallback below then reports *nothing* as ignored -- so the guard scans the
  // generated output it exists to skip and fails the build. Found by review on
  // an adopting repository, reproduced with 14000 ignored files.
  //
  // Batching bounds the output regardless of repository size; `maxBuffer` is
  // raised as well so a single pathological batch cannot reintroduce the same
  // failure quietly.
  const ignored = new Set();
  const BATCH = 2000;
  for (let index = 0; index < relativePaths.length; index += BATCH) {
    const batch = relativePaths.slice(index, index + BATCH);
    const result = spawnSync(
      "git",
      ["-C", rootDir, "check-ignore", "--stdin", "-z"],
      {
        input: batch.join("\0"),
        encoding: "utf8",
        // A gate that can hang is not a gate. An adopting repository's own
        // spawn-bounds check found this: `git` waiting on a lock or a slow
        // filesystem would stall the guard with no output and no timeout.
        timeout: 30_000,
        maxBuffer: 64 * 1024 * 1024,
      },
    );
    // 0 = some ignored, 1 = none ignored, anything else = not a repo / no git.
    if (result.status === 1) continue;
    if (result.status !== 0) return new Set();
    for (const entry of result.stdout.split("\0"))
      if (entry) ignored.add(entry);
  }
  return ignored;
}

function lineNumberForIndex(content, index) {
  return content.slice(0, index).split("\n").length;
}

function activeQuoteAt(content, end) {
  let quote = null;
  let escaped = false;
  for (let index = 0; index < end; index += 1) {
    const character = content[index];
    if (escaped) {
      escaped = false;
      continue;
    }
    if (character === "\\" && quote !== "'") {
      escaped = true;
      continue;
    }
    if (quote !== null) {
      if (character === quote) quote = null;
      continue;
    }
    if (
      (character === '"' || character === "'" || character === "`") &&
      (index === 0 || /[\s=([{,:;]/.test(content[index - 1] ?? ""))
    ) {
      quote = character;
    }
  }
  return quote;
}

function isAllowedTardisPath(content, match) {
  const prefix = match[1] ?? "";
  const matchedPath = match[0].slice(prefix.length);
  if (matchedPath.startsWith("/Volumes/TARDIS/")) return true;
  if (matchedPath !== "/Volumes/TARDIS") return false;

  const start = (match.index ?? 0) + prefix.length;
  const end = start + matchedPath.length;
  const next = content[end] ?? "";
  const quote = activeQuoteAt(content, start);
  if (quote !== null) return next === quote;
  if (next === "" || next === "\n" || next === "\r") return true;
  if (/^(?:&&|\|\||[|;&<>])/.test(content.slice(end))) return true;
  if (/^[\t ]+(?:&&|\|\||[|;&<>#)]|\r?\n|$)/.test(content.slice(end))) {
    return true;
  }
  if (next === ",") {
    return /^(?:[\t ]|\r?\n|$)/.test(content.slice(end + 1));
  }
  if (next === ")") {
    return /^(?:[\t ]|\r?\n|$|[,.;:!?])/.test(content.slice(end + 1));
  }
  return false;
}

function findViolations(rootDir, policy) {
  const violations = [];
  const candidates = walkTextFiles(
    rootDir,
    rootDir,
    policy.skipDirs,
    policy.skipPaths,
  );
  const relativeOf = (absolutePath) =>
    path.relative(rootDir, absolutePath).split(path.sep).join("/");
  const ignored = gitIgnored(rootDir, candidates.map(relativeOf));
  for (const absolutePath of candidates) {
    const relativePath = relativeOf(absolutePath);
    if (ignored.has(relativePath)) {
      continue;
    }
    if (/fixtures\/.*ABSOLUTE_PATH/i.test(relativePath)) {
      continue;
    }
    if (
      /\.(test|spec)\.(ts|tsx|mjs|js)$/.test(relativePath) ||
      /(^|\/)tests\//.test(relativePath)
    ) {
      continue;
    }
    if (
      relativePath.endsWith(".rs") &&
      readFileSync(absolutePath, "utf8").includes("#[cfg(test)]")
    ) {
      continue;
    }
    if (policy.allowedPaths.has(relativePath)) {
      continue;
    }
    const content = readFileSync(absolutePath, "utf8");
    for (const pattern of MACHINE_LOCAL_PATH_PATTERNS) {
      for (const match of content.matchAll(pattern.regex)) {
        if (
          pattern.label === "Unix machine-local absolute path" &&
          isAllowedTardisPath(content, match)
        ) {
          continue;
        }
        const index = match.index ?? 0;
        // The matched text may carry a leading delimiter from the pattern's
        // boundary group; compare the path itself against the ignore rule.
        const matched = match[0].slice((match[1] ?? "").length);
        if (pattern.ignore?.test(matched)) {
          continue;
        }
        violations.push(
          `${relativePath}:${lineNumberForIndex(content, index)} contains ${pattern.label}`,
        );
      }
    }
  }
  return violations;
}

const policy = loadPolicy();
const violations = findViolations(root, policy);

if (violations.length > 0) {
  console.error("Portability validation failed:");
  for (const violation of violations.slice(0, 50)) {
    console.error(`  - ${violation}`);
  }
  if (violations.length > 50) {
    console.error(`  ... and ${violations.length - 50} more`);
  }
  process.exit(1);
}

console.log("Portability validation passed.");
