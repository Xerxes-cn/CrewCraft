import type { Agent } from '../api/client';

interface Props {
  agent: Agent;
  onDelete: (id: number) => void;
}

const cardStyle: React.CSSProperties = {
  border: '1px solid #e0e0e0',
  borderRadius: 8,
  padding: 16,
  marginBottom: 12,
};

const btnDanger: React.CSSProperties = {
  background: '#e74c3c',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  padding: '4px 12px',
  cursor: 'pointer',
};

export default function AgentCard({ agent, onDelete }: Props) {
  return (
    <div style={cardStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <strong>{agent.name}</strong>
          <span style={{ color: '#888', marginLeft: 8 }}>{agent.role}</span>
        </div>
        <button onClick={() => onDelete(agent.id)} style={btnDanger}>删除</button>
      </div>
      {agent.system_prompt && (
        <p style={{ color: '#666', fontSize: 14, marginTop: 8 }}>{agent.system_prompt}</p>
      )}
    </div>
  );
}
