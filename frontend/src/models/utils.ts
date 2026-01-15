// Shared utility helpers

export function nowIso() {
	return new Date().toISOString();
}

export function randId(prefix = "id") {
	return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

export function urlToTitle(url: string) {
	try {
		const u = new URL(url);
		return u.hostname + u.pathname.replace(/\/$/, "");
	} catch {
		return url;
	}
}

export function cn(...args: Array<string | false | undefined | null>) {
	return args.filter(Boolean).join(" ");
}

/**
 * Normalize common URL glitches from upstream providers.
 * Currently fixes the very common "https:/example.com" -> "https://example.com".
 * Safe no-op for already-correct URLs.
 */
export function normalizeUrl(url: string): string {
	if (typeof url !== "string") return "";
	const trimmed = url.trim();
	// Add the missing slash for http/https when only one slash is present after the colon.
	// e.g. https:/host/path -> https://host/path
	const fixedProtoSlash = trimmed.replace(/^(https?:)\/(?!\/)/i, "$1//");
	return fixedProtoSlash;
}

/**
 * Truncate a string in the middle with an ellipsis when it exceeds `max` length.
 * Useful for long URLs where both the start (domain) and the end (file/anchor) are informative.
 */
export function truncateMiddle(str: string, max = 96, ellipsis = "…"): string {
	if (typeof str !== "string") return "";
	if (max <= 0) return "";
	if (str.length <= max) return str;
	const keep = Math.max(1, max - ellipsis.length);
	const head = Math.ceil(keep / 2);
	const tail = Math.floor(keep / 2);
	return str.slice(0, head) + ellipsis + str.slice(str.length - tail);
}
