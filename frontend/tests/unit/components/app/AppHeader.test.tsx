import { fireEvent, render, screen } from "@testing-library/react";
import AppHeader from "../../../../src/components/app/AppHeader";

describe("AppHeader", () => {
	const setup = (
		over: Partial<React.ComponentProps<typeof AppHeader>> = {},
	) => {
		const props: React.ComponentProps<typeof AppHeader> = {
			demoMode: true,
			sidebarOpen: true,
			viewMode: "curate",
			onToggleSidebar: vi.fn(),
			onToggleViewMode: vi.fn(),
			onOpenStats: vi.fn(),
			onExportJson: vi.fn(),
			...over,
		};
		render(<AppHeader {...props} />);
		return props;
	};

	it("renders DEMO badge when demoMode is true", () => {
		setup();
		expect(screen.getByText(/DEMO MODE/i)).toBeInTheDocument();
	});

	it("renders the application title", () => {
		setup();
		// Expect the default title "Ground Truth Curator" or part of it
		expect(screen.getByText(/Ground Truth Curator/i)).toBeInTheDocument();
	});

	it("calls onToggleSidebar when sidebar button is clicked", () => {
		const props = setup();
		fireEvent.click(
			screen.getByRole("button", { name: /Hide Sidebar|Show Sidebar/i }),
		);
		expect(props.onToggleSidebar).toHaveBeenCalled();
	});

	it("calls onToggleViewMode when view toggle clicked", () => {
		const props = setup({ viewMode: "curate" });
		fireEvent.click(
			screen.getByRole("button", { name: /Questions View|Back to Curation/i }),
		);
		expect(props.onToggleViewMode).toHaveBeenCalled();
	});

	it("calls onOpenStats when Stats clicked", () => {
		const props = setup();
		fireEvent.click(screen.getByRole("button", { name: /Stats/i }));
		expect(props.onOpenStats).toHaveBeenCalled();
	});

	it("calls onExportJson when Export JSON clicked", () => {
		const props = setup();
		fireEvent.click(screen.getByRole("button", { name: /Export JSON/i }));
		expect(props.onExportJson).toHaveBeenCalled();
	});
});
