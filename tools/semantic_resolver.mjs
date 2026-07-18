#!/usr/bin/env node

import { fileURLToPath } from 'node:url';
import { mkdir, readdir, readFile, stat, writeFile } from 'node:fs/promises';
import { dirname, extname, join, resolve } from 'node:path';

export const EDGE_VERSION = 'omi.semantic.edge.v0';
export const EVENT_TYPE_LEMMAS = Object.freeze({
  tick: 'checkpoint',
  fragment: 'fragment',
  candidate: 'candidate',
  proof: 'proof',
  gossip: 'communication',
  reject: 'rejection',
  manual: 'note'
});

const SKIP_DIRS = new Set(['.git', 'node_modules', 'Archive', 'packages', 'OMI', 'build']);
const MARKDOWN_EXTENSIONS = new Set(['.md']);
const CODE_EXTENSIONS = new Set(['.js', '.mjs', '.ts', '.mts', '.json', '.janet', '.pl', '.py', '.c', '.h']);
const MARKDOWN_TARGETS = ['README.md', 'AGENTS.md', 'docs', 'declarations'];
const CODE_TARGETS = ['src', 'test', 'tests', 'bin', 'tools', 'examples', 'golden', 'workbench/src', 'package.json'];

function orderedEdge(edge) {
  return {
    v: EDGE_VERSION,
    subject: edge.subject,
    predicate: edge.predicate,
    object: edge.object,
    basis: edge.basis,
    weight: edge.weight ?? 1
  };
}

function addEdge(edges, edge) {
  if (!edge.subject || !edge.predicate || !edge.object) return;
  const ordered = orderedEdge(edge);
  edges.set(JSON.stringify(ordered), ordered);
}

export function tokenSet(text) {
  const tokens = String(text || '').toLowerCase().match(/[a-z][a-z0-9_-]{2,}/g) ?? [];
  return [...new Set(tokens.map((token) => token.replace(/_/g, '-')))];
}

export function slug(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80) || 'item';
}

