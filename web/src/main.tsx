import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import * as Tooltip from '@radix-ui/react-tooltip';
import './styles/index.css';
import './lib/i18n';
import { queryClient } from './api/queryClient';
import { useTheme } from './lib/theme';
import { installSoftphoneDiagnostics } from './softphone/diag';
import { ToastProvider } from './ui/Toast';
import { AppRouter } from './router';

useTheme.getState();
installSoftphoneDiagnostics();

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Tooltip.Provider delayDuration={300}>
          <ToastProvider>
            <AppRouter />
          </ToastProvider>
        </Tooltip.Provider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
