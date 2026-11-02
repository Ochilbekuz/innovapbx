import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Drawer, Modal } from './Dialog';

const zClass = (el: Element) => [...el.classList].find((c) => c.startsWith('z-'));

/** Radix overlay — Content'dan oldingi aka-uka element (portal ichida). */
const overlayOf = (dialog: HTMLElement) => dialog.previousElementSibling as HTMLElement;

describe('Dialog qatlamlari', () => {
  it('Drawer overlay paneldan baland emas — panel xiralashmaydi va bosishlar overlay\'ga ketmaydi', () => {
    render(<Drawer open title="Qoʻngʻiroq yoʻli">ichki</Drawer>);
    const panel = screen.getByRole('dialog');
    expect(zClass(panel)).toBe('z-drawer');
    expect(zClass(overlayOf(panel))).toBe('z-drawer');
  });

  it('Modal overlay modal qatlamida (drawer ustidan ochilganda uni yopadi)', () => {
    render(<Modal open title="Tasdiqlash">ichki</Modal>);
    const box = screen.getByRole('dialog');
    expect(zClass(box)).toBe('z-modal');
    expect(zClass(overlayOf(box))).toBe('z-modal');
  });
});

describe.each([
  ['Modal', Modal],
  ['Drawer', Drawer],
] as const)('%s — yopish va saqlanmagan oʻzgarish', (_name, Comp) => {
  it('sarlavha, tavsif, matn va pastki qism koʻrinadi; X tugmasi yopadi', async () => {
    const onOpenChange = vi.fn();
    render(<Comp open onOpenChange={onOpenChange} title="Tahrirlash" description="101 raqami" footer={<button type="button">Saqlash</button>}>maydonlar</Comp>);
    const box = screen.getByRole('dialog', { name: 'Tahrirlash' });
    expect(box).toHaveAccessibleDescription('101 raqami');
    expect(screen.getByText('maydonlar')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Saqlash' })).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Yopish' }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('onAttemptClose false qaytarsa — Esc yopmaydi; true bo\'lsa yopadi', async () => {
    const onOpenChange = vi.fn();
    let allow = false;
    render(<Comp open onOpenChange={onOpenChange} title="Tahrirlash" onAttemptClose={() => allow}>x</Comp>);
    await userEvent.keyboard('{Escape}');
    expect(onOpenChange).not.toHaveBeenCalled();
    allow = true;
    await userEvent.keyboard('{Escape}');
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it('trigger bosilganda ochiladi', async () => {
    render(<Comp trigger={<button type="button">Ochish</button>} title="Panel">x</Comp>);
    expect(screen.queryByRole('dialog')).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Ochish' }));
    expect(screen.getByRole('dialog', { name: 'Panel' })).toBeVisible();
  });
});

it('Modal size="sm" tor kenglik oladi', () => {
  render(<Modal open size="sm" title="Tasdiq">x</Modal>);
  expect(screen.getByRole('dialog')).toHaveClass('max-w-modal-sm');
});
