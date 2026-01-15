/// <reference types="node" />

import { randomUUID } from "node:crypto";
import type { GroundTruthItemIn } from "../../../src/services/groundTruths";

export type QuestionsExplorerStatus =
	| "draft"
	| "approved"
	| "deleted"
	| "skipped";

export interface QuestionsExplorerBlueprintItem {
	id: string;
	datasetName: string;
	status: QuestionsExplorerStatus;
	tags: string[];
	question: string;
	references: number;
	answer?: string;
	reviewedAt?: string | null;
}

export interface QuestionsExplorerSeedItem {
	meta: QuestionsExplorerBlueprintItem;
	payload: GroundTruthItemIn;
}

export interface QuestionsExplorerBlueprint {
	runId: string;
	datasets: string[];
	tags: string[];
	items: QuestionsExplorerSeedItem[];
	deleteCandidateId: string;
	multiTagTarget: {
		tags: string[];
		itemId: string;
	};
	statusCounts: Record<QuestionsExplorerStatus, number>;
	primaryDataset: string;
}

interface CreateItemOptions {
	datasetIndex: number;
	status: QuestionsExplorerStatus;
	tags: string[];
	references: number;
	question?: string;
	answer?: string;
	reviewedDaysAgo?: number | null;
	markDeleteCandidate?: boolean;
	markMultiTagTarget?: boolean;
}

const DATASET_CODES = ["alpha", "beta", "gamma"] as const;

export function createQuestionsExplorerTestData(
	runId: string,
): QuestionsExplorerBlueprint {
	const datasets = DATASET_CODES.map((code) => `integration-${code}-${runId}`);
	const statusCounts: Record<QuestionsExplorerStatus, number> = {
		draft: 0,
		approved: 0,
		deleted: 0,
		skipped: 0,
	};
	const blueprintItems: QuestionsExplorerBlueprintItem[] = [];
	const tagsSet = new Set<string>();
	let deleteCandidateId = "";
	let multiTagTargetId = "";
	let sequence = 0;

	const addItem = (options: CreateItemOptions) => {
		const datasetName = datasets[options.datasetIndex];
		sequence += 1;
		const id = `qe-${DATASET_CODES[options.datasetIndex]}-${options.status}-${String(sequence).padStart(3, "0")}-${runId}`;
		const baseQuestion =
			options.question ?? `How does ${datasetName} handle case ${sequence}?`;
		const reviewedAt =
			options.reviewedDaysAgo === null
				? null
				: options.reviewedDaysAgo === undefined
					? undefined
					: new Date(
							Date.now() - options.reviewedDaysAgo * 86_400_000,
						).toISOString();

		const meta: QuestionsExplorerBlueprintItem = {
			id,
			datasetName,
			status: options.status,
			tags: [...options.tags],
			question: baseQuestion,
			references: Math.max(0, options.references),
			answer: options.answer,
			reviewedAt,
		};
		blueprintItems.push(meta);
		statusCounts[options.status] += 1;
		for (const tag of options.tags) tagsSet.add(tag);
		if (options.markDeleteCandidate) deleteCandidateId = id;
		if (options.markMultiTagTarget) multiTagTargetId = id;
	};

	// Dataset alpha: mix of draft, approved, deleted for baseline scenarios
	for (let i = 0; i < 6; i++) {
		addItem({
			datasetIndex: 0,
			status: i < 3 ? "draft" : "approved",
			tags:
				i < 3
					? ["topic:cad", "audience:sme"]
					: ["topic:cad", "audience:engineer"],
			references: i + 1,
			answer: i < 3 ? undefined : `Approved answer variant ${i}`,
			reviewedDaysAgo: i < 3 ? null : i,
			markDeleteCandidate: i === 1,
		});
	}
	addItem({
		datasetIndex: 0,
		status: "deleted",
		tags: ["topic:retired", "audience:legacy"],
		references: 2,
		question: "Legacy item flagged for deletion",
	});

	// Dataset beta: ensure multi-tag AND scenario and varied refs for sorting
	for (let i = 0; i < 8; i++) {
		const status: QuestionsExplorerStatus =
			i === 0 ? "draft" : i < 5 ? "approved" : i === 5 ? "deleted" : "draft";
		const tags =
			i === 2
				? ["topic:quality", "audience:engineer", "priority:high"]
				: i === 3
					? ["topic:quality", "audience:sme", "priority:medium"]
					: i === 6
						? ["topic:general", "audience:engineer"]
						: ["topic:general", "audience:sme"];
		addItem({
			datasetIndex: 1,
			status,
			tags,
			references: (i % 5) + 1,
			answer: status === "approved" ? `Beta approved answer ${i}` : undefined,
			reviewedDaysAgo: status === "approved" ? i + 1 : null,
			markMultiTagTarget: i === 2,
		});
	}

	// Dataset gamma: primarily approved items for pagination testing
	for (let i = 0; i < 12; i++) {
		const status: QuestionsExplorerStatus =
			i === 0 ? "deleted" : i < 3 ? "draft" : "approved";
		addItem({
			datasetIndex: 2,
			status,
			tags:
				i % 2 === 0
					? ["topic:analytics", "audience:engineer"]
					: ["topic:analytics", "audience:support"],
			references: (i % 7) + 1,
			answer: status === "approved" ? `Gamma approved answer ${i}` : undefined,
			reviewedDaysAgo: status === "approved" ? i + 2 : null,
		});
	}

	// Guarantee at least one deleted item per dataset for filtering tests
	addItem({
		datasetIndex: 1,
		status: "deleted",
		tags: ["topic:cleanup", "audience:ops"],
		references: 1,
		question: "Beta dataset archived item",
	});
	addItem({
		datasetIndex: 2,
		status: "deleted",
		tags: ["topic:analytics", "audience:retired"],
		references: 3,
		question: "Gamma dataset removed question",
	});

	// Fallback markers if loops did not set them
	if (!deleteCandidateId)
		deleteCandidateId = blueprintItems[0]?.id ?? randomUUID();
	if (!multiTagTargetId)
		multiTagTargetId = blueprintItems[1]?.id ?? deleteCandidateId;

	const items: QuestionsExplorerSeedItem[] = blueprintItems.map((meta) => ({
		meta,
		payload: createGroundTruthItem(meta),
	}));

	return {
		runId,
		datasets,
		tags: Array.from(tagsSet).sort((a, b) => a.localeCompare(b)),
		items,
		deleteCandidateId,
		multiTagTarget: {
			tags: items.find((it) => it.meta.id === multiTagTargetId)?.meta.tags ?? [
				"topic:quality",
				"audience:engineer",
			],
			itemId: multiTagTargetId,
		},
		statusCounts,
		primaryDataset: datasets[0],
	};
}

