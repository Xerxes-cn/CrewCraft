interface Message {
  agent_name: string;
  agent_role: string;
  content: string;
}

interface Props {
  messages: Message[];
  running: boolean;
}

const msgStyle: React.CSSProperties = {
  border: '1px solid #e0e0e0',
  borderRadius: 8,
  padding: 16,
  marginBottom: 12,
};

export default function MessageList({ messages, running }: Props) {
  return (
    <div>
      {messages.map((msg, i) => (
        <div key={i} style={msgStyle}>
          <div style={{ marginBottom: 8 }}>
            <strong>{msg.agent_name}</strong>
            <span style={{ color: '#888', marginLeft: 8, fontSize: 14 }}>{msg.agent_role}</span>
          </div>
          <p style={{ whiteSpace: 'pre-wrap', margin: 0, lineHeight: 1.6 }}>{msg.content}</p>
        </div>
      ))}
      {running && <p style={{ color: '#888' }}>Working...</p>}
    </div>
  );
}
