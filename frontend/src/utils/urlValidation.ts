/**
 * URL validation utilities for XSS protection.
 * Prevents malicious URL schemes from executing in reference links.
 */

/**
 * Validates that a reference URL uses a safe protocol and doesn't contain malicious patterns.
 * 
 * @param url - The URL to validate
 * @returns true if the URL is safe to open, false otherwise
 * 
 * @example
 * validateReferenceUrl("https://example.com") // true
 * validateReferenceUrl("javascript:alert('xss')") // false
 * validateReferenceUrl("data:text/html,<script>...</script>") // false
 */
export function validateReferenceUrl(url: string): boolean {
	try {
		const parsedUrl = new URL(url);

		// Only allow safe protocols
		const allowedProtocols = ["http:", "https:"];
		if (!allowedProtocols.includes(parsedUrl.protocol)) {
			console.warn("Blocked unsafe URL protocol:", parsedUrl.protocol);
			return false;
		}

		// Block known malicious patterns
		const maliciousPatterns = [
			/javascript:/i,
			/data:/i,
			/vbscript:/i,
			/about:/i,
			/blob:/i,
		];

		if (maliciousPatterns.some((pattern) => pattern.test(url))) {
			console.warn("Blocked potentially malicious URL pattern:", url);
			return false;
		}

		return true;
	} catch (_error) {
		console.warn("Invalid URL format:", url);
		return false;
	}
}
