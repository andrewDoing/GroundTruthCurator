import { ChevronDown, ChevronRight, Info } from "lucide-react";
import { useMemo, useState } from "react";
import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "../../models/utils";

type Props = {
	markdown: string | undefined | null;
	title?: string;
	className?: string;
	defaultExpanded?: boolean;
};

export default function InstructionsPane({
	markdown,
	title = "Instructions",
	className,
	defaultExpanded = true,
}: Props) {
	const [open, setOpen] = useState<boolean>(defaultExpanded);
	const content = useMemo(() => (markdown || "").trim(), [markdown]);

	return (
		<section className={cn("rounded-2xl border bg-white shadow-sm", className)}>
			<header className="flex items-center gap-2 px-4 py-3">
				<button
					type="button"
					className="inline-flex items-center justify-center rounded-md border px-2 py-1 text-slate-700 hover:bg-violet-50"
					aria-label={open ? "Collapse" : "Expand"}
					onClick={() => setOpen((v) => !v)}
				>
					{open ? (
						<ChevronDown className="h-4 w-4" />
					) : (
						<ChevronRight className="h-4 w-4" />
					)}
				</button>
				<div className="inline-flex items-center gap-2 text-sm font-medium">
					<Info className="h-4 w-4 text-violet-600" />
					{title}
				</div>
			</header>
			{open && (
				<div className="px-4 pb-4">
					<div
						className={cn(
							// Auto-height by default; allow user to adjust if desired
							"text-slate-800 text-sm leading-6",
							// Provide vertical resize affordance with scroll when content exceeds bounds
							"resize-y overflow-auto rounded-xl border px-3 py-2",
							// Sensible min/max bounds without forcing a fixed height
							"min-h-10 max-h-[32rem]",
						)}
					>
						{content ? (
							<ReactMarkdown
								remarkPlugins={[remarkGfm]}
								components={mdComponents}
							>
								{content}
							</ReactMarkdown>
						) : (
							<div className="text-sm text-slate-500">
								No instructions provided.
							</div>
						)}
					</div>
				</div>
			)}
		</section>
	);
}

const mdComponents: Components = {
	h1: ({ node, ...props }) => (
		<h1 className="text-lg font-semibold mb-2" {...props} />
	),
	h2: ({ node, ...props }) => (
		<h2 className="text-base font-semibold mb-2" {...props} />
	),
	h3: ({ node, ...props }) => (
		<h3 className="text-sm font-semibold mb-2" {...props} />
	),
	p: ({ node, ...props }) => <p className="mb-2" {...props} />,
	ul: ({ node, ...props }) => (
		<ul className="list-disc pl-5 space-y-1 mb-2" {...props} />
	),
	ol: ({ node, ...props }) => (
		<ol className="list-decimal pl-5 space-y-1 mb-2" {...props} />
	),
	li: ({ node, ...props }) => <li className="ml-1" {...props} />,
	strong: ({ node, ...props }) => (
		<strong className="font-semibold" {...props} />
	),
	em: ({ node, ...props }) => <em className="italic" {...props} />,
	a: ({ node, ...props }) => (
		<a
			className="text-violet-700 underline"
			target="_blank"
			rel="noreferrer"
			{...props}
		/>
	),
};
