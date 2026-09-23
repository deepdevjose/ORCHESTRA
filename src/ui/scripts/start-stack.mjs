import { spawn } from "node:child_process";
import { resolve } from "node:path";

const root = resolve(process.cwd(), "..");
const python = process.env.PYTHON ?? "python";
const model = spawn(python, [resolve(root, "scripts/live_inference_service.py")], {
  cwd: root,
  stdio: "inherit",
  env: { ...process.env, PYTHONPATH: resolve(root, "src") },
});
const next = spawn(process.platform === "win32" ? "npm.cmd" : "npm", ["run", "dev"], {
  cwd: process.cwd(),
  stdio: "inherit",
  env: process.env,
});

function stop() {
  model.kill("SIGTERM");
  next.kill("SIGTERM");
}
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
next.on("exit", (code) => {
  model.kill("SIGTERM");
  process.exit(code ?? 0);
});
