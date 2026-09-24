import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  MessageSquarePlus,
  ArrowUp,
  MoreHorizontal,
  Trash2,
  MessageSquare,
  ArrowRight,
  Bot,
  User,
  Brain,
  Loader2,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

/* ─── Types ─────────────────────────────────────────────────────────────── */

interface Conversation {
  id: string;
  title: string;
  summary?: string | null;
  created_at: string;
  updated_at: string;
}

interface Message {
  id: string;
  conversation_id?: string;
  role: "user" | "assistant";
  content: string;
  metadata?: Record<string, any>;
  created_at?: string;
}

/* ─── Suggestions ────────────────────────────────────────────────────────── */

const SUGGESTIONS = [
  "How much did I spend this month?",
  "What were my biggest purchases?",
  "What did I buy recently?",
  "Why did I spend more this month?",
];

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function formatDate(dateStr?: string): string {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
  } catch {
    return dateStr;
  }
}

function formatTime(dateStr?: string): string {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function renderFormattedText(text: string) {
  return text.split("\n").map((line, i, arr) => {
    const parts = line.split(/(\*\*[^*]+\*\*)/g);
    return (
      <React.Fragment key={i}>
        {parts.map((part, j) =>
          part.startsWith("**") && part.endsWith("**") ? (
            <strong key={j}>{part.slice(2, -2)}</strong>
          ) : (
            <span key={j}>{part}</span>
          )
        )}
        {i < arr.length - 1 && <br />}
      </React.Fragment>
    );
  });
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export const Insights: React.FC = () => {
  const { session } = useAuth();
  const [conversations, setConversations]       = useState<Conversation[]>([]);
  const [activeId, setActiveId]                 = useState<string | null>(null);
  const [messages, setMessages]                 = useState<Message[]>([]);
  const [input, setInput]                       = useState("");
  const [loadingConversations, setLoadingConversations] = useState(false);
  const [loadingMessages, setLoadingMessages]           = useState(false);
  const [sendingMessage, setSendingMessage]             = useState(false);
  const [error, setError]                               = useState<string | null>(null);
  const [menuOpenId, setMenuOpenId]                     = useState<string | null>(null);
  const [activeHeaderOptions, setActiveHeaderOptions]   = useState(false);

  const messagesAreaRef = useRef<HTMLDivElement>(null);
  const textareaRef     = useRef<HTMLTextAreaElement>(null);

  const API_URL = import.meta.env.VITE_API_URL || "";

  const getAuthHeaders = useCallback((): Record<string, string> => {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (session?.access_token) {
      headers["Authorization"] = `Bearer ${session.access_token}`;
    }
    return headers;
  }, [session?.access_token]);

  const activeConv = conversations.find((c) => c.id === activeId);

  /* Scroll internal message container to bottom without scrolling outer window/page */
  useEffect(() => {
    if (messagesAreaRef.current) {
      messagesAreaRef.current.scrollTop = messagesAreaRef.current.scrollHeight;
    }
  }, [messages, sendingMessage]);

  /* Auto-size textarea */
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 120) + "px";
  }, [input]);

  /* Close context menu on outside click */
  useEffect(() => {
    if (!menuOpenId && !activeHeaderOptions) return;
    const handleClickOutside = () => {
      setMenuOpenId(null);
      setActiveHeaderOptions(false);
    };
    window.addEventListener("click", handleClickOutside);
    return () => window.removeEventListener("click", handleClickOutside);
  }, [menuOpenId, activeHeaderOptions]);

  /* Fetch conversations list */
  const fetchConversations = useCallback(async (autoSelectFirst = false) => {
    if (!session?.access_token) return;
    try {
      setLoadingConversations(true);
      const res = await fetch(`${API_URL}/api/insights/conversations`, {
        headers: getAuthHeaders(),
      });
      if (!res.ok) throw new Error("Failed to load conversations.");
      const data: Conversation[] = await res.json();
      setConversations(data);
      if (autoSelectFirst && data.length > 0) {
        setActiveId(data[0].id);
      }
    } catch (err: any) {
      console.error("Error fetching conversations:", err);
    } finally {
      setLoadingConversations(false);
    }
  }, [API_URL, getAuthHeaders, session?.access_token]);

  /* Load conversation messages */
  const loadConversationMessages = useCallback(async (convId: string) => {
    if (!session?.access_token) return;
    try {
      setLoadingMessages(true);
      setError(null);
      const res = await fetch(`${API_URL}/api/insights/conversations/${convId}`, {
        headers: getAuthHeaders(),
      });
      if (res.status === 404) {
        setError("Conversation not found.");
        return;
      }
      if (res.status === 403) {
        setError("Access denied to this conversation.");
        return;
      }
      if (!res.ok) throw new Error("Failed to load messages.");
      const data = await res.json();
      setMessages(data.messages || []);
    } catch (err: any) {
      console.error("Error loading messages:", err);
      setError(err.message || "Failed to load conversation history.");
    } finally {
      setLoadingMessages(false);
    }
  }, [API_URL, getAuthHeaders, session?.access_token]);

  /* Load initial conversations on mount */
  useEffect(() => {
    fetchConversations(true);
  }, [fetchConversations]);

  /* Load messages whenever activeId changes */
  useEffect(() => {
    if (activeId) {
      loadConversationMessages(activeId);
    } else {
      setMessages([]);
    }
  }, [activeId, loadConversationMessages]);

  /* ─── 1. New Chat Flow ─────────────────────────────────────────────────── */
  const handleNewChat = async () => {
    try {
      setError(null);
      const res = await fetch(`${API_URL}/api/insights/conversations`, {
        method: "POST",
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to create new conversation.");
      }
      const newConv: Conversation = await res.json();
      // Prepend to conversation list immediately
      setConversations((prev) => [newConv, ...prev.filter((c) => c.id !== newConv.id)]);
      setActiveId(newConv.id);
      setMessages([]);
      setInput("");
      textareaRef.current?.focus();
    } catch (err: any) {
      console.error("New chat creation failed:", err);
      setError(err.message || "Could not start new chat. Please try again.");
    }
  };

  /* ─── 2. Select Conversation ───────────────────────────────────────────── */
  const handleSelectConversation = (id: string) => {
    if (activeId === id) return;
    setActiveId(id);
    setInput("");
  };

  /* ─── 3. Delete Conversation ───────────────────────────────────────────── */
  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setMenuOpenId(null);
    try {
      const res = await fetch(`${API_URL}/api/insights/conversations/${id}`, {
        method: "DELETE",
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        throw new Error("Failed to delete conversation.");
      }
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeId === id) {
        setActiveId(null);
        setMessages([]);
      }
    } catch (err: any) {
      console.error("Error deleting conversation:", err);
      setError(err.message || "Could not delete conversation.");
    }
  };

  /* ─── 4. Send Message (First or Follow-up) ─────────────────────────────── */
  const handleSendMessage = async (textToSend?: string) => {
    const text = (textToSend ?? input).trim();
    if (!text || sendingMessage) return;

    setError(null);
    let targetConvId = activeId;

    // Optimistic user message for immediate UI responsiveness
    const tempUserMsg: Message = {
      id: `temp-usr-${Date.now()}`,
      role: "user",
      content: text,
      created_at: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, tempUserMsg]);
    setInput("");
    setSendingMessage(true);

    try {
      // If there is no active conversation yet, create one first
      if (!targetConvId) {
        const convRes = await fetch(`${API_URL}/api/insights/conversations`, {
          method: "POST",
          headers: getAuthHeaders(),
        });
        if (!convRes.ok) {
          throw new Error("Failed to initialize conversation.");
        }
        const newConv: Conversation = await convRes.json();
        targetConvId = newConv.id;
        setActiveId(newConv.id);
        setConversations((prev) => [newConv, ...prev]);
      }

      const res = await fetch(`${API_URL}/api/insights/ask`, {
        method: "POST",
        headers: getAuthHeaders(),
        body: JSON.stringify({
          conversation_id: targetConvId,
          question: text,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to process question.");
      }

      const data = await res.json();

      const assistantMsg: Message = {
        id: `ai-${Date.now()}`,
        role: "assistant",
        content: data.answer,
        metadata: {
          tools_used: data.tools_used,
          rounds_used: data.rounds_used,
        },
        created_at: data.created_at,
      };

      setMessages((prev) => [...prev, assistantMsg]);

      // Refresh sidebar list to reflect updated title and ordering
      fetchConversations(false);
    } catch (err: any) {
      console.error("Error sending message:", err);
      setError(err.message || "Failed to get AI insights. Please retry.");
      // Restore user text on failure
      setInput(text);
      // Remove optimistic user message on failure
      setMessages((prev) => prev.filter((m) => m.id !== tempUserMsg.id));
    } finally {
      setSendingMessage(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="ins-workspace">

      {/* ─── Left Sidebar ─────────────────────────────────────────── */}
      <aside className="ins-sidebar">

        {/* Top: + New Chat Button */}
        <div className="ins-sidebar-top">
          <button className="ins-new-chat-btn" onClick={handleNewChat}>
            <MessageSquarePlus size={16} />
            <span>+ New Chat</span>
          </button>
        </div>

        {/* Conversation List */}
        <div className="ins-conv-section">
          <span className="ins-conv-label">Recent Conversations</span>
          {loadingConversations && conversations.length === 0 ? (
            <div className="flex items-center justify-center py-8 text-white/30 gap-2 text-xs">
              <Loader2 size={14} className="animate-spin" />
              <span>Loading...</span>
            </div>
          ) : (
            <ul className="ins-conv-list">
              {conversations.map((conv) => {
                const isActive = activeId === conv.id;
                return (
                  <li
                    key={conv.id}
                    className={`ins-conv-item ${isActive ? "active" : ""}`}
                    onClick={() => handleSelectConversation(conv.id)}
                  >
                    <MessageSquare size={14} className="ins-conv-icon" />
                    <div className="ins-conv-text">
                      <span className="ins-conv-title">{conv.title}</span>
                      <span className="ins-conv-date">{formatDate(conv.updated_at || conv.created_at)}</span>
                    </div>
                    <div
                      className="ins-conv-menu-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        setMenuOpenId(menuOpenId === conv.id ? null : conv.id);
                      }}
                    >
                      <MoreHorizontal size={14} />
                      {menuOpenId === conv.id && (
                        <div className="ins-conv-menu">
                          <button
                            className="ins-conv-menu-item danger"
                            onClick={(e) => handleDeleteConversation(conv.id, e)}
                          >
                            <Trash2 size={13} />
                            <span>Delete</span>
                          </button>
                        </div>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Bottom: Cross-chat memory card */}
        <div className="ins-memory-card">
          <div className="ins-memory-icon">
            <Brain size={16} />
          </div>
          <div className="ins-memory-text">
            <span className="ins-memory-title">Cross-chat memory enabled</span>
            <span className="ins-memory-desc">
              I remember your preferences across conversations.
            </span>
          </div>
        </div>
      </aside>

      {/* ─── Right Chat Panel ──────────────────────────────────────── */}
      <main className="ins-main">

        {/* Header */}
        <header className="ins-chat-header">
          <div className="ins-chat-header-info">
            <h2 className="ins-chat-header-title">
              {activeConv ? activeConv.title : "Ask TracePay anything"}
            </h2>
            <span className="ins-chat-header-sub">
              {activeConv ? `Started on ${formatDate(activeConv.created_at)}` : "Start a new conversation"}
            </span>
          </div>
          <div className="relative">
            <button
              className="ins-chat-more-btn"
              title="Options"
              onClick={(e) => {
                e.stopPropagation();
                setActiveHeaderOptions(!activeHeaderOptions);
              }}
            >
              <MoreHorizontal size={18} />
            </button>
            {activeHeaderOptions && (
              <div className="ins-conv-menu" style={{ right: 0, top: "calc(100% + 6px)" }}>
                <button
                  className="ins-conv-menu-item danger"
                  onClick={() => {
                    setMessages([]);
                    setActiveHeaderOptions(false);
                  }}
                >
                  <Trash2 size={13} />
                  <span>Clear messages</span>
                </button>
              </div>
            )}
          </div>
        </header>

        {/* Error notification banner */}
        {error && (
          <div className="mx-6 mt-3 px-4 py-2 rounded-xl bg-red-500/10 border border-red-500/20 text-red-300 text-xs flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-red-400 hover:text-white ml-2 text-sm">&times;</button>
          </div>
        )}

        {/* Messages / Welcome Area */}
        <div className="ins-messages-area" ref={messagesAreaRef}>
          {loadingMessages ? (
            <div className="flex-1 flex items-center justify-center text-white/40 gap-2">
              <Loader2 size={20} className="animate-spin text-[#7A9B6D]" />
              <span className="text-xs">Loading conversation history...</span>
            </div>
          ) : messages.length === 0 ? (
            /* Welcome / Empty State */
            <div className="ins-welcome">
              <h3 className="ins-welcome-title">Ask TracePay anything</h3>
              <p className="ins-welcome-sub">
                Get insights from your spending, purchases,<br />and financial history.
              </p>
              <div className="ins-suggestions">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    className="ins-suggestion-chip"
                    onClick={() => handleSendMessage(s)}
                    disabled={sendingMessage}
                  >
                    <span>{s}</span>
                    <ArrowRight size={14} className="ins-chip-arrow" />
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Messages Thread */
            <div className="ins-messages-inner">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`ins-msg ${msg.role === "user" ? "ins-msg-user" : "ins-msg-ai"}`}
                >
                  <div className="ins-msg-avatar">
                    {msg.role === "user" ? <User size={15} /> : <Bot size={15} />}
                  </div>
                  <div className="ins-msg-body">
                    <div className="ins-msg-meta">
                      <span className="ins-msg-name">
                        {msg.role === "user" ? "You" : "TracePay AI"}
                      </span>
                      {msg.created_at && (
                        <span className="ins-msg-time">{formatTime(msg.created_at)}</span>
                      )}
                    </div>
                    <div className="ins-msg-bubble">
                      {renderFormattedText(msg.content)}
                    </div>
                  </div>
                </div>
              ))}

              {/* Typing indicator */}
              {sendingMessage && (
                <div className="ins-msg ins-msg-ai">
                  <div className="ins-msg-avatar">
                    <Bot size={15} />
                  </div>
                  <div className="ins-msg-body">
                    <div className="ins-msg-meta">
                      <span className="ins-msg-name">TracePay AI</span>
                    </div>
                    <div className="ins-msg-bubble">
                      <div className="flex items-center gap-1.5 py-1 px-1">
                        <span className="w-2 h-2 rounded-full bg-[#7A9B6D] animate-bounce"></span>
                        <span className="w-2 h-2 rounded-full bg-[#7A9B6D] animate-bounce [animation-delay:150ms]"></span>
                        <span className="w-2 h-2 rounded-full bg-[#7A9B6D] animate-bounce [animation-delay:300ms]"></span>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Composer (fixed at bottom, never scrolls out of view) */}
        <div className="ins-composer">
          <div className="ins-composer-box">
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask TracePay anything..."
              className="ins-composer-input"
              disabled={sendingMessage}
            />
            <button
              className="ins-composer-send"
              onClick={() => handleSendMessage()}
              disabled={sendingMessage || !input.trim()}
              title="Send message"
            >
              {sendingMessage ? (
                <Loader2 size={16} className="animate-spin text-white" />
              ) : (
                <ArrowUp size={16} strokeWidth={2.4} />
              )}
            </button>
          </div>
          <p className="ins-composer-hint">
            TracePay AI analyzes your verified receipts and cross-chat memory to deliver personalized financial insights.
          </p>
        </div>
      </main>
    </div>
  );
};
