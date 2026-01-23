import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { FilterState } from "../../../src/types/filters";
import {
	filterStateToUrlParams,
	getCurrentSearch,
	parseFilterStateFromUrl,
	updateUrlWithoutReload,
} from "../../../src/utils/filterUrlParams";

describe("filterUrlParams utilities", () => {
	const defaultFilter: FilterState = {
		status: "all",
		dataset: "all",
		tags: { include: [], exclude: [] },
		itemId: "",
		refUrl: "",
		keyword: "",
		sortColumn: null,
		sortDirection: "desc",
	};

	beforeEach(() => {
		// Reset window.location and window.history mocks
		vi.stubGlobal("location", {
			search: "",
			pathname: "/",
			href: "/",
			origin: "http://localhost",
			protocol: "http:",
			host: "localhost",
			hostname: "localhost",
			port: "",
			hash: "",
		});
		window.history.replaceState = vi.fn();
	});

	afterEach(() => {
		vi.clearAllMocks();
	});

	describe("parseFilterStateFromUrl", () => {
		it("should parse status filter", () => {
			const result = parseFilterStateFromUrl("?status=draft");
			expect(result.status).toBe("draft");
		});

		it("should parse dataset filter", () => {
			const result = parseFilterStateFromUrl("?dataset=test-dataset");
			expect(result.dataset).toBe("test-dataset");
		});

		it("should parse tags as comma-separated list", () => {
			const result = parseFilterStateFromUrl("?tags=tag1,tag2,tag3");
			expect(result.tags).toEqual({
				include: ["tag1", "tag2", "tag3"],
				exclude: [],
			});
		});

		it("should parse itemId filter", () => {
			const result = parseFilterStateFromUrl("?itemId=item-123");
			expect(result.itemId).toBe("item-123");
		});

		it("should parse and decode refUrl filter", () => {
			const encodedUrl = encodeURIComponent(
				"https://example.com/page?param=value",
			);
			const result = parseFilterStateFromUrl(`?refUrl=${encodedUrl}`);
			expect(result.refUrl).toBe("https://example.com/page?param=value");
		});

		it("should parse sortColumn filter", () => {
			const result = parseFilterStateFromUrl("?sortColumn=refs");
			expect(result.sortColumn).toBe("refs");
		});

		it("should parse sortDirection filter", () => {
			const result = parseFilterStateFromUrl("?sortDirection=asc");
			expect(result.sortDirection).toBe("asc");
		});

		it("should parse multiple filters", () => {
			const search =
				"?status=approved&dataset=my-dataset&tags=important,validated&sortColumn=reviewedAt&sortDirection=asc";
			const result = parseFilterStateFromUrl(search);
			expect(result).toEqual({
				status: "approved",
				dataset: "my-dataset",
				tags: { include: ["important", "validated"], exclude: [] },
				sortColumn: "reviewedAt",
				sortDirection: "asc",
			});
		});

		it("should reject invalid status values", () => {
			const result = parseFilterStateFromUrl("?status=invalid");
			expect(result.status).toBeUndefined();
		});

		it("should reject invalid sortColumn values", () => {
			const result = parseFilterStateFromUrl("?sortColumn=invalid");
			expect(result.sortColumn).toBeUndefined();
		});

		it("should reject invalid sortDirection values", () => {
			const result = parseFilterStateFromUrl("?sortDirection=invalid");
			expect(result.sortDirection).toBeUndefined();
		});

		it("should handle empty search string", () => {
			const result = parseFilterStateFromUrl("");
			expect(result).toEqual({});
		});

		it("should trim whitespace from tags", () => {
			const result = parseFilterStateFromUrl("?tags=tag1%20,tag2,tag3%20");
			expect(result.tags).toEqual({
				include: ["tag1", "tag2", "tag3"],
				exclude: [],
			});
		});

		it("should filter out empty tags", () => {
			const result = parseFilterStateFromUrl("?tags=tag1,,tag2");
			expect(result.tags).toEqual({ include: ["tag1", "tag2"], exclude: [] });
		});
	});

	describe("filterStateToUrlParams", () => {
		it("should omit default values to keep URLs clean", () => {
			const filter = defaultFilter;
			const params = filterStateToUrlParams(filter, defaultFilter);
			expect(params.toString()).toBe("");
		});

		it("should include non-default status", () => {
			const filter: FilterState = { ...defaultFilter, status: "draft" };
			const params = filterStateToUrlParams(filter, defaultFilter);
			expect(params.get("status")).toBe("draft");
		});

		it("should include non-default dataset", () => {
			const filter: FilterState = { ...defaultFilter, dataset: "my-dataset" };
			const params = filterStateToUrlParams(filter, defaultFilter);
			expect(params.get("dataset")).toBe("my-dataset");
		});

		it("should include non-empty tags", () => {
			const filter: FilterState = {
				...defaultFilter,
				tags: { include: ["tag1", "tag2"], exclude: [] },
			};
			const params = filterStateToUrlParams(filter, defaultFilter);
			expect(params.get("tags")).toBe("tag1,tag2");
		});

		it("should include itemId", () => {
			const filter: FilterState = { ...defaultFilter, itemId: "item-123" };
			const params = filterStateToUrlParams(filter, defaultFilter);
			expect(params.get("itemId")).toBe("item-123");
		});

		it("should include and encode refUrl", () => {
			const refUrl = "https://example.com/page?param=value";
			const filter: FilterState = { ...defaultFilter, refUrl };
			const params = filterStateToUrlParams(filter, defaultFilter);
			expect(decodeURIComponent(params.get("refUrl") ?? "")).toBe(refUrl);
		});

		it("should include sortColumn", () => {
			const filter: FilterState = { ...defaultFilter, sortColumn: "refs" };
			const params = filterStateToUrlParams(filter, defaultFilter);
			expect(params.get("sortColumn")).toBe("refs");
		});

		it("should include non-default sortDirection", () => {
			const filter: FilterState = { ...defaultFilter, sortDirection: "asc" };
			const params = filterStateToUrlParams(filter, defaultFilter);
			expect(params.get("sortDirection")).toBe("asc");
		});

		it("should include all non-default parameters", () => {
			const filter: FilterState = {
				status: "approved",
				dataset: "my-dataset",
				tags: { include: ["important"], exclude: [] },
				itemId: "item-456",
				refUrl: "https://example.com",
				sortColumn: "reviewedAt",
				sortDirection: "asc",
			};
			const params = filterStateToUrlParams(filter, defaultFilter);
			expect(params.get("status")).toBe("approved");
			expect(params.get("dataset")).toBe("my-dataset");
			expect(params.get("tags")).toBe("important");
			expect(params.get("itemId")).toBe("item-456");
			expect(params.get("sortColumn")).toBe("reviewedAt");
			expect(params.get("sortDirection")).toBe("asc");
		});

		it("should omit empty tags", () => {
			const filter: FilterState = {
				...defaultFilter,
				tags: { include: [], exclude: [] },
			};
			const params = filterStateToUrlParams(filter, defaultFilter);
			expect(params.get("tags")).toBeNull();
		});
	});

	describe("updateUrlWithoutReload", () => {
		it("should call replaceState with correct URL", () => {
			updateUrlWithoutReload("status=draft&dataset=test");
			expect(window.history.replaceState).toHaveBeenCalledWith(
				expect.any(Object),
				"",
				"/?status=draft&dataset=test",
			);
		});

		it("should preserve pathname", () => {
			vi.stubGlobal("location", {
				search: "",
				pathname: "/explorer",
				href: "http://localhost/explorer",
				origin: "http://localhost",
				protocol: "http:",
				host: "localhost",
				hostname: "localhost",
				port: "",
				hash: "",
			});
			updateUrlWithoutReload("status=approved");
			expect(window.history.replaceState).toHaveBeenCalledWith(
				expect.any(Object),
				"",
				"/explorer?status=approved",
			);
		});

		it("should handle empty search params", () => {
			updateUrlWithoutReload("");
			expect(window.history.replaceState).toHaveBeenCalledWith(
				expect.any(Object),
				"",
				"/",
			);
		});
	});

	describe("getCurrentSearch", () => {
		it("should return current window.location.search", () => {
			vi.stubGlobal("location", {
				search: "?status=draft",
				pathname: "/",
				href: "http://localhost?status=draft",
				origin: "http://localhost",
				protocol: "http:",
				host: "localhost",
				hostname: "localhost",
				port: "",
				hash: "",
			});
			const search = getCurrentSearch();
			expect(search).toBe("?status=draft");
		});

		it("should return empty string if no search params", () => {
			vi.stubGlobal("location", {
				search: "",
				pathname: "/",
				href: "http://localhost",
				origin: "http://localhost",
				protocol: "http:",
				host: "localhost",
				hostname: "localhost",
				port: "",
				hash: "",
			});
			const search = getCurrentSearch();
			expect(search).toBe("");
		});
	});

	describe("Round-trip conversion", () => {
		it("should preserve filter state through encode/decode cycle", () => {
			const originalFilter: FilterState = {
				status: "approved",
				dataset: "production",
				tags: { include: ["validated", "important"], exclude: [] },
				itemId: "item-789",
				refUrl: "https://example.com/reference",
				sortColumn: "reviewedAt",
				sortDirection: "asc",
			};

			// Encode to URL
			const params = filterStateToUrlParams(originalFilter, defaultFilter);
			const search = `?${params.toString()}`;

			// Decode from URL
			const decodedFilter = parseFilterStateFromUrl(search);

			// Verify all fields match
			expect(decodedFilter.status).toBe(originalFilter.status);
			expect(decodedFilter.dataset).toBe(originalFilter.dataset);
			expect(decodedFilter.tags).toEqual(originalFilter.tags);
			expect(decodedFilter.itemId).toBe(originalFilter.itemId);
			expect(decodedFilter.refUrl).toBe(originalFilter.refUrl);
			expect(decodedFilter.sortColumn).toBe(originalFilter.sortColumn);
			expect(decodedFilter.sortDirection).toBe(originalFilter.sortDirection);
		});

		it("should handle special characters in URLs", () => {
			const complexUrl =
				"https://example.com/page?query=search&param=value#section";
			const filter: FilterState = { ...defaultFilter, refUrl: complexUrl };

			const params = filterStateToUrlParams(filter, defaultFilter);
			const search = `?${params.toString()}`;
			const decoded = parseFilterStateFromUrl(search);

			expect(decoded.refUrl).toBe(complexUrl);
		});
	});
});
