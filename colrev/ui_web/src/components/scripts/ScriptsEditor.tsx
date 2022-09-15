import { useState } from "react";
import Script from "../../models/script";
import DeleteIcon from "../common/icons/DeleteIcon";
import EditIcon from "../common/icons/EditIcon";
import EditScript from "./EditScript";

const ScriptsEditor: React.FC<{
  packageType: string;
  scripts: Script[];
  scriptsChanged: any;
  isSingleScript?: boolean;
}> = ({ packageType, scripts, scriptsChanged, isSingleScript = false }) => {
  const [isShowEditScript, setIsShowEditScript] = useState(false);
  const [editScript, setEditScript] = useState<Script | null>(null);

  // const scriptChangedHandler = () => {
  //   const newScripts = [...scripts];
  //   scriptsChanged(newScripts);
  // };

  const deleteScriptHandler = (script: Script) => {
    const newScripts = scripts.filter((s) => s !== script);
    scriptsChanged(newScripts);
  };

  const addScriptHandler = () => {
    setEditScript(null);
    setIsShowEditScript(true);

    // const newScript = new Script();
    // newScript.endpoint = "new";
    // const newScripts = [...scripts, newScript];
    // scriptsChanged(newScripts);
  };

  const editScriptHandler = (script: Script) => {
    // TODO remove this - this is just to init selected script
    script.endpoint = "search_pdfs_dir";

    setEditScript(script);
    setIsShowEditScript(true);

    // const newScript = new Script();
    // newScript.endpoint = "new";
    // const newScripts = [...scripts, newScript];
    // scriptsChanged(newScripts);
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
      {isShowEditScript && (
        <EditScript
          packageType={packageType}
          editScript={editScript}
          onClose={() => setIsShowEditScript(false)}
        />
      )}
    </div>
  );
};

export default ScriptsEditor;
