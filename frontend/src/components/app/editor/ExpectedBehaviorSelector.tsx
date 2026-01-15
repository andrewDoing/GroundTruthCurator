import { Check } from "lucide-react";
import type { ExpectedBehavior } from "../../../models/groundTruth";
import { cn } from "../../../models/utils";

type Props = {
	selectedBehaviors: ExpectedBehavior[];
	onChange: (behaviors: ExpectedBehavior[]) => void;
	disabled?: boolean;
};

const BEHAVIOR_OPTIONS: Array<{
	value: ExpectedBehavior;
	label: string;
	description: string;
}> = [
	{
		value: "tool:search",
		label: "Search",
		description: "Agent should perform a search/retrieval operation",
	},
	{
		value: "generation:answer",
		label: "Answer",
		description: "Agent should generate a direct answer",
	},
	{
		value: "generation:clarification",
		label: "Clarification",
		description: "Agent should ask for clarification",
	},
	{
		value: "generation:out-of-domain",
		label: "Out of Domain",
		description: "Agent should indicate the query is out of domain",
	},
];

export default function ExpectedBehaviorSelector({
	selectedBehaviors,
	onChange,
	disabled,
}: Props) {
	const toggleBehavior = (behavior: ExpectedBehavior) => {
		if (disabled) return;

		if (selectedBehaviors.includes(behavior)) {
			// Remove behavior
			onChange(selectedBehaviors.filter((b) => b !== behavior));
		} else {
			// Add behavior
			onChange([...selectedBehaviors, behavior]);
		}
	};

	return (
		<div className="space-y-2">
			<p className="text-xs font-semibold text-slate-700">
				Expected Behavior
				<span className="ml-1 text-rose-600">*</span>
			</p>
			<div className="space-y-1">
				{BEHAVIOR_OPTIONS.map((option) => {
					const isSelected = selectedBehaviors.includes(option.value);
					return (
						<button
							key={option.value}
							type="button"
							onClick={() => toggleBehavior(option.value)}
							disabled={disabled}
							className={cn(
								"w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors",
								"hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50",
								isSelected
									? "border-violet-300 bg-violet-50"
									: "border-slate-200 bg-white",
							)}
							title={option.description}
						>
							<div className="flex items-start gap-2">
								<div
									className={cn(
										"mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border",
										isSelected
											? "border-violet-500 bg-violet-500"
											: "border-slate-300 bg-white",
									)}
								>
									{isSelected && <Check className="h-3 w-3 text-white" />}
								</div>
								<div className="flex-1">
									<div className="font-medium text-slate-900">
										{option.label}
									</div>
									<div className="text-xs text-slate-600">
										{option.description}
									</div>
								</div>
							</div>
						</button>
					);
				})}
			</div>
			{selectedBehaviors.length === 0 && (
				<p className="text-xs text-rose-600 font-medium">
					⚠ Required: Select one or more expected behaviors for this agent turn.
				</p>
			)}
		</div>
	);
}
