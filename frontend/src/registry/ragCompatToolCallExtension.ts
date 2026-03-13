// RAG-compat tool call extension registration.
//
// Registers a "references" action on retrieval-type tool calls so curators
// can view and manage per-call references inline in the tool call card.
//
// This module self-registers on import (side-effect), following the same
// pattern as ExplorerExtensions.ts.

import ToolCallReferencesAction from "../components/app/editors/ToolCallReferencesAction";
import { toolCallExtensions } from "./FieldComponentRegistry";

/** Tool names that indicate a retrieval / search call. */
const RETRIEVAL_TOOL_NAMES = new Set([
	"search",
	"retrieval",
	"lookup",
	"fetch",
	"query",
	"find",
	"get_documents",
	"search_documents",
	"vector_search",
]);

function isRetrievalToolCall(name: string): boolean {
	const lower = name.toLowerCase();
	// Exact match
	if (RETRIEVAL_TOOL_NAMES.has(lower)) return true;
	// Substring match for compound names like "azure_search", "doc_retrieval"
	for (const keyword of RETRIEVAL_TOOL_NAMES) {
		if (lower.includes(keyword)) return true;
	}
	return false;
}

toolCallExtensions.register({
	discriminator: "toolCall",
	component: ToolCallReferencesAction,
	displayName: "RAG References",
	matches: (tc) => isRetrievalToolCall(tc.name),
});
