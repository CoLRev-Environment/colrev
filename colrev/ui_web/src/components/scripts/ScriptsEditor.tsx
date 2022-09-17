import { useState } from "react";
import Script from "../../models/script";
import DeleteIcon from "../common/icons/DeleteIcon";
import EditIcon from "../common/icons/EditIcon";
import ScriptEditWizard from "./ScriptEditWizard";

const ScriptsEditor: React.FC<{
  packageType: string;
  scripts: Script[];
  scriptsChanged: any;
  isSingleScript?: boolean;
}> = ({ packageType, scripts, scriptsChanged, isSingleScript = false }) => {
  const [showScriptEditor, setShowScriptEditor] = useState(false);
  const [isEditScript, setIsEditScript] = useState(false);
  const [script, setScript] = useState<Script>(new Script());
  const [scriptCopy, setScriptCopy] = useState<Script>(new Script());

  // const scriptChangedHandler = () => {
  //   const newScripts = [...scripts];
  //   scriptsChanged(newScripts);
  // };

  const deleteScriptHandler = (s: Script) => {
    const newScripts = scripts.filter((scr) => scr !== s);
    scriptsChanged(newScripts);
  };

  const addScriptHandler = () => {
    setIsEditScript(false);
    setScript(new Script());
    setShowScriptEditor(true);
  };

  const editScriptHandler = (s: Script) => {
    setIsEditScript(true);
    setScript(s);
    setScriptCopy(s.clone());
    setShowScriptEditor(true);
  };

  const cancelHanlder = () => {
    setShowScriptEditor(false);
  };

  const okHander = (newScript: Script) => {
    setShowScriptEditor(false);

    let newScripts: Script[] = [];

    if (!isEditScript) {
      newScripts = [...scripts, newScript];
    } else {
      for (const s of scripts) {
        if (s !== script) {
          newScripts.push(s);
        } else {
          newScripts.push(newScript);
        }
      }
    }

    scriptsChanged(newScripts);
  };

  return (
    <div>
      <ul className="list-group">
        {scripts.map((script, index) => (
          <li
            className="list-group-item d-flex justify-content-between align-items-center"
            key={index.toString()}
          >
            <span>{script.endpoint}</span>
            <div>
              <div
                className="btn btn-primary btn-sm"
                style={{ marginRight: 5 }}
                onClick={() => editScriptHandler(script)}
              >
                <EditIcon />
              </div>
              {!isSingleScript && (
                <div
                  className="btn btn-danger btn-sm"
                  onClick={() => deleteScriptHandler(script)}
                >
                  <DeleteIcon />
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>
      {!isSingleScript && (
        <div className="mb-3 mt-1">
          <button
            className="btn btn-primary"
            type="button"
            onClick={addScriptHandler}
          >
            Add Script
          </button>
        </div>
      )}
      {showScriptEditor && (
        <ScriptEditWizard
          packageType={packageType}
          isEditScript={isEditScript}
          script={scriptCopy}
          onOk={okHander}
          onCancel={cancelHanlder}
        />
      )}
    </div>
  );
};

export default ScriptsEditor;
