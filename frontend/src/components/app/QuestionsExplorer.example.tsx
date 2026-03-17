/**
 * Example usage of QuestionsExplorer component
 *
 * This file demonstrates how to use the QuestionsExplorer component
 * with sample data and callbacks.
 */

import QuestionsExplorer, {
	type QuestionsExplorerItem,
} from "./QuestionsExplorer";

const questionPrompts = [
	"What is the capital of France?",
	"How does photosynthesis work?",
	"What is quantum computing?",
	"Explain machine learning basics",
	"What are the benefits of exercise?",
	"How do neural networks work?",
	"What is blockchain technology?",
	"Explain the water cycle",
	"What causes climate change?",
	"How does DNA replication work?",
];

const answerSnippets = [
	"Paris is the capital city of France.",
	"Photosynthesis converts light energy into chemical energy.",
	"Quantum computing uses superposition and entanglement.",
	"Machine learning learns patterns from data.",
	"Exercise improves cardiovascular and mental health.",
	"Neural networks stack layers of weighted transformations.",
	"Blockchain is a tamper-evident distributed ledger.",
	"The water cycle moves water through evaporation and precipitation.",
	"Climate change is driven largely by greenhouse gas emissions.",
	"DNA replication copies genetic material before cell division.",
];

const datasets = ["technology", "science", "biology", "physics", "health"];
const statuses: QuestionsExplorerItem["status"][] = [
	"approved",
	"draft",
	"approved",
	"deleted",
	"approved",
];

// Sample data with canonical history turns (no top-level answer convenience fields).
const sampleItems: QuestionsExplorerItem[] = Array.from(
	{ length: 50 },
	(_, i) => {
		const prompt = questionPrompts[i % questionPrompts.length];
		const answer = answerSnippets[i % answerSnippets.length];
		const id = `gt-${String(i + 1).padStart(3, "0")}`;

		return {
			id,
			providerId: "json",
			status: statuses[i % statuses.length],
			deleted: statuses[i % statuses.length] === "deleted",
			history: [
				{ role: "user", content: prompt },
				{ role: "agent", content: answer },
			],
			tags: i % 3 === 0 ? ["popular", "beginner"] : ["technical"],
			manualTags: [],
			computedTags: [],
			datasetName: datasets[i % datasets.length],
			reviewedAt: `2025-09-${String((i % 28) + 1).padStart(2, "0")}T10:30:00Z`,
			views: 100 + i * 7,
			reuses: 5 + (i % 40),
		};
	},
);

export default function QuestionsExplorerExample() {
	const handleAssign = (item: QuestionsExplorerItem) => {
		console.log(`Assign ground truth: ${item.id}`);
		alert(`Assign functionality for ${item.id} would be triggered here`);
	};

	const handleInspect = (item: QuestionsExplorerItem) => {
		console.log(`Inspect ground truth: ${item.id}`);
		alert(`Inspect functionality for ${item.id} would be triggered here`);
	};

	const handleDelete = (item: QuestionsExplorerItem) => {
		console.log(`Delete ground truth: ${item.id}`);
		const confirmed = window.confirm(
			`Are you sure you want to delete ${item.id}?`,
		);
		if (confirmed) {
			alert(`Delete functionality for ${item.id} would be triggered here`);
		}
	};

	return (
		<div className="flex h-full flex-col">
			<QuestionsExplorer
				items={sampleItems}
				onAssign={handleAssign}
				onInspect={handleInspect}
				onDelete={handleDelete}
				className="flex-1 min-h-0"
			/>
		</div>
	);
}
