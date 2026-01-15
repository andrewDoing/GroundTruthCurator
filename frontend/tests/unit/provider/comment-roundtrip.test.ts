import { describe, expect, it } from "vitest";
import { DEMO_JSON } from "../../../src/models/demoData";
import { JsonProvider } from "../../../src/models/provider";

describe("Provider comment roundtrip", () => {
	it("json provider preserves comment on save/get", async () => {
		const jp = new JsonProvider(DEMO_JSON);
		const list = await jp.list();
		const first = list.items[0];
		const updated = await jp.save({ ...first, comment: "hello" });
		expect(updated.comment).toBe("hello");
		const fetched = await jp.get(first.id);
		expect(fetched?.comment).toBe("hello");
	});
});
