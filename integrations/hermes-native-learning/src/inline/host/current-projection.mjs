// SPDX-License-Identifier: AGPL-3.0-only
// Atomic redacted current pointer under the SAME raw-record writer lock.
// No new state engine, model, remote service or enrollment authority.
import fs from 'node:fs';
import path from 'node:path';
import {createHash, randomUUID} from 'node:crypto';
import {requireState} from '../../store.mjs';
import {currentProjectionName, parseCurrentProjection} from '../lesson-identity.mjs';
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
export function publishCurrentProjection(session, output, snapshot) {
  const raw = path.join(session.root, `${session.chatId}.json`);
  const target = path.join(output, currentProjectionName(session.chatId));
  const value = {v:1,chatId:session.chatId,kind:session.kind,revision:snapshot.view.revision,
    snapshot:`${session.kind}-r${snapshot.view.revision}-${snapshot.projectionSha256}.json`};
  let lock, temporary;
  try {
    lock = fs.openSync(raw + '.lock', 'wx');
    requireState(digest(fs.readFileSync(raw)) === snapshot.sourceSha256,
      'concurrent_state_change', 'State changed during export; reopen current state.');
    if (fs.existsSync(target)) {
      const stat=fs.lstatSync(target);
      requireState(stat.isFile() && !stat.isSymbolicLink() && stat.size <= 4096,
        'invalid_current_projection','Current export index must be a bounded regular file.');
      const previous=parseCurrentProjection(fs.readFileSync(target,'utf8'),session);
      requireState(previous.revision <= value.revision, 'stale_projection','Never replace a newer current index.');
      // Jobs/knowledge can update without a lesson revision. Their distinct
      // digest snapshot may become current; no immutable file is overwritten.
    }
    temporary = path.join(output, `.${randomUUID()}.current.pending`);
    const fd=fs.openSync(temporary,'wx');
    try {fs.writeFileSync(fd,JSON.stringify(value));fs.fsyncSync(fd);} finally {fs.closeSync(fd);}
    fs.renameSync(temporary,target);temporary=undefined;
    return target;
  } finally {
    if(temporary)fs.unlinkSync(temporary);
    if(lock!==undefined){fs.closeSync(lock);fs.unlinkSync(raw+'.lock');}
  }
}
