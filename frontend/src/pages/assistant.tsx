import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Sparkles } from "lucide-react";
import { Header } from "@/components/layout/header";
import { PageLayout } from "@/components/layout/page-layout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { api } from "@/lib/api";
import { useProject } from "@/hooks/use-project";
import type { ChatMessage } from "@/types";
import { cn } from "@/lib/utils";

const SUGGESTED_QUERIES = [
  "How many workflow blockers are open?",
  "Who created the most tickets?",
  "Which workshops have the most tickets?",
  "What's our average resolution time?",
];

export default function AssistantPage() {
  const { projectGid, dateFrom, dateTo } = useProject();
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: "Ask me anything about your ticket data and delivery metrics.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async (text: string) => {
    if (!text.trim() || loading) return;
    const userMsg: ChatMessage = { role: "user", content: text.trim() };
    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInput("");
    setLoading(true);

    try {
      const response = await api.chat(text.trim(), newHistory, projectGid, dateFrom, dateTo);
      setMessages([...newHistory, { role: "assistant", content: response.response }]);
    } catch {
      setMessages([
        ...newHistory,
        { role: "assistant", content: "Couldn't reach the backend. Ensure the API is running." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageLayout page="assistant">
      <Header title="AI Assistant" description="Natural language queries" />
      <div className="page-content flex flex-col h-[calc(100vh-6rem)]">
        <div className="flex flex-wrap gap-1.5 mb-3">
          {SUGGESTED_QUERIES.map((q) => (
            <button
              key={q}
              onClick={() => sendMessage(q)}
              className="text-[10px] rounded-full border border-border/80 px-2.5 py-1 hover:bg-muted/50 transition-colors text-muted-foreground hover:text-foreground"
            >
              {q}
            </button>
          ))}
        </div>

        <div className="flex-1 flex flex-col rounded-md border border-border/80 bg-card min-h-0">
          <ScrollArea className="flex-1 p-3">
            <div className="space-y-3">
              {messages.map((msg, i) => (
                <div key={i} className={cn("flex gap-2", msg.role === "user" ? "justify-end" : "justify-start")}>
                  {msg.role === "assistant" && (
                    <div className="rounded-full bg-primary/10 p-1.5 h-6 w-6 flex items-center justify-center shrink-0">
                      <Bot className="h-3 w-3 text-primary" />
                    </div>
                  )}
                  <div
                    className={cn(
                      "rounded-md px-3 py-2 max-w-[85%] text-[11px] leading-relaxed",
                      msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
                    )}
                  >
                    {msg.content}
                  </div>
                  {msg.role === "user" && (
                    <div className="rounded-full bg-secondary p-1.5 h-6 w-6 flex items-center justify-center shrink-0">
                      <User className="h-3 w-3" />
                    </div>
                  )}
                </div>
              ))}
              {loading && (
                <div className="flex gap-2">
                  <div className="rounded-full bg-primary/10 p-1.5 h-6 w-6 flex items-center justify-center">
                    <Sparkles className="h-3 w-3 text-primary animate-pulse" />
                  </div>
                  <div className="rounded-md bg-muted px-3 py-2 text-[11px] text-muted-foreground">Thinking…</div>
                </div>
              )}
              <div ref={scrollRef} />
            </div>
          </ScrollArea>

          <div className="flex gap-2 p-3 border-t border-border/60">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendMessage(input)}
              placeholder="Ask about tickets, metrics…"
              disabled={loading}
              className="h-8 text-xs"
            />
            <Button onClick={() => sendMessage(input)} disabled={loading || !input.trim()} size="icon" className="h-8 w-8 shrink-0">
              <Send className="h-3 w-3" />
            </Button>
          </div>
        </div>
      </div>
    </PageLayout>
  );
}
