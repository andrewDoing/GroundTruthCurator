import type { ComponentType } from "react";
import type { ToolCallRecord } from "../models/groundTruth";
import type {
	ComponentRegistration,
	EditorProps,
	FieldComponentRegistryAPI,
	ToolCallExtensionRegistration,
	ToolCallExtensionRegistryAPI,
	ViewerProps,
} from "./types";

export class FieldComponentRegistry implements FieldComponentRegistryAPI {
	private readonly store = new Map<string, ComponentRegistration>();

	register(registration: ComponentRegistration): void {
		if (import.meta.env.DEV && this.store.has(registration.discriminator)) {
			console.warn(
				`[FieldComponentRegistry] Duplicate registration for discriminator: ${registration.discriminator}`,
			);
		}
		this.store.set(registration.discriminator, registration);
	}

	registerIfAbsent(registration: ComponentRegistration): void {
		if (this.has(registration.discriminator)) {
			return;
		}
		this.store.set(registration.discriminator, registration);
	}

	resolve(
		discriminator: string,
		mode: "viewer" | "editor",
	): ComponentType<ViewerProps> | ComponentType<EditorProps> | undefined {
		const exact = this.store.get(discriminator);
		if (exact) {
			return mode === "editor" ? (exact.editor ?? exact.viewer) : exact.viewer;
		}

		for (const [key, reg] of this.store) {
			if (
				discriminator.startsWith(key) &&
				discriminator.charAt(key.length) === ":"
			) {
				return mode === "editor" ? (reg.editor ?? reg.viewer) : reg.viewer;
			}
		}

		return undefined;
	}

	has(discriminator: string): boolean {
		if (this.store.has(discriminator)) {
			return true;
		}
		for (const key of this.store.keys()) {
			if (
				discriminator.startsWith(key) &&
				discriminator.charAt(key.length) === ":"
			) {
				return true;
			}
		}
		return false;
	}

	registrations(): ReadonlyArray<ComponentRegistration> {
		return Array.from(this.store.values());
	}

	reset(): void {
		this.store.clear();
	}
}

export function toolCallDiscriminator(tc: ToolCallRecord): string {
	return `toolCall:${tc.name}`;
}

export class ToolCallExtensions implements ToolCallExtensionRegistryAPI {
	private readonly store = new Map<string, ToolCallExtensionRegistration>();

	register(registration: ToolCallExtensionRegistration): void {
		if (import.meta.env.DEV && this.store.has(registration.discriminator)) {
			console.warn(
				`[ToolCallExtensions] Replacing registration for discriminator: ${registration.discriminator}`,
			);
		}
		this.store.set(registration.discriminator, registration);
	}

	resolveAll(
		toolCall: ToolCallRecord,
	): ReadonlyArray<ToolCallExtensionRegistration> {
		const disc = toolCallDiscriminator(toolCall);
		const matches: ToolCallExtensionRegistration[] = [];

		for (const [key, reg] of this.store) {
			const discriminatorMatch =
				key === disc ||
				(disc.startsWith(key) && disc.charAt(key.length) === ":");

			if (!discriminatorMatch) continue;
			if (reg.matches && !reg.matches(toolCall)) continue;

			matches.push(reg);
		}

		return matches;
	}

	hasMatch(toolCall: ToolCallRecord): boolean {
		return this.resolveAll(toolCall).length > 0;
	}

	registrations(): ReadonlyArray<ToolCallExtensionRegistration> {
		return Array.from(this.store.values());
	}

	reset(): void {
		this.store.clear();
	}
}

export const fieldComponentRegistry = new FieldComponentRegistry();
export const toolCallExtensions = new ToolCallExtensions();
