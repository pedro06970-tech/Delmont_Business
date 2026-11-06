const stats = [
  { label: "Lojas", value: "Visão individual e consolidada" },
  { label: "Indicadores", value: "Faturamento, lucro e ticket médio" },
  { label: "Produtos", value: "Ranking dos cinco mais vendidos" },
];

const modules = [
  {
    title: "Lembretes comerciais",
    description: "Agendamentos de mensagens, clientes e históricos de disparos para comunicação mais eficiente.",
  },
  {
    title: "Inteligência financeira",
    description: "Indicadores de faturamento, margem, ticket médio e ranking de produtos com foco em decisões rápidas.",
  },
  {
    title: "Estrutura pronta para crescer",
    description: "Arquitetura pensada para evoluir com novos módulos sem perder simplicidade operacional.",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 transition-colors dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto max-w-7xl px-6 py-8 lg:px-8">
        <header className="mb-10 flex items-center justify-between rounded-full border border-emerald-200 bg-white/80 px-5 py-3 shadow-sm backdrop-blur dark:border-emerald-900/60 dark:bg-slate-900/80">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-600 text-lg font-bold text-white shadow-lg shadow-emerald-600/30">
              D
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.15em] text-emerald-600">Delmont</p>
              <h1 className="text-base font-semibold">Business</h1>
            </div>
          </div>
          <nav className="hidden items-center gap-6 text-sm text-slate-600 dark:text-slate-300 md:flex">
            <a href="#solucoes" className="transition hover:text-emerald-600">Soluções</a>
            <a href="#indicadores" className="transition hover:text-emerald-600">Indicadores</a>
            <a href="#status" className="transition hover:text-emerald-600">Status</a>
          </nav>
        </header>

        <section className="grid items-center gap-10 rounded-3xl border border-emerald-100 bg-gradient-to-br from-emerald-500 via-emerald-600 to-teal-700 p-8 text-white shadow-2xl shadow-emerald-900/20 lg:grid-cols-[1.2fr_0.8fr] lg:p-12">
          <div>
            <span className="inline-flex rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-emerald-50">
              Sprint 01
            </span>
            <h2 className="mt-5 max-w-xl text-4xl font-bold leading-tight md:text-5xl">
              Gestão comercial inteligente para lojas físicas.
            </h2>
            <p className="mt-4 max-w-xl text-base text-emerald-50/90 md:text-lg">
              Centralize lembretes automatizados, controle de clientes e visão financeira em uma base feita para operação real e crescimento sustentável.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <a
                href="/login"
                className="rounded-full bg-white px-5 py-3 text-sm font-semibold text-emerald-700 transition hover:bg-emerald-50"
              >
                Entrar na plataforma
              </a>
              <a
                href="#status"
                className="rounded-full border border-white/30 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
              >
                Ver status da plataforma
              </a>
            </div>
          </div>

          <div className="rounded-2xl border border-white/20 bg-slate-950/20 p-5 backdrop-blur-sm">
            <div className="rounded-2xl bg-white/10 p-4">
              <p className="text-xs uppercase tracking-[0.2em] text-emerald-100">Painel executivo</p>
              <div className="mt-5 space-y-4">
                <div className="flex items-end justify-between">
                  <span className="text-sm text-emerald-50/80">Faturamento</span>
                  <span className="text-2xl font-bold">Visão futura</span>
                </div>
                <div className="h-2 rounded-full bg-white/15">
                  <div className="h-2 w-[78%] rounded-full bg-emerald-300" />
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="rounded-xl bg-slate-950/20 p-3">
                    <p className="text-emerald-100">Lucro</p>
                    <p className="mt-2 text-xl font-semibold">—</p>
                  </div>
                  <div className="rounded-xl bg-slate-950/20 p-3">
                    <p className="text-emerald-100">Ticket</p>
                    <p className="mt-2 text-xl font-semibold">—</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="indicadores" className="mt-10 grid gap-4 md:grid-cols-3">
          {stats.map((item) => (
            <div key={item.label} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <p className="text-sm text-slate-500 dark:text-slate-400">{item.label}</p>
              <p className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">{item.value}</p>
            </div>
          ))}
        </section>

        <section id="solucoes" className="mt-16">
          <div className="mb-6">
            <p className="text-sm font-medium uppercase tracking-[0.2em] text-emerald-600">Módulos</p>
            <h3 className="mt-3 text-3xl font-bold text-slate-900 dark:text-white">Base para crescer com clareza</h3>
          </div>

          <div className="grid gap-5 md:grid-cols-3">
            {modules.map((module) => (
              <article
                key={module.title}
                className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-md dark:border-slate-800 dark:bg-slate-900"
              >
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300">
                  ✓
                </div>
                <h4 className="text-xl font-semibold text-slate-900 dark:text-white">{module.title}</h4>
                <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">{module.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="status" className="mt-16 rounded-3xl border border-emerald-200 bg-emerald-50 p-6 dark:border-emerald-900/60 dark:bg-emerald-950/40">
          <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-sm font-medium uppercase tracking-[0.18em] text-emerald-700 dark:text-emerald-300">Status</p>
              <h3 className="mt-2 text-2xl font-bold text-slate-900 dark:text-white">Projeto em bootstrap inicial</h3>
            </div>
            <span className="inline-flex w-fit rounded-full bg-emerald-600 px-3 py-1 text-sm font-semibold text-white">
              Base configurada
            </span>
          </div>
          <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-700 dark:text-slate-200">
            A base da plataforma está estruturada com frontend, backend e Docker. Os dados exibidos são apenas uma prévia visual; integrações e regras de negócio serão implementadas em tarefas futuras.
          </p>
        </section>
      </div>
    </main>
  );
}
