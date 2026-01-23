import DEMO_MODE from "../config/demo";
import type {
	TelemetryBackend,
	TelemetryFacade,
	TelemetryOptions,
} from "../models/telemetry";
import { NoopTelemetry } from "../models/telemetry";

// Lazy import types to avoid bundling when not used
// We keep references typed loosely to avoid requiring these libs at runtime when disabled.

let initialized = false;
let facade: TelemetryFacade = NoopTelemetry;

function getEnvBackend(): TelemetryBackend {
	const val = (import.meta.env.VITE_TELEMETRY_BACKEND as string | undefined)
		?.toString()
		.toLowerCase();
	if (val === "appinsights" || val === "none" || val === "otlp") return val;
	return "otlp";
}

function mkCommonProps() {
	return {
		environment: import.meta.env.VITE_ENVIRONMENT as string | undefined,
		buildSha: import.meta.env.VITE_BUILD_SHA as string | undefined,
	} as Record<string, unknown>;
}

async function initWithOTel(opts: TelemetryOptions): Promise<TelemetryFacade> {
	const url = opts.otlpUrl;
	if (!url) return NoopTelemetry;

	try {
		type Span = {
			setAttribute: (k: string, v: unknown) => void;
			end: () => void;
		};
		type Tracer = { startSpan: (n: string) => Span };
		type OtelApi = { trace: { getTracer: (n: string) => Tracer } };
		type WebTracerProviderI = {
			addSpanProcessor: (p: unknown) => void;
			register: () => void;
		};
		type WebTracerProviderCtor = new (cfg: unknown) => WebTracerProviderI;
		type BatchSpanProcessorCtor = new (exporter: unknown) => unknown;
		type OTLPTraceExporterCtor = new (cfg: { url: string }) => unknown;
		type ResourceCtor = new (attrs: Record<string, unknown>) => unknown;
		type InstrumentationI = { enable: () => void };
		type DocumentLoadInstrumentationCtor = new () => InstrumentationI;
		type FetchInstrumentationCtor = new () => InstrumentationI;

		const [
			{ WebTracerProvider, BatchSpanProcessor },
			{ OTLPTraceExporter },
			resources,
			docLoad,
			fetchInst,
			api,
		] = await Promise.all([
			import("@opentelemetry/sdk-trace-web") as Promise<{
				WebTracerProvider: WebTracerProviderCtor;
				BatchSpanProcessor: BatchSpanProcessorCtor;
			}>,
			import("@opentelemetry/exporter-trace-otlp-http") as Promise<{
				OTLPTraceExporter: OTLPTraceExporterCtor;
			}>,
			import("@opentelemetry/resources") as Promise<{ Resource: ResourceCtor }>,
			import("@opentelemetry/instrumentation-document-load") as Promise<{
				DocumentLoadInstrumentation: DocumentLoadInstrumentationCtor;
			}>,
			import("@opentelemetry/instrumentation-fetch") as Promise<{
				FetchInstrumentation: FetchInstrumentationCtor;
			}>,
			import("@opentelemetry/api") as Promise<OtelApi>,
		]);

		const { Resource } = resources;
		const { DocumentLoadInstrumentation } = docLoad;
		const { FetchInstrumentation } = fetchInst;

		const provider = new WebTracerProvider({
			resource: new Resource({
				"service.name": "gtc-frontend",
				"service.version": opts.buildSha || "dev",
			}),
		});

		const exporter = new OTLPTraceExporter({ url });
		provider.addSpanProcessor(new BatchSpanProcessor(exporter));
		provider.register();

		// Minimal instrumentations
		new DocumentLoadInstrumentation().enable();
		new FetchInstrumentation().enable();

		const tracer = api.trace.getTracer("gtc-frontend");

		const facade: TelemetryFacade = {
			logEvent(name, properties) {
				const span = tracer.startSpan(`event:${name}`);
				try {
					const attrs = { ...mkCommonProps(), ...(properties || {}) };
					Object.entries(attrs).forEach(([k, v]) => {
						span.setAttribute(k, v);
					});
				} finally {
					span.end();
				}
			},
			logException(error, severity, properties) {
				const span = tracer.startSpan("exception");
				try {
					const errObj =
						error instanceof Error ? error : new Error(String(error));
					const attrs = {
						...mkCommonProps(),
						message: errObj.message,
						stack: errObj.stack,
						severity: severity || "error",
						...(properties || {}),
					};
					Object.entries(attrs).forEach(([k, v]) => {
						span.setAttribute(k, v);
					});
				} finally {
					span.end();
				}
			},
			logTrace(message, properties) {
				const span = tracer.startSpan("trace");
				try {
					const attrs = { ...mkCommonProps(), message, ...(properties || {}) };
					Object.entries(attrs).forEach(([k, v]) => {
						span.setAttribute(k, v);
					});
				} finally {
					span.end();
				}
			},
		};
		return facade;
	} catch (_e) {
		// If OTel libs fail to load or unsupported, no-op
		return NoopTelemetry;
	}
}

