import '@testing-library/jest-dom/vitest';

import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  // Nach jedem Test werden gerenderte Komponenten wieder aus dem DOM entfernt.
  cleanup();
});

// Diese Browser-Funktionen fehlen in der Testumgebung und werden deshalb nachgebaut.
vi.stubGlobal('scrollTo', vi.fn());
vi.stubGlobal(
  'requestAnimationFrame',
  (callback: FrameRequestCallback) =>
    setTimeout(() => callback(performance.now()), 0) as unknown as number,
);

if (!('ResizeObserver' in globalThis)) {
  // Einige UI-Komponenten erwarten ResizeObserver; im Test reicht ein leerer Ersatz.
  vi.stubGlobal('ResizeObserver', class ResizeObserver {});
}
