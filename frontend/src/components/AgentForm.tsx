import { useState, type FormEvent } from 'react';

interface Props {
  onSubmit: (data: { name: string; role: string; system_prompt: string; order: number }) => void;
}

const formStyle: React.CSSProperties = {
  border: '1px solid #e0e0e0',
  borderRadius: 8,
  padding: 16,
  marginBottom: 16,
};

const fieldStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '8px 12px',
  marginBottom: 12,
  border: '1px solid #ddd',
  borderRadius: 4,
  fontSize: 14,
  boxSizing: 'border-box',
};

const btnPrimary: React.CSSProperties = {
  background: '#3498db',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  padding: '8px 20px',
  cursor: 'pointer',
  fontSize: 14,
};

export default function AgentForm({ onSubmit }: Props) {
  const [name, setName] = useState('');
  const [role, setRole] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [order, setOrder] = useState(0);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({ name, role, system_prompt: systemPrompt, order });
    setName('');
    setRole('');
    setSystemPrompt('');
    setOrder((n) => n + 1);
  };

  return (
    <form onSubmit={handleSubmit} style={formStyle}>
      <h3>Add Agent</h3>
      <input style={fieldStyle} placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} required />
      <input style={fieldStyle} placeholder="Role (e.g. Researcher)" value={role} onChange={(e) => setRole(e.target.value)} required />
      <textarea
        style={{ ...fieldStyle, minHeight: 80 }}
        placeholder="System prompt (optional)"
        value={systemPrompt}
        onChange={(e) => setSystemPrompt(e.target.value)}
      />
      <button type="submit" style={btnPrimary}>Add Agent</button>
    </form>
  );
}
