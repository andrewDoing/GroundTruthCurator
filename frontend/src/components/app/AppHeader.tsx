import { FileDown, Tag } from "lucide-react";
import { APP_TITLE } from "../../config/branding";
import LogoutButton from "../common/LogoutButton";

type ViewMode = "curate" | "questions" | "stats";

export default function AppHeader({
	demoMode,
	sidebarOpen,
	onToggleSidebar,
	viewMode,
	onToggleViewMode,
	onOpenStats,
	onOpenGlossary,
	onExportJson,
}: {
	demoMode: boolean;
	sidebarOpen: boolean;
	onToggleSidebar: () => void;
	viewMode: ViewMode;
	onToggleViewMode: () => void;
	onOpenStats: () => void;
	onOpenGlossary: () => void;
	onExportJson: () => void;
}) {
	return (
		<header className="sticky top-0 z-10 border-b bg-white/80 backdrop-blur">
			<div className="mx-auto flex w-full max-w-none items-center gap-3 px-4 py-3">
				<div className="text-xl font-semibold">
					{APP_TITLE}{" "}
					{demoMode && (
						<span className="ml-2 align-middle rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900">
							DEMO MODE
						</span>
					)}
				</div>
				<div className="ml-auto flex items-center gap-2">
					<button
						type="button"
						onClick={onToggleSidebar}
						className="inline-flex items-center gap-2 rounded-xl border px-3 py-1.5 text-sm hover:bg-violet-50"
						title={sidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
					>
						{sidebarOpen ? "Hide Sidebar" : "Show Sidebar"}
					</button>
					<button
						type="button"
						onClick={onToggleViewMode}
						className="inline-flex items-center gap-2 rounded-xl border px-3 py-1.5 text-sm hover:bg-violet-50"
						title="Switch between Curation and Questions views"
					>
						{viewMode === "curate" ? "Questions View" : "Back to Curation"}
					</button>
					<button
						type="button"
						onClick={onOpenStats}
						className="inline-flex items-center gap-2 rounded-xl border px-3 py-1.5 text-sm hover:bg-violet-50"
						title="Open stats page"
					>
						Stats
					</button>
					<button
						type="button"
						onClick={onOpenGlossary}
						className="inline-flex items-center gap-2 rounded-xl border px-3 py-1.5 text-sm hover:bg-violet-50"
						title="View tag glossary"
					>
						<Tag className="h-4 w-4" /> Glossary
					</button>
					<button
						type="button"
						onClick={onExportJson}
						className="inline-flex items-center gap-2 rounded-xl border px-3 py-1.5 text-sm hover:bg-violet-50"
					>
						<FileDown className="h-4 w-4" /> Export JSON
					</button>
					<LogoutButton title="Sign out" />
				</div>
			</div>
		</header>
	);
}
