import React from "react";
import { logException } from "../../services/telemetry";

type Props = {
	children: React.ReactNode;
	fallback?: React.ReactNode;
};

type State = { hasError: boolean };

class ErrorBoundary extends React.Component<Props, State> {
	constructor(props: Props) {
		super(props);
		this.state = { hasError: false };
	}

	static getDerivedStateFromError(): State {
		return { hasError: true };
	}

	componentDidCatch(error: unknown, info: React.ErrorInfo) {
		logException(error, "error", { componentStack: info.componentStack });
	}

	render() {
		if (this.state.hasError) {
			return (
				this.props.fallback ?? (
					<div
						role="alert"
						className="p-3 text-red-700 bg-red-50 border border-red-200 rounded"
					>
						Something went wrong. Try refreshing the page.
					</div>
				)
			);
		}
		return this.props.children;
	}
}

export default ErrorBoundary;
