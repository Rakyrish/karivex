import LoginForm from "./LoginForm";

export const metadata = { title: "Sign in — Karivex Control Center" };

export default async function AdminLoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string }>;
}) {
  const { next } = await searchParams;

  return (
    <div className="admin-login-page">
      <div className="admin-login-card">
        <h1>Karivex Control Center</h1>
        <p className="lede">Sign in with your Django admin credentials.</p>
        <LoginForm next={next && next.startsWith("/admin") ? next : "/admin"} />
      </div>
    </div>
  );
}
