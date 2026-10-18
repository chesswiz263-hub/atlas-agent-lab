
'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const root = path.resolve(__dirname, '../..');
const browser = path.join(root, 'docs', 'demo');
const engineLib = require(path.join(browser, 'engine.js'));

const ctx = { globalThis: {} };
vm.runInNewContext(
  fs.readFileSync(path.join(browser, 'corpus.js'), 'utf8'),
  ctx
);

const corpus = ctx.globalThis.AtlasCorpus;
const engine = engineLib.createEngine(corpus);

test('corpus matches the exact source Markdown paragraphs', () => {
  for (const doc of corpus) {
    const raw = fs.readFileSync(path.join(root, doc.source), 'utf8');
    const paras = raw
      .split(/\n\s*\n/g)
      .map(s => s.trim().replace(/\n/g, ' '))
      .filter(s => s && !s.startsWith('#'));

    assert.deepEqual(
      Array.from(doc.chunks, c => c.text),
      paras
    );
  }
});

test('public corpus ships only three reference docs, 12 passages', () => {
  assert.equal(corpus.length, 3);
  assert.equal(
    corpus.reduce((n, d) => n + d.chunks.length, 0),
    12
  );
  assert.ok(
    corpus.every(d =>
      d.source.startsWith('examples/knowledge/')
    )
  );
});

test('real BM25 search ranks expected source for all examples', () => {
  for (const item of engineLib.BENCHMARK) {
    assert.equal(
      engine.search(item.question)[0].docId,
      item.doc,
      item.question
    );
  }
});

test('source extracts exactly match real document text', () => {
  for (const item of engineLib.BENCHMARK) {
    const result = engine.run(item.question);

    assert.equal(result.isAbstention, false);
    assert.equal(result.audit.valid, true);
    assert.ok(result.evidence.length > 0);

    for (const cite of result.evidence) {
      const passage = corpus
        .flatMap(d => d.chunks)
        .find(c => c.id === cite.chunkId);

      assert.ok(passage.text.includes(cite.quote));
    }
  }
});

test('abstains on unrelated subjects, no invented sources', () => {
  const result = engine.run(
    'What is the weather forecast in Antarctica tomorrow?'
  );

  assert.equal(result.isAbstention, true);
  assert.equal(result.evidence.length, 0);
});

test('rejects blank and overlong queries', () => {
  assert.throws(
    () => engine.run('  '),
    /Enter a question/
  );
  assert.throws(
    () => engine.run('z'.repeat(321)),
    /320/
  );
  assert.throws(
    () => engine.run(null),
    /text/
  );
});

test('audit detects wrong or fabricated excerpt', () => {
  const valid = engine.run(
    engineLib.BENCHMARK[0].question
  ).evidence;

  assert.equal(engine.audit(valid).valid, true);

  assert.equal(
    engine.audit([
      {
        ...valid[0],
        quote: 'Not present in any source.'
      }
    ]).valid,
    false
  );

  assert.equal(
    engine.audit([
      {
        ...valid[0],
        chunkId: 'fabricated'
      }
    ]).valid,
    false
  );
});

test('deterministic duplicate input has identical evidence and trace', () => {
  const a = engine.run('How does MCP work?');
  const b = engine.run('How does MCP work?');

  assert.deepEqual(a, b);
  assert.equal(a.trace.length, 4);
});

test('six-case smoke benchmark is computed from actual queries', () => {
  const e = engine.evaluate();

  assert.equal(e.cases.length, 6);
  assert.equal(e.recallAt3, 1);
  assert.equal(e.citationPresence, 1);
  assert.match(e.disclaimer, /not a factuality/);
});

// Updated for ATLAS v2.0 public chat interface.
test('public UI contains explicit offline disclosure and safe local script references', () => {
  const docs = path.join(root, 'docs');
  const html = fs.readFileSync(
    path.join(docs, 'index.html'),
    'utf8'
  );

  // Ensure the public site clearly identifies demo limitations.
  assert.match(html, /not a live LLM/);

  // Verify the original v0.6 demo assets are retained.
  // They no longer need to be loaded by the new homepage.
  for (const asset of [
    'corpus.js',
    'engine.js',
    'app.js',
    'styles.css',
    'favicon.svg'
  ]) {
    assert.ok(
      fs.existsSync(path.join(browser, asset)),
      `Missing legacy demo asset: ${asset}`
    );
  }

  // Verify the redesigned ATLAS v2.0 homepage assets.
  for (const asset of [
    'atlas-chat.css',
    'atlas-chat.js'
  ]) {
    assert.ok(
      fs.existsSync(path.join(docs, asset)),
      `Missing ATLAS v2.0 asset: ${asset}`
    );

    assert.ok(
      html.includes('./' + asset),
      `Homepage does not reference: ${asset}`
    );
  }

  // Ensure no external script CDN is required.
  assert.doesNotMatch(
    html,
    /cdn\.|https:\/\/.*\.js/
  );
});

test('browser app renders dynamic text with textContent, not unsafe HTML', () => {
  const app = fs.readFileSync(
    path.join(browser, 'app.js'),
    'utf8'
  );

  assert.match(app, /\.textContent/);

  assert.doesNotMatch(
    app,
    /innerHTML|eval\s*\(|localStorage|sessionStorage|fetch\s*\(/
  );
});

test('source markdown links cannot be injected from a query', () => {
  const injected = '<img src=x onerror=alert(1)>';
  const out = engine.run(injected);

  assert.ok(
    out.evidence.every(
      item => !item.quote.includes('<img')
    )
  );

  assert.equal(out.audit.valid, true);
});

