import { useEffect, useState, useRef, type FormEvent } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, type Crew } from '../api/client';
import MessageList, { type MessageItem } from '../components/MessageList';

const inputStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '12px',
  border: '1px solid #ddd',
  borderRadius: 8,
  fontSize: 15,
  boxSizing: 'border-box',
  marginBottom: 12,
};

const btnStyle: React.CSSProperties = {
  background: '#3498db',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  padding: '10px 24px',
  cursor: 'pointer',
  fontSize: 15,
};

type Phase = 'idle' | 'task' | 'chat';

export default function CrewRun() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [crew, setCrew] = useState<Crew | null>(null);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [running, setRunning] = useState(false);
  const [phase, setPhase] = useState<Phase>('idle');
  const wsRef = useRef<WebSocket | null>(null);
  const streamingRef = useRef<MessageItem | null>(null);
  const phaseRef = useRef<Phase>('idle');

  // Keep refs in sync so WebSocket callbacks always see latest values
  phaseRef.current = phase;

  useEffect(() => {
    if (!id) return;
    api.getCrew(Number(id)).then(setCrew).catch(console.error);
  }, [id]);

  const openWebSocket = (msgType: 'task' | 'followup', text: string) => {
    wsRef.current?.close();

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${window.location.host}/api/crews/${id}/stream`);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: msgType, input: text }));
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === 'agent_message' && data.data) {
        streamingRef.current = null;
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          const newItem: MessageItem = { type: 'text', ...data.data };
          if (last && last.agent_name === data.data.agent_name && !last.agent_role) {
            const updated = [...prev];
            updated[updated.length - 1] = newItem;
            return updated;
          }
          return [...prev, newItem];
        });
      } else if (data.type === 'agent_chunk') {
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last && last.agent_name === data.agent_name && streamingRef.current?.agent_name === data.agent_name) {
            const updated = [...prev];
            updated[updated.length - 1] = { ...last, content: last.content + data.content };
            streamingRef.current = updated[updated.length - 1];
            return updated;
          } else {
            const newMsg = { agent_name: data.agent_name, agent_role: '', content: data.content };
            streamingRef.current = newMsg;
            return [...prev, newMsg];
          }
        });
      } else if (data.type === 'workflow_complete') {
        setRunning(false);
        setPhase('chat');
        streamingRef.current = null;
      } else if (data.type === 'tool_call') {
        streamingRef.current = null;
        setMessages((prev) => [...prev, {
          type: 'tool_call',
          agent_name: data.agent_name,
          tool_name: data.tool_name,
          arguments: data.arguments,
        }]);
      } else if (data.type === 'tool_result') {
        streamingRef.current = null;
        setMessages((prev) => {
          const updated = [...prev];
          for (let i = updated.length - 1; i >= 0; i--) {
            if (updated[i].type === 'tool_call' &&
                updated[i].agent_name === data.agent_name &&
                updated[i].tool_name === data.tool_name) {
              updated[i] = { ...updated[i], type: 'tool_call_result', result: data.result };
              break;
            }
          }
          return updated;
        });
      } else if (data.type === 'followup_complete') {
        setRunning(false);
        streamingRef.current = null;
      } else if (data.type === 'error') {
        setRunning(false);
        alert(data.message || '发生错误');
      }
    };

    ws.onerror = () => {
      setRunning(false);
      if (phaseRef.current === 'task') {
        setPhase('idle');
      }
    };

    ws.onclose = () => {
      setRunning(false);
    };
  };

  const handleSend = (e: FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || !id || running) return;

    setRunning(true);

    if (phase === 'idle') {
      setMessages([]);
      setPhase('task');
      openWebSocket('task', text);
      return;
    }

    setInput('');
    if (phase === 'chat') {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'followup', input: text }));
      } else {
        openWebSocket('followup', text);
      }
    }
  };

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  if (!crew) return <p>加载中...</p>;

  return (
    <div>
      <button onClick={() => { wsRef.current?.close(); navigate(`/crews/${id}`); }} style={{ ...btnStyle, background: '#95a5a6', marginBottom: 16 }}>
        &larr; 返回
      </button>

      <h2>运行：{crew.name}</h2>
      {phase === 'chat' && <p style={{ color: '#2ecc71', fontSize: 14, marginBottom: 12 }}>任务已完成，你可以继续与智能体讨论</p>}

      <form onSubmit={handleSend}>
        <div style={{ display: 'flex', gap: 12 }}>
          <input
            style={{ ...inputStyle, flex: 1, marginBottom: 0 }}
            placeholder={phase === 'idle' ? '请输入任务...' : '输入后续消息与智能体讨论...'}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={running}
          />
          <button type="submit" style={btnStyle} disabled={running || !input.trim()}>
            {running ? '运行中...' : phase === 'idle' ? '下发任务' : '发送'}
          </button>
        </div>
      </form>

      <div style={{ marginTop: 24 }}>
        <h3>对话记录</h3>
        <MessageList messages={messages} running={running} />
      </div>
    </div>
  );
}
