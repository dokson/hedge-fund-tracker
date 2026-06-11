/**
 * Route-level error boundary: a render crash in any page shows a recoverable
 * fallback card inside the app shell instead of white-screening the SPA.
 *
 * Recovery paths: the "Try again" button re-renders the subtree, and a
 * resetKey change (the current route path) clears the error automatically so
 * sidebar navigation always escapes a crashed page.
 */
import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ErrorBoundaryProps {
  children: ReactNode;
  /** Changing this value (e.g. route pathname) clears a caught error. */
  resetKey?: string;
}

interface ErrorBoundaryState {
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught a render error", error, info.componentStack);
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    if (this.state.error && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  private handleRetry = () => {
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="flex justify-center px-4 py-16">
        <div className="surface relative w-full max-w-xl overflow-hidden p-10 text-center">
          <div
            aria-hidden
            className="absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-transparent via-destructive/70 to-transparent"
          />
          <AlertTriangle className="mx-auto mb-4 h-12 w-12 text-destructive opacity-60" />
          <h2 className="text-lg font-semibold">Something went wrong</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            This page hit an unexpected error while rendering. Your data is untouched — retry, or
            navigate to another section from the sidebar.
          </p>
          <pre className="mt-6 overflow-x-auto rounded-md border border-destructive/20 bg-destructive/5 px-4 py-3 text-left font-mono text-xs text-destructive/90">
            {error.message || error.toString()}
          </pre>
          <div className="mt-6 flex justify-center gap-3">
            <Button onClick={this.handleRetry} variant="default" size="sm">
              <RotateCcw className="mr-2 h-4 w-4" />
              Try again
            </Button>
            <Button onClick={() => window.location.reload()} variant="outline" size="sm">
              Reload app
            </Button>
          </div>
        </div>
      </div>
    );
  }
}
