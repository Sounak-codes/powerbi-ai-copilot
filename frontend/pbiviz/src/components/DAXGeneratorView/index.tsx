type DAXGeneratorViewProps = {
  dax?: string;
};

export function DAXGeneratorView({ dax = "" }: DAXGeneratorViewProps) {
  return <pre className="dax-generator-view">{dax || "Generated DAX will appear here."}</pre>;
}
