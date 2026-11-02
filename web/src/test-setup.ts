import '@testing-library/jest-dom/vitest';
import '@/lib/i18n';

// jsdom'da yo'q — Radix Popover/Tooltip o'lcham kuzatuvchisini talab qiladi.
class RO { observe() {} unobserve() {} disconnect() {} }
globalThis.ResizeObserver ??= RO as unknown as typeof ResizeObserver;
Element.prototype.scrollIntoView ??= function scrollIntoView() {};
Element.prototype.hasPointerCapture ??= () => false;

// vitest globals o'chiq — RTL avtomatik tozalamaydi.
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
afterEach(cleanup);
