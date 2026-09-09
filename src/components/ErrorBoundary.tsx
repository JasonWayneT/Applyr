import React from 'react';

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

/** Reusable React error boundary — catches render errors in its subtree.
 * Logs via console.error (never swallows silently) and shows a fallback UI.
 * CR-104 Epic 4 Story 4.1. */
class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error('[ErrorBoundary] Caught render error:', error, info.componentStack);
  }

  render(): React.ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="p-4 rounded-xl bg-surface-container-low text-on-surface-variant text-sm">
          Something went wrong here.
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
