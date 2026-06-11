import type { Message as ChatMessage } from "../../types/chat";

type MessageProps = {
  message: ChatMessage;
};

export function Message({ message }: MessageProps) {
  return (
    <article className={`message message-${message.role}`}>
      <div className="message-content">{message.content}</div>
    </article>
  );
}
