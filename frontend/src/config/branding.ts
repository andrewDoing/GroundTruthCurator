/**
 * Application branding configuration.
 *
 * This configuration allows the application title to be customized via environment variables,
 * making the frontend product-agnostic.
 */

// Vite exposes env vars via import.meta.env
// We default to a generic name if not specified.
export const APP_TITLE =
	(import.meta.env.VITE_APP_TITLE as string) || "Ground Truth Curator";
