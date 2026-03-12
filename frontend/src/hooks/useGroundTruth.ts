import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiProvider } from "../adapters/apiProvider";
import { isDemoModeIgnored, shouldUseDemoProvider } from "../config/demo";
import type {
	ContextEntry,
	ConversationTurn,
	ExpectedTools,
	GroundTruthItem,
	Reference,
} from "../models/groundTruth";
import {
	createConversationTurn,
	ensureConversationTurnIdentity,
	getItemReferences,
	getLastAgentTurn,
	getLastUserTurn,
	getReferenceMessageIndex,
	withDerivedLegacyFields,
	withUpdatedReferences,
} from "../models/groundTruth";
import { canApproveCandidate } from "../models/gtHelpers";
import type { Provider } from "../models/provider";
import { randId } from "../models/utils";
import {
	type ChatReference,
	callAgentChat,
	formatConversationForAgent,
	formatExpectedBehaviorForChat,
} from "../services/chatService";
import { mapApiErrorToMessage } from "../services/http";
import { addTags } from "../services/tags";
import { logEvent } from "../services/telemetry";
import { invalidateGroundTruthCache } from "./useGroundTruthCache";
import { useReferencesEditor } from "./useReferencesEditor";
import { useReferencesSearch } from "./useReferencesSearch";

type SaveResult =
	| { ok: true; saved: GroundTruthItem; message?: string }
	| { ok: false; error: string };

type ExportResult = { ok: true; json: string } | { ok: false; error: string };

export type AgentGenerationResult =
	| { ok: false; error: string }
	| { ok: true; messageIndex: number }
	| { ok: true };

type UseGroundTruth = {
	// Provider (exposed for ExportModal convenience)
	provider: Provider | null;

	// Collection
	items: GroundTruthItem[];
	refreshList: () => Promise<void>;

	// Selection + current editable copy
	selectedId: string | null;
	setSelectedId: (id: string | null) => void;
	selectItem: (
		id: string | null,
		options?: { force?: boolean },
	) => Promise<boolean>;
	current: GroundTruthItem | null;

	// QA change tracking
	qaChanged: boolean;
	// Tags live on current item; expose updater
	updateTags: (tags: string[]) => void;

	// Comments
	updateComment: (v: string) => void;

	// Search (right panel)
	query: string;
	setQuery: (q: string) => void;
	searching: boolean;
	searchResults: Reference[];
	runSearch: () => Promise<void>;
	addReferences: (refs: Reference[]) => void;

	// Reference actions on current
	updateReference: (refId: string, patch: Partial<Reference>) => void;
	removeReferenceWithUndo: (
		refId: string,
		onUndoRegister: (undo: () => void, timeoutMs: number) => void,
	) => void;
	openReference: (ref: Reference) => void; // marks visited; UI decides how to open

	// Edit Q/A
	updateQuestion: (q: string) => void;
	updateAnswer: (a: string) => void;

	// Multi-turn support
	updateHistory: (history: ConversationTurn[]) => void;
	addTurn: (role: string, content: string) => void;
	deleteTurn: (messageIndex: number) => void;
	regenerateAgentTurn: (messageIndex: number) => Promise<AgentGenerationResult>;
	generateAgentTurn: (messageIndex: number) => Promise<AgentGenerationResult>;
	runAgentTurn: (messageIndex: number) => Promise<AgentGenerationResult>;

	// Context entries
	updateContextEntries: (entries: ContextEntry[]) => void;

	// Expected tools
	updateExpectedTools: (tools: ExpectedTools) => void;

	// Save + status
	saving: boolean;
	save: (nextStatus?: GroundTruthItem["status"]) => Promise<SaveResult>;
	canApprove: boolean;
	toggleDeletedCurrent: (nextDeleted: boolean) => Promise<SaveResult>;
	toggleDeletedAny: (
		itemId: string,
		nextDeleted: boolean,
	) => Promise<SaveResult>;

	// Duplicate current as rephrase
	duplicateCurrent: () => Promise<
		{ ok: true; created: GroundTruthItem } | { ok: false; error: string }
	>;

	// Export
	exportJson: () => Promise<ExportResult>;

	// UI helpers
	hasUnsaved: boolean;
};

