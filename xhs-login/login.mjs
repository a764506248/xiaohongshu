import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import puppeteer from "puppeteer";

const [sessionDir, timeoutText = "120"] = process.argv.slice(2);
if (!sessionDir) throw new Error("missing session directory");
const timeoutMs = Number(timeoutText) * 1000;
const statusFile = path.join(sessionDir, "status.json");
const qrFile = path.join(sessionDir, "qrcode.png");
const cookieFile = path.join(os.homedir(), ".xhs-mcp", "cookies.json");
const writeStatus = (value) => fs.writeFile(statusFile, JSON.stringify(value), "utf8");

await fs.mkdir(sessionDir, { recursive: true });
await writeStatus({ status: "starting", message: "正在打开小红书登录页" });
let browser;
try {
  browser = await puppeteer.launch({ headless: true, args: ["--no-sandbox", "--disable-setuid-sandbox"] });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1.5 });
  try {
    const cookies = JSON.parse(await fs.readFile(cookieFile, "utf8"));
    if (Array.isArray(cookies) && cookies.length) await page.setCookie(...cookies);
  } catch {}
  await page.goto("https://www.xiaohongshu.com/explore", { waitUntil: "networkidle2", timeout: 60000 });
  const loggedInSelector = ".main-container .user .link-wrapper .channel";
  if (await page.$(loggedInSelector)) {
    await writeStatus({ status: "logged_in", message: "小红书账号已登录" });
    process.exitCode = 0;
  } else {
    const selectors = [
      "[class*='qrcode'] canvas", "[class*='qr-code'] canvas", "[class*='qrcode'] img",
      "[class*='qr-code'] img", "img[src*='qr']", "canvas"
    ];
    let qr = null;
    const deadline = Date.now() + 30000;
    while (!qr && Date.now() < deadline) {
      for (const selector of selectors) {
        qr = await page.$(selector);
        if (qr) break;
      }
      if (!qr) await new Promise((resolve) => setTimeout(resolve, 500));
    }
    if (!qr) throw new Error("登录页未找到二维码，请稍后重试");
    await qr.screenshot({ path: qrFile });
    await writeStatus({ status: "waiting_scan", message: "请使用小红书 App 扫码登录" });
    await page.waitForSelector(loggedInSelector, { timeout: timeoutMs });
    await fs.mkdir(path.dirname(cookieFile), { recursive: true });
    await fs.writeFile(cookieFile, JSON.stringify(await page.cookies(), null, 2), "utf8");
    await writeStatus({ status: "logged_in", message: "扫码成功，小红书账号已登录" });
  }
} catch (error) {
  await writeStatus({ status: "failed", message: error?.message || String(error) });
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
}
