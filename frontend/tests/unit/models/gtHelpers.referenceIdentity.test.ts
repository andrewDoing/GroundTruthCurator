import { describe, expect, it } from "vitest";
import type { Reference } from "../../../src/models/groundTruth";
import { dedupeReferences } from "../../../src/models/gtHelpers";

function makeReference(overrides: Partial<Reference> = {}): Reference {
	return {
		id: overrides.id ?? "ref-1",
		url: overrides.url ?? "https://example.com/doc",
		title: overrides.title,
		snippet: overrides.snippet,
		visitedAt: overrides.visitedAt ?? null,
		keyParagraph: overrides.keyParagraph,
		bonus: overrides.bonus ?? false,
		messageIndex: overrides.messageIndex,
		turnId: overrides.turnId ?? "turn-agent-1",
		toolCallId: overrides.toolCallId ?? "tool-call-search",
	};
}

describe("dedupeReferences chunk-aware identity", () => {
	it("keeps same-url references distinct when snippet data differs within one tool/turn owner", () => {
		const existing = [
			makeReference({
				id: "ref-existing",
				snippet: "Chunk A",
				keyParagraph: "Paragraph A",
			}),
		];
		const chosen = [
			makeReference({
				id: "ref-chosen",
				snippet: "Chunk B",
				keyParagraph: "Paragraph B",
			}),
		];

		const deduped = dedupeReferences(existing, chosen);

		expect(deduped).toHaveLength(2);
		expect(deduped.map((ref) => ref.snippet)).toEqual(["Chunk A", "Chunk B"]);
	});

	it("preserves legacy same-owner URL dedupe when chunk-level data is absent", () => {
		const existing = [
			makeReference({
				id: "ref-existing",
				snippet: undefined,
				keyParagraph: undefined,
			}),
		];
		const chosen = [
			makeReference({
				id: "ref-chosen",
				snippet: undefined,
				keyParagraph: undefined,
			}),
		];

		const deduped = dedupeReferences(existing, chosen);

		expect(deduped).toHaveLength(1);
		expect(deduped[0]?.id).toBe("ref-existing");
	});
});
