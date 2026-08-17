"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

type WidgetErrorBoundaryProps = {
  fallback: string;
  children: ReactNode;
};

type WidgetErrorBoundaryState = {
  failed: boolean;
};

export class WidgetErrorBoundary extends Component<
  WidgetErrorBoundaryProps,
  WidgetErrorBoundaryState
> {
  state: WidgetErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): WidgetErrorBoundaryState {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(this.props.fallback, error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.failed) {
      return <p className="text-sm text-[var(--muted)]">{this.props.fallback}</p>;
    }
    return this.props.children;
  }
}
