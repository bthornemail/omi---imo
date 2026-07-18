import assert from 'node:assert/strict';
import { mkdir, readFile, rm } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { join } from 'node:path';
import {
  EDGE_VERSION,
  EVENT_TYPE_LEMMAS,
  canvasFromEdges,
  resolveSemanticGraph
} from '../tools/semantic_resolver.mjs';

const repoRoot = new URL('..', import.meta.url).pathname;
const fixtureRoot = join(repoRoot, 'tests/fixtures/semantic-resolver');
const outDir = join(repoRoot, 'build/semantic-resolver-test');
const edgesPath = join(outDir, 'edges.jsonl');

function edgeKey(edge) {
  return `${edge.subject}|${edge.predicate}|${edge.object}|${edge.basis}|${edge.weight}`;
}

function hasEdge(edges, partial) {
  return edges.some((edge) => Object.entries(partial).every(([key, value]) => edge[key] === value));
}

console.log('Testing semantic resolver deterministic edge generation');

assert.deepEqual(EVENT_TYPE_LEMMAS, {
  tick: 'checkpoint',
  fragment: 'fragment',
  candidate: 'candidate',
  proof: 'proof',
  gossip: 'communication',
  reject: 'rejection',
  manual: 'note'
});

const first = await resolveSemanticGraph({
  root: fixtureRoot,
  trace: 'trace.jsonl',
  fallbackTrace: false,
  markdownTargets: ['README.md'],
  codeTargets: ['tools']
});
const second = await resolveSemanticGraph({
  root: fixtureRoot,
  trace: 'trace.jsonl',
  fallbackTrace: false,
  markdownTargets: ['README.md'],
  codeTargets: ['tools']
});

assert.deepEqual(first.edges, second.edges);
assert.ok(first.edges.length > 0);
assert.ok(first.edges.every((edge) => edge.v === EDGE_VERSION));
assert.equal(new Set(first.edges.map(edgeKey)).size, first.edges.length);

assert.ok(hasEdge(first.edges, { subject: 'trace:1', predicate: 'has-type', object: 'type:tick', basis: 'trace.type', weight: 1 }));
assert.ok(hasEdge(first.edges, { subject: 'trace:1', predicate: 'mentions', object: 'lemma:checkpoint', basis: 'event-type-taxonomy', weight: 1 }));
assert.ok(hasEdge(first.edges, { subject: 'trace:2', predicate: 'mentions', object: 'lemma:fragment', basis: 'event-type-taxonomy', weight: 1 }));
assert.ok(hasEdge(first.edges, { subject: 'trace:3', predicate: 'mentions', object: 'lemma:candidate', basis: 'event-type-taxonomy', weight: 1 }));
assert.ok(hasEdge(first.edges, { subject: 'trace:4', predicate: 'mentions', object: 'lemma:proof', basis: 'event-type-taxonomy', weight: 1 }));
assert.ok(hasEdge(first.edges, { subject: 'trace:5', predicate: 'mentions', object: 'lemma:communication', basis: 'event-type-taxonomy', weight: 1 }));
assert.ok(hasEdge(first.edges, { subject: 'trace:6', predicate: 'mentions', object: 'lemma:rejection', basis: 'event-type-taxonomy', weight: 1 }));
assert.ok(hasEdge(first.edges, { subject: 'trace:7', predicate: 'mentions', object: 'lemma:note', basis: 'event-type-taxonomy', weight: 1 }));
assert.ok(hasEdge(first.edges, { subject: 'trace:2', predicate: 'references-code', object: 'tools/semantic_resolver.mjs', basis: 'payload.code_path', weight: 1 }));
assert.ok(hasEdge(first.edges, { subject: 'trace:2', predicate: 'renders', object: 'canvas:trace-2', basis: 'generated-canvas', weight: 1 }));
assert.ok(hasEdge(first.edges, { subject: 'base:trace-2', predicate: 'indexes', object: 'trace:2', basis: 'generated-base', weight: 1 }));
assert.ok(hasEdge(first.edges, { subject: 'note:trace-2', predicate: 'documents', object: 'trace:2', basis: 'generated-note', weight: 1 }));
assert.ok(hasEdge(first.edges, { subject: 'markdown:README.md#resolver-heading', predicate: 'appears-in', object: 'README.md', basis: 'markdown-heading', weight: 1 }));
assert.ok(hasEdge(first.edges, { subject: 'markdown:README.md', predicate: 'mentions-code', object: 'tools/semantic_resolver.mjs', basis: 'markdown-term', weight: 0.25 }));
assert.ok(hasEdge(first.edges, { subject: 'code:tools/semantic_resolver.mjs', predicate: 'mentions', object: 'lemma:semantic-resolver', basis: 'code-path-token', weight: 0.25 }));
assert.ok(!first.edges.some((edge) => edge.basis === 'wordnet'), 'missing WordNet data should not fail or fabricate WordNet edges');

await rm(outDir, { recursive: true, force: true });
await mkdir(outDir, { recursive: true });
execFileSync('node', [
  'tools/semantic_resolver.mjs',
  '--root', fixtureRoot,
  '--trace', 'trace.jsonl',
  '--no-fallback-trace',
  '--edges', edgesPath
], { cwd: repoRoot, stdio: 'pipe' });
const writtenEdges = (await readFile(edgesPath, 'utf8')).trim().split('\n').map((line) => JSON.parse(line));
assert.deepEqual(writtenEdges, first.edges);

console.log('  OK semantic resolver emits deterministic fallback edges without WordNet\n');

console.log('Testing semantic resolver Canvas projection');
const canvas = canvasFromEdges(first.edges);
assert.ok(canvas.nodes.length > 0);
assert.ok(canvas.edges.length > 0);
const nodeIds = new Set(canvas.nodes.map((node) => node.id));
for (const edge of canvas.edges) {
  assert.ok(nodeIds.has(edge.fromNode), `missing fromNode ${edge.fromNode}`);
  assert.ok(nodeIds.has(edge.toNode), `missing toNode ${edge.toNode}`);
}

console.log('  OK semantic resolver Canvas projection is internally linked\n');
console.log('ALL SEMANTIC RESOLVER TESTS PASSED');
