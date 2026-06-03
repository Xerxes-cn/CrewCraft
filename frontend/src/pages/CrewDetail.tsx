import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, type Crew } from '../api/client';
import AgentCard from '../components/AgentCard';
import AgentForm from '../components/AgentForm';
import WorkflowConfig from '../components/WorkflowConfig';

const btnStyle: React.CSSProperties = {
  background: '#2ecc71',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  padding: '10px 24px',
  cursor: 'pointer',
  fontSize: 15,
  marginTop: 16,
};

export default function CrewDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [crew, setCrew] = useState<Crew | null>(null);

  const load = () => {
    if (!id) return;
    api.getCrew(Number(id)).then(setCrew).catch(console.error);
  };

  useEffect(load, [id]);

  if (!crew) return <p>加载中...</p>;

  const handleAddAgent = async (data: { name: string; role: string; system_prompt: string; order: number }) => {
    await api.createAgent(crew.id, data);
    load();
  };

  const handleDeleteAgent = async (agentId: number) => {
    await api.deleteAgent(agentId);
    load();
  };

  const handleUpdateWorkflow = async (type: string, maxRounds?: number) => {
    const config = type === 'roundtable' ? { max_rounds: maxRounds || 2 } : null;
    const updated = await api.updateCrew(crew.id, {
      workflow_type: type,
      workflow_config: config,
    });
    setCrew(updated);
  };

  return (
    <div>
      <button onClick={() => navigate('/')} style={{ ...btnStyle, background: '#95a5a6', marginBottom: 16, marginTop: 0 }}>
        &larr; 返回
      </button>

      <h2>{crew.name}</h2>
      {crew.description && <p style={{ color: '#666' }}>{crew.description}</p>}

      <WorkflowConfig
        workflowType={crew.workflow_type}
        maxRounds={(crew.workflow_config as Record<string, unknown>)?.max_rounds as number || 2}
        onChangeType={(type) => handleUpdateWorkflow(type)}
        onChangeMaxRounds={(rounds) => handleUpdateWorkflow(crew.workflow_type, rounds)}
      />

      <h3>智能体（{crew.agents.length}）</h3>
      {crew.agents.map((agent) => (
        <AgentCard key={agent.id} agent={agent} onDelete={handleDeleteAgent} />
      ))}

      <AgentForm
        onSubmit={handleAddAgent}
        crewName={crew.name}
        crewDescription={crew.description}
        workflowType={crew.workflow_type}
      />

      {crew.agents.length > 0 && (
        <button style={btnStyle} onClick={() => navigate(`/crews/${crew.id}/run`)}>
          运行任务 &rarr;
        </button>
      )}
    </div>
  );
}
