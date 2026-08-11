import { Component, type ReactNode } from 'react';

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: any) {
    console.error('Unhandled render error:', error, info);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <h1 className="text-xl font-semibold text-danger mb-2">Something went wrong</h1>
        <p className="text-sm text-fg-3 mb-4">
          The page hit an unexpected error. The console has the stack trace.
        </p>
        <pre className="text-xs whitespace-pre-wrap font-mono bg-bg-2 p-3 rounded border border-border-1 mb-4">
          {this.state.error.message}
        </pre>
        <button
          type="button"
          onClick={() => {
            this.setState({ error: null });
            window.location.reload();
          }}
          className="ck-btn ck-btn-secondary ck-btn-sm"
        >
          Reload
        </button>
      </div>
    );
  }
}
