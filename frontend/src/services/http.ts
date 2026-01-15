/** HTTP helper utilities for backend API calls */

export function getApiBaseUrl(): string {
	// In the browser, use relative "/v1" so Vite dev proxy can intercept; in production
	// VITE_API_BASE_URL can still be used if absolute URLs are needed in deployments.
	// Prefer relative path for browser calls; backend is expected under /v1
	// If you need absolute base for SSR or other contexts, revise as needed.
	return "/v1";
}

export function withDevUser(init: RequestInit = {}): RequestInit {
	const devUser = import.meta.env.VITE_DEV_USER_ID as string | undefined;
	if (!devUser) return init;
	return {
		...init,
		headers: { ...(init.headers || {}), "X-User-Id": devUser },
	};
}

type ApiError = {
	status: number;
	statusText: string;
	url: string;
	data?: unknown;
};

export function mapApiErrorToMessage(err: unknown): string {
	const e = err as Partial<ApiError & { data?: Record<string, unknown> }>; // best-effort narrowing
	if (e && typeof e === "object" && typeof e.status === "number") {
		const data = e.data as Record<string, unknown> | undefined;
		const detail =
			(typeof data?.detail === "string" && data.detail) ||
			(typeof data?.message === "string" && data.message) ||
			"";
		return `${e.status} ${e.statusText ?? "Error"}${detail ? ` – ${detail}` : ""}`;
	}
	return "Network or unexpected error";
}
