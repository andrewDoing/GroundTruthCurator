import { client } from "../api/client";
import type { Reference } from "../models/groundTruth";
import { randId } from "../models/utils";
import { logEvent } from "./telemetry";

type SearchResultWire =
	| {
			id?: string;
			title?: string | null;
			url: string;
			snippet?: string | null;
			chunk?: string | null; // some backends return `chunk` instead of `snippet`
			document?:
				| {
						id?: string | null;
						title?: string | null;
						url?: string | null;
				  }
				| Record<string, unknown>
				| null;
	  }
	| Record<string, unknown>;

function mapWireToReference(x: SearchResultWire): Reference | null {
	const o = x as Record<string, unknown>;

	// Try direct fields first
	let url = typeof o.url === "string" ? o.url : undefined;
	let title = typeof o.title === "string" ? o.title : undefined;
	// Prefer `snippet`, but also accept `chunk` (persisted in our `snippet` field)
	let snippet: string | undefined =
		typeof o.snippet === "string" ? (o.snippet as string) : undefined;
	if (!snippet) {
		const chunkVal = (o as Record<string, unknown>).chunk;
		if (typeof chunkVal === "string") snippet = chunkVal;
	}
	// Check nested document/doc shapes for fallback fields
	const doc: Record<string, unknown> | undefined =
		(o.document as Record<string, unknown> | undefined) ||
		((o as Record<string, unknown>).doc as Record<string, unknown> | undefined);
	if ((!url || !title) && doc && typeof doc === "object") {
		if (!url && typeof doc.url === "string") url = doc.url as string;
		if (!title && typeof doc.title === "string") title = doc.title as string;
	}

	if (!url) return null;
	// Derive id from top-level or nested document
	let id: string = randId("ref");
	if (typeof o.id === "string" && o.id) id = o.id;
	else if (doc && typeof doc.id === "string") id = doc.id as string;
	return {
		id,
		title: title || undefined,
		url,
		snippet,
		visitedAt: null,
		keyParagraph: "",
	};
}

export async function searchReferences(
	query: string,
	top = 10,
	signal?: AbortSignal,
): Promise<Reference[]> {
	const q = query.trim();
	if (!q) return [];
	const { data, error } = await client.GET("/v1/search", {
		params: { query: { q, top } },
		signal,
	});
	if (error) throw error;
	let arrUnknown: unknown[] = [];
	if (Array.isArray(data)) {
		arrUnknown = data as unknown[];
	} else if (
		data &&
		typeof data === "object" &&
		Array.isArray((data as Record<string, unknown>).items)
	) {
		arrUnknown = (data as Record<string, unknown>).items as unknown[];
	} else if (
		data &&
		typeof data === "object" &&
		Array.isArray((data as Record<string, unknown>).results)
	) {
		// Support `{ results: [...] }` shape as well
		arrUnknown = (data as Record<string, unknown>).results as unknown[];
	}
	const mapped = (arrUnknown as SearchResultWire[])
		.map(mapWireToReference)
		.filter(Boolean) as Reference[];
	try {
		logEvent("gtc.search", { queryLen: q.length, resultCount: mapped.length });
	} catch {}
	return mapped;
}

function createAbortError(): DOMException {
	return new DOMException("The operation was aborted.", "AbortError");
}

function abortableDelay(ms: number, signal?: AbortSignal): Promise<void> {
	if (signal?.aborted) {
		return Promise.reject(createAbortError());
	}

	return new Promise((resolve, reject) => {
		const onAbort = () => {
			window.clearTimeout(timeoutId);
			reject(createAbortError());
		};
		const timeoutId = window.setTimeout(() => {
			signal?.removeEventListener("abort", onAbort);
			resolve();
		}, ms);

		signal?.addEventListener("abort", onAbort, { once: true });
	});
}

// Mock for demo mode only
export async function mockAiSearch(
	query: string,
	signal?: AbortSignal,
): Promise<Reference[]> {
	await abortableDelay(500, signal);
	const normalized = query.trim().toLowerCase();
	const catalog = [
		{
			slug: "data-usage-check-usage",
			title: "Check mobile data usage",
			snippet:
				"Compare current-cycle usage to the plan cap before treating a spike as a defect.",
		},
		{
			slug: "wifi-assist",
			title: "Reduce cellular usage with Wi-Fi",
			snippet:
				"Streaming and tethering over cellular are common causes of data overage charges.",
		},
		{
			slug: "travel-pass-timing",
			title: "Travel pass activation timing",
			snippet:
				"Roaming passes only apply after activation and do not retroactively cover earlier sessions.",
		},
		{
			slug: "sim-swap-refresh",
			title: "Refresh service after SIM swap",
			snippet:
				"If feature entitlements lag a SIM swap, run a targeted refresh before escalating.",
		},
		{
			slug: "event-congestion",
			title: "Understand temporary event congestion",
			snippet:
				"Large venues can saturate nearby sectors briefly without indicating a persistent outage.",
		},
	];

	const ranked = catalog
		.filter((entry) => {
			if (!normalized) return true;
			const haystack = `${entry.title} ${entry.snippet}`.toLowerCase();
			return haystack.includes(normalized);
		})
		.slice(0, 5);

	const res = (ranked.length ? ranked : catalog.slice(0, 5)).map((entry) => ({
		id: randId("ref"),
		title: entry.title,
		url: `https://telco.example.com/help/${entry.slug}`,
		snippet: entry.snippet,
		visitedAt: null,
		keyParagraph: "",
	}));
	try {
		logEvent("gtc.search", {
			queryLen: query.trim().length,
			resultCount: res.length,
		});
	} catch {}
	return res;
}
