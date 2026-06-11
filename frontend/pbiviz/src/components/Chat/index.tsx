import { useChat } from "../../hooks/useChat";
import { Loading } from "../Loading";
import { Message } from "../Message";
import { SuggestedQuestions } from "../SuggestedQuestions";

export function Chat() {
  const { messages, input, setInput, sendMessage, isLoading, suggestions } = useChat();

  return (
    <section className="chat">
      <div className="chat-messages">
        {messages.map((message) => (
          <Message key={message.id} message={message} />
        ))}
        {isLoading ? <Loading /> : null}
      </div>
      <SuggestedQuestions questions={suggestions} onSelect={setInput} />
      <form
        onSubmit={(event) => {
          event.preventDefault();
          sendMessage(input);
        }}
      >
        <textarea value={input} onChange={(event) => setInput(event.target.value)} />
        <button type="submit">Send</button>
      </form>
    </section>
  );
}
