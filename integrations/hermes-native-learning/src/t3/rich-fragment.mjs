// SPDX-License-Identifier: AGPL-3.0-only
// Same existing LearnHarness renderer dependencies, statically bundled for T3.
import * as React from 'react';
import {createRoot} from 'react-dom/client';
import {Streamdown} from 'streamdown';
import {cjk} from '@streamdown/cjk';
import {createMathPlugin} from '@streamdown/math';
import {createMermaidPlugin} from '@streamdown/mermaid';
import remarkBreaks from 'remark-breaks';
import {createRichRenderer} from './rich-core.mjs';
export const {mount:mountRichFragment}=createRichRenderer({React,createRoot,Streamdown,cjk,createMathPlugin,createMermaidPlugin,remarkBreaks});
