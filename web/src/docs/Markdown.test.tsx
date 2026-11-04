import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import '@/lib/i18n';
import { Blocks } from './Markdown';
import { parseMarkdown } from './markdown';

const show = (md: string) => render(<MemoryRouter><Blocks blocks={parseMarkdown(md)} /></MemoryRouter>);

describe('Markdown (qo\'llanma ko\'rsatgichi)', () => {
  it('sarlavhalar bir daraja pastga suriladi va langar oladi', () => {
    show('# Asosiy\n\n## Bo\'lim\n\n### Kichik');
    expect(screen.getByRole('heading', { level: 2, name: 'Asosiy' })).toHaveAttribute('id', 'asosiy');
    expect(screen.getByRole('heading', { level: 3, name: 'Bo\'lim' })).toHaveAttribute('id', 'bolim');
    expect(screen.getByRole('heading', { level: 4, name: 'Kichik' })).toBeInTheDocument();
  });

  it('ichki havola — panel yo\'li, tashqi — yangi oynada, xavfli — oddiy matn', () => {
    show('[IVR](/docs/ivr), [sayt](https://example.com), [yomon](javascript:alert(1)), [langar](#qadamlar)');
    expect(screen.getByRole('link', { name: 'IVR' })).toHaveAttribute('href', '/docs/ivr');
    const ext = screen.getByRole('link', { name: 'sayt' });
    expect(ext).toHaveAttribute('target', '_blank');
    expect(ext).toHaveAttribute('rel', 'noopener noreferrer');
    expect(screen.getByRole('link', { name: 'langar' })).toHaveAttribute('href', '#qadamlar');
    expect(screen.queryByRole('link', { name: 'yomon' })).toBeNull();
    expect(screen.getByText('yomon')).toBeInTheDocument();
  });

  it('matn ichidagi formatlash: qalin, kursiv, kod', () => {
    show('**Saqlash** tugmasini *albatta* bosing, keyin `*72` tering.');
    expect(screen.getByText('Saqlash').tagName).toBe('STRONG');
    expect(screen.getByText('albatta').tagName).toBe('EM');
    expect(screen.getByText('*72').tagName).toBe('CODE');
  });

  it('ogohlantirish bloki o\'z sarlavhasi bilan chiqadi', () => {
    show('> [!WARNING]\n> Diqqat qiling.\n\n> [!TIP]\n> Maslahat.\n\n> [!NOTE]\n> Eslatma.\n\n> [!CAUTION]\n> Xavf.\n\n> oddiy iqtibos');
    const boxes = screen.getAllByRole('complementary');
    expect(boxes).toHaveLength(4);
    expect(boxes[0]).toHaveTextContent('Diqqat qiling.');
    expect(boxes.map((b) => b.querySelector('p')?.textContent)).toEqual(['Diqqat', 'Maslahat', 'Eslatma', 'Xavfli']);
    expect(screen.getByText('oddiy iqtibos').closest('blockquote')).not.toBeNull();
  });

  it('jadval, raqamli va ichki ro\'yxat, kod bloki', () => {
    show('| Maydon | Ma\'nosi |\n|---|---|\n| Nomi | Navbat nomi |\n\n1. Birinchi\n   - ichki\n2. Ikkinchi\n\n```\nasterisk -rx "core show channels"\n```');
    const table = screen.getByRole('table');
    expect(within(table).getAllByRole('columnheader').map((h) => h.textContent)).toEqual(['Maydon', 'Ma\'nosi']);
    expect(within(table).getByRole('cell', { name: 'Navbat nomi' })).toBeInTheDocument();
    const [outer] = screen.getAllByRole('list');
    expect(outer?.tagName).toBe('OL');
    expect(within(outer!).getByText('ichki').closest('ul')).not.toBeNull();
    expect(screen.getByText('asterisk -rx "core show channels"').closest('pre')).not.toBeNull();
  });
});
