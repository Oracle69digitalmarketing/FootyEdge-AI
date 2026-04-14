import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
  }
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  public render() {
    const { hasError, error } = this.state;
    const { children } = this.props;

    if (hasError) {
      let errorMessage = error?.message || "Something went wrong.";
      
      // Try to parse if it might be a JSON error from Supabase/Firestore
      if (error?.message && (error.message.startsWith('{') || error.message.includes('{"error":'))) {
        try {
          const parsedError = JSON.parse(error.message);
          if (parsedError.error) {
            errorMessage = `Database Error: ${parsedError.error} (${parsedError.operationType || 'unknown'} on ${parsedError.path || 'unknown'})`;
          }
        } catch (e) {
          // Fallback to original message if parse fails
        }
      }

      return (
        <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center p-4">
          <div className="bg-zinc-900 border border-red-500/50 p-8 rounded-3xl max-w-lg w-full space-y-4">
            <h2 className="text-2xl font-bold text-red-500">Application Error</h2>
            <p className="text-zinc-400 font-mono text-sm break-all">
              {errorMessage}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="w-full bg-white text-black font-bold py-3 rounded-xl hover:bg-zinc-200 transition-colors"
            >
              Reload Application
            </button>
          </div>
        </div>
      );
    }

    return children;
  }
}
