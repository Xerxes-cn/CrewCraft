import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type Crew } from '../api/client';
import { useCrewStore } from '../store';

const cardStyle: React.CSSProperties = {
  border: '1px solid #e0e0e0',
  borderRadius: 8,
  padding: 16,
  marginBottom: 12,
  cursor: 'pointer',
};

const btnStyle: React.CSSProperties = {
  background: '#3498db',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  padding: '8px 20px',
  cursor: 'pointer',
  fontSize: 14,
};

const inputStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '8px 12px',
  marginBottom: 12,
  border: '1px solid #ddd',
  borderRadius: 4,
  fontSize: 14,
  boxSizing: 'border-box',
};

export default function CrewList() {
  const { crews, setCrews } = useCrewStore();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    api.listCrews().then(setCrews).catch(console.error);
  }, [setCrews]);

  const handleCreate = async (e: FormEvent) => {
    e.preventDefault();
    const crew = await api.createCrew({ name, description });
    setCrews([crew, ...crews]);
    setName('');
    setDescription('');
    setShowForm(false);
  };

  const handleDelete = async (id: number) => {
    await api.deleteCrew(id);
    setCrews(crews.filter((c) => c.id !== id));
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <h2>团队列表</h2>
        <button style={btnStyle} onClick={() => setShowForm(!showForm)}>
          {showForm ? '取消' : '新建团队'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} style={{ marginBottom: 24, padding: 16, border: '1px solid #e0e0e0', borderRadius: 8 }}>
          <input style={inputStyle} placeholder="团队名称" value={name} onChange={(e) => setName(e.target.value)} required />
          <input style={inputStyle} placeholder="描述（可选）" value={description} onChange={(e) => setDescription(e.target.value)} />
          <button type="submit" style={btnStyle}>创建</button>
        </form>
      )}

      {crews.length === 0 && <p style={{ color: '#888' }}>暂无团队，创建一个开始使用吧。</p>}

      {crews.map((crew) => (
        <div key={crew.id} style={cardStyle} onClick={() => navigate(`/crews/${crew.id}`)}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <strong>{crew.name}</strong>
              <span style={{ color: '#888', marginLeft: 8, fontSize: 13 }}>{crew.workflow_type}</span>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); handleDelete(crew.id); }}
              style={{ background: '#e74c3c', color: '#fff', border: 'none', borderRadius: 4, padding: '4px 12px', cursor: 'pointer' }}
            >
              删除
            </button>
          </div>
          {crew.description && <p style={{ color: '#666', fontSize: 14, marginTop: 8 }}>{crew.description}</p>}
          <p style={{ color: '#aaa', fontSize: 12, marginTop: 8 }}>
            {crew.agents.length} 个智能体
          </p>
        </div>
      ))}
    </div>
  );
}
