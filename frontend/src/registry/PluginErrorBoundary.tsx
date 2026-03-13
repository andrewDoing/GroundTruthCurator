import type { ErrorInfo, ReactNode } from "react";
import { Component } from "react";

type Props = {
	/** Rendered when the child tree throws. */
	fallback: ReactNode;
	children: ReactNode;
};

type State = {
	hasError: boolean;
};

/**
 * Error boundary that catches render-time errors from plugin-contributed
 * components and swaps in a fallback renderer so the rest of the UI stays
 * intact.
 */
export class PluginErrorBoundary extends Component<Props, State> {
	constructor(props: Props) {
		super(props);
		this.state = { hasError: false };
	}

	static getDerivedStateFromError(): State {
		return { hasError: true };
	}

	override componentDidCatch(error: Error, info: ErrorInfo): void {
		if (import.meta.env.DEV) {
			console.error("[PluginErrorBoundary] Caught error:", error, info);
		}
	}

	override render(): ReactNode {
		if (this.state.hasError) {
			return this.props.fallback;
		}
		return this.props.children;
	}
}