export async function readJsonl(path) {
  let raw = '';
  try {
    raw = await readFile(path, 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT') return [];
    throw error;
  }

  return raw.split('\n').map((line, index) => {
    const trimmed = line.trim();
    if (!trimmed) return null;
    try {
      return { ok: true, index: index + 1, event: JSON.parse(trimmed), raw: trimmed };
    } catch (error) {
      return { ok: false, index: index + 1, error: String(error), raw: trimmed };
    }
  }).filter(Boolean);
}

async function collectFiles(root, targets, accept) {
  const files = [];

  async function visit(rel) {
    let info;
    try {
      info = await stat(join(root, rel));
    } catch {
      return;
    }

    if (info.isFile()) {
      if (accept(rel)) files.push(rel);
      return;
    }

    if (!info.isDirectory()) return;

    const entries = await readdir(join(root, rel), { withFileTypes: true });
    for (const entry of entries) {
      if (entry.isDirectory() && SKIP_DIRS.has(entry.name)) continue;
      await visit(join(rel, entry.name));
    }
  }

  for (const target of targets) {
    await visit(target);
  }

  return [...new Set(files)].sort();
}

export async function indexMarkdown(root, targets = MARKDOWN_TARGETS) {
  const files = await collectFiles(root, targets, (path) => MARKDOWN_EXTENSIONS.has(extname(path)));
  const docs = [];

  for (const path of files) {
    const text = await readFile(join(root, path), 'utf8');
    const headings = [...text.matchAll(/^(#{1,6})\s+(.+)$/gm)].map((match) => match[2].trim());
    docs.push({ path, headings, terms: tokenSet(`${path}\n${headings.join('\n')}\n${text.slice(0, 4000)}`) });
  }

  return docs;
}

export async function indexCodebase(root, targets = CODE_TARGETS) {
  const files = await collectFiles(root, targets, (path) => CODE_EXTENSIONS.has(extname(path)));
  return files.map((path) => ({
    path,
    terms: tokenSet(path.replace(/\.[^.]+$/, '').replace(/[/-]/g, ' '))
  }));
}

function payloadCodePaths(payload) {
  const paths = [];
  const keys = new Set(['code_path', 'codePath', 'file', 'path', 'test', 'source']);

  function visit(value) {
    if (!value || typeof value !== 'object') return;
    for (const [key, child] of Object.entries(value)) {
      if (typeof child === 'string' && keys.has(key) && CODE_EXTENSIONS.has(extname(child))) {
        paths.push(child);
      } else if (Array.isArray(child)) {
        child.forEach(visit);
      } else if (child && typeof child === 'object') {
        visit(child);
      }
    }
  }

  visit(payload);
  return [...new Set(paths)];
}

function unquoteAtom(value) {
  return String(value).replace(/''/g, "'");
}

async function readOptional(path) {
  try {
    return await readFile(path, 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}

async function loadWordIndex(root) {
  const base = join(root, 'packages/WNprolog-3.0/prolog');
  const [sRaw, gRaw, hypRaw, skRaw] = await Promise.all([
    readOptional(join(base, 'wn_s.pl')),
    readOptional(join(base, 'wn_g.pl')),
    readOptional(join(base, 'wn_hyp.pl')),
    readOptional(join(base, 'wn_sk.pl'))
  ]);

  if (!sRaw || !gRaw || !hypRaw || !skRaw) {
    return {
      sensesByLemma: new Map(),
      wordBySynset: new Map(),
      glossBySynset: new Map(),
      hypernymsBySynset: new Map(),
      senseKeyBySynsetWord: new Map()
    };
  }

  const sensesByLemma = new Map();
  const wordBySynset = new Map();
  const sPattern = /^s\((\d+),(\d+),'((?:''|[^'])*)',([a-z]),(\d+),(\d+)\)\.$/gm;
  for (const match of sRaw.matchAll(sPattern)) {
    const synsetId = Number(match[1]);
    const wordNumber = Number(match[2]);
    const lemma = unquoteAtom(match[3]);
    const sense = {
      lemma,
      synset_id: synsetId,
      word_number: wordNumber,
      ss_type: match[4],
      sense_number: Number(match[5]),
      tag_count: Number(match[6])
    };

    if (!sensesByLemma.has(lemma)) sensesByLemma.set(lemma, []);
    sensesByLemma.get(lemma).push(sense);
    if (!wordBySynset.has(synsetId)) wordBySynset.set(synsetId, lemma);
  }

  const glossBySynset = new Map();
  const gPattern = /^g\((\d+),'((?:''|[^'])*)'\)\.$/gm;
  for (const match of gRaw.matchAll(gPattern)) {
    glossBySynset.set(Number(match[1]), unquoteAtom(match[2]));
  }

  const hypernymsBySynset = new Map();
  const hypPattern = /^hyp\((\d+),(\d+)\)\.$/gm;
  for (const match of hypRaw.matchAll(hypPattern)) {
    const from = Number(match[1]);
    const to = Number(match[2]);
    if (!hypernymsBySynset.has(from)) hypernymsBySynset.set(from, []);
    hypernymsBySynset.get(from).push(to);
  }

  const senseKeyBySynsetWord = new Map();
  const skPattern = /^sk\((\d+),(\d+),'((?:''|[^'])*)'\)\.$/gm;
  for (const match of skRaw.matchAll(skPattern)) {
    senseKeyBySynsetWord.set(`${match[1]}:${match[2]}`, unquoteAtom(match[3]));
  }

  return { sensesByLemma, wordBySynset, glossBySynset, hypernymsBySynset, senseKeyBySynsetWord };
}

export async function lookupWordNetLemmas(root, lemmas) {
  const unique = [...new Set(lemmas.map((lemma) => String(lemma || '').trim()).filter(Boolean))];
  const index = await loadWordIndex(root);
  const out = {};

  for (const lemma of unique) {
    const senses = index.sensesByLemma.get(lemma) ?? [];
    const sense = senses[0];
    if (!sense) {
      out[lemma] = null;
      continue;
    }

    const hypernyms = (index.hypernymsBySynset.get(sense.synset_id) ?? []).map((synsetId) => ({
      synset_id: synsetId,
      word: index.wordBySynset.get(synsetId) ?? ''
    }));

    out[lemma] = {
      lemma: sense.lemma,
      synset_id: sense.synset_id,
      word_number: sense.word_number,
      ss_type: sense.ss_type,
      sense_number: sense.sense_number,
      sense_key: index.senseKeyBySynsetWord.get(`${sense.synset_id}:${sense.word_number}`) ?? '',
      gloss: index.glossBySynset.get(sense.synset_id) ?? '',
      hypernyms
    };
  }

  return out;
}

