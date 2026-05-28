import { useEffect, useState, useRef, type FormEvent } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, type Crew, type Task } from '../api/client';
import MessageList from '../components/MessageList';

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

export default function CrewRun() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [crew, setCrew] = useState<Crew | null>(null);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Array<{ agent_name: string; agent_role: string; content: string }>>([]);
  const [running, setRunning] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!id) return;
    api.getCrew(Number(id)).then(setCrew).catch(console.error);
  }, [id]);

  useEffect(() => {
    if (!id || !running) return;

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const ws = new WebSocket(`${protocol}://${window.location.host}/api/crews/${id}/stream`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'agent_message' && data.data) {
        setMessages((prev) => [...prev, data.data]);
      } else if (data.type === 'workflow_complete') {
        setRunning(false);
      }
    };

    ws.onerror = () => setRunning(false);

    return () => { ws.close(); };
  }, [id, running]);

  const handleRun = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !id) return;

    setMessages([]);
    setRunning(true);

    try {
      const task: Task = await api.runTask(Number(id), input);
      if (task.messages) {
        setMessages(task.messages as Array<{ agent_name: string; agent_role: string; content: string }>);
      }
    } catch (err) {
      console.error(err);
    }
    setRunning(false);
  };

  if (!crew) return <p>Loading...</p>;

  return (
    <div>
      <button onClick={() => navigate(`/crews/${id}`)} style={{ ...btnStyle, background: '#95a5a6', marginBottom: 16 }}>
        &larr; Back
      </button>

      <h2>Run: {crew.name}</h2>

      <form onSubmit={handleRun}>
        <input
          style={inputStyle}
          placeholder="Enter your task..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={running}
        />
        <button type="submit" style={btnStyle} disabled={running || !input.trim()}>
          {running ? 'Running...' : 'Run'}
        </button>
      </form>

      <div style={{ marginTop: 24 }}>
        <h3>Conversation</h3>
        <MessageList messages={messages} running={running} />
      </div>
    </div>
  );
}
