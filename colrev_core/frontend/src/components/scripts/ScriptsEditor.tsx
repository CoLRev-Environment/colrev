import Script from "../../models/script";
import ScriptEditor from "./ScriptEditor";

const ScriptsEditor: React.FC<{ scripts: Script[]; scriptsChanged: any }> = ({
  scripts,
  scriptsChanged,
}) => {
  const scriptChangedHandler = () => {
    const newScripts = [...scripts];
    scriptsChanged(newScripts);
  };

  const deleteScriptHandler = (script: Script) => {
    const newScripts = scripts.filter((s) => s !== script);
    scriptsChanged(newScripts);
  };

  const addScriptHandler = () => {
    console.log("add");
    const newScripts = [...scripts, new Script()];
    scriptsChanged(newScripts);
  };

  return (
    <div>
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
            <ScriptEditor
              script={script}
              scriptChanged={scriptChangedHandler}
            />
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
  );
};

export default ScriptsEditor;
