import Script from "../../models/script";

const ScriptsEdit: React.FC<{ scripts: Script[]; scriptsChanged: any }> = ({
  scripts,
  scriptsChanged,
}) => {
  const endpointChangeHandler = (script: Script, event: any) => {
    const newEndpoint = event.target.value;
    script.endpoint = newEndpoint;
    const newScripts = [...scripts];
    scriptsChanged(newScripts);
  };

  const deleteScriptHandler = (script: Script) => {
    const newScripts = scripts.filter((s) => s !== script);
    scriptsChanged(newScripts);
  };

  const addScriptHandler = () => {
    const newScripts = [...scripts, new Script()];
    scriptsChanged(newScripts);
  };

  return (
    <div>
      <div className="card">
        <div className="card-header">Scripts</div>
        <div className="card-body">
          {scripts.map((script, index) => (
            <div className="card mb-2" key={index.toString()}>
              <div className="card-header d-flex justify-content-between align-items-center">
                <span>Script {index + 1}</span>
                <button
                  className="btn btn-danger"
                  type="button"
                  onClick={() => deleteScriptHandler(script)}
                >
                  X
                </button>
              </div>
              <div className="card-body">
                <div className="form-group">
                  <label htmlFor="endpoint">Endpoint</label>
                  <input
                    className="form-control"
                    type="text"
                    id="endpoint"
                    value={script.endpoint ?? ""}
                    onChange={(event) => endpointChangeHandler(script, event)}
                  />
                </div>
              </div>
            </div>
          ))}
          <button
            className="btn btn-primary"
            type="button"
            onClick={addScriptHandler}
          >
            Add
          </button>
        </div>
      </div>
    </div>
  );
};

export default ScriptsEdit;
