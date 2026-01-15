import { describe, expect, it } from "vitest";
import { DEMO_JSON } from "../../../src/models/demoData";
import { JsonProvider } from "../../../src/models/provider";

describe("JsonProvider duplicate", () => {
	it("creates a new draft with rephrase tag (mutates list)", async () => {
		const jp = new JsonProvider(DEMO_JSON);
		const before = await jp.list();
		const original = before.items[0];

		const created = await jp.duplicate(original);

		// New id
		expect(created.id).not.toBe(original.id);
		expect(created.id.startsWith("temp-")).toBe(true);
		// Core fields copied
		expect(created.question).toBe(original.question);
		expect(created.answer).toBe(original.answer);
		expect(created.references?.length).toBe(original.references?.length);
		// Draft status and not deleted
		expect(created.status).toBe("draft");
		expect(created.deleted).toBe(false);
		// Tag present exactly once
		const tag = `rephrase:${original.id}`;
		const occurrences = (created.tags || []).filter((t) => t === tag).length;
		expect(occurrences).toBe(1);

		// Provider state: duplicate is inserted at the front
		const after = await jp.list();
		expect(after.items.length).toBe(before.items.length + 1);
		expect(after.items[0].id).toBe(created.id);
	});
});
