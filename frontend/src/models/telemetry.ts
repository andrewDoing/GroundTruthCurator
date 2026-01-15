// Common types for telemetry event properties

export type TelemetryBackend = "otlp" | "appinsights" | "none";

export type TelemetryOptions = {
	backend: TelemetryBackend;
	otlpUrl?: string;
	appInsightsConnectionString?: string;
	environment?: string;
	buildSha?: string;
	sampleRatio?: number; // 0..1
	disabled?: boolean; // force disable
};

export type TelemetryFacade = {
	logEvent: (name: string, properties?: Record<string, unknown>) => void;
	logException: (
		error: unknown,
		severity?: "error" | "warning" | "info",
		properties?: Record<string, unknown>,
	) => void;
	logTrace: (message: string, properties?: Record<string, unknown>) => void;
	shutdown?: () => void | Promise<void>;
};

export const NoopTelemetry: TelemetryFacade = {
	logEvent: () => {},
	logException: () => {},
	logTrace: () => {},
};
