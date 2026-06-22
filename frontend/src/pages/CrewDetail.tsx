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
  const [availableTools, setAvailableTools] = useState<Array<{ name: string; description: string }>>([]);
  const [skills, setSkills] = useState<Array<{ name: string; label: string; description: string; tools: string[] }>>([]);

  const load = () => {
    if (!id) return;
    api.getCrew(Number(id)).then(setCrew).catch(console.error);
  };

  useEffect(() => {
    api.listTools().then(setAvailableTools).catch(() => {});
    api.listSkills().then(setSkills).catch(() => {});
  }, []);

  useEffect(load, [id]);

  if (!crew) return <p>加载中...</p>;

  const handleAddAgent = async (data: { name: string; role: string; system_prompt: string; order: number }) => {
    await api.createAgent(crew.id, data);
    load();
  };

  const currentTools = (crew?.tools as string[]) || [];

  const toggleTool = (toolName: string) => {
    if (!crew) return;
    const updated = currentTools.includes(toolName)
      ? currentTools.filter((t) => t !== toolName)
      : [...currentTools, toolName];
    setCrew({ ...crew, tools: updated });
    api.updateCrew(crew.id, { tools: updated }).catch(console.error);
  };

  const toggleSkill = (skill: { name: string; label: string; description: string; tools: string[] }) => {
    if (!crew) return;
    const allSelected = skill.tools.every((t) => currentTools.includes(t));
    const updated = allSelected
      ? currentTools.filter((t) => !skill.tools.includes(t))
      : [...new Set([...currentTools, ...skill.tools])];
    setCrew({ ...crew, tools: updated });
    api.updateCrew(crew.id, { tools: updated }).catch(console.error);
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

      {skills.length > 0 && (
        <div style={{ padding: '12px 16px', background: '#f0f4f8', borderRadius: 8, marginBottom: 12 }}>
          <p style={{ fontSize: 14, color: '#555', margin: '0 0 8px 0', fontWeight: 500 }}>技能包</p>
          <div style={{ display: 'flex', gap: 8 }}>
            {skills.map((skill) => {
              const allSelected = skill.tools.every((t) => currentTools.includes(t));
              return (
                <button
                  key={skill.name}
                  type="button"
                  title={skill.description}
                  onClick={() => toggleSkill(skill)}
                  style={{
                    padding: '8px 14px',
                    borderRadius: 6,
                    border: allSelected ? '2px solid #2980b9' : '1px solid #ddd',
                    background: allSelected ? '#eaf2f8' : '#fff',
                    cursor: 'pointer',
                    fontSize: 13,
                    textAlign: 'left',
                  }}
                >
                  <div style={{ fontWeight: 600, color: '#2c3e50', marginBottom: 2 }}>{skill.label}</div>
                  <div style={{ fontSize: 11, color: '#888' }}>{skill.tools.join(', ')}</div>
                </button>
              );
            })}
          </div>
        </div>
      )}
      {availableTools.length > 0 && (
        <div style={{ padding: '12px 16px', background: '#f8f9fa', borderRadius: 8, marginBottom: 16 }}>
          <p style={{ fontSize: 14, color: '#555', margin: '0 0 8px 0', fontWeight: 500 }}>团队工具</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {availableTools.map((tool) => {
              const selected = currentTools.includes(tool.name);
              return (
                <button
                  key={tool.name}
                  type="button"
                  title={tool.description}
                  onClick={() => toggleTool(tool.name)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: 4,
                    border: selected ? '1px solid #2980b9' : '1px solid #ddd',
                    background: selected ? '#eaf2f8' : '#fff',
                    color: selected ? '#2980b9' : '#888',
                    cursor: 'pointer',
                    fontSize: 13,
                  }}
                >
                  {selected ? '✓ ' : ''}{tool.name}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <h3>智能体（{crew.agents.length}）</h3>
      {crew.agents.map((agent) => (
        <AgentCard key={agent.id} agent={agent} onDelete={handleDeleteAgent} onUpdate={load} />
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
