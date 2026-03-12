/**
 * EvidenceDrawer — mobile slide-in drawer for the evidence/references panel.
 *
 * Below the `lg` breakpoint the evidence pane is hidden from the main layout
 * and instead rendered inside this overlay drawer that slides in from the right.
 * Closes on outside click or via the explicit close button.
 *
 * Phase 3 Step 3.2.
 */

import { useEffect, useRef } from "react";
import { cn } from "../../../models/utils";

export default function EvidenceDrawer({
	open,
	onClose,
	children,
}: {
	open: boolean;
	onClose: () => void;
	children: React.ReactNode;
}) {
	const drawerRef = useRef<HTMLDivElement>(null);

	// Close on Escape
	useEffect(() => {
		if (!open) return;
		function handleKey(e: KeyboardEvent) {
			if (e.key === "Escape") onClose();
		}
		window.addEventListener("keydown", handleKey);
		return () => window.removeEventListener("keydown", handleKey);
	}, [open, onClose]);

	// Close on outside click
	useEffect(() => {
		if (!open) return;
		function handleClick(e: MouseEvent) {
			if (drawerRef.current && !drawerRef.current.contains(e.target as Node)) {
				onClose();
			}
		}
		// Delay listener to avoid capturing the toggle click itself
		const timer = setTimeout(
			() => window.addEventListener("mousedown", handleClick),
			0,
		);
		return () => {
			clearTimeout(timer);
			window.removeEventListener("mousedown", handleClick);
		};
	}, [open, onClose]);

	return (
		<>
			{/* Backdrop */}
			<div
				className={cn(
					"fixed inset-0 z-40 bg-black/30 transition-opacity duration-200",
					open
						? "opacity-100 pointer-events-auto"
						: "opacity-0 pointer-events-none",
				)}
				aria-hidden="true"
			/>

			{/* Drawer panel */}
			<div
				ref={drawerRef}
				role="dialog"
				aria-modal={open}
				aria-label="Evidence panel"
				className={cn(
					"fixed inset-y-0 right-0 z-50 w-[85vw] max-w-md transform transition-transform duration-200 ease-out bg-white shadow-xl overflow-y-auto",
					open ? "translate-x-0" : "translate-x-full",
				)}
			>
				{/* Close button */}
				<div className="sticky top-0 z-10 flex items-center justify-between border-b bg-white px-3 py-2">
					<span className="text-sm font-medium text-slate-700">
						Evidence &amp; References
					</span>
					<button
						type="button"
						onClick={onClose}
						className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
						aria-label="Close evidence panel"
					>
						✕
					</button>
				</div>

				<div className="p-3">{children}</div>
			</div>
		</>
	);
}
