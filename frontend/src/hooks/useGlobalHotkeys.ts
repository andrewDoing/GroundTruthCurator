import { useEffect } from "react";

export default function useGlobalHotkeys(opts: {
	onSaveDraft?: () => void;
	onApprove?: () => void;
	canApprove?: boolean;
	enabled?: boolean;
}) {
	const { onSaveDraft, onApprove, canApprove, enabled = true } = opts || {};
	useEffect(() => {
		if (!enabled) return;
		function onKeyDown(e: KeyboardEvent) {
			const target = e.target as HTMLElement | null;
			const tag = (target?.tagName || "").toLowerCase();
			const isEditable =
				tag === "input" || tag === "textarea" || target?.isContentEditable;
			const isMod = e.metaKey || e.ctrlKey;
			if (!isMod) return;
			if (e.key.toLowerCase() === "s") {
				e.preventDefault();
				onSaveDraft?.();
				return;
			}
			if (e.key === "Enter") {
				if (isEditable) return; // don't steal enter from text inputs
				if (canApprove) {
					e.preventDefault();
					onApprove?.();
				}
			}
		}
		window.addEventListener("keydown", onKeyDown);
		return () => window.removeEventListener("keydown", onKeyDown);
	}, [onSaveDraft, onApprove, canApprove, enabled]);
}
