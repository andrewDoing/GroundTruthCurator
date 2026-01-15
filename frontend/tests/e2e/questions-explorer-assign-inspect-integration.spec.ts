import type { Page } from "@playwright/test";
import { expect, test } from "@playwright/test";

import {
	type IntegrationState,
	loadIntegrationState,
} from "./setup/integration-helpers";

let integrationState: IntegrationState;

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

function escapeRegex(input: string): string {
	return input.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

test.describe.configure({ mode: "serial" });

test.beforeAll(async () => {
	const state = await loadIntegrationState();
	if (!state) {
		throw new Error("Integration state not found. Ensure global setup ran.");
	}
	integrationState = state;
});

test.beforeEach(async ({ page }) => {
	await openQuestionsExplorer(page);
});

test("assign button sends request to assign endpoint", async ({ page }) => {
	// Find a draft item
	const draftItem = integrationState.blueprint.items.find(
		(item) => item.meta.status === "draft",
	);
	
	if (!draftItem) {
		throw new Error("No draft item found in test data");
	}

	const itemId = draftItem.meta.id;

	// Wait for the row to be visible
	await waitForTableReady(page);
	
	const row = page.getByRole("row", {
		name: new RegExp(escapeRegex(itemId)),
	});
	await expect(row).toBeVisible();

	// Set up request monitoring
	const assignRequest = page.waitForRequest((request) => {
		return (
			request.method() === "POST" &&
			request.url().includes("/assign") &&
			request.url().includes(itemId)
		);
	});

	// Click the assign button
	const assignButton = row.getByRole("button", { name: /Assign/i });
	await expect(assignButton).toBeVisible();
	await assignButton.click();

	// Verify the assign request was made
	const request = await assignRequest;
	expect(request.url()).toContain(`/${itemId}/assign`);
	
	// Wait for response - may be 200 (newly assigned) or 409 (already assigned)
	const response = await request.response();
	const status = response?.status();
	// Accept both 200 (success) and 409 (already assigned to same user)
	expect([200, 409]).toContain(status);
});

test("inspect button opens modal with item details", async ({ page }) => {
	// Find an item with rich data (question, answer, tags, refs)
	const itemWithData = integrationState.blueprint.items.find(
		(item) =>
			item.meta.question &&
			item.meta.answer &&
			item.meta.tags &&
			item.meta.tags.length > 0,
	);

	if (!itemWithData) {
		throw new Error("No item with rich data found in test data");
	}

	const itemId = itemWithData.meta.id;
	const question = itemWithData.meta.question;
	const answer = itemWithData.meta.answer || "";

	await waitForTableReady(page);

	const row = page.getByRole("row", {
		name: new RegExp(escapeRegex(itemId)),
	});
	await expect(row).toBeVisible();

	// Click the inspect button
	const inspectButton = row.getByRole("button", { name: /Inspect/i });
	await expect(inspectButton).toBeVisible();
	await inspectButton.click();

	// Verify modal opens
	const modal = page.locator('[role="dialog"], .fixed.inset-0').first();
	await expect(modal).toBeVisible({ timeout: 5_000 });

	// Verify modal title
	await expect(modal.getByText("Inspect Ground Truth Item")).toBeVisible();

	// Verify item ID is shown in the modal's ID field
	await expect(modal.getByText("ID")).toBeVisible();
	const idField = modal.locator('.font-mono.text-sm.text-slate-800').filter({ hasText: itemId });
	await expect(idField).toBeVisible();

	// Verify question is shown
	await expect(modal.getByText(question)).toBeVisible();

	// Verify answer is shown (at least partial match)
	if (answer) {
		const answerPreview = answer.substring(0, 50);
		await expect(page.getByText(new RegExp(escapeRegex(answerPreview)))).toBeVisible();
	}
});

test("inspect modal displays all item fields correctly", async ({ page }) => {
	// Find an item with maximum data
	const fullItem = integrationState.blueprint.items.find(
		(item) =>
			item.meta.question &&
			item.meta.answer &&
			item.meta.tags &&
			item.meta.tags.length > 0 &&
			item.meta.status &&
			item.meta.datasetName,
	);

	if (!fullItem) {
		throw new Error("No full item found in test data");
	}

	const itemId = fullItem.meta.id;

	await waitForTableReady(page);

	const row = page.getByRole("row", {
		name: new RegExp(escapeRegex(itemId)),
	});
	await row.getByRole("button", { name: /Inspect/i }).click();

	const modal = page.locator('[role="dialog"], .fixed.inset-0').first();
	await expect(modal).toBeVisible();

	// Verify ID field
	await expect(modal.getByText("ID")).toBeVisible();
	const idField = modal
		.locator(".font-mono.text-sm.text-slate-800")
		.filter({ hasText: itemId });
	await expect(idField).toBeVisible();

	// Verify Status field
	await expect(modal.getByText("Status")).toBeVisible();
	const statusBadge = modal
		.locator("span.inline-block.rounded-full")
		.filter({ hasText: fullItem.meta.status });
	await expect(statusBadge).toBeVisible();

	// Verify Dataset field (if present)
	if (fullItem.meta.datasetName) {
		await expect(modal.getByText("Dataset")).toBeVisible();
		const datasetField = modal
			.locator(".rounded-lg.border.bg-slate-50")
			.filter({ hasText: fullItem.meta.datasetName });
		await expect(datasetField).toBeVisible();
	}

	// Verify Question field
	await expect(modal.getByText("Question")).toBeVisible();
	const questionField = modal
		.locator(".rounded-lg.border.bg-white.min-h-\\[60px\\]")
		.filter({ hasText: fullItem.meta.question });
	await expect(questionField).toBeVisible();

	// Verify Answer field
	const answerLabel = modal.locator(".text-xs.font-medium.text-slate-600", {
		hasText: "Answer",
	});
	await expect(answerLabel).toBeVisible();

	// Verify Tags (if present)
	if (fullItem.meta.tags && fullItem.meta.tags.length > 0) {
		await expect(modal.getByText("Tags")).toBeVisible();
		for (const tag of fullItem.meta.tags) {
			await expect(modal.getByText(tag)).toBeVisible();
		}
	}
});

test("inspect modal can be closed via close button", async ({ page }) => {
	const anyItem = integrationState.blueprint.items[0];
	if (!anyItem) throw new Error("No items in test data");

	const itemId = anyItem.meta.id;

	await waitForTableReady(page);

	const row = page.getByRole("row", {
		name: new RegExp(escapeRegex(itemId)),
	});
	await row.getByRole("button", { name: /Inspect/i }).click();

	const modal = page.locator('[role="dialog"], .fixed.inset-0').first();
	await expect(modal).toBeVisible();

	// Click the close button at the bottom
	const closeButton = page.getByRole("button", { name: /Close/i }).last();
	await closeButton.click();

	// Verify modal is closed
	await expect(modal).not.toBeVisible({ timeout: 5_000 });
});

test("inspect modal can be closed via X button", async ({ page }) => {
	const anyItem = integrationState.blueprint.items[0];
	if (!anyItem) throw new Error("No items in test data");

	const itemId = anyItem.meta.id;

	await waitForTableReady(page);

	const row = page.getByRole("row", {
		name: new RegExp(escapeRegex(itemId)),
	});
	await row.getByRole("button", { name: /Inspect/i }).click();

	const modal = page.locator('[role="dialog"], .fixed.inset-0').first();
	await expect(modal).toBeVisible();

	// Click the X button in the header
	const xButton = page.getByRole("button", { name: "Close" }).first();
	await xButton.click();

	// Verify modal is closed
	await expect(modal).not.toBeVisible({ timeout: 5_000 });
});

test("inspect modal can be closed via ESC key", async ({ page }) => {
	const anyItem = integrationState.blueprint.items[0];
	if (!anyItem) throw new Error("No items in test data");

	const itemId = anyItem.meta.id;

	await waitForTableReady(page);

	const row = page.getByRole("row", {
		name: new RegExp(escapeRegex(itemId)),
	});
	await row.getByRole("button", { name: /Inspect/i }).click();

	const modal = page.locator('[role="dialog"], .fixed.inset-0').first();
	await expect(modal).toBeVisible();

	// Press ESC key
	await page.keyboard.press("Escape");

	// Verify modal is closed
	await expect(modal).not.toBeVisible({ timeout: 5_000 });
});

test("inspect modal handles items without answers", async ({ page }) => {
	// Find an item without an answer
	const itemWithoutAnswer = integrationState.blueprint.items.find(
		(item) => !item.meta.answer || item.meta.answer.trim() === "",
	);

	if (!itemWithoutAnswer) {
		throw new Error("No item without answer found in test data");
	}

	const itemId = itemWithoutAnswer.meta.id;

	await waitForTableReady(page);

	const row = page.getByRole("row", {
		name: new RegExp(escapeRegex(itemId)),
	});
	await row.getByRole("button", { name: /Inspect/i }).click();

	const modal = page.locator('[role="dialog"], .fixed.inset-0').first();
	await expect(modal).toBeVisible();

	// Verify the "no answer" placeholder is shown
	await expect(modal.getByText("(no answer)")).toBeVisible();
});

test("inspect modal displays references when present", async ({ page }) => {
	// Find an item with references (references > 0 means payload has refs)
	const itemWithRefs = integrationState.blueprint.items.find(
		(item) => item.meta.references > 0,
	);

	if (!itemWithRefs) {
		// Skip this test if no items with references exist
		test.skip();
		return;
	}

	const itemId = itemWithRefs.meta.id;
	const refCount = itemWithRefs.meta.references;

	await waitForTableReady(page);

	const row = page.getByRole("row", {
		name: new RegExp(escapeRegex(itemId)),
	});
	await row.getByRole("button", { name: /Inspect/i }).click();

	const modal = page.locator('[role="dialog"], .fixed.inset-0').first();
	await expect(modal).toBeVisible();

	// Verify References section is shown with count
	await expect(
		modal.getByText(new RegExp(`References \\(${refCount}\\)`)),
	).toBeVisible();

	// Verify at least one reference is displayed
	if (itemWithRefs.payload.refs && itemWithRefs.payload.refs.length > 0) {
		const firstRef = itemWithRefs.payload.refs[0];
		if (firstRef?.url) {
			await expect(modal.getByText(new RegExp(escapeRegex(firstRef.url)))).toBeVisible();
		}
	}
});
