import { Profiler, StrictMode, type ProfilerOnRenderCallback } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import '@fontsource-variable/inter';
import './index.css';
import { initTheme } from './lib/theme';

initTheme();

const root = document.getElementById('root');
if (!root) throw new Error('Root element #root not found');

declare global {
  interface Window {
    __reactCommits?: number;
  }
}

// Dev-only render counter: lets e2e tests prove that scrubbing causes zero React commits.
const countCommits: ProfilerOnRenderCallback = () => {
  window.__reactCommits = (window.__reactCommits ?? 0) + 1;
};

const app = import.meta.env.DEV ? (
  <Profiler id="app" onRender={countCommits}>
    <App />
  </Profiler>
) : (
  <App />
);

createRoot(root).render(<StrictMode>{app}</StrictMode>);
