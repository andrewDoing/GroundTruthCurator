import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "../../models/utils";

type MarkdownRendererProps = {
	content: string | undefined | null;
	className?: string;
	emptyFallback?: React.ReactNode;
	compact?: boolean; // ultra-dense mode for timeline turns
};

/**
 * Shared markdown renderer with curated styling used across curator UI.
 * Provides GitHub-flavored markdown (GFM) support and constrained layout.
 */
export default function MarkdownRenderer({
	content,
	className,
	emptyFallback = <span className="italic text-slate-400">Empty</span>,
	compact = false,
}: MarkdownRendererProps) {
	const body = (content || "").trim();
	return (
		<div
			className={cn(
				"markdown-body text-slate-800", // base color
				compact ? "text-[13px] leading-[1.25]" : "text-sm leading-[1.35]",
				"whitespace-pre-wrap", // preserve newlines
				className,
			)}
		>
			{body ? (
				<ReactMarkdown
					remarkPlugins={[remarkGfm]}
					components={compact ? compactComponents : mdComponents}
				>
					{body}
				</ReactMarkdown>
			) : (
				emptyFallback
			)}
		</div>
	);
}

// Tailwind-enhanced components mirroring InstructionsPane styling
const mdComponents: Components = {
	h1: ({ node, ...props }) => (
		<h1 className="text-base font-semibold m-0" {...props} />
	),
	h2: ({ node, ...props }) => (
		<h2 className="text-sm font-semibold m-0" {...props} />
	),
	h3: ({ node, ...props }) => (
		<h3 className="text-xs font-semibold m-0" {...props} />
	),
	p: ({ node, ...props }) => <p className="m-0" {...props} />,
	ul: ({ node, ...props }) => (
		<ul className="list-disc pl-4 space-y-[2px] m-0" {...props} />
	),
	ol: ({ node, ...props }) => (
		<ol className="list-decimal pl-4 space-y-[2px] m-0" {...props} />
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
			rel="noopener noreferrer"
			{...props}
		/>
	),
	code: ({ node, ...props }) => {
		// Heuristic: if children contain a line break, treat as block code
		const text = String(props.children || "");
		const isBlock = /\n/.test(text);
		return (
			<code
				className={cn(
					"rounded bg-slate-100 px-1 py-0.5 text-[11px] font-mono",
					isBlock &&
						"block w-full whitespace-pre overflow-auto p-2 text-[12px]",
				)}
				{...props}
			/>
		);
	},
};

// Even denser variant used when compact=true
const compactComponents: Components = {
	h1: ({ node, ...props }) => (
		<h1 className="text-[13px] font-semibold m-0" {...props} />
	),
	h2: ({ node, ...props }) => (
		<h2 className="text-[12px] font-semibold m-0" {...props} />
	),
	h3: ({ node, ...props }) => (
		<h3 className="text-[11px] font-semibold m-0" {...props} />
	),
	p: ({ node, ...props }) => <p className="m-0" {...props} />,
	ul: ({ node, ...props }) => (
		<ul className="list-disc pl-3 space-y-[1px] m-0" {...props} />
	),
	ol: ({ node, ...props }) => (
		<ol className="list-decimal pl-3 space-y-[1px] m-0" {...props} />
	),
	li: ({ node, ...props }) => <li className="m-0" {...props} />,
	strong: ({ node, ...props }) => (
		<strong className="font-semibold" {...props} />
	),
	em: ({ node, ...props }) => <em className="italic" {...props} />,
	a: ({ node, ...props }) => (
		<a
			className="text-violet-700 underline"
			target="_blank"
			rel="noopener noreferrer"
			{...props}
		/>
	),
	code: ({ node, ...props }) => {
		const text = String(props.children || "");
		const isBlock = /\n/.test(text);
		return (
			<code
				className={cn(
					"rounded bg-slate-100 px-1 py-[1px] text-[10px] font-mono",
					isBlock &&
						"block w-full whitespace-pre overflow-auto p-1 text-[11px] leading-[1.15]",
				)}
				{...props}
			/>
		);
	},
};
