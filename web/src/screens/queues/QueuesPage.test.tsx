// Xatti-harakat testi — navbat aʼzosining dinamik belgisi va joriy holati (kirgan/pauzada/chiqgan)
// tahrirlash drawer'ida koʻrsatiladi (M2b §1). Qarang ../../../replica/m2b-contract.md §1.
import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createFakeClient } from '@/api/fake';
import { useSession } from '@/api/session';
import { loginAs, renderPage } from '@/test-pages';

const client = createFakeClient();
vi.mock('@/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api')>();
  return { ...actual, apiClient: client };
});

const { QueuesPage } = await import('./QueuesPage');

describe('QueuesPage — aʼzo holati belgilari', () => {
  beforeEach(async () => {
    await loginAs(client, 'admin');
  });
  afterEach(() => useSession.getState().clear());

  it("pauzadagi dinamik aʼzo uchun «Dinamik» va «Pauzada» belgilari koʻrinadi", async () => {
    const user = userEvent.setup();
    const { items } = await client.listQueues();
    const queue = items[0]!;
    const memberId = queue.members[0]!.extension.id;
    await client.updateQueueMember(queue.id, memberId, { dynamic: true });
    await client.queueMemberAction(queue.id, memberId, 'pause', { reason: 'tushlik' });

    renderPage(<QueuesPage />);
    await user.dblClick(await screen.findByText(queue.name));

    expect(await screen.findByText('Pauzada')).toBeTruthy();
    expect(screen.getAllByText('Dinamik').length).toBeGreaterThan(0);
  });
});
