import { createContext, ReactNode, useContext, useMemo, useState } from "react";
import type { Message } from "../types/chat";

type ChatContextValue = {
  messages: Message[];
  setMessages: (messages: Message[]) => void;
};

const ChatContext = createContext<ChatContextValue | undefined>(undefined);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const value = useMemo(() => ({ messages, setMessages }), [messages]);
  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChatContext() {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error("useChatContext must be used inside ChatProvider");
  }
  return context;
}
