import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  fallback: (reset: () => void) => ReactNode;
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/** Catches render/lazy-chunk failures (e.g. the map chunk failing to load on a bad network). */
export class ErrorBoundary extends Component<Props, State> {
  override state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('UI error boundary', error, info.componentStack);
  }

  reset = () => this.setState({ error: null });

  override render(): ReactNode {
    return this.state.error ? this.props.fallback(this.reset) : this.props.children;
  }
}
