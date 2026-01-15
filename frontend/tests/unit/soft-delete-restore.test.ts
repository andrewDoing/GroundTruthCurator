import { describe, expect, it } from "vitest";
import { DEMO_JSON } from "../../src/models/demoData";
import { JsonProvider } from "../../src/models/provider";

describe("soft-delete and restore (JsonProvider)", () => {
	it("marks item as deleted without bumping version (content unchanged)", async () => {
		const p = new JsonProvider(JSON.parse(JSON.stringify(DEMO_JSON)));
		const list = await p.list();
		const base = list.items[0];
		expect(base.deleted).toBe(false);

		const saved = await p.save({ ...base, deleted: true });
		expect(saved.deleted).toBe(true);

		// Item is persisted as deleted on subsequent get
		const again = await p.get(base.id);
		expect(again?.deleted).toBe(true);
	});

	it("restores item (deleted -> false) without content change", async () => {
		const p = new JsonProvider(JSON.parse(JSON.stringify(DEMO_JSON)));
		const list = await p.list();
		const base = list.items[0];

		const deleted = await p.save({ ...base, deleted: true });
		expect(deleted.deleted).toBe(true);

		const restored = await p.save({ ...deleted, deleted: false });
		expect(restored.deleted).toBe(false);
	});
});
