import { expect, type Page } from "@playwright/test";

export async function startApp(page: Page) {
	await page.goto("/");
	// Header actions are visible
	await expect(page.getByRole("button", { name: "Export JSON" })).toBeVisible();
	// Wait for main editor controls to be ready (implies an item is selected)
	// Multi-turn mode is now the default, so check for Save Draft instead
	await expect(
		page.getByRole("button", { name: /Save Draft/ }),
	).toBeVisible();
	// Ensure right panel defaults to Search tab when present
	const searchTab = page.getByTitle("Search");
	if (await searchTab.count()) await searchTab.click();
}

export async function toggleSidebar(page: Page, show: boolean) {
	const btn = page.getByRole("button", { name: /Hide Sidebar|Show Sidebar/ });
	const want = show ? "Hide Sidebar" : "Show Sidebar";
	const isWant = await btn.getByText(want).count();
	if (!isWant) await btn.click();
	await expect(page.getByRole("button", { name: want })).toBeVisible();
}

export async function switchToQuestionsView(page: Page) {
	await page.getByRole("button", { name: "Questions View" }).click();
	await expect(
		page.getByRole("button", { name: "Back to Curation" }),
	).toBeVisible();
}

export async function switchToCurateView(page: Page) {
	const btn = page.getByRole("button", {
		name: /Back to Curation|Questions View/,
	});
	const backTo = await btn.getByText("Back to Curation").count();
	if (backTo) {
		await btn.getByText("Back to Curation").click();
	} else {
		// already on curate
	}
	// Multi-turn mode is now the default, so check for Save Draft instead
	await expect(
		page.getByRole("button", { name: /Save Draft/ }),
	).toBeVisible();
}

export async function openStats(page: Page) {
	await page.getByRole("button", { name: "Stats" }).click();
	await expect(
		page.getByRole("button", { name: /Back( to Curation)?/ }),
	).toBeVisible();
}

export async function selectQueueItemByLabel(page: Page, idPrefix: string) {
	const option = page
		.getByRole("option", { name: new RegExp(`^${idPrefix}`) })
		.first();
	if ((await option.count()) > 0) {
		await option.click();
	} else {
		await page
			.getByRole("button", { name: new RegExp(`^${idPrefix}`) })
			.first()
			.click();
	}
}

export async function ensureCurateItemLoaded(page: Page) {
	// Prefer selecting the first queue option to guarantee current item
	const firstOption = page.getByRole("option").first();
	if ((await firstOption.count()) > 0) await firstOption.click();
	// Wait for either Delete or Restore to appear in the editor actions
	const del = page.getByRole("button", { name: "Delete" });
	const rest = page.getByRole("button", { name: "Restore" });
	await Promise.race([
		del.waitFor({ state: "visible" }).catch(() => {}),
		rest.waitFor({ state: "visible" }).catch(() => {}),
	]);
}

export async function ensureDeleteButton(page: Page) {
	const del = page.getByRole("button", { name: "Delete" });
	const rest = page.getByRole("button", { name: "Restore" });
	if ((await del.count()) > 0) return;
	if ((await rest.count()) > 0) {
		await rest.click();
		await expect(del).toBeVisible();
		return;
	}
	// As a last resort, wait briefly for either to appear
	await Promise.race([
		del.waitFor({ state: "visible" }).catch(() => {}),
		rest.waitFor({ state: "visible" }).catch(() => {}),
	]);
}

export async function ensureRestoreButton(page: Page) {
	const del = page.getByRole("button", { name: "Delete" });
	const rest = page.getByRole("button", { name: "Restore" });
	if ((await rest.count()) > 0) return;
	if ((await del.count()) > 0) {
		await del.click();
		await expect(rest).toBeVisible();
		return;
	}
	await Promise.race([
		rest.waitFor({ state: "visible" }).catch(() => {}),
		del.waitFor({ state: "visible" }).catch(() => {}),
	]);
}

export async function saveDraft(page: Page) {
	await page.getByRole("button", { name: /Save Draft|Saving…/ }).click();
	await expectToast(page, /Saved|No changes/i);
}

export async function approve(page: Page) {
	const btn = page.getByRole("button", { name: /Approve|Saving…/ });
	await expect(btn).toBeEnabled();
	await btn.click();
	await expectToast(page, /Saved|approved/i);
}

export async function runSearch(page: Page, query: string) {
	// Support both three-dot and ellipsis characters in placeholder
	const input = page.getByPlaceholder(/Add references via AI Search(\.|…)/);
	await input.fill(query || "CAD");
	await input.locator("..").getByRole("button", { name: "Search" }).click();
}

// Ensure there are at least `minCount` references present by adding from Search if needed
export async function ensureReferences(page: Page, minCount = 2) {
	// Switch to Selected and check how many reference rows exist
	await page.getByRole("button", { name: /Selected \(\d+\)/ }).click();
	const selectedTabBtn = page.getByRole("button", { name: /Selected \(\d+\)/ });
	// Count total reference rows present in Selected tab (by checkbox label)
	const refChecks = page.getByLabel("Selected");
	const totalRows = await refChecks.count();
	// Count how many are currently selected for the model
	// Selected count is shown in the tab label, but we only need total rows here
	await selectedTabBtn.innerText();
	if (totalRows >= minCount) {
		// We have enough references present already; we're done. Tests will choose which to select.
		return;
	}

	// Go to Search, run a query, and click Add on first few results
	await page.getByRole("button", { name: "Search" }).click();
	await runSearch(page, "CAD");
	await expect(page.getByText("Search Results")).toBeVisible({
		timeout: 10_000,
	});
	// Scope to the Search Results panel for row-level actions
	const resultsPanel = page.getByText("Search Results").locator("..");
	// Try direct Add buttons first (exclude ones showing "Added")
	const addButtons = resultsPanel.getByRole("button", { name: /^Add$/ });
	const canAdd = await addButtons.count();
	for (let i = 0; i < Math.min(minCount - totalRows, canAdd); i++) {
		await addButtons.nth(i).click();
		// Wait for confirmation toast of add action (pick first to avoid strict mode)
		await expect(
			page.getByText(/Added \d+ reference\(s\)/).first(),
		).toBeVisible();
		// Short delay to allow state to propagate
		await page.waitForTimeout(100);
	}
	// Also try multi-select + sticky bar as a fallback
	const checks = resultsPanel.locator('input[type="checkbox"]:not([disabled])');
	const checksCount = await checks.count();
	for (let i = 0; i < Math.min(minCount - totalRows, checksCount); i++) {
		await checks.nth(i).check();
	}
	const addSelectedBtn = page.getByRole("button", {
		name: /Add \d+ to Selected/,
	});
	if (await addSelectedBtn.isEnabled()) {
		await addSelectedBtn.click();
		await expect(
			page.getByText(/Added \d+ reference\(s\)/).first(),
		).toBeVisible();
	}
	// Back to Selected and ensure reference rows exist (count may still be 0 if not selected yet)
	await selectedTabBtn.click();
	// Wait until Selected tab badge shows expected count or rows appear
	await expect(async () => {
		const text = await selectedTabBtn.innerText();
		const m = text.match(/Selected \((\d+)\)/);
		const n = m ? Number(m[1]) : 0;
		if (n >= minCount) return;
		const rows = await page.getByLabel("Selected").count();
		if (rows >= minCount) return;
		throw new Error(`No reference rows yet (have ${rows})`);
	}).toPass({ timeout: 10_000 });
}

export async function expectToast(page: Page, pattern: RegExp) {
	// Toast uses a small container in bottom-right; match role button optional
	await expect(page.getByText(pattern)).toBeVisible();
}
