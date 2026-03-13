/** HTTP helper utilities for backend API calls */

export function normalizeAppBasePath(basePath: string | undefined): string {
	if (!basePath) return "";
	const trimmed = basePath.trim();
	if (!trimmed || trimmed === "/") return "";
	return `/${trimmed.replace(/^\/+|\/+$/g, "")}`;
}

export function getAppBasePath(): string {
	return normalizeAppBasePath(import.meta.env.BASE_URL as string | undefined);
}

export function prefixAppBasePath(path: string): string {
	if (!path.startsWith("/") || path.startsWith("//")) return path;
	const basePath = getAppBasePath();
	if (!basePath || path === basePath || path.startsWith(`${basePath}/`)) {
		return path;
	}
	return `${basePath}${path}`;
}

export function getApiBaseUrl(): string {
	// Keep browser calls same-origin, but honor an optional Vite base path like "/gtc".
	return prefixAppBasePath("/v1");
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
