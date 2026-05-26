import '@testing-library/jest-dom/vitest';

import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
});

vi.stubGlobal('scrollTo', vi.fn());
vi.stubGlobal(
  'requestAnimationFrame',
  (callback: FrameRequestCallback) =>
    setTimeout(() => callback(performance.now()), 0) as unknown as number,
);

if (!('ResizeObserver' in globalThis)) {
  vi.stubGlobal('ResizeObserver', class ResizeObserver {});
}
