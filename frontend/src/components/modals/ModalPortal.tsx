import type { PropsWithChildren } from "react";
import { createPortal } from "react-dom";

export default function ModalPortal({ children }: PropsWithChildren) {
	// Access DOM directly during render - safe in browser environment
	// This avoids issues with useMemo caching null during SSR or initial hydration
	if (typeof document === "undefined") return null;

	const target = document.getElementById("modal-root") ?? document.body;
	return createPortal(children, target);
}
