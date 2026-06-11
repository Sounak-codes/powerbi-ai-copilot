import { SuggestedQuestions } from "../SuggestedQuestions";

type FollowUpQuestionsProps = {
  questions: string[];
  onSelect: (question: string) => void;
};

export function FollowUpQuestions({ questions, onSelect }: FollowUpQuestionsProps) {
  return <SuggestedQuestions questions={questions} onSelect={onSelect} />;
}
