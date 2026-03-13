/**
 * SplitPaneLayout — resizable split-pane wrapper for the curate workspace.
 *
 * Uses react-resizable-panels to provide a draggable gutter between the
 * editor (left) and evidence (right) panes. Persists gutter position in
 * localStorage so it survives across sessions.
 *
 * Replaces the prior CSS grid layout (demo.tsx:277-431) per Phase 3 Step 3.1.
 */

import { useCallback, useState } from "react";
import type { Layout } from "react-resizable-panels";
import { Group, Panel, Separator } from "react-resizable-panels";

const STORAGE_KEY = "gtc-split-pane-sizes";
const MIN_SIZE_PERCENT = 20;
const LEFT_PANEL_ID = "editor";
const RIGHT_PANEL_ID = "evidence";

function loadLayout(): Layout | undefined {
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (raw) return JSON.parse(raw) as Layout;
	} catch {
		// Ignore corrupt data
	}
	return undefined;
}

export default function SplitPaneLayout({
	left,
	right,
	className,
}: {
	left: React.ReactNode;
	right: React.ReactNode;
	className?: string;
}) {
	const [defaultLayout] = useState(
		() => loadLayout() ?? { [LEFT_PANEL_ID]: 60, [RIGHT_PANEL_ID]: 40 },
	);

	const handleLayoutChanged = useCallback((layout: Layout) => {
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
		} catch {
			// Storage full or unavailable
		}
	}, []);

	return (
		<Group
			orientation="horizontal"
			defaultLayout={defaultLayout}
			onLayoutChanged={handleLayoutChanged}
			className={className}
		>
			<Panel id={LEFT_PANEL_ID} minSize={MIN_SIZE_PERCENT}>
				{left}
			</Panel>
			<Separator className="group mx-1 flex w-2 items-center justify-center rounded-full transition-colors hover:bg-violet-100 active:bg-violet-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400">
				<div className="h-8 w-0.5 rounded-full bg-slate-300 transition-colors group-hover:bg-violet-500 group-active:bg-violet-600" />
			</Separator>
			<Panel id={RIGHT_PANEL_ID} minSize={MIN_SIZE_PERCENT}>
				{right}
			</Panel>
		</Group>
	);
}
