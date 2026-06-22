import { useState } from 'react';

export interface MessageItem {
  type?: 'text' | 'tool_call' | 'tool_call_result';
  agent_name: string;
  agent_role?: string;
  content?: string;
  tool_calls?: Array<{ name: string; arguments: Record<string, unknown>; result: string }>;
  tool_name?: string;
  arguments?: Record<string, unknown>;
  result?: string;
}

interface Props {
  messages: MessageItem[];
  running: boolean;
}

const msgStyle: React.CSSProperties = {
  border: '1px solid #e0e0e0',
  borderRadius: 8,
  padding: 16,
  marginBottom: 12,
};

const toolStyle: React.CSSProperties = {
  border: '1px solid #2980b9',
  borderRadius: 6,
  padding: 10,
  marginBottom: 8,
  background: '#eaf2f8',
  fontSize: 13,
};

const toolResultStyle: React.CSSProperties = {
  border: '1px solid #bdc3c7',
  borderRadius: 6,
  padding: 10,
  marginBottom: 8,
  background: '#f8f9fa',
  fontSize: 13,
  maxHeight: 200,
  overflow: 'auto',
};

export default function MessageList({ messages, running }: Props) {
  return (
    <div>
      {messages.map((msg, i) => {
        const msgType = msg.type || 'text';

        if (msgType === 'tool_call') {
          return <ToolCallCard key={i} msg={msg} />;
        }
        if (msgType === 'tool_call_result') {
          return <ToolResultCard key={i} msg={msg} />;
        }

        // text message (default)
        return (
          <div key={i} style={msgStyle}>
            <div style={{ marginBottom: 8 }}>
              <strong>{msg.agent_name}</strong>
              {msg.agent_role && (
                <span style={{ color: '#888', marginLeft: 8, fontSize: 14 }}>{msg.agent_role}</span>
              )}
            </div>
            {msg.content && (
              <p style={{ whiteSpace: 'pre-wrap', margin: 0, lineHeight: 1.6 }}>{msg.content}</p>
            )}
            {msg.tool_calls && msg.tool_calls.length > 0 && (
              <div style={{ marginTop: 10 }}>
                {msg.tool_calls.map((tc, j) => (
                  <ToolCallWithResult key={j} tc={tc} />
                ))}
              </div>
            )}
          </div>
        );
      })}
      {running && <p style={{ color: '#888' }}>运行中...</p>}
    </div>
  );
}

function ToolCallCard({ msg }: { msg: MessageItem }) {
  const argsStr = msg.arguments
    ? Object.entries(msg.arguments)
        .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
        .join(', ')
    : '';

  return (
    <div style={toolStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 16 }}>&#128295;</span>
        <strong style={{ color: '#2980b9' }}>{msg.agent_name}</strong>
        <span style={{ color: '#555' }}>
          调用工具 <code>{msg.tool_name}</code>
          {argsStr && (
            <span style={{ color: '#888', fontSize: 12 }}>({argsStr.substring(0, 80)}{argsStr.length > 80 ? '...' : ''})</span>
          )}
        </span>
      </div>
    </div>
  );
}

function ToolResultCard({ msg }: { msg: MessageItem }) {
  const [expanded, setExpanded] = useState(false);
  const result = msg.result || '';
  const long = result.length > 500;

  return (
    <div style={toolResultStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        <span style={{ fontSize: 14 }}>&#128194;</span>
        <strong style={{ color: '#555' }}>{msg.agent_name}</strong>
        <span style={{ color: '#888', fontSize: 12 }}>
          <code>{msg.tool_name}</code> 执行结果
        </span>
        {long && (
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              marginLeft: 'auto',
              background: 'none',
              border: 'none',
              color: '#2980b9',
              cursor: 'pointer',
              fontSize: 12,
            }}
          >
            {expanded ? '收起' : '展开全部'}
          </button>
        )}
      </div>
      <pre style={{
        whiteSpace: 'pre-wrap',
        margin: 0,
        fontSize: 12,
        color: '#333',
        maxHeight: expanded ? 'none' : long ? 120 : undefined,
        overflow: expanded ? 'visible' : long ? 'hidden' : undefined,
      }}>
        {long && !expanded ? result.substring(0, 500) + '\n...(已截断，点击展开)' : result}
      </pre>
    </div>
  );
}

function ToolCallWithResult({ tc }: { tc: { name: string; arguments: Record<string, unknown>; result: string } }) {
  const [expanded, setExpanded] = useState(false);
  const argsStr = Object.entries(tc.arguments || {})
    .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
    .join(', ');
  const long = tc.result.length > 500;

  return (
    <div style={{ ...toolStyle, background: '#f0f4f8', marginBottom: 4 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontSize: 14 }}>&#128295;</span>
        <code style={{ color: '#2980b9' }}>{tc.name}</code>
        {argsStr && <span style={{ color: '#888', fontSize: 12 }}>({argsStr.substring(0, 60)}{argsStr.length > 60 ? '...' : ''})</span>}
        {long && (
          <button
            onClick={() => setExpanded(!expanded)}
            style={{ marginLeft: 'auto', background: 'none', border: 'none', color: '#2980b9', cursor: 'pointer', fontSize: 12 }}
          >
            {expanded ? '收起' : '展开结果'}
          </button>
        )}
      </div>
      <pre style={{
        whiteSpace: 'pre-wrap',
        margin: '6px 0 0 0',
        fontSize: 12,
        color: '#555',
        maxHeight: expanded ? 'none' : long ? 80 : undefined,
        overflow: expanded ? 'visible' : long ? 'hidden' : undefined,
      }}>
        {long && !expanded ? tc.result.substring(0, 500) + '\n...(已截断)' : tc.result}
      </pre>
    </div>
  );
}
