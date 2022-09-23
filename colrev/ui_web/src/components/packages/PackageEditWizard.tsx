import { useEffect, useState } from "react";
import Package from "../../models/package";
import dataService from "../../services/dataService";
import ModalWindow from "../common/ModalWindow";
import PackageTitle from "./PackageTitle";
import PackageParametersEditor from "./PackageParametersEditor";
import PackageDefinition from "../../models/packageDefinition";

const PackageEditWizard: React.FC<{
  packageEntity: string;
  packageType: string;
  isEdit: boolean;
  package: Package;
  onOk: any;
  onCancel: any;
}> = ({
  packageEntity,
  packageType,
  isEdit,
  package: currentPackage,
  onOk,
  onCancel,
}) => {
  const [packageDefinitions, setPackageDefinitions] = useState<
    PackageDefinition[]
  >([]);
  const [newPackage, setNewPackage] = useState<Package>(currentPackage);
  const [showOk, setShowOk] = useState(false);
  const [isOkEnabled, setIsOkEnabled] = useState(false);
  const [stepIndex, setStepIndex] = useState<number>(0);
  const [selectedPackageDefinition, setSelectedPackageDefinition] =
    useState<PackageDefinition>(new PackageDefinition());

  useEffect(() => {
    const init = async () => {
      const packageDefs = await dataService.getPackageDefinitions(packageType);

      setStepIndex(0);

      if (!isEdit) {
        setPackageDefinitions(packageDefs);
      } else {
        let packageDefinition = packageDefs.find(
          (pd) => pd.endpoint === currentPackage.endpoint
        );

        // TODO: Show message: package not found
        if (!packageDefinition) {
          packageDefinition = packageDefs[0];
        }

        setSelectedPackageDefinition(packageDefinition);
        next();
      }
    };

    init();
  }, [packageType, isEdit, currentPackage]);

  const next = () => {
    setStepIndex(1);
    setShowOk(true);
    setIsOkEnabled(true);
  };

  const cancelHandler = () => {
    onCancel();
  };

  const okHandler = () => {
    onOk(newPackage);
  };

  return (
    <ModalWindow
      title={isEdit ? `Edit ${packageEntity}` : `Add ${packageEntity}`}
      isShowOk={showOk}
      isOkEnabled={isOkEnabled}
      onOk={okHandler}
      onCancel={cancelHandler}
    >
      {stepIndex === 0 && (
        <div>
          <p>Select {packageEntity}</p>
          <div
            className="list-group"
            style={{
              maxHeight: "300px",
            }}
          >
            <div style={{ overflowY: "auto" }}>
              {packageDefinitions.map(
                (packageDefinition: PackageDefinition, index: number) => (
                  <button
                    type="button"
                    className={
                      "list-group-item list-group-item-action" +
                      (selectedPackageDefinition?.endpoint ===
                      packageDefinition.endpoint
                        ? " active"
                        : "")
                    }
                    key={index.toString()}
                    onClick={() => {
                      setSelectedPackageDefinition(packageDefinition);
                      newPackage.endpoint = packageDefinition.endpoint;
                      next();
                    }}
                  >
                    <PackageTitle packageDefinition={packageDefinition} />
                  </button>
                )
              )}
            </div>
          </div>
        </div>
      )}
      {stepIndex === 1 && (
        <PackageParametersEditor
          packageEntity={packageEntity}
          packageType={packageType}
          packageDefinition={selectedPackageDefinition}
          package={newPackage}
          packageChanged={(newPkg: Package) => setNewPackage(newPkg)}
        />
      )}
    </ModalWindow>
  );
};

export default PackageEditWizard;