export function createGroundTruthItem(
	meta: QuestionsExplorerBlueprintItem,
): GroundTruthItemIn {
	const now = new Date().toISOString();
	const refs = Array.from(
		{ length: Math.max(meta.references, 0) },
		(_, idx) => ({
			url: `https://example.com/${meta.id}/ref-${idx + 1}`,
			content: `Reference ${idx + 1} content for ${meta.id}`,
			keyExcerpt: `Detailed excerpt ${idx + 1} for ${meta.id} that exceeds forty characters.`,
			type: "web",
			bonus: idx % 3 === 0,
		}),
	);

	return {
		id: meta.id,
		datasetName: meta.datasetName,
		status: meta.status as GroundTruthItemIn["status"],
		docType: "ground-truth-item",
		schemaVersion: "v1",
		synthQuestion: meta.question,
		editedQuestion: meta.question,
		answer: meta.answer ?? null,
		refs,
		tags: [...meta.tags],
		comment:
			meta.status === "deleted"
				? "Seeded as deleted"
				: "Seeded for integration tests",
		history: [
			{ role: "user", msg: `User asked about ${meta.question}` },
			{ role: "assistant", msg: meta.answer ?? "Pending answer" },
		],
		contextUsedForGeneration: null,
		contextSource: null,
		modelUsedForGeneration: null,
		semanticClusterNumber: null,
		weight: null,
		samplingBucket: null,
		questionLength: meta.question.length,
		assignedTo: "integration-tester",
		assignedAt: now,
		updatedAt: now,
		updatedBy: "integration-tests",
		reviewedAt: meta.reviewedAt ?? null,
		_etag: null,
	};
}

export function extractPayloads(
	blueprint: QuestionsExplorerBlueprint,
): GroundTruthItemIn[] {
	return blueprint.items.map((item) => item.payload);
}
