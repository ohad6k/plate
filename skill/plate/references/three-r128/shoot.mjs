/* Shoot one or more film-time frames of a capture page at 1920x1080.
 * Usage: node shoot.mjs <page.html> <out-prefix> [t0,t1,...]
 *   node shoot.mjs capture.html check/before 20
 *
 * Dependencies, all supplied by you — this script installs nothing:
 *   node 18+
 *   puppeteer (brings its own Chrome), or puppeteer-core plus a browser you point at
 * Browser resolution order:
 *   1. CHROME_PATH / PUPPETEER_EXECUTABLE_PATH / CHROME_BIN, if set
 *   2. the browser bundled with an installed puppeteer
 *   3. puppeteer-core's configured executablePath
 * Run `node shoot.mjs --help` for the same summary.
 */
import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { pathToFileURL } from "node:url";

const HELP = `shoot.mjs — screenshot a capture page at exact film times

  node shoot.mjs <page.html> <out-prefix> [t0,t1,...]
  node shoot.mjs capture.html check/before 20
  node shoot.mjs after.html check/frame 0,4.5,9

Writes <out-prefix>_<t>.png for each time, creating the directory if needed.
The page must define window.seek(seconds), which draws one frame synchronously.
If it defines window.__assetsReady(), capture waits for it to return true.

Requires: node 18+, and either the puppeteer package (which ships its own
Chrome) or puppeteer-core with a browser binary you provide. Set CHROME_PATH
(or PUPPETEER_EXECUTABLE_PATH / CHROME_BIN) to choose the browser explicitly.
Nothing is downloaded or installed for you.`;

if (process.argv.includes("--help") || process.argv.includes("-h")) {
  console.log(HELP);
  process.exit(0);
}

function fail(lines) {
  console.error("shoot.mjs: " + [].concat(lines).join("\n  "));
  process.exit(1);
}

/* Resolve puppeteer from wherever it is actually installed: next to this
 * script, or in the project the command was run from. No absolute path to
 * anyone's machine is baked in. */
async function loadModule(name) {
  const bases = [import.meta.url, pathToFileURL(path.join(process.cwd(), "package.json")).href];
  for (const base of bases) {
    try { const m = createRequire(base)(name); return m && m.default ? m.default : m; } catch {}
  }
  try { const m = await import(name); return m && m.default ? m.default : m; } catch {}
  return null;
}

async function resolveBrowser() {
  const envName = ["CHROME_PATH", "PUPPETEER_EXECUTABLE_PATH", "CHROME_BIN"].find((k) => process.env[k]);
  const envPath = envName ? process.env[envName] : "";
  if (envPath && !existsSync(envPath)) {
    fail([`${envName} points at "${envPath}", but there is no file there.`,
          "Correct it, or unset it to use the browser that comes with puppeteer."]);
  }

  const full = await loadModule("puppeteer");
  const core = full ? null : await loadModule("puppeteer-core");
  const puppeteer = full || core;
  if (!puppeteer) {
    fail(["neither puppeteer nor puppeteer-core could be resolved.",
          "Install one of them yourself, in this project or beside this script:",
          "  npm install puppeteer            # includes a Chrome build",
          "  npm install puppeteer-core       # then set CHROME_PATH to your own Chrome",
          "This script never installs packages or browsers on your behalf."]);
  }

  let executablePath = envPath || undefined;
  if (!executablePath && core) {
    try { executablePath = core.executablePath(); } catch {}
    if (!executablePath || !existsSync(executablePath)) {
      fail(["puppeteer-core is installed but no browser was found.",
            "Set CHROME_PATH to a Chrome or Chromium binary, for example:",
            "  Windows  set CHROME_PATH=C:\\Path\\To\\chrome.exe",
            "  macOS    export CHROME_PATH=\"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome\"",
            "  Linux    export CHROME_PATH=/usr/bin/google-chrome",
            "Or install the full puppeteer package, which brings its own build."]);
    }
  }
  return { puppeteer, executablePath, pkg: full ? "puppeteer" : "puppeteer-core" };
}

const page_ = process.argv[2] || "capture.html";
const prefix = process.argv[3] || "check/frame";
const times = (process.argv[4] || "20").split(",").map(Number);

if (!existsSync(page_)) fail([`page "${page_}" does not exist.`, "Pass the capture page as the first argument."]);
if (!times.length || times.some((t) => !Number.isFinite(t))) {
  fail([`could not read the times "${process.argv[4]}".`, "Pass seconds as a comma-separated list, for example 0,4.5,9."]);
}

const { puppeteer, executablePath, pkg } = await resolveBrowser();

const launchOptions = {
  headless: "new",
  args: ["--hide-scrollbars", "--allow-file-access-from-files",
         "--font-render-hinting=none", "--force-color-profile=srgb",
         "--use-gl=angle", "--use-angle=default",
         "--enable-webgl", "--ignore-gpu-blocklist"],
};
if (executablePath) launchOptions.executablePath = executablePath;

let browser;
try {
  browser = await puppeteer.launch(launchOptions);
} catch (e) {
  fail([`could not start a browser through ${pkg}: ${e.message}`,
        "Set CHROME_PATH to a Chrome or Chromium binary, or reinstall puppeteer so its bundled browser is present."]);
}

const page = await browser.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text()); });
await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });
await page.goto(pathToFileURL(path.resolve(page_)).href, { waitUntil: "networkidle0", timeout: 60000 });
try {
  await page.waitForFunction(() => !!window.seek && (!window.__assetsReady || window.__assetsReady()), { timeout: 60000 });
} catch {
  await browser.close();
  fail([`${page_} never became ready to capture.`,
        "It must define window.seek(seconds) to draw one frame synchronously,",
        "and window.__assetsReady() must return true once its assets have loaded."]);
}
await mkdir(path.dirname(prefix), { recursive: true });
for (const t of times) {
  await page.evaluate((tt) => window.seek(tt), t);
  await new Promise((r) => setTimeout(r, 400));
  await page.evaluate((tt) => window.seek(tt), t);
  await new Promise((r) => setTimeout(r, 150));
  const file = `${prefix}_${t}.png`;
  await page.screenshot({ path: file });
  console.log("wrote", file);
}
if (errors.length) console.log("PAGE ERRORS:\n" + errors.join("\n"));
await browser.close();
