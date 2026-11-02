import { Component, type ErrorInfo, type ReactNode } from 'react';
import { RotateCw } from 'lucide-react';
import i18n from '@/lib/i18n';
import { Button } from '@/ui/Button';

// Render xatosi butun panelni bo'sh oq sahifaga aylantirmasin: xabar + qayta yuklash.
// Klass komponent — React'da xatoni ushlashning yagona yo'li; matn i18n'dan to'g'ridan-to'g'ri.

type Props = { children: ReactNode };
type State = { error: Error | null };

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[innova] render xatosi', error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;
    const t = (k: string) => i18n.t(`common:crash.${k}`);
    return (
      <div role="alert" className="mx-auto mt-24 max-w-xl space-y-4 rounded-lg border border-line bg-surface p-6 text-fg">
        <h1 className="text-lg font-semibold">{t('title')}</h1>
        <p className="text-sm text-muted">{t('body')}</p>
        <pre className="overflow-auto rounded bg-surface-2 p-3 font-mono text-xs">{`${error.name}: ${error.message}`}</pre>
        <Button icon={<RotateCw />} onClick={() => window.location.reload()}>{t('reload')}</Button>
      </div>
    );
  }
}
