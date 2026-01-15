import { render } from "@testing-library/react";
import type React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ErrorBoundary from "../../src/components/common/ErrorBoundary";
import * as telemetry from "../../src/services/telemetry";

describe("ErrorBoundary", () => {
	beforeEach(() => {
		vi.spyOn(telemetry, "logException").mockImplementation(() => {});
	});

	it("renders fallback on error and logs exception", () => {
		const Boom: React.FC = () => {
			throw new Error("boom");
		};
		const { getByRole } = render(
			<ErrorBoundary>
				<Boom />
			</ErrorBoundary>,
		);
		expect(getByRole("alert")).toBeTruthy();
		expect(telemetry.logException).toHaveBeenCalled();
	});
});
