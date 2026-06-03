interface Props {
  workflowType: string;
  maxRounds: number;
  onChangeType: (type: string) => void;
  onChangeMaxRounds: (rounds: number) => void;
}

const selectStyle: React.CSSProperties = {
  padding: '8px 12px',
  border: '1px solid #ddd',
  borderRadius: 4,
  fontSize: 14,
  marginRight: 12,
};

const containerStyle: React.CSSProperties = {
  padding: 16,
  background: '#f8f9fa',
  borderRadius: 8,
  marginBottom: 16,
};

export default function WorkflowConfig({ workflowType, maxRounds, onChangeType, onChangeMaxRounds }: Props) {
  return (
    <div style={containerStyle}>
      <h3 style={{ marginTop: 0 }}>工作流</h3>
      <label style={{ marginRight: 12 }}>
        类型：
        <select value={workflowType} onChange={(e) => onChangeType(e.target.value)} style={{ ...selectStyle, marginLeft: 8 }}>
          <option value="sequential">顺序执行</option>
          <option value="hierarchical">层级协作</option>
          <option value="roundtable">圆桌讨论</option>
        </select>
      </label>
      {workflowType === 'roundtable' && (
        <label>
          最大轮次：
          <input
            type="number"
            min={1}
            max={5}
            value={maxRounds}
            onChange={(e) => onChangeMaxRounds(Number(e.target.value))}
            style={{ ...selectStyle, width: 60, marginLeft: 8 }}
          />
        </label>
      )}
    </div>
  );
}
