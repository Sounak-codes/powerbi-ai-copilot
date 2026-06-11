import { createContext, ReactNode, useContext, useMemo, useState } from "react";
import type { PowerBIContext } from "../types/powerbi";

type ReportContextValue = {
  reportContext: PowerBIContext | null;
  setReportContext: (context: PowerBIContext | null) => void;
};

const ReportContext = createContext<ReportContextValue | undefined>(undefined);

export function ReportProvider({ children }: { children: ReactNode }) {
  const [reportContext, setReportContext] = useState<PowerBIContext | null>(null);
  const value = useMemo(() => ({ reportContext, setReportContext }), [reportContext]);
  return <ReportContext.Provider value={value}>{children}</ReportContext.Provider>;
}

export function useReportContext() {
  const context = useContext(ReportContext);
  if (!context) {
    throw new Error("useReportContext must be used inside ReportProvider");
  }
  return context;
}
