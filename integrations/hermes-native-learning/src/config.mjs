// SPDX-License-Identifier: AGPL-3.0-only
// Private local configuration, never model-selected paths or account credentials.
import fs from 'node:fs';
import path from 'node:path';
import { requireState, chatId } from './store.mjs';
const canonical = value => typeof value === 'string' && value.length > 0 && value.length <= 300 && value === value.trim() && value !== 'new';
function inside(base, target) {
  const rel = path.relative(base, target);
  return rel === '' || (!path.isAbsolute(rel) && rel !== '..' && !rel.startsWith('..' + path.sep));
}
function configuredRoot(base, relative) {
  requireState(typeof relative === 'string' && relative.length > 0 && !path.isAbsolute(relative), 'invalid_config', 'State/export roots must be relative to the private config.');
  const target = path.resolve(base, relative);
  requireState(inside(base, target) && target !== base, 'invalid_config', 'A configured root escaped its workspace.');
  let existing=target;const suffix=[];
  while(!fs.existsSync(existing)){suffix.unshift(path.basename(existing));existing=path.dirname(existing);}
  requireState(fs.statSync(existing).isDirectory(),'invalid_config','Configured roots require a directory ancestor.');
  const physical=path.join(fs.realpathSync(existing),...suffix);
  requireState(inside(fs.realpathSync(base),physical),'invalid_config','A configured root traverses an outside link.');
  return physical;
}
export function loadConfiguration(file) {
  const actual = fs.realpathSync(file);
  requireState(fs.statSync(actual).size <= 65536, 'invalid_config', 'Configuration exceeds 64 KiB.');
  const config = JSON.parse(fs.readFileSync(actual, 'utf8'));
  requireState(config?.version === 1 && Array.isArray(config.lessons) && config.lessons.length > 0 &&
    Object.keys(config).every(k => ['version','lessons'].includes(k)), 'invalid_config', 'Use a version1 private lesson configuration.');
  const base = path.dirname(actual), ids = new Set();
  const lessons = config.lessons.map(item => {
    requireState(item && Object.keys(item).every(k => ['ownerSessionId','chatId','kind','stateRoot','exportRoot','graphRoot','knowledgeRoot','materials','jobRoot'].includes(k)) &&
      canonical(item.ownerSessionId) && ['teach','practice'].includes(item.kind), 'invalid_config', 'Invalid explicit lesson/owner binding.');
    chatId(item.chatId);
    requireState(!ids.has(item.chatId), 'invalid_config', 'Each configured lesson ID must be unique.'); ids.add(item.chatId);
    const root = configuredRoot(base, item.stateRoot), output = configuredRoot(base, item.exportRoot);
    requireState(!inside(root, output) && !inside(output, root), 'invalid_config', 'Raw state and redacted exports must have disjoint roots.');
    let graphRoot;
    if(item.graphRoot!==undefined) {
      requireState(item.kind==='practice'&&typeof item.graphRoot==='string'&&item.graphRoot.trim()===item.graphRoot&&item.graphRoot.length>0,
        'invalid_config','Only an explicitly enrolled practice graph directory is accepted.');
      // Trusted private configuration only, never an input action or directive.
      // An external source requires explicit additional data-read enrollment.
      graphRoot=fs.realpathSync(path.resolve(base,item.graphRoot));
      requireState(fs.statSync(graphRoot).isDirectory(),'invalid_config','Graph source must be an existing directory.');
      requireState(!inside(root,graphRoot)&&!inside(graphRoot,root)&&!inside(output,graphRoot)&&!inside(graphRoot,output),
        'invalid_config','Read-only graph, mutable lesson state and exports must be disjoint.');
    }
    const knowledgeRoot=item.knowledgeRoot===undefined?undefined:configuredRoot(base,item.knowledgeRoot);
    requireState(!(knowledgeRoot&&graphRoot),'invalid_config','Choose the enrolled native graph reader or private knowledge store, not both.');
    requireState(item.materials===undefined||Array.isArray(item.materials),'invalid_config','Materials require an explicit file enrollment list.');
    const materialIds=new Set();
    const materials=(item.materials??[]).map(material=>{
      requireState(material&&Object.keys(material).every(key=>['id','label','kind','file'].includes(key))&&
        typeof material.id==='string'&&/^[A-Za-z0-9_-]{1,80}$/.test(material.id)&&!materialIds.has(material.id)&&
        typeof material.label==='string'&&material.label.trim()&&material.label.length<=300&&['notes','pdf'].includes(material.kind)&&
        typeof material.file==='string'&&material.file&&!path.isAbsolute(material.file),'invalid_config','Enroll named notes/PDF files explicitly; no model-selected path.');
      materialIds.add(material.id);
      const lexical=path.resolve(base,material.file),actual=fs.realpathSync(lexical);
      requireState(inside(base,lexical)&&inside(fs.realpathSync(base),actual)&&fs.statSync(actual).isFile(),
        'invalid_config','Material file must stay in its private enrolled workspace.');
      return Object.freeze({id:material.id,label:material.label.trim(),kind:material.kind,file:actual});
    });
    const jobRoot=item.jobRoot===undefined?undefined:configuredRoot(base,item.jobRoot);
    return Object.freeze({ ownerSessionId: item.ownerSessionId, chatId: item.chatId, kind: item.kind, root, output,graphRoot,knowledgeRoot,jobRoot,materials:Object.freeze(materials) });
  });
  for(const exported of lessons)for(const raw of lessons)
    requireState(!inside(exported.output,raw.root)&&!inside(raw.root,exported.output),
      'invalid_config','Every export directory must be physically disjoint from every raw lesson directory.');
  for(const graph of lessons.filter(b=>b.graphRoot))for(const mutable of lessons)
    requireState(!inside(graph.graphRoot,mutable.root)&&!inside(mutable.root,graph.graphRoot)&&
      !inside(graph.graphRoot,mutable.output)&&!inside(mutable.output,graph.graphRoot),
      'invalid_config','Read-only graph sources must be disjoint from all mutable lesson directories.');
  for(const knowledge of lessons.filter(b=>b.knowledgeRoot))for(const other of lessons) {
    for(const target of [other.root,other.output,other.graphRoot].filter(Boolean))
      requireState(!inside(knowledge.knowledgeRoot,target)&&!inside(target,knowledge.knowledgeRoot),
        'invalid_config','Private knowledge storage must be physically disjoint from lessons, exports and external graph sources.');
    if(other.knowledgeRoot&&other.knowledgeRoot!==knowledge.knowledgeRoot)
      requireState(!inside(knowledge.knowledgeRoot,other.knowledgeRoot)&&!inside(other.knowledgeRoot,knowledge.knowledgeRoot),
        'invalid_config','Knowledge roots may be identical or disjoint, never nested.');
  }
  for(const lesson of lessons)for(const material of lesson.materials)for(const other of lessons)
    for(const mutable of [other.root,other.output,other.knowledgeRoot,other.jobRoot].filter(Boolean))
      requireState(!inside(mutable,material.file),'invalid_config','Enrolled raw material must not be a state, export or knowledge file.');
  for(const job of lessons.filter(b=>b.jobRoot))for(const other of lessons) {
    for(const target of [other.root,other.output,other.knowledgeRoot,other.graphRoot].filter(Boolean))
      requireState(!inside(job.jobRoot,target)&&!inside(target,job.jobRoot),'invalid_config','Private job output must be separate from lessons, exports and graphs.');
    if(other.jobRoot&&job.jobRoot!==other.jobRoot)requireState(!inside(job.jobRoot,other.jobRoot)&&!inside(other.jobRoot,job.jobRoot),
      'invalid_config','Job roots may be identical or disjoint, never nested.');
  }
  return { lessons };
}
// This local tool contract is valid only after qualifying Hermes' per-command
// ContextVar bridge. Environment values alone are not remote authentication.
// Never copy an owner from the message into env/argv to manufacture provenance.
export function bindingForCaller(config, id, env) {
  const aliases = [env.HERMES_SESSION_ID, env.HERMES_UI_SESSION_ID].filter(canonical);
  requireState(aliases.length > 0, 'caller_unqualified', 'Run through a qualified Hermes local terminal tool; no caller fallback.');
  const matches = config.lessons.filter(item => item.chatId === id && aliases.includes(item.ownerSessionId));
  requireState(matches.length === 1, 'wrong_native_owner', 'This caller has no unique configured lesson binding.');
  return matches[0];
}
