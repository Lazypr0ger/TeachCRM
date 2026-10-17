import { TokenPasswordForm } from "@/components/auth/token-password-form";

export default async function ResetPasswordPage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token = "" } = await searchParams;
  return <TokenPasswordForm endpoint="/api/v1/auth/reset-password" token={token} title="Новый пароль" description="После смены пароля все прежние сессии будут завершены." />;
}
