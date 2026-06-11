import { useMemo } from "react";
import { useChatContext } from "../context/ChatContext";

export function useConversation() {
  const { messages } = useChatContext();

  return useMemo(
    () => ({
      messages,
      lastMessage: messages[messages.length - 1] ?? null,
      messageCount: messages.length,
    }),
    [messages]
  );
}
