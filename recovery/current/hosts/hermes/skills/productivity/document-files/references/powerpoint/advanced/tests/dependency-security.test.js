const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

test('all upstream non-manifest files remain byte-identical', () => {
  const provenance = JSON.parse(fs.readFileSync(path.join(__dirname, '../vendor/provenance.json'), 'utf8'));
  const packageRoot = path.resolve(path.dirname(require.resolve('pptxgenjs')), '..');
  for (const [relative, expected] of Object.entries(provenance.unchanged_files_sha256)) {
    const actual = crypto.createHash('sha256').update(fs.readFileSync(path.join(packageRoot, relative))).digest('hex');
    assert.equal(actual, expected, relative);
  }
  const manifest = JSON.parse(fs.readFileSync(path.join(packageRoot, 'package.json'), 'utf8'));
  assert.deepEqual(manifest.dependencies, provenance.repacked_dependencies);
});

test('installed production graph does not contain the vulnerable image-size parsers', () => {
  const lock = JSON.parse(fs.readFileSync(path.join(__dirname, '../package-lock.json'), 'utf8'));
  assert.equal(Object.keys(lock.packages).some(key => /(^|\/)node_modules\/image-size$/.test(key)), false);
  const packageRoot = path.resolve(path.dirname(require.resolve('pptxgenjs')), '..');
  const manifest = JSON.parse(fs.readFileSync(path.join(packageRoot, 'package.json'), 'utf8'));
  assert.equal(Object.hasOwn(manifest.dependencies, 'image-size'), false);
  assert.throws(() => require.resolve('image-size', { paths: [path.dirname(require.resolve('pptxgenjs'))] }), { code: 'MODULE_NOT_FOUND' });
});

test('unchanged PptxGenJS can construct a deck without the removed dependency', async () => {
  const PptxGenJS = require('pptxgenjs');
  const deck = new PptxGenJS();
  deck.addSlide().addText('Dependency-removal regression', { x: 1, y: 1, w: 8, h: 1 });
  const bytes = await deck.write({ outputType: 'nodebuffer' });
  assert.equal(bytes.subarray(0, 2).toString(), 'PK');
});
