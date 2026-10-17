const capabilities = [
  ["Ученики", "Приглашения и доступы"],
  ["Расписание", "Уроки, повторы и переносы"],
  ["Финансы", "Учёт без обработки денег"],
];

export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col justify-center px-5 py-16 sm:px-8">
      <p className="mb-4 text-sm font-semibold uppercase tracking-[0.18em] text-[var(--info)]">
        Tutor CRM · локальная версия
      </p>
      <h1 className="max-w-3xl text-4xl font-bold leading-tight sm:text-6xl">
        Рабочее пространство преподавателя и ученика
      </h1>
      <p className="mt-6 max-w-2xl text-base leading-7 text-[var(--text-muted)] sm:text-lg">
        Безопасный доступ к расписанию, домашним заданиям и финансовому учёту.
        Интерфейс заполняется реальными данными с сервера по мере подключения модулей.
      </p>
      <section className="mt-12 grid gap-4 md:grid-cols-3" aria-label="Разделы системы">
        {capabilities.map(([title, description]) => (
          <article key={title} className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-6">
            <h2 className="text-xl font-semibold">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--text-muted)]">{description}</p>
            <p className="mt-6 text-sm font-medium text-[var(--warning)]">Подключается по этапам</p>
          </article>
        ))}
      </section>
    </main>
  );
}

