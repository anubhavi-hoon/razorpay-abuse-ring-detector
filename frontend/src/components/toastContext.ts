import { createContext, useContext } from 'react';

export interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error';
}

export interface ToastContextValue {
  addToast: (message: string, type: 'success' | 'error') => void;
}

export const ToastContext = createContext<ToastContextValue>({
  addToast: () => {},
});

export function useToast() {
  return useContext(ToastContext);
}
