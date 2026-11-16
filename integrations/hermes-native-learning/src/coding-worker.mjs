// SPDX-License-Identifier: AGPL-3.0-only
// Only guest JavaScript is evaluated, in filesystem-free QuickJS WASM.
// No Emscripten or host functions are registered in the guest context.
import {parentPort, workerData} from 'node:worker_threads';
import {isDeepStrictEqual} from 'node:util';
import makeQuickJS from './vendor/coding-runtime.cjs';

const TEST_DEADLINE_MS = 350;
const MAX_OBSERVED_VALUE = 4096;
const QuickJS = await makeQuickJS();

function evaluate(test, code) {
  const runtime = QuickJS.newRuntime();
  runtime.setMemoryLimit(8 * 1024 * 1024);
  runtime.setMaxStackSize(256 * 1024);
  const deadline = performance.now() + TEST_DEADLINE_MS;
  let interrupted = false;
  runtime.setInterruptHandler(() => {
    interrupted ||= performance.now() >= deadline;
    return interrupted;
  });
  const vm = runtime.newContext();
  const handles = [];
  function value(result) {
    if (result.error) {
      result.error.dispose();
      return null;
    }
    handles.push(result.value);
    return result.value;
  }
  function unsuccessful(message) {
    return interrupted ? {status: 'timeout', message: 'The test exceeded its execution time.'} : {status: 'error', message};
  }
  try {
    const serializer = value(vm.evalCode(`(() => {
      const tag = Function.prototype.call.bind(Object.prototype.toString);
      const stringify = JSON.stringify;
      return (value) => {
        if (tag(value) === '[object Promise]') throw new TypeError('Expected a synchronous value.');
        return stringify(value);
      };
    })()`, 'runner.js', {type: 'global'}));
    if (!serializer) return unsuccessful('The JavaScript runner could not prepare the test.');
    if (!value(vm.evalCode(code, 'answer.js', {type: 'global'}))) return unsuccessful('The submitted code could not be evaluated.');
    const answer = value(vm.evalCode('(' + test.expression + '\n)', 'test.js', {type: 'global'}));
    if (!answer) return unsuccessful('The test expression raised an error.');
    const encoded = value(vm.callFunction(serializer, vm.undefined, answer));
    if (!encoded || vm.typeof(encoded) !== 'string') return unsuccessful('The test did not return a JSON value.');
    const actual = vm.getString(encoded);
    if (actual.length > MAX_OBSERVED_VALUE) return unsuccessful('The test returned too much data to compare.');
    if (isDeepStrictEqual(JSON.parse(actual), test.expected)) return {status: 'pass'};
    return {status: 'fail', actual: actual.length > 400 ? actual.slice(0, 400) + '…' : actual};
  } catch {
    return unsuccessful('The test could not finish.');
  } finally {
    for (const handle of handles.reverse()) handle.dispose();
    vm.dispose();
    runtime.dispose();
  }
}

parentPort.postMessage(workerData.tests.map(test => ({name: test.name, ...evaluate(test, workerData.code)})));
