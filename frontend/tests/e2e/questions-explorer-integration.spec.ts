import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

import {
	type IntegrationState,
	loadIntegrationState,
} from "./setup/integration-helpers";
import type {
	QuestionsExplorerBlueprintItem,
	QuestionsExplorerSeedItem,
} from "./setup/test-data";

let integrationState: IntegrationState;
let metasByDataset: Map<string, QuestionsExplorerBlueprintItem[]>;

const STATUS_BUTTON_LABEL: Record<string, string> = {
	all: "All",
	draft: "Draft",
	approved: "Approved",
	skipped: "Skipped",
	deleted: "Deleted",
};

async function openQuestionsExplorer(page: Page) {
	await page.goto("/");
	await expect(page.getByRole("button", { name: "Export JSON" })).toBeVisible();
	await page.getByRole("button", { name: "Questions View" }).click();
	await expect(
		page.getByRole("button", { name: /Apply Filters|Loading/ }),
	).toBeVisible({ timeout: 15_000 });
	await waitForTableReady(page);
}

async function waitForTableReady(page: Page, minimum = 1) {
	await expect(async () => {
		const legacyLoading = await page
			.getByText("Loading ground truths…")
			.isVisible()
			.catch(() => false);
		const applyButtonLoading = await page
			.getByRole("button", { name: "Loading..." })
			.isVisible()
			.catch(() => false);
		if (legacyLoading || applyButtonLoading)
			throw new Error("table still loading");
		const rows = await page.locator("tbody tr").count();
		if (rows < minimum)
			throw new Error(`have ${rows} rows, expected ≥ ${minimum}`);
	}).toPass({ timeout: 15_000 });
}

async function applyFilters(page: Page, expectedRows?: number) {
	const button = page.getByRole("button", { name: "Apply Filters" });
	const isEnabled = await button.isEnabled();
	if (isEnabled) {
		await button.click();
		await expect(button).toBeDisabled({ timeout: 15_000 });
	} else {
		// Filters already applied; allow UI to settle.
		await page.waitForTimeout(250);
	}
	if (typeof expectedRows === "number") {
		await expect(async () => {
			const rows = await page.locator("tbody tr").count();
			if (rows !== expectedRows) {
				throw new Error(`expected ${expectedRows} rows, saw ${rows}`);
			}
		}).toPass({ timeout: 15_000 });
	} else {
		await waitForTableReady(page);
	}
}

async function selectStatus(
	page: Page,
	status: keyof typeof STATUS_BUTTON_LABEL,
) {
	const label = STATUS_BUTTON_LABEL[status];
	await page
		.getByRole("button", { name: new RegExp(`^${escapeRegex(label)}$`) })
		.click();
}

async function selectDataset(page: Page, datasetName: string) {
	const dropdown = page.getByLabel("Dataset:");
	await expect(dropdown).toBeVisible({ timeout: 15_000 });
	const option = dropdown.locator(`option[value="${datasetName}"]`);
	await option.waitFor({ state: "attached", timeout: 15_000 });
	// Selecting "all" first avoids React ignoring a redundant value update.
	await dropdown.selectOption({ value: "all" });
	await dropdown.selectOption({ value: datasetName });
	await expect(dropdown).toHaveValue(datasetName);
}

async function expandTagsFilter(page: Page) {
	const toggle = page.getByRole("button", {
		name: /Filter by Tags|Expand tag filters/i,
	});
	const expanded = await toggle.getAttribute("aria-expanded");
	if (expanded !== "true") await toggle.click();
}

async function selectTag(page: Page, tag: string) {
	await page
		.getByRole("button", { name: new RegExp(`^${escapeRegex(tag)}$`) })
		.click();
}

