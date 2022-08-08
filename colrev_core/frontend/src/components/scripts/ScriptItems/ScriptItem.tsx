import Script from "../../../models/script";

const ScriptItem: React.FC<{ script: Script; scriptChanged: any }> = ({
  script,
  scriptChanged,
}) => {
  const endpointChangedHandler = (event: any) => {
    script.endpoint = event.target.value;
    scriptChanged();
  };

  return (
    <div>
      <label htmlFor="endpoint">Endpoint</label>
      <input
        className="form-control"
        type="text"
        id="endpoint"
        value={script.endpoint ?? ""}
        onChange={endpointChangedHandler}
      />
    </div>
  );
};

export default ScriptItem;
