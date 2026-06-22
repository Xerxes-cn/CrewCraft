import { useState } from 'react';
import type { Agent } from '../api/client';
import { api } from '../api/client';

interface Props {
  agent: Agent;
  onDelete: (id: number) => void;
  onUpdate: () => void;
}

const cardStyle: React.CSSProperties = {
  border: '1px solid #e0e0e0',
  borderRadius: 8,
  padding: 16,
  marginBottom: 12,
};

const btnStyle: React.CSSProperties = {
  border: 'none',
  borderRadius: 4,
  padding: '4px 12px',
  cursor: 'pointer',
  fontSize: 13,
  marginLeft: 6,
};

const fieldStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '6px 10px',
  marginBottom: 8,
  border: '1px solid #ddd',
  borderRadius: 4,
  fontSize: 13,
  boxSizing: 'border-box',
};

export default function AgentCard({ agent, onDelete, onUpdate }: Props) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(agent.name);
  const [role, setRole] = useState(agent.role);
  const [systemPrompt, setSystemPrompt] = useState(agent.system_prompt || '');
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.updateAgent(agent.id, {
        name: name.trim(),
        role: role.trim(),
        system_prompt: systemPrompt.trim() || null,
      });
      onUpdate();
      setEditing(false);
    } catch (err) {
      console.error(err);
      alert('更新失败，请重试');
    }
    setSaving(false);
  };

  const handleCancel = () => {
    setName(agent.name);
    setRole(agent.role);
    setSystemPrompt(agent.system_prompt || '');
    setEditing(false);
  };

  if (editing) {
    return (
      <div style={cardStyle}>
        <input style={fieldStyle} placeholder="名称" value={name} onChange={(e) => setName(e.target.value)} required />
        <input style={fieldStyle} placeholder="角色" value={role} onChange={(e) => setRole(e.target.value)} required />
        <textarea
          style={{ ...fieldStyle, minHeight: 60 }}
          placeholder="系统提示词（可选）"
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
        />
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6 }}>
          <button onClick={handleCancel} style={{ ...btnStyle, background: '#95a5a6', color: '#fff' }}>取消</button>
          <button onClick={handleSave} disabled={saving || !name.trim() || !role.trim()} style={{
            ...btnStyle, background: saving ? '#95a5a6' : '#2ecc71', color: '#fff',
          }}>
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={cardStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <strong>{agent.name}</strong>
          <span style={{ color: '#888', marginLeft: 8 }}>{agent.role}</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
          <button onClick={() => { setEditing(true); }} style={{ ...btnStyle, background: '#f39c12', color: '#fff' }}>编辑</button>
          <button onClick={() => onDelete(agent.id)} style={{ ...btnStyle, background: '#e74c3c', color: '#fff' }}>删除</button>
        </div>
      </div>
      {agent.system_prompt && (
        <p style={{ color: '#666', fontSize: 14, marginTop: 8 }}>{agent.system_prompt}</p>
      )}
    </div>
  );
}
