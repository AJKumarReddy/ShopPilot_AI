"use client";
import {
  ArrowUp,
  Mic,
  MicOff,
  Sparkles,
  Square,
  Volume2,
  VolumeX,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { ChatMessage } from "@/types/commerce";
import type { useVoice } from "@/hooks/useVoice";
export function ChatPanel({
  messages,
  busy,
  status,
  voice,
  onSend,
}: {
  messages: ChatMessage[];
  busy: boolean;
  status: string;
  voice: ReturnType<typeof useVoice>;
  onSend: (text: string) => void;
}) {
  const [input, setInput] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages, status]);
  function send() {
    if (!input.trim() || busy) return;
    onSend(input.trim());
    setInput("");
  }
  return (
    <aside className="chat-panel" aria-label="Shopping assistant">
      <div className="chat-heading">
        <div className="assistant-avatar">
          <Sparkles size={20} />
        </div>
        <div>
          <h2>Your shopping copilot</h2>
          <p>
            <span className="online-dot" /> Here to help you find your fit
          </p>
        </div>
        <span className="ai-label">AI</span>
      </div>
      <div
        className="conversation"
        role="log"
        aria-live="polite"
        aria-label="Conversation"
      >
        <div className="conversation-date">LET&apos;S FIND SOMETHING GREAT</div>
        {messages.length === 0 && (
          <div className="welcome-message">
            <div className="little-spark">✦</div>
            <h3>Good finds. Less searching.</h3>
            <p>
              Tell me what you&apos;re looking for. I&apos;ll help you discover
              your options, compare the details, and find the right one.
            </p>
            <div className="chat-suggestions">
              <button
                disabled={busy}
                onClick={() =>
                  onSend(
                    "I'm looking for wireless noise-cancelling headphones under $150 with good battery life.",
                  )
                }
              >
                Headphones for my everyday 🎧
              </button>
              <button
                disabled={busy}
                onClick={() => onSend("Show me running shoes under $120")}
              >
                A fresh pair of running shoes ↗
              </button>
              <button
                disabled={busy}
                onClick={() => onSend("I need coffee accessories under $50")}
              >
                Something for my coffee corner ☕
              </button>
            </div>
            <p className="hint">
              A budget and a few must-haves are a great start.
            </p>
          </div>
        )}
        {messages.map((message) => (
          <div key={message.id} className={`message ${message.role}`}>
            <span className="message-author">
              {message.role === "assistant" ? "✦ ShopPilot" : "You"}
            </span>
            <p>{message.content}</p>
          </div>
        ))}
        {busy && (
          <div className="thinking" role="status">
            <span />
            <span />
            <span />
            <p>{status || "Understanding request"}</p>
          </div>
        )}
        <div ref={end} />
      </div>
      {voice.state === "listening" && (
        <div className="transcript" role="status">
          <span className="listening-dot" /> Listening… {voice.transcript}
        </div>
      )}
      {voice.state === "speaking" && (
        <button className="speaking-bar" onClick={voice.cancel}>
          <Volume2 size={14} /> Speaking · click to stop <Square size={11} />
        </button>
      )}
      <div className="chat-composer">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            send();
          }}
        >
          <label className="sr-only" htmlFor="chat-input">
            Your shopping request
          </label>
          <textarea
            id="chat-input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            maxLength={2000}
            placeholder="What are you looking for?"
            rows={2}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                send();
              }
            }}
          />
          <div className="composer-actions">
            <button
              type="button"
              className={`icon-button mic ${voice.state === "listening" ? "active" : ""}`}
              aria-label={
                voice.state === "listening"
                  ? "Stop listening"
                  : "Start voice input"
              }
              disabled={!voice.supported || !voice.enabled || busy}
              onClick={voice.state === "listening" ? voice.stop : voice.start}
            >
              {voice.state === "listening" ? (
                <Square size={16} />
              ) : (
                <Mic size={18} />
              )}
            </button>
            <span>
              {voice.supported && voice.enabled
                ? "Type it. Or just say it."
                : "Text is always available."}
            </span>
            <button
              type="submit"
              className="send-button"
              aria-label="Send message"
              disabled={busy || !input.trim()}
            >
              <ArrowUp size={19} />
            </button>
          </div>
        </form>
        <div className="voice-settings">
          <button
            className="text-button"
            aria-pressed={voice.enabled}
            onClick={() => voice.setEnabled(!voice.enabled)}
          >
            {voice.enabled ? <Mic size={12} /> : <MicOff size={12} />} Voice{" "}
            {voice.enabled ? "on" : "off"}
          </button>
          <button
            className="text-button"
            aria-pressed={voice.readAloud}
            onClick={() => voice.setReadAloud(!voice.readAloud)}
          >
            {voice.readAloud ? <Volume2 size={12} /> : <VolumeX size={12} />}{" "}
            Read aloud {voice.readAloud ? "on" : "off"}
          </button>
        </div>
      </div>
    </aside>
  );
}
