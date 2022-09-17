import ScriptDefinition from "../../models/scriptDefinition";

const ScriptTitle: React.FC<{ scriptDefinition: ScriptDefinition }> = ({
  scriptDefinition: script,
}) => {
  return (
    <div>
      <div>
        {script.name} - {script.description}
      </div>
      <div style={{ fontSize: "0.8em" }}>{script.endpoint}</div>
    </div>
  );
};

export default ScriptTitle;
