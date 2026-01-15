import { useCallback, useEffect, useRef, useState } from "react";
import { randId } from "../models/utils";

export type Toast = {
	id: string;
	kind: "success" | "error" | "info";
	msg: string;
	actionLabel?: string;
	onAction?: () => void;
};

type ShowOptions = {
	duration?: number; // ms
	actionLabel?: string;
	onAction?: () => void;
};

export function useToasts() {
	const [toasts, setToasts] = useState<Toast[]>([]);
	const timersRef = useRef<Map<string, number>>(new Map());

	// Clear all timers on unmount
	useEffect(() => {
		return () => {
			for (const id of timersRef.current.keys()) {
				const t = timersRef.current.get(id);
				if (t) window.clearTimeout(t);
			}
			timersRef.current.clear();
		};
	}, []);

	const dismiss = useCallback((id: string) => {
		setToasts((arr) => arr.filter((x) => x.id !== id));
		const t = timersRef.current.get(id);
		if (t) window.clearTimeout(t);
		timersRef.current.delete(id);
	}, []);

	const clear = useCallback(() => {
		setToasts([]);
		for (const id of timersRef.current.keys()) {
			const t = timersRef.current.get(id);
			if (t) window.clearTimeout(t);
		}
		timersRef.current.clear();
	}, []);

	const showToast = useCallback(
		(kind: Toast["kind"], msg: string, opts?: ShowOptions) => {
			const id = randId("t");
			const toast: Toast = {
				id,
				kind,
				msg,
				actionLabel: opts?.actionLabel,
				onAction: opts?.onAction,
			};
			setToasts((arr) => [...arr, toast]);
			const duration = Math.max(1000, opts?.duration ?? 3500);
			const timerId = window.setTimeout(
				() => dismiss(id),
				duration,
			) as unknown as number;
			timersRef.current.set(id, timerId);
			return id;
		},
		[dismiss],
	);

	return { toasts, showToast, dismiss, clear } as const;
}
