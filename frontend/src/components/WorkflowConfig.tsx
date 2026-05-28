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
      <h3 style={{ marginTop: 0 }}>Workflow</h3>
      <label style={{ marginRight: 12 }}>
        Type:
        <select value={workflowType} onChange={(e) => onChangeType(e.target.value)} style={{ ...selectStyle, marginLeft: 8 }}>
          <option value="sequential">Sequential</option>
          <option value="hierarchical">Hierarchical</option>
          <option value="roundtable">Roundtable</option>
        </select>
      </label>
      {workflowType === 'roundtable' && (
        <label>
          Max rounds:
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
