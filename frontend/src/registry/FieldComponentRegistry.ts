// Discriminator-based field component registry.
//
// Resolves viewer / editor components for a given discriminator string.
// Supports exact matching and prefix fallback (e.g. registered "toolCall"
// matches requested "toolCall:retrieval").

import type { ComponentType } from "react";
import type {
	ComponentRegistration,
	EditorProps,
	FieldComponentRegistryAPI,
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
		// Exact match first
		const exact = this.store.get(discriminator);
		if (exact) {
			return mode === "editor" ? (exact.editor ?? exact.viewer) : exact.viewer;
		}

		// Prefix fallback — find a registration whose discriminator is a prefix
		// of the requested discriminator (separated by ":").
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

/** Singleton registry instance used throughout the application. */
export const fieldComponentRegistry = new FieldComponentRegistry();
