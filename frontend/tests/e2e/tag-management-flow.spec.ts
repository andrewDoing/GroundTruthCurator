import { expect, test } from "@playwright/test";
import {
	datasetNameForRun,
	itemIdForDataset,
	openExplorerAndFilter,
	seedDeterministicItem,
} from "./helpers";

test("tag management persists manual tags and filters Explorer results", async ({
	page,
}) => {
	const datasetName = datasetNameForRun();
	const itemId = itemIdForDataset(datasetName);
	const manualTagValue = "playwright-e2e-tag-management";
	const normalizedManualTag = `custom:${manualTagValue}`;

	await seedDeterministicItem(datasetName, itemId);

	await page.goto("/");
	await expect(page.getByText("Ground Truth Curator")).toBeVisible();

	await page.getByRole("button", { name: /Glossary/i }).click();
	await expect(
		page.getByRole("heading", { name: "Tag Glossary" }),
	).toBeVisible();
	await page.keyboard.press("Escape");
	await expect(page.getByRole("heading", { name: "Tag Glossary" })).toHaveCount(
		0,
	);

	await openExplorerAndFilter(page, datasetName, itemId);
	await page.getByRole("button", { name: `Assign ${itemId}` }).click();
	await expect(page.locator('[data-turn-index="0"]').first()).toContainText(
		"Original seeded user message",
	);

	await page.getByRole("button", { name: "Manage Tags" }).click();
	const tagsDialog = page.getByRole("dialog", { name: "Manage Tags" });
	await expect(tagsDialog.getByText("Ground Truth Level Tags")).toBeVisible();
	await tagsDialog.getByPlaceholder("Enter tag name...").fill(manualTagValue);
	await tagsDialog.getByRole("button", { name: "Add" }).click();
	await tagsDialog.getByRole("button", { name: "Done" }).click();

	await expect(
		page.getByText(normalizedManualTag, { exact: true }).first(),
	).toBeVisible();

	await page.getByRole("button", { name: "Save Draft" }).click();
	await expect(page.getByText(`Saved ${itemId} – draft`)).toBeVisible();

	await page.reload();
	await page.getByRole("option", { name: new RegExp(itemId) }).click();
	await expect(page.locator('[data-turn-index="0"]').first()).toContainText(
		"Original seeded user message",
	);
	await expect(
		page.getByText(normalizedManualTag, { exact: true }).first(),
	).toBeVisible();

	await page.getByRole("button", { name: "Explorer" }).click();
	await expect(page.getByText("Explore all ground truths")).toBeVisible();

	const referenceUrlFilter = page.getByLabel("Reference URL:");
	await expect(referenceUrlFilter).toBeVisible();
	await referenceUrlFilter.fill("https://example.com/reference");
	await expect(referenceUrlFilter).toHaveValue("https://example.com/reference");
	await referenceUrlFilter.clear();

	const keywordFilter = page.getByLabel("Keyword Search:");
	await expect(keywordFilter).toBeVisible();
	await keywordFilter.fill(manualTagValue);
	await expect(keywordFilter).toHaveValue(manualTagValue);
	await keywordFilter.clear();

	await page
		.getByRole("button", { name: /Expand tag filters|Collapse tag filters/ })
		.click();
	const manualTagFilter = page
		.locator("button")
		.filter({ hasText: normalizedManualTag })
		.first();
	await manualTagFilter.click();
	await expect(manualTagFilter).toContainText("✓");
	await expect(
		page.getByText(`Including tag: ${normalizedManualTag}`),
	).toBeVisible();
	await page.getByRole("button", { name: "Apply Filters" }).click();

	const filteredRow = page
		.locator("tbody tr")
		.filter({ hasText: itemId })
		.first();
	await expect(filteredRow).toBeVisible();
	await filteredRow.getByRole("button", { name: "Expand tags" }).click();
	await expect(filteredRow).toContainText(normalizedManualTag);
});
