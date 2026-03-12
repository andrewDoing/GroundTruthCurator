// Tool call extension registry.
//
// Resolves action components for tool calls based on discriminator matching.
// Supports exact matching and prefix fallback (e.g. registered "toolCall"
// matches tool call with discriminator "toolCall:retrieval").

import type { ToolCallRecord } from "../models/groundTruth";
import type {
	ToolCallExtensionRegistration,
	ToolCallExtensionRegistryAPI,
} from "./types";

/**
 * Build a discriminator string for a tool call based on its name.
 * Convention: "toolCall:{toolName}" (e.g. "toolCall:search", "toolCall:retrieval").
 */
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
			// Exact match or prefix match (separated by ":")
			const discriminatorMatch =
				key === disc ||
				(disc.startsWith(key) && disc.charAt(key.length) === ":");

			if (!discriminatorMatch) continue;

			// If the registration has a predicate, it must also pass
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

/** Singleton registry instance used throughout the application. */
export const toolCallExtensions = new ToolCallExtensions();
