import React, { useState } from "react";
import { askCopilot, ReportContext } from "./api";


type ChatProps = {
  reportContext?: ReportContext;
};


export function Chat({ reportContext = {} }: ChatProps) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");

  async function submit() {
    const result = await askCopilot(question, reportContext);
    setAnswer(result.answer);
  }

  return (
    <section className="chat-panel">
      <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
      <button onClick={submit}>Ask</button>
      <p>{answer}</p>
    </section>
  );
}
