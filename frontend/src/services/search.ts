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
): Promise<Reference[]> {
	const q = query.trim();
	if (!q) return [];
	const { data, error } = await client.GET("/v1/search", {
		params: { query: { q, top } },
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

// Mock for demo mode only
export async function mockAiSearch(query: string): Promise<Reference[]> {
	await new Promise((r) => setTimeout(r, 500));
	const base = `https://example.com/product/${encodeURIComponent(
		query.toLowerCase().replace(/\s+/g, "-"),
	)}`;
	const mk = (n: number): Reference => ({
		id: randId("ref"),
		title: `${query} – Result ${n}`,
		url: `${base}-${n}`,
		snippet: `Relevant snippet ${n} for ${query}. Mentions key commands, options, and caveats...`,
		visitedAt: null,
		keyParagraph: "",
	});
	const res = [mk(1), mk(2), mk(3), mk(4), mk(5)];
	try {
		logEvent("gtc.search", {
			queryLen: query.trim().length,
			resultCount: res.length,
		});
	} catch {}
	return res;
}
