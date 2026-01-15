import { client } from "../api/client";
import type { components } from "../api/generated";
import type { ConversationTurn, ExpectedBehavior } from "../models/groundTruth";
import { formatConversationForAgent as formatTurns } from "../models/groundTruth";

export type ChatReference = components["schemas"]["ChatReference"];

/**
 * Maps expected behavior identifiers to descriptive instructions for the agent.
 * These provide rich context to help the backend generate appropriate responses.
 */
const BEHAVIOR_DESCRIPTIONS: Record<ExpectedBehavior, string> = {
	"tool:search":
		"Perform a search or retrieval operation to find relevant information",
	"generation:answer":
		"Generate a direct, comprehensive answer to the user's question",
	"generation:need-context":
		"Indicate that more context or background information is needed to properly answer the question",
	"generation:clarification":
		"Ask for clarification about ambiguous or unclear aspects of the user's question",
	"generation:out-of-domain":
		"Politely indicate that the question is outside the scope of what you can help with",
};

/**
 * Formats expected behavior array into descriptive instructions for inclusion in chat requests.
 * Returns empty string if array is empty or undefined.
 * Example output:
 * "Expected Behavior: Perform a search or retrieval operation to find relevant information; Generate a direct, comprehensive answer to the user's question"
 */
export function formatExpectedBehaviorForChat(
	behaviors: ExpectedBehavior[] | undefined,
): string {
	if (!behaviors || behaviors.length === 0) return "";

	const descriptions = behaviors
		.map((behavior) => BEHAVIOR_DESCRIPTIONS[behavior])
		.filter(Boolean); // Filter out any undefined descriptions

	if (descriptions.length === 0) return "";

	return `Expected Behavior: ${descriptions.join("; ")}`;
}

export function formatConversationForAgent(
	turns: ConversationTurn[] | undefined,
	upToIndex?: number,
): string {
	return formatTurns(turns, upToIndex);
}

export async function callAgentChat(
	message: string,
): Promise<{ content: string; references: ChatReference[] }> {
	const trimmed = message.trim();
	if (!trimmed) {
		throw new Error("Agent chat message is required.");
	}

	// Create AbortController for timeout protection
	const controller = new AbortController();
	const timeoutId = setTimeout(() => controller.abort(), 120000); // 120s timeout

	try {
		const body: components["schemas"]["ChatRequest"] = {
			message: trimmed,
		};
		const { data, error } = await client.POST("/v1/chat", {
			body,
			signal: controller.signal,
		});

		if (error) throw error;
		const payload = data as components["schemas"]["ChatResponse"];
		return {
			content: payload.content,
			references: payload.references ?? [],
		};
	} finally {
		clearTimeout(timeoutId);
	}
}
