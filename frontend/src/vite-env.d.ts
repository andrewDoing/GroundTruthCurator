/// <reference types="vite/client" />

declare module "*.md?raw" {
	const content: string;
	export default content;
}

declare global {
	interface ImportMetaEnv {
		readonly VITE_TELEMETRY_BACKEND?: "otlp" | "appinsights" | "none";
		readonly VITE_OTLP_EXPORTER_URL?: string;
		readonly VITE_APPINSIGHTS_CONNECTION_STRING?: string;
		readonly VITE_ENVIRONMENT?: string;
		readonly VITE_BUILD_SHA?: string;
		readonly VITE_DEMO_MODE?: string | boolean;
		readonly VITE_TRUSTED_REFERENCE_DOMAINS?: string;
		readonly DEMO_MODE?: string | boolean;
	}
}

// ImportMeta is provided by vite/client types
