import type { ComponentType } from "react";
import type {
	GroundTruthItem,
	Reference,
	ToolCallRecord,
} from "../models/groundTruth";

// ---------------------------------------------------------------------------
// Field component registry
// ---------------------------------------------------------------------------

export type RenderContext = {
	itemId: string;
	fieldPath: string;
	pluginKind?: string;
	readOnly: boolean;
};

export type ViewerProps = {
	data: unknown;
	context: RenderContext;
};

export type EditorProps = ViewerProps & {
	onChange: (data: unknown) => void;
	onValidate?: (data: unknown) => string[];
};

export type ComponentRegistration = {
	discriminator: string;
	viewer: ComponentType<ViewerProps>;
	editor?: ComponentType<EditorProps>;
	displayName: string;
};

export type FieldComponentRegistryAPI = {
	register(registration: ComponentRegistration): void;
	registerIfAbsent(registration: ComponentRegistration): void;
	resolve(
		discriminator: string,
		mode: "viewer" | "editor",
	): ComponentType<ViewerProps> | ComponentType<EditorProps> | undefined;
	registrations(): ReadonlyArray<ComponentRegistration>;
	has(discriminator: string): boolean;
};

// ---------------------------------------------------------------------------
// Tool call extension registry
// ---------------------------------------------------------------------------

export type ToolCallActionContext = {
	item: GroundTruthItem;
	readOnly: boolean;
};

export type ToolCallActionProps = {
	toolCall: ToolCallRecord;
	context: ToolCallActionContext;
	references: Reference[];
	onAddReferences?: (refs: Reference[]) => void;
	onOpenReference?: (ref: Reference) => void;
	onUpdateReference?: (refId: string, partial: Partial<Reference>) => void;
	onRemoveReference?: (refId: string) => void;
};

export type ToolCallExtensionRegistration = {
	discriminator: string;
	component: ComponentType<ToolCallActionProps>;
	displayName: string;
	matches?: (toolCall: ToolCallRecord) => boolean;
};

export type ToolCallExtensionRegistryAPI = {
	register(registration: ToolCallExtensionRegistration): void;
	resolveAll(
		toolCall: ToolCallRecord,
	): ReadonlyArray<ToolCallExtensionRegistration>;
	registrations(): ReadonlyArray<ToolCallExtensionRegistration>;
	hasMatch(toolCall: ToolCallRecord): boolean;
};
