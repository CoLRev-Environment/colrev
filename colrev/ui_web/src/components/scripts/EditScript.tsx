import { useEffect, useState } from "react";
import Script from "../../models/script";
import dataService from "../../services/dataService";
import ModalWindow from "../common/ModalWindow";
import ScriptParametersEditor from "./ScriptParametersEditor";

const EditScript: React.FC<{
  packageType: string;
  editScript: Script | null;
  onClose: any;
}> = ({ packageType, editScript, onClose }) => {
  const [scripts, setScripts] = useState<Script[]>([]);
  const [isShowNext, setIsShowNext] = useState(false);
  const [isNextEnabled, setIsNextEnabled] = useState(false);
  const [isShowOk, setIsShowOk] = useState(false);
  const [isOkEnabled, setIsOkEnabled] = useState(false);
  const [stepIndex, setStepIndex] = useState<number>(0);
  const [selectedScriptEndpoint, setSelectedScriptEndpoint] = useState<any>();

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    const scripts = await dataService.getScripts(packageType);
    setScripts(scripts);
  };

  useEffect(() => {
    if (editScript) {
      const selectedEndpoint = { endpoint: editScript.endpoint };
      setSelectedScriptEndpoint(selectedEndpoint);
      setIsNextEnabled(true);
    }
    if (stepIndex === 0) {
      setIsShowNext(true);
    }
  }, [editScript, stepIndex, packageType]);

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
          <div
            className="list-group"
            style={{
              maxHeight: "300px",
            }}
          >
            <div style={{ overflowY: "auto" }}>
              {scripts.map((script: any, index: number) => (
                <button
                  type="button"
                  className={
                    "list-group-item list-group-item-action" +
                    (selectedScriptEndpoint?.endpoint === script.endpoint
                      ? " active"
                      : "")
                  }
                  key={index.toString()}
                  onClick={() => {
                    setSelectedScriptEndpoint(script);
                    setIsNextEnabled(true);
                  }}
                >
                  <div>
                    <div>
                      {script.name} - {script.description}
                    </div>
                    <div style={{ fontSize: "0.8em" }}>{script.endpoint}</div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
      {stepIndex === 1 && (
        <ScriptParametersEditor
          scriptType={packageType}
          scriptEndpoint={selectedScriptEndpoint?.endpoint}
        />
      )}
    </ModalWindow>
  );
};

export default EditScript;