async function initWithAppInsights(
	opts: TelemetryOptions,
): Promise<TelemetryFacade> {
	const conn = opts.appInsightsConnectionString;
	if (!conn) return NoopTelemetry;
	try {
		const ai = await import("@microsoft/applicationinsights-web");
		type AppInsightsLike = new (
			cfg: unknown,
		) => {
			loadAppInsights: () => void;
			trackEvent: (ev: unknown, props?: Record<string, unknown>) => void;
			trackException: (o: {
				exception: unknown;
				severityLevel?: number;
				properties?: Record<string, unknown>;
			}) => void;
			trackTrace: (
				o: { message: string },
				props?: Record<string, unknown>,
			) => void;
		};
		const { ApplicationInsights } = ai as {
			ApplicationInsights: AppInsightsLike;
		};
		const appInsights = new ApplicationInsights({
			config: {
				connectionString: conn,
				enableAutoRouteTracking: false,
				enableAjaxErrorStatusText: false,
				samplingPercentage: Math.round(
					100 *
						(typeof opts.sampleRatio === "number" ? opts.sampleRatio : 0.25),
				),
				enableUnhandledPromiseRejectionTracking: true,
			},
		});
		appInsights.loadAppInsights();

		const common = mkCommonProps();

		const facade: TelemetryFacade = {
			logEvent(name, properties) {
				appInsights.trackEvent({ name }, { ...common, ...(properties || {}) });
			},
			logException(error, severity, properties) {
				const errObj =
					error instanceof Error ? error : new Error(String(error));
				appInsights.trackException({
					exception: errObj,
					severityLevel:
						severity === "warning" ? 1 : severity === "info" ? 0 : 3,
					properties: { ...common, ...(properties || {}) },
				});
			},
			logTrace(message, properties) {
				appInsights.trackTrace(
					{ message },
					{ ...common, ...(properties || {}) },
				);
			},
		};
		return facade;
	} catch (_e) {
		return NoopTelemetry;
	}
}

export async function initTelemetry(custom?: Partial<TelemetryOptions>) {
	if (initialized) return;

	const backend = custom?.backend ?? getEnvBackend();
	const options: TelemetryOptions = {
		backend,
		environment:
			(import.meta.env.VITE_ENVIRONMENT as string | undefined) ||
			(custom?.environment as string | undefined),
		buildSha:
			(import.meta.env.VITE_BUILD_SHA as string | undefined) ||
			(custom?.buildSha as string | undefined),
		otlpUrl:
			(import.meta.env.VITE_OTLP_EXPORTER_URL as string | undefined) ||
			custom?.otlpUrl,
		appInsightsConnectionString:
			(import.meta.env.VITE_APPINSIGHTS_CONNECTION_STRING as
				| string
				| undefined) || custom?.appInsightsConnectionString,
		sampleRatio:
			typeof custom?.sampleRatio === "number" ? custom.sampleRatio : 0.25,
		disabled: custom?.disabled ?? false,
	};

	if (DEMO_MODE || options.disabled) {
		initialized = true;
		facade = NoopTelemetry;
		return;
	}

	if (options.backend === "none") {
		initialized = true;
		facade = NoopTelemetry;
		return;
	}

	if (options.backend === "otlp") {
		facade = await initWithOTel(options);
		if (facade === NoopTelemetry && options.appInsightsConnectionString) {
			// Optional fallback to App Insights if configured
			facade = await initWithAppInsights(options);
		}
	} else if (options.backend === "appinsights") {
		facade = await initWithAppInsights(options);
	}

	initialized = true;
}

export function getTelemetry(): TelemetryFacade {
	return facade;
}

export function logEvent(name: string, properties?: Record<string, unknown>) {
	facade.logEvent(name, properties);
}

export function logException(
	error: unknown,
	severity?: "error" | "warning" | "info",
	properties?: Record<string, unknown>,
) {
	facade.logException(error, severity, properties);
}

// Global safety nets
if (typeof window !== "undefined") {
	window.addEventListener("error", (e) => {
		try {
			facade.logException(e.error || e.message || "window.error");
		} catch {}
	});
	window.addEventListener("unhandledrejection", (e) => {
		try {
			facade.logException(e.reason || "unhandledrejection");
		} catch {}
	});
}
