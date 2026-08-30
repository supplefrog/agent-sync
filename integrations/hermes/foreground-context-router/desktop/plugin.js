import { COMPOSER_AREAS, PALETTE_AREA, host } from '@hermes/plugin-sdk'

const ID = 'foreground-context-router'
const NORMAL_MODEL = 'gpt-5.6-sol'
const EXTENDED_MODEL = 'gpt-5.6-sol-900k'
const PROVIDER = 'openai-codex'
const MIN_CONFIDENCE = 0.75
const TASK_PATTERN = /\b(audit|refactor|migrate|rewrite|research|investigate|debug|build|implement|fix|analy[sz]e|review|compare|test|deploy|inspect|search|trace|benchmark|reconcile)\b/i
const EXTENDED_PATTERN = /\b(entire|whole|repository[- ]wide|across (?:the )?repo|all (?:files|packages|modules|documents)|large codebase|comprehensive|end[- ]to[- ]end|many documents|broad refactor|full audit)\b/i

export function shouldClassify(text, currentMode) {
  const value = String(text || '').trim()
  if (!value || value.startsWith('/')) return false
  if (currentMode === 'extended') return true
  return value.length >= 240 || EXTENDED_PATTERN.test(value) || TASK_PATTERN.test(value)
}

export function routeAction(currentMode, decision, hasAttachments) {
  if (hasAttachments || !decision || Number(decision.confidence || 0) < MIN_CONFIDENCE) return 'stay'
  const need = decision.context_need
  const relation = decision.topic_relation
  if (!['normal', 'extended'].includes(need) || !['same', 'new'].includes(relation)) return 'stay'
  if (currentMode === 'normal') return need === 'extended' ? 'new_extended' : 'stay'
  if (relation !== 'new') return 'stay'
  return need === 'extended' ? 'new_extended' : 'new_normal'
}

function messageText(message) {
  if (typeof message?.content === 'string') return message.content
  if (!Array.isArray(message?.parts)) return ''
  return message.parts
    .filter(part => part?.type === 'text' && typeof part.text === 'string')
    .map(part => part.text)
    .join('\n')
}

export function boundedHistory(messages, maxChars = 12000) {
  if (!Array.isArray(messages)) return []
  const selected = []
  let used = 0
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i]
    const role = String(message?.role || '').toLowerCase()
    if (role !== 'user' && role !== 'assistant') continue
    const content = messageText(message).trim().slice(0, 4000)
    if (!content) continue
    if (used + content.length > maxChars) break
    selected.push({ role, content })
    used += content.length
  }
  selected.reverse()
  const repaired = []
  for (const message of selected) {
    const previous = repaired.at(-1)
    if (previous?.role === message.role) previous.content = `${previous.content}\n\n${message.content}`
    else repaired.push(message)
  }
  while (repaired[0]?.role === 'assistant') repaired.shift()
  return repaired
}

function modeForSession(ctx) {
  const storedId = host.state.focusedStoredSessionId.get()
  const pinned = storedId ? ctx.storage.get(`mode:${storedId}`, '') : ''
  if (pinned === 'normal' || pinned === 'extended') return pinned
  return String(host.state.model.get() || '').includes('-900k') ? 'extended' : 'normal'
}

async function recentHistory() {
  const runtimeId = host.state.focusedSessionId.get()
  if (!runtimeId) return []
  try {
    const result = await host.request('session.history', { session_id: runtimeId })
    return boundedHistory(result?.messages || [])
  } catch {
    return []
  }
}

function destinationTitle(mode, decision) {
  const title = String(decision?.title || '').trim().slice(0, 60)
  if (mode === 'extended') return title ? `Extended · ${title}` : 'Extended-context task'
  return title || undefined
}

