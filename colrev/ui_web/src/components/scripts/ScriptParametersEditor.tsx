import { useEffect, useState } from "react";
import Script from "../../models/script";
import ScriptDefinition from "../../models/scriptDefinition";
import ScriptParameterDefinition from "../../models/scriptParameterDefinition";
import ScriptParameterType from "../../models/scriptParameterType";
import dataService from "../../services/dataService";
import FiedlsEditor from "../fields/FieldsEditor";
import ScriptTitle from "./ScriptTitle";

const ScriptParametersEditor: React.FC<{
  packageType: string;
  scriptDefinition: ScriptDefinition;
  script: Script;
  scriptChanged: any;
}> = ({ packageType, scriptDefinition, script, scriptChanged }) => {
  const [hasParameters, setHasParameters] = useState<boolean>(false);
  const [parameterDefinitions, setParameterDefinitions] = useState<
    ScriptParameterDefinition[]
  >([]);

  useEffect(() => {
    const init = async () => {
      const paramDefs = await dataService.getScriptParameterDefinitions(
        packageType,
        scriptDefinition.name
      );

      if (paramDefs.length === 0) {
        setHasParameters(false);
        return;
      }

      setHasParameters(true);
      setParameterDefinitions(paramDefs);

      for (const pd of paramDefs) {
        if (!script.parameters.has(pd.name)) {
          let paramValue = undefined;

          if (pd.type === ScriptParameterType.StringList) {
            paramValue = [];
          } else if (pd.type === ScriptParameterType.Boolean) {
            paramValue = false;
          }

          script.parameters.set(pd.name, paramValue);
        }
      }
    };

    init();
  }, [packageType, scriptDefinition, script]);

  const getParameterValue = (paramDef: ScriptParameterDefinition) => {
    let paramValue = script.parameters.get(paramDef.name);
    return paramValue;
  };

  const setParameterValue = (
    paramDef: ScriptParameterDefinition,
    paramValue: any
  ) => {
    const newScript = { ...script };
    newScript.parameters.set(paramDef.name, paramValue);
    scriptChanged(newScript);
  };

  return (
    <div>
      <ScriptTitle scriptDefinition={scriptDefinition} />
      <div style={{ marginTop: "10px" }}>
        {!hasParameters && <p>Script has no paramaters</p>}
        {hasParameters && (
          <>
            <p>Set Script Parameters</p>
            {parameterDefinitions.map((parameterDefinition, index) => (
              <div key={index.toString()} className="mb-3">
                {parameterDefinition.type === ScriptParameterType.Boolean && (
                  <div className="form-check form-switch">
                    <input
                      className="form-check-input"
                      type="checkbox"
                      checked={getParameterValue(parameterDefinition)}
                      onChange={() =>
                        setParameterValue(
                          parameterDefinition,
                          !getParameterValue(parameterDefinition)
                        )
                      }
                    />
                    <label className="form-check-label">
                      {parameterDefinition.name}
                    </label>
                  </div>
                )}
                {parameterDefinition.type === ScriptParameterType.Float && (
                  <div>
                    <label>{parameterDefinition.name}</label>
                    <input
                      className="form-control"
                      type="number"
                      step={0.1}
                      min={parameterDefinition.min}
                      max={parameterDefinition.max}
                      value={getParameterValue(parameterDefinition) ?? ""}
                      onChange={(event) =>
                        setParameterValue(
                          parameterDefinition,
                          Number(event.target.value)
                        )
                      }
                    />
                  </div>
                )}
                {parameterDefinition.type === ScriptParameterType.Int && (
                  <div>
                    <label>{parameterDefinition.name}</label>
                    <input
                      className="form-control"
                      type="number"
                      step="any"
                      min={parameterDefinition.min}
                      max={parameterDefinition.max}
                      value={getParameterValue(parameterDefinition) ?? ""}
                      onChange={(event) =>
                        setParameterValue(
                          parameterDefinition,
                          Number(event.target.value)
                        )
                      }
                    />
                  </div>
                )}
                {parameterDefinition.type === ScriptParameterType.String && (
                  <div>
                    <label>{parameterDefinition.name}</label>
                    <input
                      className="form-control"
                      type="text"
                      value={getParameterValue(parameterDefinition) ?? ""}
                      onChange={(event) =>
                        setParameterValue(
                          parameterDefinition,
                          event.target.value
                        )
                      }
                    />
                  </div>
                )}
                {parameterDefinition.type ===
                  ScriptParameterType.StringList && (
                  <div>
                    <FiedlsEditor
                      title={parameterDefinition.name}
                      fields={getParameterValue(parameterDefinition)}
                      fieldsChanged={(newValues: string[]) =>
                        setParameterValue(parameterDefinition, newValues)
                      }
                    />
                  </div>
                )}
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
};

export default ScriptParametersEditor;
