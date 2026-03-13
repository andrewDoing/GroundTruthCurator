import createClient from "openapi-fetch";
import { prefixAppBasePath } from "../services/http";
import type { paths } from "./generated";

// Typed OpenAPI client configured for our backend
// Note: generated paths already include "/v1/...", so we don't set baseUrl to avoid duplicating it.
const defaultHeaders = (() => {
	const h: Record<string, string> = {};
	const devUser = import.meta.env.VITE_DEV_USER_ID as string | undefined;
	if (devUser) h["X-User-Id"] = devUser;
	return h as HeadersInit;
})();

// Wrap fetch to ensure JSON payloads are emitted as UTF-8 with charset declared.
// We do NOT manually craft \uXXXX sequences; we rely on JSON.stringify and send bytes as-is.
function withAppBasePath(input: RequestInfo | URL): RequestInfo | URL {
	if (typeof input === "string") {
		return prefixAppBasePath(input);
	}
	if (typeof Request !== "undefined" && input instanceof Request) {
		const nextUrl = prefixAppBasePath(input.url);
		return nextUrl === input.url ? input : new Request(nextUrl, input);
	}
	return input;
}

const utf8JsonFetch: typeof fetch = (input, init) => {
	const resolvedInput = withAppBasePath(input);
	if (init && init.body != null) {
		const hdrs = new Headers(init.headers as HeadersInit | undefined);
		const contentType = hdrs.get("Content-Type") || hdrs.get("content-type");
		const isJson = !!contentType && contentType.includes("application/json");
		if (isJson) {
			// Ensure charset is present
			if (!/charset=/i.test(contentType)) {
				hdrs.set("Content-Type", "application/json; charset=utf-8");
			}
			// If body is a stringified JSON, keep it as-is but ensure it's sent as UTF-8 bytes
			// If body is an object (shouldn't be with openapi-fetch), we'll stringify defensively
			let bodyStr: string;
			if (typeof init.body === "string") {
				bodyStr = init.body;
			} else if (
				init.body instanceof Blob ||
				init.body instanceof ArrayBuffer
			) {
				// Already a binary payload; leave it alone
				return fetch(resolvedInput, { ...init, headers: hdrs });
			} else {
				try {
					// Best effort stringify
					bodyStr = JSON.stringify(
						init.body as unknown as Record<string, unknown>,
					);
				} catch {
					// Fall back to default
					return fetch(resolvedInput, { ...init, headers: hdrs });
				}
			}
			// Send as Blob with explicit type to avoid any implicit re-encoding quirks
			const blob = new Blob([bodyStr], {
				type: hdrs.get("Content-Type") || "application/json; charset=utf-8",
			});
			return fetch(resolvedInput, { ...init, headers: hdrs, body: blob });
		}
	}
	return fetch(resolvedInput, init as RequestInit);
};

export const client = createClient<paths>({
	headers: defaultHeaders,
	fetch: utf8JsonFetch,
});
