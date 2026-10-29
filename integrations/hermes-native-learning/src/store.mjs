// SPDX-License-Identifier: AGPL-3.0-only
// Task-local file storage; no host settings, database, or provider integration.
import * as fs from 'node:fs';
import * as path from 'node:path';
import { randomUUID } from 'node:crypto';

export class StateError extends Error {
  constructor(code, message) { super(message); this.name = 'StateError'; this.code = code; }
}
export function requireState(condition, code, message) {
  if (!condition) throw new StateError(code, message);
}
export function chatId(value) {
  requireState(typeof value === 'string' && /^[A-Za-z0-9_-]{1,80}$/.test(value), 'invalid_chat_id', 'Use a chat ID of 1–80 letters, digits, underscores, or hyphens.');
  return value;
}

export class FileSessionStore {
  constructor(root) { this.root = path.resolve(root); }
  file(id) { return path.join(this.root, `${chatId(id)}.json`); }
  read(id) {
    const target = this.file(id);
    requireState(fs.existsSync(target), 'not_found', 'Session does not exist.');
    requireState(fs.statSync(target).size <= 4 * 1024 * 1024, 'record_too_large', 'Session exceeds the first-slice storage limit.');
    const record = JSON.parse(fs.readFileSync(target, 'utf8'));
    requireState(record.id === id && record.version === 1 && record.adapter?.version === 1,
      'unsupported_record', 'Refusing to rewrite an unknown record/version.');
    requireState(Array.isArray(record.messages) && Number.isSafeInteger(record.adapter.revision), 'invalid_record', 'Invalid session record.');
    return record;
  }
  change(id, update, { create = false, activity = true } = {}) {
    const target = this.file(id);
    fs.mkdirSync(this.root, { recursive: true });
    let lock;
    try { lock = fs.openSync(`${target}.lock`, 'wx'); }
    catch (error) {
      if (error.code === 'EEXIST') throw new StateError('busy', 'Another writer owns this session; retry after it finishes.');
      throw error;
    }
    let temporary;
    try {
      requireState(!create || !fs.existsSync(target), 'already_exists', 'Session already exists.');
      const current = create ? null : this.read(id);
      const { record, result, changed = true } = update(current);
      if (changed) {
        record.adapter.revision = (current?.adapter.revision ?? -1) + 1;
        record.updatedAt = !activity&&current ? current.updatedAt : new Date().toISOString();
        const bytes = JSON.stringify(record, null, 2) + '\n';
        requireState(Buffer.byteLength(bytes) <= 4 * 1024 * 1024, 'record_too_large', 'Session exceeds the first-slice storage limit.');
        temporary = `${target}.${randomUUID()}.tmp`;
        const descriptor = fs.openSync(temporary, 'wx');
        try { fs.writeFileSync(descriptor, bytes); fs.fsyncSync(descriptor); }
        finally { fs.closeSync(descriptor); }
        fs.renameSync(temporary, target);
        temporary = undefined;
      }
      return structuredClone(result);
    } finally {
      if (temporary && fs.existsSync(temporary)) fs.unlinkSync(temporary);
      fs.closeSync(lock);
      fs.unlinkSync(`${target}.lock`);
    }
  }
}
