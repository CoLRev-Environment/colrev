import { useEffect, useState } from "react";
import Script from "../../models/script";
import ModalWindow from "../common/ModalWindow";
import ScriptParametersEditor from "./ScriptParametersEditor";

//API: getScripts(script_type)
const scriptEndpoints = [
  {
    endpoint: "crossref_prep",
    description: "The script retrieves metadata from Crossref ...",
  },
  {
    endpoint: "search_pdfs_dir",
    description: "The script hadles searching pdfs ...",
  },
  {
    endpoint: "drop_fields",
    description: "The script drops fields ...",
  },
];

const EditScript: React.FC<{
  scriptType: string;
  editScript: Script | null;
  onClose: any;
}> = ({ scriptType, editScript, onClose }) => {
  const [isShowNext, setIsShowNext] = useState(false);
  const [isNextEnabled, setIsNextEnabled] = useState(false);
  const [isShowOk, setIsShowOk] = useState(false);
  const [isOkEnabled, setIsOkEnabled] = useState(false);
  const [stepIndex, setStepIndex] = useState<number>(0);
  const [selectedScriptEndpoint, setSelectedScriptEndpoint] = useState<any>();

  useEffect(() => {
    if (editScript) {
      const selectedEndpoint = { endpoint: editScript.endpoint };
      setSelectedScriptEndpoint(selectedEndpoint);
      setIsNextEnabled(true);
    }
    if (stepIndex === 0) {
      setIsShowNext(true);
    }
  }, [editScript, stepIndex]);

  const nextHandler = () => {
    setStepIndex(1);
    setIsShowNext(false);
    setIsShowOk(true);
    setIsOkEnabled(true);
  };

  const okHandler = () => {};

  return (
    <ModalWindow
      title={editScript ? "Edit Script" : "Add Script"}
      isShowNext={isShowNext}
      isNextEnabled={isNextEnabled}
      isShowOk={isShowOk}
      isOkEnabled={isOkEnabled}
      onNext={nextHandler}
      onOk={okHandler}
      onClose={onClose}
    >
      {stepIndex === 0 && (
        <div>
          <p>Select Script</p>
          <div className="list-group">
            {scriptEndpoints.map((scriptEndpoint: any, index: number) => (
              <button
                type="button"
                className={
                  "list-group-item list-group-item-action" +
                  (selectedScriptEndpoint?.endpoint === scriptEndpoint.endpoint
                    ? " active"
                    : "")
                }
                key={index.toString()}
                onClick={() => {
                  setSelectedScriptEndpoint(scriptEndpoint);
                  setIsNextEnabled(true);
                }}
              >
                <div>
                  <div>{scriptEndpoint.endpoint}</div>
                  <div>
                    <em>{scriptEndpoint.description}</em>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
      {stepIndex === 1 && (
        <ScriptParametersEditor
          scriptType={scriptType}
          scriptEndpoint={selectedScriptEndpoint?.endpoint}
        />
      )}
    </ModalWindow>
  );
};

export default EditScript;