// Pure helper to compute a stable fingerprint for unsaved detection
function stateSignature(it: GroundTruthItem): string {
	const refs = [...getItemReferences(it)]
		.map((r) => ({
			id: r.id,
			title: r.title || "",
			url: r.url,
			snippet: r.snippet || "",
			// visitedAt is intentionally excluded from unsaved signature
			keyParagraph: (r.keyParagraph || "").trim(),
			bonus: !!r.bonus,
			messageIndex: r.messageIndex,
			turnId: r.turnId,
			toolCallId: r.toolCallId,
		}))
		.sort((a, b) => a.id.localeCompare(b.id));
	return JSON.stringify({
		id: it.id,
		providerId: it.providerId,
		question: getLastUserTurn(it).trim(),
		answer: getLastAgentTurn(it).trim(),
		comment: (it.comment ?? "").trim(),
		history: ensureConversationTurnIdentity(it.history),
		references: refs,
		manualTags: [...(it.manualTags || [])]
			.map((t) => t.trim())
			.filter(Boolean)
			.sort(),
		status: it.status,
		deleted: !!it.deleted,
	});
}

function chatReferencesToGroundTruth(
	chatRefs: ChatReference[],
	targetTurn: ConversationTurn,
): Reference[] {
	if (!chatRefs?.length) return [];
	return chatRefs.map((ref) => ({
		id: ref.id?.trim() || randId("ref"),
		title: ref.title?.trim() || undefined,
		url: ref.url?.trim() || "",
		snippet: ref.snippet?.trim() || undefined,
		keyParagraph: ref.keyParagraph?.trim() || undefined,
		turnId: targetTurn.turnId,
	}));
}

function ensureEditableHistory(item: GroundTruthItem): ConversationTurn[] {
	return ensureConversationTurnIdentity(item.history);
}

function withCanonicalHistory(
	item: GroundTruthItem,
	history: ConversationTurn[],
): GroundTruthItem {
	return withDerivedLegacyFields({
		...item,
		history: ensureConversationTurnIdentity(history),
	});
}

function pruneReferencesForHistory(
	refs: Reference[],
	history: ConversationTurn[],
): Reference[] {
	const nextTurnIds = new Set(
		history.map((turn) => turn.turnId).filter(Boolean),
	);
	return refs
		.map((ref) => {
			if (ref.turnId) {
				if (!nextTurnIds.has(ref.turnId)) {
					return null;
				}
				return {
					...ref,
					messageIndex: undefined,
				};
			}
			if (typeof ref.messageIndex !== "number") {
				return ref;
			}
			if (ref.messageIndex < history.length) {
				const turnId = history[ref.messageIndex]?.turnId;
				return {
					...ref,
					messageIndex: turnId ? undefined : ref.messageIndex,
					turnId,
				};
			}
			return null;
		})
		.filter((ref): ref is Reference => ref !== null);
}

function getCompatExpectedBehaviorPrompt(
	turn: ConversationTurn | undefined,
): string {
	return formatExpectedBehaviorForChat(turn?.expectedBehavior);
}

function withCanonicalItem(item: GroundTruthItem): GroundTruthItem {
	const history = ensureEditableHistory(item);
	return withCanonicalHistory(item, history);
}

