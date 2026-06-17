import { useState, useRef, useEffect } from "react"
import { Send, Trash2, Bot, User, Copy, Check, MessageSquare } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { streamChat, clearChat, type ChatCitation, type Profile } from "@/api"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const SESSION_KEY = "cie_chat_session"
const MESSAGES_KEY = "cie_chat_messages"

const QUICK_PROMPTS = [
  "Compare all backend engineers",
  "List all applicants from Islamabad",
  "Who are the strongest Python developers?",
  "How many candidates know React?",
  "Find someone with FastAPI experience",
  "Which candidates have DevOps skills?",
]

interface Message {
  role: "user" | "assistant"
  content: string
  citations?: ChatCitation[]
}

interface ChatPanelProps {
  onSelectProfile: (p: Profile) => void
}

export function ChatPanel({ onSelectProfile }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>(() => {
    try {
      const saved = localStorage.getItem(MESSAGES_KEY)
      return saved ? (JSON.parse(saved) as Message[]) : []
    } catch {
      return []
    }
  })
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [stage, setStage] = useState("")
  const [streamingText, setStreamingText] = useState("")
  const [sessionId, setSessionId] = useState<string | undefined>(
    () => localStorage.getItem(SESSION_KEY) ?? undefined
  )

  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const streamingTextRef = useRef("")
  const pendingCitationsRef = useRef<ChatCitation[]>([])

  useEffect(() => {
    localStorage.setItem(MESSAGES_KEY, JSON.stringify(messages))
  }, [messages])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading, streamingText])

  useEffect(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${el.scrollHeight}px`
  }, [input])

  const send = (question: string) => {
    if (!question.trim() || loading) return
    setInput("")
    if (inputRef.current) inputRef.current.style.height = "auto"

    setMessages((prev) => [...prev, { role: "user", content: question }])
    setLoading(true)
    setStage("")
    setStreamingText("")
    streamingTextRef.current = ""
    pendingCitationsRef.current = []

    abortRef.current = streamChat(question, sessionId, {
      onStage: (text) => setStage(text),

      onMeta: (newSessionId, citations) => {
        pendingCitationsRef.current = citations
        if (!sessionId || sessionId !== newSessionId) {
          setSessionId(newSessionId)
          localStorage.setItem(SESSION_KEY, newSessionId)
        }
      },

      onToken: (token) => {
        streamingTextRef.current += token
        setStreamingText(streamingTextRef.current)
      },

      onDone: (fullText) => {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: fullText, citations: pendingCitationsRef.current },
        ])
        setStreamingText("")
        setStage("")
        streamingTextRef.current = ""
        setLoading(false)
      },

      onError: () => {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: "I couldn't reach the backend. Please check the API is running.", citations: [] },
        ])
        setStreamingText("")
        setStage("")
        streamingTextRef.current = ""
        setLoading(false)
      },
    })
  }

  const handleClear = async () => {
    abortRef.current?.abort()
    if (sessionId) {
      try { await clearChat(sessionId) } catch { /* best-effort */ }
    }
    setMessages([])
    setSessionId(undefined)
    setStreamingText("")
    setStage("")
    setLoading(false)
    streamingTextRef.current = ""
    localStorage.removeItem(SESSION_KEY)
    localStorage.removeItem(MESSAGES_KEY)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  const handleCitationClick = async (citation: ChatCitation) => {
    try {
      const { default: axios } = await import("axios")
      const base = import.meta.env.VITE_API_URL ?? "http://localhost:8000"
      const res = await axios.get(`${base}/profiles/${citation.id}`)
      onSelectProfile(res.data as Profile)
    } catch { /* silent */ }
  }

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className="h-14 flex items-center justify-between px-5 border-b border-gray-100 flex-none">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-purple-100 flex items-center justify-center">
            <Bot className="w-4 h-4 text-purple-600" />
          </div>
          <div>
            <div className="text-sm font-semibold text-gray-900">Chat Bot</div>
            <div className="text-xs text-gray-400">RAG · Grounded in your database</div>
          </div>
        </div>
        {(messages.length > 0 || loading) && (
          <Button variant="ghost" size="sm" onClick={handleClear} className="text-gray-400 hover:text-red-500 gap-1.5">
            <Trash2 className="w-3.5 h-3.5" /> Clear
          </Button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
        {messages.length === 0 && !loading && (
          <EmptyState onPrompt={send} />
        )}

        {messages.map((msg, i) => (
          <ChatMessage
            key={i}
            message={msg}
            onCitationClick={handleCitationClick}
          />
        ))}

        {/* Streaming / stage bubble */}
        {loading && (
          <div className="flex items-start gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-purple-100 flex items-center justify-center flex-none">
              <Bot className="w-3.5 h-3.5 text-purple-600" />
            </div>
            <div className="bg-gray-50 rounded-2xl rounded-tl-sm border border-gray-100 px-4 py-3 text-sm text-gray-800 leading-relaxed max-w-[82%]">
              {streamingText ? (
                <div className="chat-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamingText}</ReactMarkdown>
                  <span className="inline-block w-0.5 h-3.5 bg-purple-400 ml-0.5 align-middle animate-pulse" />
                </div>
              ) : (
                <div className="flex items-center gap-2 text-gray-400">
                  <span className="flex gap-0.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-bounce [animation-delay:0ms]" />
                    <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-bounce [animation-delay:150ms]" />
                    <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-bounce [animation-delay:300ms]" />
                  </span>
                  <span className="text-xs">{stage || "Thinking…"}</span>
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex-none px-4 pb-4 pt-2 border-t border-gray-100">
        <div className="flex items-end gap-2 bg-gray-50 rounded-xl border border-gray-200 focus-within:shadow-[0_0_0_3px_rgba(124,58,237,0.12)] transition-all duration-150 px-4 py-3">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about candidates… (Enter to send, Shift+Enter for new line)"
            rows={1}
            className="flex-1 resize-none bg-transparent text-sm text-gray-900 placeholder:text-gray-400 focus:outline-none leading-relaxed max-h-40 overflow-y-auto"
          />
          <button
            onClick={() => send(input)}
            disabled={!input.trim() || loading}
            className={cn(
              "flex-none w-8 h-8 rounded-lg flex items-center justify-center transition-all",
              input.trim() && !loading
                ? "bg-purple-700 text-white hover:bg-purple-800"
                : "bg-gray-200 text-gray-400 cursor-not-allowed"
            )}
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </div>
        <p className="text-[10px] text-gray-400 mt-1.5 text-center">
          Answers are grounded in your candidate database · Session stored locally
        </p>
      </div>
    </div>
  )
}

function EmptyState({ onPrompt }: { onPrompt: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full text-center py-8 space-y-5">
      <div className="w-12 h-12 rounded-2xl bg-purple-50 flex items-center justify-center">
        <MessageSquare className="w-6 h-6 text-purple-400" />
      </div>
      <div>
        <h3 className="text-sm font-semibold text-gray-800">Ask anything about candidates</h3>
        <p className="text-xs text-gray-400 mt-1 max-w-xs leading-relaxed">
          I'll search your database and answer with specific candidates, citing their actual profiles.
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2 max-w-sm">
        {QUICK_PROMPTS.map((p) => (
          <button
            key={p}
            onClick={() => onPrompt(p)}
            className="text-xs bg-white border border-gray-200 text-gray-600 hover:border-purple-300 hover:text-purple-700 hover:bg-purple-50 rounded-full px-3 py-1.5 transition-all duration-100"
          >
            {p}
          </button>
        ))}
      </div>
    </div>
  )
}

function ChatMessage({ message, onCitationClick }: {
  message: Message
  onCitationClick: (c: ChatCitation) => void
}) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === "user"

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={cn("flex items-start gap-2.5", isUser && "flex-row-reverse")}>
      {/* Avatar */}
      <div className={cn(
        "w-7 h-7 rounded-lg flex items-center justify-center flex-none",
        isUser ? "bg-gray-200" : "bg-purple-100"
      )}>
        {isUser
          ? <User className="w-3.5 h-3.5 text-gray-500" />
          : <Bot className="w-3.5 h-3.5 text-purple-600" />
        }
      </div>

      <div className={cn("flex flex-col gap-2 max-w-[82%]", isUser && "items-end")}>
        {/* Bubble */}
        <div className={cn(
          "group relative rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "bg-purple-700 text-white rounded-tr-sm"
            : "bg-gray-50 text-gray-800 rounded-tl-sm border border-gray-100"
        )}>
          {isUser ? message.content : (
            <div className="chat-markdown">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          )}

          {/* Copy button — assistant messages only */}
          {!isUser && (
            <button
              onClick={handleCopy}
              title={copied ? "Copied!" : "Copy response"}
              className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-md hover:bg-gray-200"
            >
              {copied
                ? <Check className="w-3 h-3 text-green-500" />
                : <Copy className="w-3 h-3 text-gray-400" />
              }
            </button>
          )}
        </div>

        {/* Citations */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {message.citations.map((c) => (
              <CitationChip key={c.id} citation={c} onClick={() => onCitationClick(c)} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function CitationChip({ citation, onClick }: { citation: ChatCitation; onClick: () => void }) {
  const isFilter = citation.source === "filter"
  return (
    <button
      onClick={onClick}
      title="Click to view full profile"
      className="flex items-center gap-1.5 rounded-full border border-purple-200 bg-purple-50 px-2.5 py-1 hover:bg-purple-100 hover:border-purple-300 transition-colors"
    >
      <div className="w-4 h-4 rounded-full bg-purple-200 flex items-center justify-center text-[9px] font-bold text-purple-700 flex-none">
        {(citation.name ?? "?")[0].toUpperCase()}
      </div>
      <span className="text-xs font-medium text-purple-700">{citation.name}</span>
      {isFilter
        ? <span className="text-[10px] text-purple-400">Matched</span>
        : <span className="text-[10px] font-mono text-purple-400">{Math.round(citation.score * 100)}%</span>
      }
    </button>
  )
}
