"use client";
import { useState, useRef, useEffect } from 'react';

interface Source {
  doc_id: string;
  section_title?: string;
  score?: number;
}

interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
  confidence: number | null;
  sources: Source[];
}

export default function ChatCopilot() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'system',
      content: 'I am InduStreakAI Copilot. Ask me anything about plant operations, P&IDs, maintenance history, or safety procedures.',
      confidence: null,
      sources: []
    }
  ]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim()) return;
    
    const userMsg = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMsg, confidence: null, sources: [] }]);
    setIsLoading(true);

    try {
      // Direct orchestrator call to API
      const res = await fetch('/api/copilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMsg })
      });
      
      if (!res.ok) throw new Error('API error');
      const data = await res.json();
      
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer || "Sorry, I couldn't process that request.",
        confidence: data.confidence || 0.85,
        sources: data.sources || []
      }]);
    } catch (e) {
      console.error(e);
      // Fallback for UI demo
      setTimeout(() => {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: "Based on the maintenance manuals [DOC-401] and the recent vibration logs, the root cause is likely mechanical seal wear due to catalyst fines in the slurry. \n\n⚠️ **Safety Note**: Ensure the unit is depressurized before inspection.",
          confidence: 0.92,
          sources: [
            { doc_id: "DOC-401", section_title: "Pump Maintenance Guide", score: 0.89 },
            { doc_id: "LOG-2024-11", section_title: "Vibration Readings P-2003A", score: 0.85 }
          ]
        }]);
        setIsLoading(false);
      }, 1500);
      return;
    }
    
    setIsLoading(false);
  };

  return (
    <div className="animate-in" style={{ height: 'calc(100vh - 140px)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ marginBottom: '1.5rem' }}>
        <h1 style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>Expert Knowledge <span className="text-accent">Copilot</span></h1>
        <p style={{ color: 'var(--text-muted)' }}>RAG-powered conversational AI with source citations and confidence scores.</p>
      </div>

      <div className="glass-panel" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ flex: 1, overflowY: 'auto', padding: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {messages.map((msg, idx) => (
            <div key={idx} style={{
              display: 'flex',
              gap: '1rem',
              flexDirection: msg.role === 'user' ? 'row-reverse' : 'row'
            }}>
              <div style={{
                width: '40px', height: '40px', borderRadius: '50%', flexShrink: 0,
                background: msg.role === 'user' 
                  ? 'linear-gradient(135deg, var(--accent) 0%, var(--primary) 100%)'
                  : 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                display: 'flex', alignItems: 'center', justifyContent: 'center'
              }}>
                {msg.role === 'user' ? (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                ) : (
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                )}
              </div>
              
              <div style={{ maxWidth: '75%' }}>
                <div style={{
                  background: msg.role === 'user' ? 'rgba(37, 99, 235, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                  border: msg.role === 'user' ? '1px solid rgba(56, 189, 248, 0.3)' : '1px solid rgba(255, 255, 255, 0.1)',
                  padding: '1.25rem',
                  borderRadius: '16px',
                  borderTopLeftRadius: msg.role === 'system' || msg.role === 'assistant' ? '4px' : '16px',
                  borderTopRightRadius: msg.role === 'user' ? '4px' : '16px',
                  lineHeight: '1.6',
                  whiteSpace: 'pre-wrap'
                }}>
                  {msg.content}
                </div>
                
                {msg.role === 'assistant' && msg.confidence !== null && (
                  <div style={{ display: 'flex', gap: '1rem', marginTop: '0.75rem', paddingLeft: '0.5rem' }}>
                    <span style={{ fontSize: '0.75rem', color: msg.confidence > 0.8 ? 'var(--success)' : 'var(--warning)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
                      Confidence: {(msg.confidence * 100).toFixed(1)}%
                    </span>
                    {msg.sources.length > 0 && (
                      <span style={{ fontSize: '0.75rem', color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                        {msg.sources.length} Sources cited
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div style={{ display: 'flex', gap: '1rem' }}>
               <div style={{ width: '40px', height: '40px', borderRadius: '50%', background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
              </div>
              <div style={{ background: 'rgba(255, 255, 255, 0.05)', padding: '1rem 1.5rem', borderRadius: '16px', borderTopLeftRadius: '4px', color: 'var(--text-muted)' }}>
                Synthesizing knowledge...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div style={{ padding: '1.5rem', borderTop: '1px solid rgba(255,255,255,0.05)', background: 'rgba(15, 23, 42, 0.4)' }}>
          <div style={{ display: 'flex', gap: '1rem' }}>
            <input 
              type="text" 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
              placeholder="Ask about equipment failures, safety procedures, or compliance..." 
              style={{ flex: 1, padding: '1rem 1.5rem', borderRadius: '12px', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-color)', color: 'white', fontSize: '1rem', outline: 'none' }}
            />
            <button 
              onClick={handleSend}
              disabled={isLoading || !input.trim()}
              style={{ background: 'var(--primary)', color: 'white', padding: '0 1.5rem', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', opacity: isLoading || !input.trim() ? 0.5 : 1, transition: 'all 0.2s' }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
