import type { ApiClient } from './client';
import { fakeClient } from './fake';
import { realClient } from './real';

/** `VITE_API=fake|real` — ekran kodi o'zgarmaydi, faqat shu nuqtada tanlanadi. Sukut: fake. */
export const apiClient: ApiClient = import.meta.env.VITE_API === 'real' ? realClient : fakeClient;

export * from './client';
export * from './errors';
export * from './session';
export * from './types';
