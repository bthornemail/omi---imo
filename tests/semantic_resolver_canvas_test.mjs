import assert from 'node:assert/strict';
import { mkdir, readFile, rm } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';

const repoRoot = new URL('..', import.meta.url).pathname;
const fixtureRoot = join(repoRoot, 'tests/fixtures/semantic-resolver');
const outDir = join(repoRoot, 'build/semantic-resolver-canvas-test');
const edgesPath = join(outDir, 'edges.jsonl');
const canvasPath = join(outDir, 'lattice.canvas');

console.log('Testing semantic resolver CLI Canvas output');

await rm(outDir, { recursive: true, force: true });
await mkdir(outDir, { recursive: true });
execFileSync('node', [
  'tools/semantic_resolver.mjs',
  '--root', fixtureRoot,
  '--trace', 'trace.jsonl',
  '--no-fallback-trace',
  '--edges', edgesPath,
  '--canvas',
  '--canvas-path', canvasPath
], { cwd: repoRoot, stdio: 'pipe' });

const edges = (await readFile(edgesPath, 'utf8')).trim().split('\n').map((line) => JSON.parse(line));
const canvas = JSON.parse(await readFile(canvasPath, 'utf8'));
assert.ok(edges.length > 0);
assert.ok(Array.isArray(canvas.nodes));
assert.ok(Array.isArray(canvas.edges));
assert.ok(canvas.nodes.some((node) => node.id === 'summary'));

const nodeIds = new Set(canvas.nodes.map((node) => node.id));
for (const edge of canvas.edges) {
  assert.ok(nodeIds.has(edge.fromNode), `missing fromNode ${edge.fromNode}`);
  assert.ok(nodeIds.has(edge.toNode), `missing toNode ${edge.toNode}`);
}

console.log('  OK semantic resolver CLI writes parseable Canvas projection\n');
console.log('ALL SEMANTIC RESOLVER CANVAS TESTS PASSED');
