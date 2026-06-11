type ExecutiveSummaryProps = {
  summary: string;
};

export function ExecutiveSummary({ summary }: ExecutiveSummaryProps) {
  return <section className="executive-summary">{summary}</section>;
}
