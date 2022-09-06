import { useEffect, useState } from "react";

//API: getScriptsParametersOptions(script_type, endpoint_name)
//Map<string, any>
const parameters = {
  retrieval_similarity: { type: "float", min: 0, max: 1 },
  rank: { type: "int", min: 0, max: 100 },
  label: { type: "text" },
  use_filers: { type: "boolean" },
};

const ScriptParametersEditor: React.FC<{
  scriptType: string;
  scriptEndpoint: string;
}> = ({ scriptType, scriptEndpoint }) => {
  const [parametersMap, setParametersMap] = useState<Map<string, any>>(
    new Map()
  );

  useEffect(() => {
    if (scriptEndpoint === "search_pdfs_dir") {
      setHasParameters(false);
      return;
    }

    setHasParameters(true);
    const paramsMap = new Map(Object.entries(parameters));
    setParametersMap(paramsMap);
  }, [scriptEndpoint]);

  const [hasParameters, setHasParameters] = useState<boolean>(false);
  return (
    <div>
      <p>
        Script <b>{scriptEndpoint}</b>
      </p>
      {!hasParameters && <p>Script has no paramaters.</p>}
      {hasParameters && (
        <>
          <p>Set Script Parameters</p>
          {Array.from(parametersMap).map(([key, value], index) => (
            <div
              key={index.toString()}
              className={
                "mb-3" +
                (value.type === "boolean" ? " form-check form-switch" : "")
              }
            >
              {value.type !== "boolean" && (
                <>
                  <label style={{ textTransform: "capitalize" }}>
                    {key.replace("_", " ")}
                  </label>
                  {value.type === "float" && (
                    <input
                      className="form-control"
                      type="number"
                      step={0.1}
                      min={value.min}
                      max={value.max}
                    />
                  )}
                  {value.type === "int" && (
                    <input
                      className="form-control"
                      type="number"
                      step="any"
                      min={value.min}
                      max={value.max}
                    />
                  )}
                  {value.type === "text" && (
                    <input className="form-control" type="text" />
                  )}
                </>
              )}
              {value.type === "boolean" && (
                <>
                  <input className="form-check-input" type="checkbox" />
                  <label
                    className="form-check-label"
                    style={{ textTransform: "capitalize" }}
                  >
                    {key.replace("_", " ")}
                  </label>
                </>
              )}
            </div>
          ))}
        </>
      )}
    </div>
  );
};

export default ScriptParametersEditor;
