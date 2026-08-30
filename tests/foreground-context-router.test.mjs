import assert from 'node:assert/strict'
import fs from 'node:fs/promises'
import path from 'node:path'
import test from 'node:test'
import vm from 'node:vm'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const pluginPath = path.join(here, '..', 'integrations', 'hermes', 'foreground-context-router', 'desktop', 'plugin.js')

async function loadPlugin(overrides = {}) {
  const source = await fs.readFile(pluginPath, 'utf8')
  const calls = []
  let openAttempts = 0
  const host = {
    state: {
      cwd: { get: () => 'C:/repo' },
      focusedSessionId: { get: () => 'runtime-current' },
      focusedStoredSessionId: { get: () => 'stored-current' },
      model: { get: () => 'gpt-5.6-sol' },
      profile: { get: () => 'default' },
      focusedUsage: { get: () => ({ context_percent: 0.1 }) },
    },
    request: async (method, params) => {
      calls.push([method, params])
      if (method === overrides.failMethod) throw new Error(`${method} failed`)
      if (method === 'session.history') return { messages: [] }
      if (method === 'session.create') return { session_id: 'runtime-new', stored_session_id: 'stored-new' }
      if (method === 'prompt.submit') return { status: 'streaming' }
      if (method === 'session.close') return { ok: true }
      throw new Error(`unexpected method ${method}`)
    },
    openSession: async (id, options) => {
      calls.push(['openSession', { id, options }])
      openAttempts += 1
      if (openAttempts <= Number(overrides.openFailures || 0)) throw new Error('navigation failed')
    },
    notify: payload => calls.push(['notify', payload]),
    ...overrides.host,
  }
  const context = vm.createContext({ console, setTimeout, clearTimeout })
  const module = new vm.SourceTextModule(source, { context, identifier: pluginPath })
  await module.link(async specifier => {
    if (specifier !== '@hermes/plugin-sdk') throw new Error(`unexpected import ${specifier}`)
    const sdk = new vm.SyntheticModule(
      ['COMPOSER_AREAS', 'PALETTE_AREA', 'host'],
      function () {
        this.setExport('COMPOSER_AREAS', { middleware: 'composer.middleware' })
        this.setExport('PALETTE_AREA', 'palette')
        this.setExport('host', host)
      },
      { context }
    )
    await sdk.evaluate()
    return sdk
  })
  await module.evaluate()
  return { namespace: module.namespace, plugin: module.namespace.default, host, calls }
}

function context(restResult) {
  const contributions = []
  const storage = new Map()
  return {
    contributions,
    ctx: {
      register: contribution => contributions.push(contribution),
      registerMany: items => contributions.push(...items),
      rest: async () => restResult,
      storage: {
        get: (key, fallback) => storage.has(key) ? storage.get(key) : fallback,
        set: (key, value) => storage.set(key, value),
        remove: key => storage.delete(key),
      },
    },
  }
}

test('routeAction is conservative and isolates clearly new topics', async () => {
  const { namespace } = await loadPlugin()
  assert.equal(namespace.routeAction('normal', { context_need: 'extended', topic_relation: 'same', confidence: 0.9 }, false), 'new_extended')
  assert.equal(namespace.routeAction('extended', { context_need: 'normal', topic_relation: 'new', confidence: 0.9 }, false), 'new_normal')
  assert.equal(namespace.routeAction('extended', { context_need: 'extended', topic_relation: 'new', confidence: 0.9 }, false), 'new_extended')
  assert.equal(namespace.routeAction('extended', { context_need: 'normal', topic_relation: 'same', confidence: 0.99 }, false), 'stay')
  assert.equal(namespace.routeAction('normal', { context_need: 'extended', topic_relation: 'same', confidence: 0.7 }, false), 'stay')
  assert.equal(namespace.routeAction('normal', { context_need: 'extended', topic_relation: 'same', confidence: 0.99 }, true), 'stay')
})

test('obvious ordinary chat bypasses the model classifier', async () => {
  const { namespace } = await loadPlugin()
  assert.equal(namespace.shouldClassify('thanks!', 'normal'), false)
  assert.equal(namespace.shouldClassify('how are you?', 'normal'), false)
  assert.equal(namespace.shouldClassify('audit every package in this repository and implement the fixes', 'normal'), true)
  assert.equal(namespace.shouldClassify('new question: what is TCP slow start?', 'extended'), true)
})

