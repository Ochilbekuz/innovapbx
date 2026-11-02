import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { DestinationPicker } from './DestinationPicker';
import type { Catalog } from '@/domain/destination';

const catalog: Catalog = {
  e101: { id: 'e101', kind: 'extension', name: 'Dilnoza Karimova', number: '101' },
  q1: { id: 'q1', kind: 'queue', name: 'Sotuv boʻlimi', number: '600' },
};

describe('DestinationPicker', () => {
  it('singan havola: aria-invalid, sabab matni va screen reader nomi', () => {
    render(<DestinationPicker label="Manzil" value={{ kind: 'extension', targetId: 'e1099' }} onChange={() => {}} catalog={catalog} />);
    const trigger = screen.getByRole('button', { name: /oʻchirilgan/i });
    expect(trigger).toHaveAttribute('aria-invalid', 'true');
    expect(trigger).toHaveAccessibleDescription(/oʻchirib yuborilgan/);
  });

  it('toʻgʻri manzil: xato belgisi yoʻq, nomi oʻqiladi', () => {
    render(<DestinationPicker label="Manzil" value={{ kind: 'queue', targetId: 'q1' }} onChange={() => {}} catalog={catalog} />);
    const trigger = screen.getByRole('button', { name: /Sotuv boʻlimi/ });
    expect(trigger).not.toHaveAttribute('aria-invalid');
  });

  it('majburiy va boʻsh: xato tavsifi beriladi', () => {
    render(<DestinationPicker label="Manzil" value={null} onChange={() => {}} catalog={catalog} required />);
    expect(screen.getByRole('button', { name: /tanlanmagan/ })).toHaveAccessibleDescription(/PBX bilmaydi/);
  });

  it('roʻyxatdan tanlash onChange ga manzil beradi', async () => {
    const onChange = vi.fn();
    render(<DestinationPicker label="Manzil" value={null} onChange={onChange} catalog={catalog} />);
    await userEvent.click(screen.getByRole('button', { name: /Manzil/ }));
    const list = await screen.findByRole('listbox');
    await userEvent.click(within(list).getByRole('option', { name: /Dilnoza/ }));
    expect(onChange).toHaveBeenCalledWith({ kind: 'extension', targetId: 'e101' });
  });

  it('klaviatura: qidiruv + Enter', async () => {
    const onChange = vi.fn();
    render(<DestinationPicker label="Manzil" value={null} onChange={onChange} catalog={catalog} />);
    await userEvent.click(screen.getByRole('button', { name: /Manzil/ }));
    await userEvent.type(await screen.findByRole('combobox'), '600{Enter}');
    expect(onChange).toHaveBeenCalledWith({ kind: 'queue', targetId: 'q1' });
  });
});
