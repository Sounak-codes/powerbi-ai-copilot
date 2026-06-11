type RootCauseViewProps = {
  drivers: string[];
};

export function RootCauseView({ drivers }: RootCauseViewProps) {
  return (
    <section className="root-cause-view">
      {drivers.map((driver) => (
        <div key={driver}>{driver}</div>
      ))}
    </section>
  );
}
