import { useEffect, useState } from "react";
import Script from "../../models/script";
import dataService from "../../services/dataService";
import ModalWindow from "../common/ModalWindow";
import ScriptTitle from "./ScriptTitle";
import ScriptParametersEditor from "./ScriptParametersEditor";
import ScriptDefinition from "../../models/scriptDefinition";

const ScriptEditWizard: React.FC<{
  packageType: string;
  isEditScript: boolean;
  script: Script;
  onOk: any;
  onCancel: any;
}> = ({ packageType, isEditScript, script, onOk, onCancel }) => {
  const [scriptDefinitions, setScriptDefinitions] = useState<
    ScriptDefinition[]
  >([]);
  const [newScript, setNewScript] = useState<Script>(script);
  const [showOk, setShowOk] = useState(false);
  const [isOkEnabled, setIsOkEnabled] = useState(false);
  const [stepIndex, setStepIndex] = useState<number>(0);
  const [selectedScriptDefinition, setSelectedScriptDefinition] =
    useState<ScriptDefinition>(new ScriptDefinition());

  useEffect(() => {
    const init = async () => {
      const scriptDefs = await dataService.getScriptDefinitions(packageType);

      setStepIndex(0);

      if (!isEditScript) {
        setScriptDefinitions(scriptDefs);
      } else {
        let scriptDefinition = scriptDefs.find(
          (sd) => sd.endpoint === script.endpoint
        );

        if (!scriptDefinition) {
          scriptDefinition = scriptDefs[0];
        }

        setSelectedScriptDefinition(scriptDefinition);
        next();
      }
    };

    init();
  }, [packageType, isEditScript, script]);

  const next = () => {
    setStepIndex(1);
    setShowOk(true);
    setIsOkEnabled(true);
  };

  const cancelHandler = () => {
    onCancel();
  };

  const okHandler = () => {
    onOk(newScript);
  };

  return (
    <ModalWindow
      title={isEditScript ? "Edit Script" : "Add Script"}
      isShowOk={showOk}
      isOkEnabled={isOkEnabled}
      onOk={okHandler}
      onCancel={cancelHandler}
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
              {scriptDefinitions.map(
                (scriptDefinition: ScriptDefinition, index: number) => (
                  <button
                    type="button"
                    className={
                      "list-group-item list-group-item-action" +
                      (selectedScriptDefinition?.endpoint ===
                      scriptDefinition.endpoint
                        ? " active"
                        : "")
                    }
                    key={index.toString()}
                    onClick={() => {
                      setSelectedScriptDefinition(scriptDefinition);
                      newScript.endpoint = scriptDefinition.endpoint;
                      next();
                    }}
                  >
                    <ScriptTitle scriptDefinition={scriptDefinition} />
                  </button>
                )
              )}
            </div>
          </div>
        </div>
      )}
      {stepIndex === 1 && (
        <ScriptParametersEditor
          packageType={packageType}
          scriptDefinition={selectedScriptDefinition}
          script={newScript}
          scriptChanged={(newScr: Script) => setNewScript(newScr)}
        />
      )}
    </ModalWindow>
  );
};

export default ScriptEditWizard;
