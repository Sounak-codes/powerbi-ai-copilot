import type { AnalyticsResult } from "../../types/analytics";

type InsightCardsProps = {
  insights: AnalyticsResult[];
};

export function InsightCards({ insights }: InsightCardsProps) {
  return (
    <section className="insight-cards">
      {insights.map((insight) => (
        <article key={`${insight.type}-${insight.timestamp}`} className="insight-card">
          <h3>{insight.type}</h3>
          <p>{insight.summary}</p>
        </article>
      ))}
    </section>
  );
}
