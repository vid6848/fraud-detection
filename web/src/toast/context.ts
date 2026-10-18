import { createContext, useContext } from 'react'

export interface ToastInput {
  title: string
  body?: string
  tone?: 'info' | 'success' | 'alert' | 'error'
  /** Optional in-app link, e.g. to open the alert that triggered the toast. */
  action?: { label: string; to: string }
}

export interface Toast extends ToastInput {
  id: number
}

export const ToastContext = createContext<((toast: ToastInput) => void) | null>(null)

/** Show a short notification. Outside a ToastProvider it does nothing. */
export function useToast() {
  return useContext(ToastContext) ?? (() => {})
}