function useGroundTruth(): UseGroundTruth {
	const providerRef = useRef<Provider | null>(null);
	const [items, setItems] = useState<GroundTruthItem[]>([]);
	const [selectedId, setSelectedId] = useState<string | null>(null);
	const [current, setCurrent] = useState<GroundTruthItem | null>(null);

	// QA tracking
	const qaBaseline = useRef<{ q: string; a: string }>({ q: "", a: "" });
	// tags mutate current directly through updateTags

	// Search (delegated to sub-hook)
	const { query, setQuery, searching, searchResults, runSearch, clearResults } =
		useReferencesSearch({
			getSeedQuery: () => (current ? getLastUserTurn(current) : undefined),
		});

	// Save idempotency
	const [lastSavedStateFp, setLastSavedStateFp] = useState<string>("");
	const [saving, setSaving] = useState(false);

	// References editor (delegated to sub-hook)
	const {
		updateReference,
		addReferences,
		removeReferenceWithUndo,
		openReference,
	} = useReferencesEditor({ setCurrent });

	// init
	useEffect(() => {
		let cancelled = false;

		(async () => {
			if (isDemoModeIgnored()) {
				try {
					logEvent("demo_mode_ignored_non_dev_build", {
						reason: "DEMO_MODE is only supported in dev builds",
					});
				} catch {}
			}

			let p: Provider;
			if (shouldUseDemoProvider()) {
				const { createDemoProvider } = await import("../models/demoData");
				p = createDemoProvider();
			} else {
				p = new ApiProvider();
			}

			if (cancelled) return;
			providerRef.current = p;

			try {
				const { items } = await p.list();
				if (cancelled) return;

				setItems(items);
				const first = items[0];
				setSelectedId(first?.id ?? null);
				if (first) {
					// Prime the editor immediately so fields populate without waiting for a follow-up get()
					const clone = withCanonicalItem(
						JSON.parse(JSON.stringify(first)) as GroundTruthItem,
					);
					setCurrent(clone);
					qaBaseline.current = {
						q: getLastUserTurn(first),
						a: getLastAgentTurn(first),
					};
					setLastSavedStateFp(stateSignature(withCanonicalItem(first)));
				}
			} catch {
				// Load errors are handled elsewhere via explicit actions.
			}
		})();

		return () => {
			cancelled = true;
		};
	}, []);

	// Internal ref to track if selection change is already in progress
	const selectionChangeInProgress = useRef(false);
	// Internal ref to track ongoing agent generation
	const abortGenerationRef = useRef<(() => void) | null>(null);

	// load selected - now acts as a sync mechanism for setSelectedId
	useEffect(() => {
		const p = providerRef.current;
		if (!p || !selectedId || selectionChangeInProgress.current) return;
		// If we already have the current item matching the selection (primed from list), skip fetch
		if (current?.id === selectedId) return;

		// Selection changed externally (e.g., from initialization), load without warning
		(async () => {
			const it = await p.get(selectedId);
			if (!it) return;
			const clone = withCanonicalItem(
				JSON.parse(JSON.stringify(it)) as GroundTruthItem,
			);
			setCurrent(clone);
			qaBaseline.current = { q: getLastUserTurn(it), a: getLastAgentTurn(it) };
			clearResults();
			setLastSavedStateFp(stateSignature(withCanonicalItem(it)));
		})();
	}, [selectedId, clearResults, current?.id]);

	const qaChanged = useMemo(() => {
		if (!current) return false;
		return (
			getLastUserTurn(current) !== qaBaseline.current.q ||
			getLastAgentTurn(current) !== qaBaseline.current.a
		);
	}, [current]);

	// reference actions come from useReferencesEditor

	const refreshList = useCallback(async () => {
		const p = providerRef.current;
		if (!p) return;
		const res = await p.list();
		setItems(res.items);
	}, []);

	const updateQuestion = useCallback((q: string) => {
		setCurrent((prev) => {
			if (!prev) return prev;
			const history = ensureEditableHistory(prev);
			let updated = false;
			const nextHistory = [...history];
			for (let i = nextHistory.length - 1; i >= 0; i--) {
				if (nextHistory[i].role === "user") {
					nextHistory[i] = { ...nextHistory[i], content: q };
					updated = true;
					break;
				}
			}
			if (!updated) {
				nextHistory.push(createConversationTurn({ role: "user", content: q }));
			}
			return withCanonicalHistory(prev, nextHistory);
		});
	}, []);
	const updateAnswer = useCallback((a: string) => {
		setCurrent((prev) => {
			if (!prev) return prev;
			const history = ensureEditableHistory(prev);
			let updated = false;
			const nextHistory = [...history];
			for (let i = nextHistory.length - 1; i >= 0; i--) {
				if (nextHistory[i].role !== "user") {
					nextHistory[i] = { ...nextHistory[i], content: a };
					updated = true;
					break;
				}
			}
			if (!updated) {
				nextHistory.push(createConversationTurn({ role: "agent", content: a }));
			}
			return withCanonicalHistory(prev, nextHistory);
		});
	}, []);
	const updateComment = useCallback((v: string) => {
		setCurrent((prev) => (prev ? { ...prev, comment: v } : prev));
	}, []);

	const canApprove = useMemo(() => canApproveCandidate(current), [current]);

	const save = useCallback(
		async (nextStatus?: GroundTruthItem["status"]): Promise<SaveResult> => {
			const p = providerRef.current;
			if (!current || !p || saving) return { ok: false, error: "Not ready" };

			const candidate: GroundTruthItem = withCanonicalItem({
				...current,
				status: nextStatus || current.status,
			});
			const stateFp = stateSignature(candidate);
			if (stateFp === lastSavedStateFp) {
				return { ok: true, saved: current, message: "No changes" };
			}

			if (
				["approved"].includes(candidate.status) &&
				!canApproveCandidate(candidate)
			) {
				return { ok: false, error: "References not complete for approval" };
			}
			// No gating by change category anymore

			setSaving(true);
			const started = Date.now();
			try {
				const prevBeforeSave = current; // capture to merge transient fields
				const saved = await p.save(candidate);
				// SA-232: Backend does not persist visitedAt; reattach any prior visitedAt values by URL.
				const prevRefs = getItemReferences(prevBeforeSave);
				const savedRefs = getItemReferences(saved);
				if (prevRefs.length && savedRefs.length) {
					const visitedByUrl = new Map(
						prevRefs
							.filter((r) => r.visitedAt)
							.map((r) => [r.url, r.visitedAt as string]),
					);
					let changed = false;
					const merged = savedRefs.map((r) => {
						if (!r.visitedAt) {
							const v = visitedByUrl.get(r.url);
							if (v) {
								changed = true;
								return { ...r, visitedAt: v };
							}
						}
						return r;
					});
					if (changed) {
						// Re-write saved item with visitedAt merged
						Object.assign(saved, withUpdatedReferences(saved, merged));
					}
				}
				const canonicalSaved = withCanonicalItem(saved);
				setItems((arr) =>
					arr.map((i) => (i.id === canonicalSaved.id ? canonicalSaved : i)),
				);
				setCurrent(canonicalSaved);
				setLastSavedStateFp(stateSignature(canonicalSaved));
				if (qaChanged)
					qaBaseline.current = {
						q: getLastUserTurn(canonicalSaved),
						a: getLastAgentTurn(canonicalSaved),
					};

				// FR-002: Invalidate cache after successful save to ensure fresh data on next inspection
				if (saved.datasetName && saved.bucket && saved.id) {
					invalidateGroundTruthCache(saved.datasetName, saved.bucket, saved.id);
				}

				// Persist any new manual tags only after a successful save; fire-and-forget
				try {
					const tags = Array.from(
						new Set(
							(saved.manualTags || [])
								.map((t) => (t || "").trim())
								.filter(Boolean),
						),
					);
					if (tags.length) void addTags(tags).catch(() => {});
				} catch {}
				try {
					const baseProps = {
						providerId: canonicalSaved.providerId,
						itemId: canonicalSaved.id,
						status: canonicalSaved.status,
						selectedRefCount: getItemReferences(canonicalSaved).length,
						durationMs: Date.now() - started,
					};
					if (nextStatus === "approved" || canonicalSaved.status === "approved")
						logEvent("gtc.approve", baseProps);
					else logEvent("gtc.save_draft", baseProps);
				} catch {}
				return { ok: true, saved };
			} catch (e) {
				const msg = e instanceof Error ? e.message : String(e);
				return { ok: false, error: msg };
			} finally {
				setSaving(false);
			}
		},
		[current, saving, lastSavedStateFp, qaChanged],
	);

	// Determine if current item differs from last saved state
	const hasUnsaved = useMemo(() => {
		if (!current) return false;
		return stateSignature(current) !== lastSavedStateFp;
	}, [current, lastSavedStateFp]);

	// Controlled selection with unsaved changes warning
	const selectItem = useCallback(
		async (
			id: string | null,
			options?: { force?: boolean },
		): Promise<boolean> => {
			const p = providerRef.current;
			if (!p || !id) {
				setSelectedId(id);
				return true;
			}

			// If already selected, do nothing
			if (current?.id === id) return true;

			// Check for unsaved changes
			if (!options?.force && current && hasUnsaved) {
				const confirmed = window.confirm(
					"You have unsaved changes. Switching items will discard them. Continue?",
				);
				if (!confirmed) return false;
			}

			// Abort any ongoing agent generation
			if (abortGenerationRef.current) {
				abortGenerationRef.current();
				abortGenerationRef.current = null;
			}

			// Mark selection change in progress to prevent side effects
			selectionChangeInProgress.current = true;

			try {
				// Fetch the item from backend
				const it = await p.get(id);
				if (!it) {
					selectionChangeInProgress.current = false;
					return false;
				}

				const clone = withCanonicalItem(
					JSON.parse(JSON.stringify(it)) as GroundTruthItem,
				);
				setCurrent(clone);
				qaBaseline.current = {
					q: getLastUserTurn(it),
					a: getLastAgentTurn(it),
				};
				clearResults();
				setLastSavedStateFp(stateSignature(withCanonicalItem(it)));
				setSelectedId(id);
				return true;
			} catch (error) {
				console.error("Failed to load item:", error);
				return false;
			} finally {
				selectionChangeInProgress.current = false;
			}
		},
		[current, hasUnsaved, clearResults],
	);

	const exportJson = useCallback(async (): Promise<ExportResult> => {
		const p = providerRef.current;
		if (!p) return { ok: false, error: "No provider" };
		try {
			try {
				logEvent("gtc.export_snapshot_start");
			} catch {}
			const json = await p.export();
			try {
				logEvent("gtc.export_snapshot_complete", { bytes: json.length });
			} catch {}
			return { ok: true, json };
		} catch (e) {
			const msg = e instanceof Error ? e.message : String(e);
			try {
				logEvent("gtc.export_snapshot_error", { error: msg });
			} catch {}
			return { ok: false, error: msg };
		}
	}, []);

	const toggleDeletedCurrent = useCallback(
		async (nextDeleted: boolean): Promise<SaveResult> => {
			const p = providerRef.current;
			if (!current || !p) return { ok: false, error: "No current" };
			try {
				const saved = withCanonicalItem(
					await p.save({ ...current, deleted: nextDeleted }),
				);
				setItems((arr) => arr.map((i) => (i.id === saved.id ? saved : i)));
				setCurrent(saved);
				setLastSavedStateFp(stateSignature(saved));
				try {
					logEvent(nextDeleted ? "gtc.soft_delete" : "gtc.restore", {
						providerId: saved.providerId,
						itemId: saved.id,
						status: saved.status,
					});
				} catch {}
				return { ok: true, saved };
			} catch (e) {
				const msg = e instanceof Error ? e.message : String(e);
				return { ok: false, error: msg };
			}
		},
		[current],
	);

	const toggleDeletedAny = useCallback(
		async (itemId: string, nextDeleted: boolean): Promise<SaveResult> => {
			const p = providerRef.current;
			if (!p) return { ok: false, error: "No provider" };
			const it = items.find((i) => i.id === itemId);
			if (!it) return { ok: false, error: "Item not found" };
			try {
				const saved = withCanonicalItem(
					await p.save({ ...it, deleted: nextDeleted }),
				);
				setItems((arr) => arr.map((i) => (i.id === saved.id ? saved : i)));
				if (current && current.id === saved.id) {
					setCurrent(saved);
					setLastSavedStateFp(stateSignature(saved));
				}
				try {
					logEvent(nextDeleted ? "gtc.soft_delete" : "gtc.restore", {
						providerId: saved.providerId,
						itemId: saved.id,
						status: saved.status,
					});
				} catch {}
				return { ok: true, saved };
			} catch (e) {
				const msg = e instanceof Error ? e.message : String(e);
				return { ok: false, error: msg };
			}
		},
		[items, current],
	);

	const updateTags = useCallback((manualTags: string[]) => {
		setCurrent((prev) => (prev ? { ...prev, manualTags } : prev));
	}, []);

	const updateHistory = useCallback((history: ConversationTurn[]) => {
		setCurrent((prev) => {
			if (!prev) return prev;
			return withCanonicalHistory(prev, history);
		});
	}, []);

	const addTurn = useCallback((role: string, content: string) => {
		setCurrent((prev) => {
			if (!prev) return prev;
			const newHistory: ConversationTurn[] = [
				...ensureEditableHistory(prev),
				createConversationTurn({ role, content }),
			];
			return withCanonicalHistory(prev, newHistory);
		});
	}, []);

	const deleteTurn = useCallback((messageIndex: number) => {
		setCurrent((prev) => {
			if (!prev) return prev;
			const history = ensureEditableHistory(prev);
			if (messageIndex < 0 || messageIndex >= history.length) return prev;

			const deletedTurnId = history[messageIndex]?.turnId;
			// Remove the turn at the specified index
			const newHistory = history.filter((_, i) => i !== messageIndex);

			const currentRefs = getItemReferences(prev).filter((ref) =>
				ref.turnId
					? ref.turnId !== deletedTurnId
					: ref.messageIndex !== messageIndex,
			);
			const updatedReferences = pruneReferencesForHistory(
				currentRefs,
				newHistory,
			);

			return withUpdatedReferences(
				withCanonicalHistory(prev, newHistory),
				updatedReferences,
			);
		});
	}, []);

	const updateContextEntries = useCallback((entries: ContextEntry[]) => {
		setCurrent((prev) => (prev ? { ...prev, contextEntries: entries } : prev));
	}, []);

	const updateExpectedTools = useCallback((tools: ExpectedTools) => {
		setCurrent((prev) => (prev ? { ...prev, expectedTools: tools } : prev));
	}, []);

	const appendAgentTurn =
		useCallback(async (): Promise<AgentGenerationResult> => {
			const item = current;
			if (!item)
				return { ok: false, error: "Select a ground truth item first." };
			const history = item.history || [];
			if (!history.length)
				return {
					ok: false,
					error: "Add a user turn before requesting an agent response.",
				};
			const lastTurn = history[history.length - 1];
			if (lastTurn.role !== "user")
				return {
					ok: false,
					error: "Add a user message before requesting an agent response.",
				};
			const transcript = formatConversationForAgent(history);
			if (!transcript)
				return {
					ok: false,
					error: "Conversation history is empty.",
				};
			const targetId = item.id;
			const started = Date.now();
			try {
				const { content, references } = await callAgentChat(transcript);
				const trimmed = content.trim();
				if (!trimmed)
					return {
						ok: false,
						error: "Agent returned an empty response.",
					};
				const newMessageIndex = history.length;
				setCurrent((prev) => {
					if (!prev || prev.id !== targetId) return prev;
					const prevHistory = ensureEditableHistory(prev);
					const newTurn = createConversationTurn({
						role: "agent",
						content: trimmed,
					});
					const nextHistory: ConversationTurn[] = [...prevHistory, newTurn];
					const mappedRefs = chatReferencesToGroundTruth(references, newTurn);
					const currentRefs = getItemReferences(prev);
					const filteredRefs = currentRefs.filter(
						(ref) =>
							getReferenceMessageIndex(ref, prevHistory) !== newMessageIndex &&
							ref.turnId !== newTurn.turnId,
					);
					return withUpdatedReferences(
						withCanonicalHistory(prev, nextHistory),
						[...filteredRefs, ...mappedRefs],
					);
				});
				try {
					logEvent("gtc.agent_turn_add", {
						referenceCount: references.length,
						messageIndex: newMessageIndex,
						durationMs: Date.now() - started,
					});
				} catch {}
				return { ok: true as const, messageIndex: newMessageIndex };
			} catch (err) {
				const message = mapApiErrorToMessage(err);
				try {
					logEvent("gtc.agent_turn_error", {
						stage: "add",
						error: message,
					});
				} catch {}
				return { ok: false as const, error: message };
			}
		}, [current]);

	const regenerateAgentTurn = useCallback(
		async (messageIndex: number): Promise<AgentGenerationResult> => {
			const item = current;
			if (!item)
				return { ok: false, error: "Select a ground truth item first." };

			const history = item.history || [];
			if (messageIndex < 0 || messageIndex >= history.length)
				return { ok: false, error: "Turn index is out of range." };

			const targetTurn = history[messageIndex];
			if (targetTurn.role === "user")
				return { ok: false, error: "Only non-user turns can be regenerated." };

			// Format conversation history up to this turn
			const transcript = formatConversationForAgent(history, messageIndex);
			if (!transcript)
				return { ok: false, error: "Conversation history is empty." };

			// Append expected behavior if present
			const expectedBehaviorStr = getCompatExpectedBehaviorPrompt(targetTurn);
			const messageWithBehavior = expectedBehaviorStr
				? `${transcript}\n\n${expectedBehaviorStr}`
				: transcript;

			const targetId = item.id;
			const started = Date.now();

			try {
				const { content, references } =
					await callAgentChat(messageWithBehavior);
				const trimmed = content.trim();
				if (!trimmed)
					return {
						ok: false,
						error: "Agent returned an empty response.",
					};

				// Single state update with all changes (React 18 auto-batches)
				setCurrent((prev) => {
					if (!prev || prev.id !== targetId) return prev;

					// Optimize: only copy/update what changed
					const updatedHistory = [...ensureEditableHistory(prev)];
					const targetTurnId = updatedHistory[messageIndex]?.turnId;

					// Direct index update instead of map (O(1) vs O(n))
					if (messageIndex < updatedHistory.length) {
						updatedHistory[messageIndex] = {
							...updatedHistory[messageIndex],
							content: trimmed,
						};
					}

					// Filter refs for this turn only
					const currentRefs = getItemReferences(prev);
					const refsToKeep = currentRefs.filter(
						(ref) =>
							ref.messageIndex !== messageIndex && ref.turnId !== targetTurnId,
					);

					const mappedRefs = chatReferencesToGroundTruth(
						references,
						updatedHistory[messageIndex],
					);

					// Single state update with all changes
					return withUpdatedReferences(
						withCanonicalHistory(prev, updatedHistory),
						[...refsToKeep, ...mappedRefs],
					);
				});

				// Fire-and-forget logging (non-blocking)
				try {
					logEvent("gtc.agent_turn_regenerate", {
						referenceCount: references.length,
						messageIndex,
						hasExpectedBehavior: !!expectedBehaviorStr,
						durationMs: Date.now() - started,
					});
				} catch {}

				return { ok: true as const, messageIndex };
			} catch (err) {
				const message = mapApiErrorToMessage(err);
				try {
					logEvent("gtc.agent_turn_error", {
						stage: "regenerate",
						error: message,
					});
				} catch {}
				return { ok: false as const, error: message };
			}
		},
		[current],
	);

	const generateAgentTurn = useCallback(
		async (messageIndex: number): Promise<AgentGenerationResult> => {
			if (messageIndex < 0) return appendAgentTurn();
			return regenerateAgentTurn(messageIndex);
		},
		[appendAgentTurn, regenerateAgentTurn],
	);

	/**
	 * Run full agent with tools (searches + retrieval) to regenerate an agent turn.
	 * Updates both the answer and references for the turn.
	 * This is the same as regenerateAgentTurn.
	 */
	const runAgentTurn = useCallback(
		async (messageIndex: number): Promise<AgentGenerationResult> => {
			return regenerateAgentTurn(messageIndex);
		},
		[regenerateAgentTurn],
	);

	const duplicateCurrent = useCallback(async () => {
		const p = providerRef.current;
		if (!current || !p) return { ok: false as const, error: "No current" };
		try {
			const created = withCanonicalItem(await p.duplicate(current));
			// Insert at top of list and select it
			setItems((arr) => [created, ...arr]);
			setSelectedId(created.id);
			setCurrent(JSON.parse(JSON.stringify(created)) as GroundTruthItem);
			qaBaseline.current = {
				q: getLastUserTurn(created),
				a: getLastAgentTurn(created),
			};
			setLastSavedStateFp(stateSignature(created));
			try {
				logEvent("gtc.duplicate_rephrase", {
					originalId: current.id,
					createdId: created.id,
				});
			} catch {}
			return { ok: true as const, created };
		} catch (e) {
			const msg = e instanceof Error ? e.message : String(e);
			return { ok: false as const, error: msg };
		}
	}, [current]);

	return {
		provider: providerRef.current,
		items,
		refreshList,
		selectedId,
		setSelectedId,
		selectItem,
		current,
		qaChanged,
		updateTags,
		updateComment,
		query,
		setQuery,
		searching,
		searchResults,
		runSearch,
		addReferences,
		updateReference,
		removeReferenceWithUndo,
		openReference,
		updateQuestion,
		updateAnswer,
		updateHistory,
		addTurn,
		deleteTurn,
		updateContextEntries,
		updateExpectedTools,
		regenerateAgentTurn,
		generateAgentTurn,
		runAgentTurn,
		saving,
		save,
		canApprove,
		toggleDeletedCurrent,
		toggleDeletedAny,
		exportJson,
		duplicateCurrent,
		hasUnsaved,
	};
}

export default useGroundTruth;
