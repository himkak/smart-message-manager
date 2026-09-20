import { StatusBar } from "./components/StatusBar";
import { SearchPanel } from "./components/SearchPanel";
import { ChatPanel } from "./components/ChatPanel";
import "./App.css";

function App() {
  return (
    <div className="app">
      <header>
        <h1>Smart Messages Manager</h1>
        <p className="tagline">Search and ask evidence-grounded questions about your Gmail messages.</p>
      </header>
      <StatusBar />
      <main>
        <SearchPanel />
        <ChatPanel />
      </main>
    </div>
  );
}

export default App;
