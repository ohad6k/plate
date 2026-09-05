/* Render every frame of a capture page at 60 fps straight into an mp4 through ffmpeg.
 * No frame folder is written: each screenshot is piped to the encoder and discarded.
 * Usage: node render.mjs <page.html> <out.mp4> <frameCount> [crf]
 *   node render.mjs after.html after.mp4 1662
 * In capture mode window.seek(t) simulates and renders synchronously, so no wait is needed.
 *
 * Dependencies, all supplied by you — this script installs nothing:
 *   node 18+
 *   ffmpeg on PATH
 *   puppeteer (brings its own Chrome), or puppeteer-core plus a browser you point at
 * Browser resolution order:
 *   1. CHROME_PATH / PUPPETEER_EXECUTABLE_PATH / CHROME_BIN, if set
 *   2. the browser bundled with an installed puppeteer
 *   3. puppeteer-core's configured executablePath
 * Run `node render.mjs --help` for the same summary.
 */
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { pathToFileURL } from "node:url";

const HELP = `render.mjs — capture a page frame by frame into an mp4

  node render.mjs <page.html> <out.mp4> [frameCount] [crf]
  node render.mjs after.html after.mp4 1662 14

The page must define window.seek(seconds), which draws one frame synchronously.
If it defines window.__assetsReady(), rendering waits for it to return true.

Requires: node 18+, ffmpeg on PATH, and either the puppeteer package (which
ships its own Chrome) or puppeteer-core with a browser binary you provide.
Set CHROME_PATH (or PUPPETEER_EXECUTABLE_PATH / CHROME_BIN) to choose the
browser explicitly. Nothing is downloaded or installed for you.`;

if (process.argv.includes("--help") || process.argv.includes("-h")) {
  console.log(HELP);
  process.exit(0);
}

function fail(lines) {
  console.error("render.mjs: " + [].concat(lines).join("\n  "));
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

const page_ = process.argv[2] || "after.html";
const out = process.argv[3] || "after.mp4";
const count = Number(process.argv[4] || 1662);
const crf = process.argv[5] || "14";
const FPS = 60;

if (!existsSync(page_)) fail([`page "${page_}" does not exist.`, "Pass the capture page as the first argument."]);
if (!Number.isFinite(count) || count < 1) fail([`frameCount "${process.argv[4]}" is not a positive number.`]);

const { puppeteer, executablePath, pkg } = await resolveBrowser();

const launchOptions = {
  headless: "new",
  args: ["--hide-scrollbars", "--allow-file-access-from-files", "--font-render-hinting=none",
         "--force-color-profile=srgb", "--use-gl=angle", "--use-angle=default",
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
await page.setViewport({ width: 1920, height: 1080, deviceScaleFactor: 1 });
await page.goto(pathToFileURL(path.resolve(page_)).href, { waitUntil: "networkidle0", timeout: 90000 });
try {
  await page.waitForFunction(() => !!window.seek && (!window.__assetsReady || window.__assetsReady()), { timeout: 120000 });
} catch {
  await browser.close();
  fail([`${page_} never became ready to capture.`,
        "It must define window.seek(seconds) to draw one frame synchronously,",
        "and window.__assetsReady() must return true once its assets have loaded."]);
}

const ff = spawn("ffmpeg", ["-y", "-hide_banner", "-loglevel", "error",
  "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
  "-c:v", "libx264", "-preset", "slow", "-crf", crf, "-pix_fmt", "yuv420p", "-movflags", "+faststart", out],
  { stdio: ["pipe", "inherit", "inherit"] });
ff.on("error", async (e) => {
  await browser.close().catch(() => {});
  fail([`ffmpeg could not be started: ${e.message}`, "Install ffmpeg and make sure it is on your PATH."]);
});
ff.stdin.on("error", () => {});

const t0 = Date.now();
for (let i = 0; i < count; i++) {
  await page.evaluate((t) => window.seek(t), i / FPS);
  const png = await page.screenshot({ type: "png" });
  if (!ff.stdin.write(png)) await new Promise((r) => ff.stdin.once("drain", r));
  if (i % 120 === 0) console.log(`frame ${i}/${count}  ${((Date.now() - t0) / 1000).toFixed(0)}s`);
}
ff.stdin.end();
await new Promise((res, rej) => ff.on("close", (c) => (c === 0 ? res() : rej(new Error("ffmpeg exit " + c)))));
console.log(`wrote ${out}: ${count} frames in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
if (errors.length) console.log("PAGE ERRORS:\n" + errors.slice(0, 5).join("\n"));
await browser.close();
