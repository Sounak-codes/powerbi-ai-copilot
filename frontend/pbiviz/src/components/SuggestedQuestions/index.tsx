type SuggestedQuestionsProps = {
  questions: string[];
  onSelect: (question: string) => void;
};

export function SuggestedQuestions({ questions, onSelect }: SuggestedQuestionsProps) {
  return (
    <section className="suggested-questions">
      {questions.map((question) => (
        <button key={question} type="button" onClick={() => onSelect(question)}>
          {question}
        </button>
      ))}
    </section>
  );
}
