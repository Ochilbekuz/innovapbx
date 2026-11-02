import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@/lib/i18n';
import { AppErrorBoundary } from './AppErrorBoundary';

function Boom(): never {
  throw new TypeError('crypto.randomUUID is not a function');
}

afterEach(() => vi.restoreAllMocks());

describe('AppErrorBoundary', () => {
  it('shows a readable error with a reload button instead of a blank page', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    render(<AppErrorBoundary><Boom /></AppErrorBoundary>);
    expect(screen.getByRole('alert')).toHaveTextContent('Sahifada xato yuz berdi');
    expect(screen.getByText(/crypto\.randomUUID is not a function/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Qayta yuklash' })).toBeInTheDocument();
  });

  it('renders children untouched when nothing throws', () => {
    render(<AppErrorBoundary><p>ichki</p></AppErrorBoundary>);
    expect(screen.getByText('ichki')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).toBeNull();
  });
});
