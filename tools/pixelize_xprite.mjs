// Evaluation-only bridge to a separately installed MIT package. No network or install.
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { performance } from "node:perf_hooks";
import { createInterface } from "node:readline";

const api = await import(pathToFileURL(resolve(process.argv[2], "dist/index.js")));
async function run(input) {
const record = JSON.parse(input);
const image = { width: record.width, height: record.height,
  data: new Uint8ClampedArray(record.data) };
const started = performance.now();
const analysis = await api.analyzePixelArtAsync(image, { algorithm: api.PixelationAlgorithm.Auto });
const result = await api.pixelateImageAsync(image, {
  mode: api.PixelationMode.RecoverGrid, algorithm: api.PixelationAlgorithm.Auto,
  preserveDimensions: false, removeNoise: false,
});
process.stdout.write(JSON.stringify({ width: result.width, height: result.height,
  data: Array.from(result.data), metrics: { grid: analysis.grid,
    classification: analysis.classification, confidence: analysis.confidence,
    elapsed_ms: performance.now() - started, version: "0.1.2", level_a: false,
    accepted: null, gate_policy: "External heuristic; CyberSprite gates not applied" } }) + "\n");
}
if (process.argv[3] === "--worker") {
  for await (const line of createInterface({ input: process.stdin })) await run(line);
} else {
  let input = "";
  for await (const chunk of process.stdin) input += chunk;
  await run(input);
}
