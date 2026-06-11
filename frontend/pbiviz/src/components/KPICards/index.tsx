import type { Metric } from "../../types/analytics";

type KPICardsProps = {
  metrics: Metric[];
};

export function KPICards({ metrics }: KPICardsProps) {
  return (
    <section className="kpi-cards">
      {metrics.map((metric) => (
        <article key={metric.name} className="kpi-card">
          <span>{metric.name}</span>
          <strong>{metric.value}</strong>
        </article>
      ))}
    </section>
  );
}