async function createDestination(ctx, draft, currentMode, action, decision, history) {
  const targetMode = action === 'new_extended' ? 'extended' : 'normal'
  const targetModel = targetMode === 'extended' ? EXTENDED_MODEL : NORMAL_MODEL
  const sourceStoredId = host.state.focusedStoredSessionId.get()
  const carryHistory = currentMode === 'normal' && targetMode === 'extended' && decision.topic_relation === 'same'
  const seed = carryHistory ? boundedHistory(history) : []
  const params = {
    cols: 96,
    source: 'desktop',
    cwd: String(host.state.cwd.get() || '').trim(),
    provider: PROVIDER,
    model: targetModel,
    title: destinationTitle(targetMode, decision),
    ...(seed.length ? { messages: seed } : {}),
    ...(carryHistory && sourceStoredId ? { parent_session_id: sourceStoredId } : {}),
  }

  let created = null
  let submitAttempted = false
  let opened = false
  try {
    created = await host.request('session.create', params)
    if (!created?.session_id || !created?.stored_session_id) throw new Error('session.create returned no destination')
    ctx.storage.set(`mode:${created.stored_session_id}`, targetMode)

    // Match Hermes Bot Mode's lazy-session lifecycle: mount first so streaming
    // output has a visible owner; if the row does not exist yet, retry after the
    // first prompt persists it.
    try {
      await host.openSession(created.stored_session_id, { intent: 'in-place' })
      opened = true
    } catch {
      // prompt.submit below materializes the lazy stored row.
    }

    submitAttempted = true
    await host.request('prompt.submit', { session_id: created.session_id, text: draft.text })

    if (!opened) {
      try {
        await host.openSession(created.stored_session_id, {
          intent: 'in-place',
          awaitHydration: true,
          expectHistory: true,
          retryHydrationTimeoutOnce: true,
        })
        opened = true
      } catch {
        // The task is already submitted; preserve exactly-once behavior and let
        // the user recover it from Sessions rather than duplicating the prompt.
      }
    }

    host.notify({
      kind: opened ? 'info' : 'warning',
      message: opened
        ? (targetMode === 'extended'
            ? 'Opened an extended-context chat for this task.'
            : 'Opened a fresh normal-context chat for the new topic.')
        : 'The routed task started, but its chat could not be opened automatically.',
    })
    return true
  } catch {
    if (submitAttempted) {
      // A transport error after dispatch is ambiguous: the gateway may have
      // accepted the prompt. Never send it again in the origin session.
      if (!opened && created?.stored_session_id) {
        await host.openSession(created.stored_session_id, {
          intent: 'in-place',
          awaitHydration: true,
          retryHydrationTimeoutOnce: true,
        }).catch(() => undefined)
      }
      host.notify({
        kind: 'warning',
        message: 'The routed submit status is uncertain; the original was not sent twice. Check the destination chat or return here to retry.',
      })
      return true
    }
    if (created?.session_id) {
      await host.request('session.close', { session_id: created.session_id }).catch(() => undefined)
    }
    return false
  }
}

async function handleDraft(ctx, draft) {
  if (draft?.attachments?.length) return draft
  const currentMode = modeForSession(ctx)
  if (!shouldClassify(draft?.text, currentMode)) return draft
  const history = await recentHistory()
  let decision
  try {
    decision = await ctx.rest('/classify', {
      method: 'POST',
      body: { text: draft.text, current_mode: currentMode, recent_messages: history },
      timeoutMs: 35000,
    })
  } catch {
    return draft
  }
  const action = routeAction(currentMode, decision, false)
  if (action === 'stay') return draft
  return (await createDestination(ctx, draft, currentMode, action, decision, history)) ? null : draft
}

export default {
  id: ID,
  name: 'Foreground Context Router',
  register(ctx) {
    ctx.registerMany([
      {
        id: 'route-before-send',
        area: COMPOSER_AREAS.middleware,
        order: 20,
        data: { handler: draft => handleDraft(ctx, draft) },
      },
      {
        id: 'status',
        area: PALETTE_AREA,
        data: {
          id: 'foreground-context-router.status',
          label: 'Context router: show current chat mode',
          keywords: ['context', 'router', 'extended'],
          run: () => host.notify({
            kind: 'info',
            message: `Current chat uses ${modeForSession(ctx)} context (${host.state.model.get() || 'unknown model'}).`,
          }),
        },
      },
    ])
  },
}
