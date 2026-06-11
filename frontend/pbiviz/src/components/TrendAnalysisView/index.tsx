import type { Trend } from "../../types/analytics";

type TrendAnalysisViewProps = {
  trends: Trend[];
};

export function TrendAnalysisView({ trends }: TrendAnalysisViewProps) {
  return (
    <section className="trend-analysis-view">
      {trends.map((trend) => (
        <article key={`${trend.startDate}-${trend.endDate}-${trend.direction}`}>
          <strong>{trend.description}</strong>
          <span>{trend.direction}</span>
        </article>
      ))}
    </section>
  );
}
