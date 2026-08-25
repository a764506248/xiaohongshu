export function Notice({ type = 'error', children }: { type?: 'error' | 'success'; children: React.ReactNode }) {
  return <div className={`notice notice-${type}`}>{children}</div>
}

