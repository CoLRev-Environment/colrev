import { useEffect, useState } from "react";
import Package from "../../models/package";
import PackageDefinition from "../../models/packageDefinition";
import PackageParameterDefinition from "../../models/packageParameterDefinition";
import PackageParameterType from "../../models/packageParameterType";
import dataService from "../../services/dataService";
import FiedlsEditor from "../fields/FieldsEditor";
import PackagesEditor from "./PackagesEditor";
import PackageTitle from "./PackageTitle";

const PackageParametersEditor: React.FC<{
  packageEntity: string;
  packageType: string;
  packageDefinition: PackageDefinition;
  package: Package;
  packageChanged: any;
}> = ({
  packageEntity,
  packageType,
  packageDefinition,
  package: currentPackage,
  packageChanged,
}) => {
  const [hasParameters, setHasParameters] = useState<boolean>(true);
  const [parameterDefinitions, setParameterDefinitions] = useState<
    PackageParameterDefinition[]
  >([]);

  useEffect(() => {
    const init = async () => {
      const paramDefs = await dataService.getPackageParameterDefinitions(
        packageType,
        packageDefinition.name
      );

      if (paramDefs.length === 0) {
        setHasParameters(false);
        return;
      }

      setHasParameters(true);
      setParameterDefinitions(paramDefs);

      for (const pd of paramDefs) {
        if (!currentPackage.parameters.has(pd.name)) {
          let paramValue = undefined;

          if (pd.type === PackageParameterType.StringList) {
            paramValue = [];
          } else if (pd.type === PackageParameterType.Boolean) {
            paramValue = false;
          }

          currentPackage.parameters.set(pd.name, paramValue);
        }
      }
    };

    init();
  }, [packageType, packageDefinition, currentPackage]);

  const getParameterValue = (paramDef: PackageParameterDefinition) => {
    let paramValue = currentPackage.parameters.get(paramDef.name);
    return paramValue;
  };

  const setParameterValue = (
    paramDef: PackageParameterDefinition,
    paramValue: any
  ) => {
    const newPackage = { ...currentPackage };
    newPackage.parameters.set(paramDef.name, paramValue);
    packageChanged(newPackage);
  };

  return (
    <div>
      <PackageTitle packageDefinition={packageDefinition} />
      <div style={{ marginTop: "10px" }}>
        {!hasParameters && <p>{packageEntity} has no paramaters</p>}
        {hasParameters && (
          <>
            <p>Set {packageEntity} Parameters</p>
            {parameterDefinitions.map((parameterDefinition, index) => (
              <div key={index.toString()} className="mb-3">
                {parameterDefinition.type === PackageParameterType.Boolean && (
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
                {parameterDefinition.type === PackageParameterType.Int && (
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
                {parameterDefinition.type === PackageParameterType.Float && (
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
                {parameterDefinition.type === PackageParameterType.String && (
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
                  PackageParameterType.StringList && (
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
                {parameterDefinition.type === PackageParameterType.Options && (
                  <div>
                    <label>{parameterDefinition.name}</label>
                    <select
                      className="form-select"
                      aria-label="Select"
                      value={getParameterValue(parameterDefinition) ?? ""}
                      onChange={(event) =>
                        setParameterValue(
                          parameterDefinition,
                          event.target.value
                        )
                      }
                    >
                      {parameterDefinition.options.map((option, index) => (
                        <option key={index.toString()}>{option}</option>
                      ))}
                    </select>
                  </div>
                )}
                {parameterDefinition.type === PackageParameterType.Package && (
                  <div>
                    <label>{parameterDefinition.name}</label>
                    <PackagesEditor
                      packageEntity="Package"
                      packageType={parameterDefinition.packageType}
                      isSinglePackage={true}
                      packages={
                        getParameterValue(parameterDefinition)
                          ? [getParameterValue(parameterDefinition)]
                          : []
                      }
                      packagesChanged={(packages: Package[]) => {
                        setParameterValue(parameterDefinition, packages[0]);
                      }}
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

export default PackageParametersEditor;