function escapeRegex(input: string): string {
	return input.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

async function getStatuses(page: Page): Promise<string[]> {
	return page.locator("tbody tr td:nth-child(2)").evaluateAll((cells) =>
		cells.map((cell) => {
			const raw = (cell.textContent || "").toLowerCase();
			if (raw.includes("deleted")) return "deleted";
			if (raw.includes("approved")) return "approved";
			if (raw.includes("skipped")) return "skipped";
			if (raw.includes("draft")) return "draft";
			return (cell.textContent || "").trim().split(/\s+/)[0] ?? "";
		}),
	);
}

async function getRowIds(page: Page): Promise<string[]> {
	return page
		.locator("tbody tr td:first-child div")
		.evaluateAll((cells) =>
			cells.map((cell) => (cell.textContent || "").trim()),
		);
}

async function getReferenceCounts(page: Page): Promise<number[]> {
	return page
		.locator("tbody tr td:nth-child(6)")
		.evaluateAll((cells) =>
			cells.map(
				(cell) => Number.parseInt((cell.textContent || "0").trim(), 10) || 0,
			),
		);
}

async function changeItemsPerPage(page: Page, value: number) {
	const selector = page.getByLabel("Items per page:");
	await selector.selectOption(String(value));
	await expect(async () => {
		const rows = await page.locator("tbody tr").count();
		if (rows === 0) throw new Error("no rows present");
		if (rows > value)
			throw new Error(
				`expected ≤ ${value} rows after pagination change, saw ${rows}`,
			);
	}).toPass({ timeout: 15_000 });
}

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
	const state = await loadIntegrationState();
	if (!state) {
		throw new Error("Integration state not found. Ensure global setup ran.");
	}
	integrationState = state;
	metasByDataset = new Map();
	for (const entry of state.blueprint.items) {
		const arr = metasByDataset.get(entry.meta.datasetName) ?? [];
		arr.push(entry.meta);
		metasByDataset.set(entry.meta.datasetName, arr);
	}
});

test.beforeEach(async ({ page }) => {
	await openQuestionsExplorer(page);
});

test("loads seeded questions from backend", async ({ page }) => {
	const dataset = integrationState.blueprint.primaryDataset;
	await selectDataset(page, dataset);
	const datasetItems = metasByDataset.get(dataset) ?? [];
	await applyFilters(page, datasetItems.length);
	const firstMatch = integrationState.blueprint.items.find(
		(item: QuestionsExplorerSeedItem) =>
			item.meta.datasetName === dataset && item.meta.status !== "deleted",
	);
	if (!firstMatch) throw new Error(`No item found for dataset ${dataset}`);
	const row = page.getByRole("row", {
		name: new RegExp(escapeRegex(firstMatch.meta.id)),
	});
	await expect(row).toContainText(firstMatch.meta.question);
	await expect(row).toContainText(firstMatch.meta.status);
});

test("filters by status categories", async ({ page }) => {
	await selectStatus(page, "draft");
	await applyFilters(page, integrationState.blueprint.statusCounts.draft);
	const draftStatuses = await getStatuses(page);
	expect(new Set(draftStatuses)).toEqual(new Set(["draft"]));
	await selectStatus(page, "approved");
	await applyFilters(page, integrationState.blueprint.statusCounts.approved);
	const approvedStatuses = await getStatuses(page);
	expect(new Set(approvedStatuses)).toEqual(new Set(["approved"]));
	await selectStatus(page, "deleted");
	await applyFilters(page, integrationState.blueprint.statusCounts.deleted);
	const deletedStatuses = await getStatuses(page);
	expect(new Set(deletedStatuses)).toEqual(new Set(["deleted"]));
});

test("filters by dataset", async ({ page }) => {
	const datasetKeys = Array.from(metasByDataset.keys());
	const targetDataset =
		datasetKeys[1] ?? integrationState.blueprint.primaryDataset;
	const datasetItems = metasByDataset.get(targetDataset) ?? [];
	const expectedCount = datasetItems.length;
	await selectDataset(page, targetDataset);
	await applyFilters(page, expectedCount);
	const ids = await getRowIds(page);
	const expectedIds = new Set(datasetItems.map((meta) => meta.id));
	for (const id of ids) {
		expect(expectedIds.has(id)).toBeTruthy();
	}
});

