/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API?: 'fake' | 'real';
  readonly VITE_FAKE_DELAY?: string;
}
