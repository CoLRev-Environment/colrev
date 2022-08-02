import Script from "../../models/script";
import Expander from "../common/Expander";
import ExpanderItem from "../common/ExpanderItem";
import ScriptEditor from "./ScriptEditor";

const ScriptsEditor: React.FC<{
  id: string;
  scripts: Script[];
  scriptsChanged: any;
  isEdit?: boolean;
}> = ({ id, scripts, scriptsChanged, isEdit = true }) => {
  const scriptChangedHandler = () => {
    const newScripts = [...scripts];
    scriptsChanged(newScripts);
  };

  const deleteScriptHandler = (script: Script) => {
    const newScripts = scripts.filter((s) => s !== script);
    scriptsChanged(newScripts);
  };

  const addScriptHandler = () => {
    const newScript = new Script();
    newScript.endpoint = "new";
    const newScripts = [...scripts, newScript];
    scriptsChanged(newScripts);
  };

  return (
    <div>
      <Expander id={`${id}Expander`}>
        {scripts.map((script, index) => (
          <ExpanderItem
            key={index.toString()}
            name={script.endpoint}
            id={`${id}${index + 1}`}
            parentContainerId={`${id}Expander`}
            show={false}
            hasDelete={isEdit}
            onDelete={() => deleteScriptHandler(script)}
          >
            <ScriptEditor
              script={script}
              scriptChanged={scriptChangedHandler}
            />
          </ExpanderItem>
        ))}
      </Expander>
      {isEdit && (
        <button
          className="btn btn-primary mt-1"
          type="button"
          onClick={addScriptHandler}
        >
          Add
        </button>
      )}
    </div>
  );
};

export default ScriptsEditor;
