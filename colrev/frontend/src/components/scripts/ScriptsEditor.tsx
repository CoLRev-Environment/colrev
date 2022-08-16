import Script from "../../models/script";
import ScriptWithLanguageScope from "../../models/scriptWithLanguageScope";
import ScripWithTresholds from "../../models/scriptWithTresholds";
import Expander from "../common/Expander";
import ExpanderItem from "../common/ExpanderItem";
import ScriptItem from "./ScriptItems/ScriptItem";
import ScriptItemWithLanguageScope from "./ScriptItems/ScriptItemWithLanguageScope";
import ScriptItemWithTresholds from "./ScriptItems/ScriptItemWithTresholds";

const ScriptsEditor: React.FC<{
  id: string;
  scripts: Script[];
  scriptsChanged: any;
  isSingleScript?: boolean;
}> = ({ id, scripts, scriptsChanged, isSingleScript = false }) => {
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

  const addScriptWithTresholdsHandler = () => {
    const newScript = new ScripWithTresholds();
    newScript.endpoint = "new";
    const newScripts = [...scripts, newScript];
    scriptsChanged(newScripts);
  };

  const addScriptWithLanguageScopeHandler = () => {
    const newScript = new ScriptWithLanguageScope();
    newScript.endpoint = "new";
    const newScripts = [...scripts, newScript];
    scriptsChanged(newScripts);
  };

  const renderScriptItem = (script: Script, scriptChangedHandler: any) => {
    if (script instanceof ScripWithTresholds) {
      return (
        <ScriptItemWithTresholds
          script={script}
          scriptChanged={scriptChangedHandler}
        />
      );
    }

    if (script instanceof ScriptWithLanguageScope) {
      return (
        <ScriptItemWithLanguageScope
          script={script}
          scriptChanged={scriptChangedHandler}
        />
      );
    }

    return <ScriptItem script={script} scriptChanged={scriptChangedHandler} />;
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
            hasDelete={!isSingleScript}
            onDelete={() => deleteScriptHandler(script)}
          >
            {renderScriptItem(script, scriptChangedHandler)}
          </ExpanderItem>
        ))}
      </Expander>
      {!isSingleScript && (
        <div className="mb-3 mt-1">
          <button
            className="btn btn-primary dropdown-toggle"
            type="button"
            data-bs-toggle="dropdown"
            aria-expanded="false"
          >
            Add
          </button>
          <ul className="dropdown-menu">
            <li>
              <button className="dropdown-item" onClick={addScriptHandler}>
                Simple Script
              </button>
            </li>
            <li>
              <button
                className="dropdown-item"
                onClick={addScriptWithTresholdsHandler}
              >
                Script with Tresholds
              </button>
            </li>
            <li>
              <button
                className="dropdown-item"
                onClick={addScriptWithLanguageScopeHandler}
              >
                Script with Language Scope
              </button>
            </li>
          </ul>
        </div>
      )}
    </div>
  );
};

export default ScriptsEditor;
