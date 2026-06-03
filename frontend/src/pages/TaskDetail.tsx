import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, type Task } from '../api/client';
import MessageList from '../components/MessageList';

const btnStyle: React.CSSProperties = {
  background: '#95a5a6',
  color: '#fff',
  border: 'none',
  borderRadius: 4,
  padding: '10px 24px',
  cursor: 'pointer',
  fontSize: 15,
  marginBottom: 16,
};

export default function TaskDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [task, setTask] = useState<Task | null>(null);

  useEffect(() => {
    if (!id) return;
    api.getTask(Number(id)).then(setTask).catch(console.error);
  }, [id]);

  if (!task) return <p>加载中...</p>;

  const msgs = (task.messages as Array<{ agent_name: string; agent_role: string; content: string }>) || [];

  return (
    <div>
      <button onClick={() => navigate(`/crews/${task.crew_id}`)} style={btnStyle}>
        &larr; 返回团队
      </button>

      <h2>任务 #{task.id}</h2>
      <div style={{ padding: 16, background: '#f8f9fa', borderRadius: 8, marginBottom: 24 }}>
        <strong>输入：</strong>
        <p>{task.input}</p>
        <span style={{ color: '#888', fontSize: 13 }}>
          状态：{task.status} | {new Date(task.created_at).toLocaleString()}
        </span>
      </div>

      {task.result && (
        <div style={{ padding: 16, background: '#e8f8f5', borderRadius: 8, marginBottom: 24 }}>
          <strong>最终结果：</strong>
          <p style={{ whiteSpace: 'pre-wrap' }}>{task.result}</p>
        </div>
      )}

      <h3>消息记录</h3>
      <MessageList messages={msgs} running={false} />
    </div>
  );
}
