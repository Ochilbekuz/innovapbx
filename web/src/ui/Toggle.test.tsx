import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Toggle } from './Toggle';

describe('Toggle', () => {
  it('role=switch, yorliq bogʻlangan, bosish va Space almashtiradi', async () => {
    const onChange = vi.fn();
    render(<Toggle label="Ovozli pochta" description="Javobsiz qoʻngʻiroqlar uchun" onCheckedChange={onChange} />);
    const sw = screen.getByRole('switch', { name: 'Ovozli pochta' });
    expect(sw).toHaveAttribute('aria-checked', 'false');
    expect(sw).toHaveAccessibleDescription('Javobsiz qoʻngʻiroqlar uchun');
    await userEvent.click(sw);
    expect(sw).toHaveAttribute('aria-checked', 'true');
    sw.focus();
    await userEvent.keyboard(' ');
    expect(sw).toHaveAttribute('aria-checked', 'false');
    expect(onChange).toHaveBeenNthCalledWith(1, true);
    expect(onChange).toHaveBeenNthCalledWith(2, false);
  });

  it('yorliq ustiga bosish ham ishlaydi', async () => {
    render(<Toggle label="Yozib olish" />);
    await userEvent.click(screen.getByText('Yozib olish'));
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true');
  });

  it('disabled — oʻzgarmaydi', async () => {
    const onChange = vi.fn();
    render(<Toggle label="DND" disabled onCheckedChange={onChange} />);
    const sw = screen.getByRole('switch', { name: 'DND' });
    await userEvent.click(sw);
    expect(sw).toHaveAttribute('aria-checked', 'false');
    expect(onChange).not.toHaveBeenCalled();
  });

  it('hideLabel — koʻrinmaydi, lekin nom saqlanadi', () => {
    render(<Toggle label="101 yoqilgan" hideLabel defaultChecked />);
    expect(screen.getByRole('switch', { name: '101 yoqilgan' })).toHaveAttribute('aria-checked', 'true');
  });
});
