import "./admin.css";

// Defense-in-depth on top of the existing app/robots.ts disallow rule for
// "/admin/" — this /admin section must never be indexed.
export const metadata = {
  robots: { index: false, follow: false },
};

export default function AdminRootLayout({ children }: { children: React.ReactNode }) {
  return <div className="admin-body">{children}</div>;
}
