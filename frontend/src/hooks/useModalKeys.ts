import { useEffect } from "react";

export default function useModalKeys(opts: {
	enabled?: boolean;
	onClose?: () => void;
	onConfirm?: () => void;
	busy?: boolean;
}) {
	const { enabled = true, onClose, onConfirm, busy } = opts || {};
	useEffect(() => {
		if (!enabled) return;
		function onKeyDown(e: KeyboardEvent) {
			const target = e.target as HTMLElement | null;
			const tag = (target?.tagName || "").toLowerCase();
			const isEditable =
				tag === "input" ||
				tag === "textarea" ||
				Boolean(target?.isContentEditable);

			if (e.key === "Escape") {
				e.preventDefault();
				onClose?.();
				return;
			}
			if (
				(e.key === "Enter" || e.key === "NumpadEnter") &&
				onConfirm &&
				!busy
			) {
				if (isEditable) return; // don't hijack typing inside inputs for confirm
				e.preventDefault();
				onConfirm();
			}
		}
		window.addEventListener("keydown", onKeyDown);
		return () => window.removeEventListener("keydown", onKeyDown);
	}, [enabled, onClose, onConfirm, busy]);
}