export async function enrichEventTypes(root, types) {
  const eventTypes = [...new Set(types.map((type) => String(type || 'event')))];
  const lemmas = eventTypes.map((type) => EVENT_TYPE_LEMMAS[type]).filter(Boolean);
  const wordnetByLemma = await lookupWordNetLemmas(root, lemmas);
  const result = {};

  for (const eventType of eventTypes) {
    const lemma = EVENT_TYPE_LEMMAS[eventType];
    result[eventType] = lemma
      ? { lemma, wordnet: wordnetByLemma[lemma] ?? null }
      : { lemma: null, wordnet: null };
  }

  return result;
}

export async function buildEdges({ root, traceEntries, markdownDocs, codeFiles }) {
  const edges = new Map();
  const validTrace = traceEntries.filter((entry) => entry.ok);
  const eventEnrichment = await enrichEventTypes(root, validTrace.map((entry) => entry.event.type));
  const lemmaCandidates = new Set(Object.values(EVENT_TYPE_LEMMAS));

  for (const entry of validTrace) {
    const event = entry.event;
    const traceId = `trace:${entry.index}`;
    const type = String(event.type || 'event');
    const enrichment = eventEnrichment[type];

    addEdge(edges, { subject: traceId, predicate: 'has-type', object: `type:${type}`, basis: 'trace.type' });
    addEdge(edges, { subject: traceId, predicate: 'renders', object: `canvas:trace-${entry.index}`, basis: 'generated-canvas' });
    addEdge(edges, { subject: `base:trace-${entry.index}`, predicate: 'indexes', object: traceId, basis: 'generated-base' });
    addEdge(edges, { subject: `note:trace-${entry.index}`, predicate: 'documents', object: traceId, basis: 'generated-note' });

    if (enrichment?.lemma) {
      addEdge(edges, { subject: traceId, predicate: 'mentions', object: `lemma:${enrichment.lemma}`, basis: 'event-type-taxonomy' });
      lemmaCandidates.add(enrichment.lemma);
    }

    for (const token of tokenSet(`${event.summary || ''} ${JSON.stringify(event.payload ?? {})}`)) {
      if (EVENT_TYPE_LEMMAS[token]) continue;
      if (['fragment', 'candidate', 'proof', 'gossip', 'reject', 'manual', 'checkpoint', 'communication', 'rejection', 'note'].includes(token)) {
        addEdge(edges, { subject: traceId, predicate: 'mentions', object: `lemma:${token}`, basis: 'summary-token', weight: 0.5 });
        lemmaCandidates.add(token);
      }
    }

    for (const codePath of payloadCodePaths(event.payload ?? {})) {
      addEdge(edges, { subject: traceId, predicate: 'references-code', object: codePath, basis: 'payload.code_path' });
    }
  }

  for (const doc of markdownDocs) {
    for (const heading of doc.headings) {
      addEdge(edges, {
        subject: `markdown:${doc.path}#${slug(heading)}`,
        predicate: 'appears-in',
        object: doc.path,
        basis: 'markdown-heading'
      });
    }

    for (const code of codeFiles) {
      if (doc.terms.includes(code.path.toLowerCase()) || doc.terms.some((term) => code.terms.includes(term))) {
        addEdge(edges, {
          subject: `markdown:${doc.path}`,
          predicate: 'mentions-code',
          object: code.path,
          basis: 'markdown-term',
          weight: 0.25
        });
      }
    }
  }

  for (const code of codeFiles) {
    for (const term of code.terms.slice(0, 5)) {
      if (term.length >= 4) {
        addEdge(edges, { subject: `code:${code.path}`, predicate: 'mentions', object: `lemma:${term}`, basis: 'code-path-token', weight: 0.25 });
        lemmaCandidates.add(term);
      }
    }
  }

  const wordnet = await lookupWordNetLemmas(root, [...lemmaCandidates]);
  for (const [lemma, meta] of Object.entries(wordnet)) {
    if (!meta) continue;
    const sense = `wn:${lemma}.${meta.ss_type}.${String(meta.sense_number).padStart(2, '0')}`;
    addEdge(edges, { subject: `lemma:${lemma}`, predicate: 'sense', object: sense, basis: 'wordnet' });
    for (const hypernym of meta.hypernyms ?? []) {
      addEdge(edges, {
        subject: sense,
        predicate: 'hypernym',
        object: `wn:${hypernym.synset_id}`,
        basis: 'wordnet',
        weight: 0.75
      });
    }
  }

  return [...edges.values()].sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));
}

