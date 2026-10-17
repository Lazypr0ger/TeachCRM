import { TokenPasswordForm } from "@/components/auth/token-password-form";

export default async function ActivatePage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token = "" } = await searchParams;
  return <TokenPasswordForm endpoint="/api/v1/auth/activate" token={token} title="Активация аккаунта" description="Придумайте пароль длиной не менее 12 символов." />;
}
