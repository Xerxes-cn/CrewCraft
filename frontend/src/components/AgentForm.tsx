import { useState, type FormEvent } from 'react';
import { api } from '../api/client';

interface Props {
  onSubmit: (data: { name: string; role: string; system_prompt: string; order: number }) => void;
  crewName: string;
  crewDescription: string | null;
  workflowType: string;
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

export default function AgentForm({ onSubmit, crewName, crewDescription, workflowType }: Props) {
  const [name, setName] = useState('');
  const [role, setRole] = useState('');
  const [systemPrompt, setSystemPrompt] = useState('');
  const [order, setOrder] = useState(0);
  const [generating, setGenerating] = useState(false);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit({ name, role, system_prompt: systemPrompt, order });
    setName('');
    setRole('');
    setSystemPrompt('');
    setOrder((n) => n + 1);
  };

  const handleGeneratePrompt = async () => {
    if (!role.trim()) return;
    setGenerating(true);
    try {
      const res = await api.generatePrompt({
        role: role.trim(),
        crew_name: crewName,
        crew_description: crewDescription,
        workflow_type: workflowType,
      });
      setSystemPrompt(res.prompt);
    } catch (err) {
      console.error(err);
      alert('生成提示词失败，请重试');
    }
    setGenerating(false);
  };

  return (
    <form onSubmit={handleSubmit} style={formStyle}>
      <h3>添加智能体</h3>
      <input style={fieldStyle} placeholder="名称" value={name} onChange={(e) => setName(e.target.value)} required />
      <input style={fieldStyle} placeholder="角色（例如：研究员）" value={role} onChange={(e) => setRole(e.target.value)} required />
      <div style={{ position: 'relative', marginBottom: 12 }}>
        <textarea
          style={{ ...fieldStyle, minHeight: 80, marginBottom: 0, paddingRight: 90 }}
          placeholder="系统提示词（可选）"
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
        />
        <button
          type="button"
          onClick={handleGeneratePrompt}
          disabled={generating || !role.trim()}
          style={{
            position: 'absolute',
            top: 8,
            right: 8,
            background: generating ? '#95a5a6' : '#8e44ad',
            color: '#fff',
            border: 'none',
            borderRadius: 4,
            padding: '4px 10px',
            cursor: generating || !role.trim() ? 'not-allowed' : 'pointer',
            fontSize: 13,
            whiteSpace: 'nowrap',
          }}
        >
          {generating ? '生成中...' : 'AI 生成'}
        </button>
      </div>
      <button type="submit" style={btnPrimary}>添加智能体</button>
    </form>
  );
}
