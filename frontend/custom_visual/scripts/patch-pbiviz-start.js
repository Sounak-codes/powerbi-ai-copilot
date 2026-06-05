const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const commandManagerPath = path.join(
  root,
  "node_modules",
  "powerbi-visuals-tools",
  "lib",
  "CommandManager.js"
);
const tmpPath = path.join(root, ".tmp");

if (fs.existsSync(tmpPath)) {
  fs.rmSync(tmpPath, { recursive: true, force: true });
}

if (!fs.existsSync(commandManagerPath)) {
  console.warn("powerbi-visuals-tools CommandManager.js was not found. Run npm install first.");
  process.exit(0);
}

const original = fs.readFileSync(commandManagerPath, "utf8");
const patched = original.replace('devtool: "source-map"', "devtool: false");

if (patched !== original) {
  fs.writeFileSync(commandManagerPath, patched);
  console.log("Patched pbiviz start to disable source maps.");
}