export function canvasFromEdges(edges, generatedAt = 'deterministic') {
  const subjects = [...new Set(edges.flatMap((edge) => [edge.subject, edge.object]).filter((id) => /^(trace|lemma|wn|code|markdown):/.test(id)))].slice(0, 80);
  const nodeIds = new Map(subjects.map((subject, index) => [subject, `n${index}`]));
  const nodes = subjects.map((subject, index) => ({
    id: nodeIds.get(subject),
    type: 'text',
    text: subject,
    x: (index % 4) * 360,
    y: Math.floor(index / 4) * 180,
    width: 300,
    height: 110,
    color: subject.startsWith('trace:') ? '1' : subject.startsWith('lemma:') ? '2' : subject.startsWith('wn:') ? '5' : subject.startsWith('code:') ? '4' : '6'
  }));

  nodes.unshift({
    id: 'summary',
    type: 'text',
    text: `OMI Semantic Lattice\nGenerated: ${generatedAt}\nEdges: ${edges.length}`,
    x: -380,
    y: 0,
    width: 320,
    height: 140,
    color: '3'
  });

  const canvasEdges = edges
    .filter((edge) => nodeIds.has(edge.subject) && nodeIds.has(edge.object))
    .slice(0, 160)
    .map((edge, index) => ({
      id: `e${index}`,
      fromNode: nodeIds.get(edge.subject),
      fromSide: 'right',
      toNode: nodeIds.get(edge.object),
      toSide: 'left',
      label: edge.predicate
    }));

  return { nodes, edges: canvasEdges };
}

export async function resolveSemanticGraph(options = {}) {
  const root = resolve(options.root || process.cwd());
  const tracePath = resolve(root, options.trace || 'trace.jsonl');
  const fallbackTracePath = resolve(root, options.fallbackTrace || 'tests/fixtures/semantic-resolver/trace.jsonl');
  let traceEntries = await readJsonl(tracePath);
  if (traceEntries.length === 0 && options.fallbackTrace !== false) {
    traceEntries = await readJsonl(fallbackTracePath);
  }

  const [markdownDocs, codeFiles] = await Promise.all([
    indexMarkdown(root, options.markdownTargets || MARKDOWN_TARGETS),
    indexCodebase(root, options.codeTargets || CODE_TARGETS)
  ]);
  const edges = await buildEdges({ root, traceEntries, markdownDocs, codeFiles });
  return { root, tracePath, traceEntries, markdownDocs, codeFiles, edges };
}

export async function writeEdges(path, edges) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${edges.map((edge) => JSON.stringify(edge)).join('\n')}\n`);
}

export async function writeCanvas(path, canvas) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(canvas, null, 2)}\n`);
}

function parseArgs(argv) {
  const args = {
    root: process.cwd(),
    trace: 'trace.jsonl',
    fallbackTrace: 'tests/fixtures/semantic-resolver/trace.jsonl',
    edges: 'build/semantic-resolver/Semantic Edges.jsonl',
    canvas: 'build/semantic-resolver/Semantic Lattice.canvas',
    emitCanvas: false,
    print: false
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--canvas') {
      args.emitCanvas = true;
    } else if (arg === '--all') {
      args.emitCanvas = true;
    } else if (arg === '--print') {
      args.print = true;
    } else if (arg === '--root') {
      args.root = argv[++index];
    } else if (arg === '--trace') {
      args.trace = argv[++index];
    } else if (arg === '--fallback-trace') {
      args.fallbackTrace = argv[++index];
    } else if (arg === '--no-fallback-trace') {
      args.fallbackTrace = false;
    } else if (arg === '--edges') {
      args.edges = argv[++index];
    } else if (arg === '--canvas-path') {
      args.canvas = argv[++index];
    } else {
      throw new Error(`unknown argument: ${arg}`);
    }
  }

  return args;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const result = await resolveSemanticGraph(args);
  const edgesPath = resolve(result.root, args.edges);
  await writeEdges(edgesPath, result.edges);

  if (args.emitCanvas) {
    const canvasPath = resolve(result.root, args.canvas);
    await writeCanvas(canvasPath, canvasFromEdges(result.edges, 'deterministic'));
  }

  if (args.print) {
    for (const edge of result.edges) console.log(JSON.stringify(edge));
    return;
  }

  const validTraceCount = result.traceEntries.filter((entry) => entry.ok).length;
  console.log(`resolved ${result.edges.length} semantic edges from ${validTraceCount} trace events`);
  console.log(`wrote ${edgesPath}`);
  if (args.emitCanvas) console.log(`wrote ${resolve(result.root, args.canvas)}`);
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  main().catch((error) => {
    console.error(error.stack || error.message);
    process.exit(1);
  });
}
