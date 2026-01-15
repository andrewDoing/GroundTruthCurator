import React from "react";

/**
 * Logout button for Azure Easy Auth (Container Apps).
 * Hitting `/.auth/logout` clears the Easy Auth session on the host.
 * We pass `post_logout_redirect_uri` to navigate back to the app after logout.
 */
export default function LogoutButton({
	className = "",
	children,
	title = "Sign out",
}: {
	className?: string;
	children?: React.ReactNode;
	title?: string;
}) {
	const handleLogout = React.useCallback(() => {
		const base = "/.auth/logout";
		const post = encodeURIComponent(`${window.location.origin}/`);
		const url = `${base}?post_logout_redirect_uri=${post}`;
		window.location.assign(url);
	}, []);

	return (
		<button
			type="button"
			onClick={handleLogout}
			className={
				className ||
				"inline-flex items-center gap-2 rounded-xl border px-3 py-1.5 text-sm hover:bg-violet-50"
			}
			title={title}
		>
			{children ?? "Logout"}
		</button>
	);
}