test("filters by tags with AND logic", async ({ page }) => {
	const { tags, itemId } = integrationState.blueprint.multiTagTarget;
	await expandTagsFilter(page);
	for (const tag of tags) await selectTag(page, tag);
	await applyFilters(page, 1);
	const ids = await getRowIds(page);
	expect(ids).toContain(itemId);
});

test("sorts by references count", async ({ page }) => {
	const dataset = integrationState.blueprint.primaryDataset;
	const datasetItems = metasByDataset.get(dataset) ?? [];
	await selectDataset(page, dataset);
	await applyFilters(page, datasetItems.length);
	await page.getByRole("button", { name: /Sort by References|Refs/i }).click();
	await applyFilters(page, datasetItems.length);
	const refsDesc = await getReferenceCounts(page);
	const sortedDesc = [...refsDesc].sort((a, b) => b - a);
	expect(refsDesc).toEqual(sortedDesc);
	await page.getByRole("button", { name: /Sort by References|Refs/i }).click();
	await applyFilters(page, datasetItems.length);
	const refsAsc = await getReferenceCounts(page);
	const sortedAsc = [...refsAsc].sort((a, b) => a - b);
	expect(refsAsc).toEqual(sortedAsc);
});

test("paginates results when page size changes", async ({ page }) => {
	await changeItemsPerPage(page, 10);
	await waitForTableReady(page, 10);
	const firstPageIds = await getRowIds(page);
	expect(firstPageIds.length).toBe(10);
	await page.getByRole("button", { name: "Next" }).click();
	await waitForTableReady(page, 1);
	const secondPageIds = await getRowIds(page);
	expect(secondPageIds.length).toBeGreaterThan(0);
	expect(secondPageIds[0]).not.toBe(firstPageIds[0]);
	await expect(page.getByText(/Page 2 of/)).toBeVisible();
});

test("applies dataset, status, and tag filters together", async ({ page }) => {
	const { tags, itemId } = integrationState.blueprint.multiTagTarget;
	const datasetEntry = integrationState.blueprint.items.find(
		(item: QuestionsExplorerSeedItem) => item.meta.id === itemId,
	);
	const dataset = datasetEntry?.meta.datasetName;
	if (!dataset) throw new Error("Multi-tag dataset missing");
	await selectDataset(page, dataset);
	await selectStatus(page, "approved");
	await expandTagsFilter(page);
	for (const tag of tags) await selectTag(page, tag);
	await applyFilters(page, 1);
	const ids = await getRowIds(page);
	expect(ids).toEqual([itemId]);
});

test("soft deletes an item from explorer", async ({ page }) => {
	const deleteId = integrationState.blueprint.deleteCandidateId;
	const datasetEntry = integrationState.blueprint.items.find(
		(item: QuestionsExplorerSeedItem) => item.meta.id === deleteId,
	);
	const dataset = datasetEntry?.meta.datasetName;
	if (!dataset) throw new Error("Delete candidate dataset missing");
	await selectDataset(page, dataset);
	const datasetItems = metasByDataset.get(dataset) ?? [];
	await applyFilters(page, datasetItems.length);
	const row = page.getByRole("row", {
		name: new RegExp(escapeRegex(deleteId)),
	});
	await expect(row).toBeVisible();
	const deleteRequest = page.waitForRequest((request) => {
		return request.method() === "DELETE" && request.url().includes(deleteId);
	});
	await row.getByRole("button", { name: `Delete ${deleteId}` }).click();
	const deleteIssued = await deleteRequest;
	await deleteIssued.response();
	await selectStatus(page, "deleted");
	await selectDataset(page, "all");
	await applyFilters(page);
	await expect(async () => {
		const ids = await getRowIds(page);
		if (!ids.includes(deleteId))
			throw new Error(`deleted list missing ${deleteId}`);
	}).toPass({ timeout: 15_000 });
	const ids = await getRowIds(page);
	expect(ids.length).toBeGreaterThanOrEqual(
		integrationState.blueprint.statusCounts.deleted,
	);
});