test('extended decision creates, submits, and foreground-opens a fixed extended session', async () => {
  const loaded = await loadPlugin()
  const fixture = context({ context_need: 'extended', topic_relation: 'same', confidence: 0.93, title: 'Repository audit' })
  loaded.plugin.register(fixture.ctx)
  const middleware = fixture.contributions.find(item => item.area === 'composer.middleware')
  const draft = { text: 'Audit every package in this repository and implement all verified fixes' }

  assert.equal(await middleware.data.handler(draft), null)
  const create = loaded.calls.find(([method]) => method === 'session.create')
  assert.equal(create[1].model, 'gpt-5.6-sol-900k')
  assert.equal(create[1].provider, 'openai-codex')
  assert.equal(create[1].parent_session_id, 'stored-current')
  assert.deepEqual(loaded.calls.map(([method]) => method), ['session.history', 'session.create', 'openSession', 'prompt.submit', 'notify'])
})

test('classifier or route failure passes the original message through', async () => {
  const loaded = await loadPlugin()
  const fixture = context({ context_need: 'extended', topic_relation: 'same', confidence: 0.95 })
  fixture.ctx.rest = async () => { throw new Error('classifier unavailable') }
  loaded.plugin.register(fixture.ctx)
  const middleware = fixture.contributions.find(item => item.area === 'composer.middleware')
  const draft = { text: 'Audit every package in this repository' }
  assert.equal(await middleware.data.handler(draft), draft)
  assert.equal(loaded.calls.some(([method]) => method === 'session.create'), false)
})

test('lazy destinations retry foreground open once after submit persistence', async () => {
  const loaded = await loadPlugin({ openFailures: 1 })
  const fixture = context({ context_need: 'extended', topic_relation: 'same', confidence: 0.95 })
  loaded.plugin.register(fixture.ctx)
  const middleware = fixture.contributions.find(item => item.area === 'composer.middleware')
  const draft = { text: 'Audit every package in this repository' }

  assert.equal(await middleware.data.handler(draft), null)
  assert.deepEqual(
    loaded.calls.map(([method]) => method),
    ['session.history', 'session.create', 'openSession', 'prompt.submit', 'openSession', 'notify']
  )
  assert.equal(loaded.calls.filter(([method]) => method === 'prompt.submit').length, 1)
  assert.equal(loaded.calls.at(-1)[1].kind, 'info')
})

test('a successful submit is consumed even when both foreground opens fail', async () => {
  const loaded = await loadPlugin({ openFailures: 2 })
  const fixture = context({ context_need: 'extended', topic_relation: 'same', confidence: 0.95 })
  loaded.plugin.register(fixture.ctx)
  const middleware = fixture.contributions.find(item => item.area === 'composer.middleware')
  const draft = { text: 'Audit every package in this repository' }

  assert.equal(await middleware.data.handler(draft), null)
  assert.equal(loaded.calls.filter(([method]) => method === 'prompt.submit').length, 1)
  assert.equal(loaded.calls.filter(([method]) => method === 'openSession').length, 2)
  assert.equal(loaded.calls.some(([method]) => method === 'session.close'), false)
  assert.equal(loaded.calls.at(-1)[1].kind, 'warning')
})

test('an ambiguous submit failure is consumed and never duplicated in the origin', async () => {
  const loaded = await loadPlugin({ failMethod: 'prompt.submit' })
  const fixture = context({ context_need: 'extended', topic_relation: 'same', confidence: 0.95 })
  loaded.plugin.register(fixture.ctx)
  const middleware = fixture.contributions.find(item => item.area === 'composer.middleware')
  const draft = { text: 'Audit every package in this repository' }

  assert.equal(await middleware.data.handler(draft), null)
  assert.equal(loaded.calls.filter(([method]) => method === 'prompt.submit').length, 1)
  assert.equal(loaded.calls.filter(([method]) => method === 'session.close').length, 0)
  assert.equal(loaded.calls.filter(([method]) => method === 'openSession').length, 1)
  assert.equal(loaded.calls.at(-1)[1].kind, 'warning')
})

test('a pre-submit create failure passes the original draft through', async () => {
  const loaded = await loadPlugin({ failMethod: 'session.create' })
  const fixture = context({ context_need: 'extended', topic_relation: 'same', confidence: 0.95 })
  loaded.plugin.register(fixture.ctx)
  const middleware = fixture.contributions.find(item => item.area === 'composer.middleware')
  const draft = { text: 'Audit every package in this repository' }

  assert.equal(await middleware.data.handler(draft), draft)
  assert.equal(loaded.calls.some(([method]) => method === 'prompt.submit'), false)
  assert.equal(loaded.calls.some(([method]) => method === 'openSession'), false)
})

test('attachments are never swallowed or moved by the router', async () => {
  const loaded = await loadPlugin()
  const fixture = context({ context_need: 'extended', topic_relation: 'same', confidence: 0.99 })
  loaded.plugin.register(fixture.ctx)
  const middleware = fixture.contributions.find(item => item.area === 'composer.middleware')
  const draft = { text: 'Audit this repository', attachments: [{ id: 'a1' }] }
  assert.equal(await middleware.data.handler(draft), draft)
  assert.equal(loaded.calls.length, 0)
})
