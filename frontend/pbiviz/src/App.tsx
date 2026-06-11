import { Chat } from "./components/Chat";
import { ChatProvider } from "./context/ChatContext";
import { ReportProvider } from "./context/ReportContext";

export function App() {
  return (
    <ReportProvider>
      <ChatProvider>
        <Chat />
      </ChatProvider>
    </ReportProvider>
  );
}

export default App;
