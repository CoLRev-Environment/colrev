import { useState } from "react";
import Package from "../../models/package";
import DeleteIcon from "../common/icons/DeleteIcon";
import EditIcon from "../common/icons/EditIcon";
import PackageEditWizard from "./PackageEditWizard";

const PackagesEditor: React.FC<{
  packageEntity: string;
  packageType: string;
  packages: Package[];
  packagesChanged: any;
  isSinglePackage?: boolean;
}> = ({
  packageEntity,
  packageType,
  packages,
  packagesChanged,
  isSinglePackage = false,
}) => {
  const [showPackageEditor, setShowPackageEditor] = useState(false);
  const [isEdit, setIsEdit] = useState(false);
  const [currentPackage, setCurrentPacakge] = useState<Package>(new Package());
  const [currentPackageCopy, setCurrentPackageCopy] = useState<Package>(
    new Package()
  );

  const deletePackageHandler = (pkg: Package) => {
    const newPackages = packages.filter((p) => p !== pkg);
    packagesChanged(newPackages);
  };

  const addPackageHandler = () => {
    setIsEdit(false);
    setCurrentPacakge(new Package());
    setShowPackageEditor(true);
  };

  const editPackageHandler = (pkg: Package) => {
    setIsEdit(true);
    setCurrentPacakge(pkg);
    setCurrentPackageCopy(pkg.clone());
    setShowPackageEditor(true);
  };

  const cancelHanlder = () => {
    setShowPackageEditor(false);
  };

  const okHander = (newPackage: Package) => {
    setShowPackageEditor(false);

    let newPackages: Package[] = [];

    if (!isEdit) {
      newPackages = [...packages, newPackage];
    } else {
      for (const pkg of packages) {
        if (pkg !== currentPackage) {
          newPackages.push(pkg);
        } else {
          newPackages.push(newPackage);
        }
      }
    }

    packagesChanged(newPackages);
  };

  return (
    <div>
      <ul className="list-group">
        {packages.map((pkg, index) => (
          <li
            className="list-group-item d-flex justify-content-between align-items-center"
            key={index.toString()}
          >
            <span>{pkg.endpoint}</span>
            <div>
              <div
                className="btn btn-primary btn-sm"
                style={{ marginRight: 5 }}
                onClick={() => editPackageHandler(pkg)}
              >
                <EditIcon />
              </div>
              <div
                className="btn btn-danger btn-sm"
                onClick={() => deletePackageHandler(pkg)}
              >
                <DeleteIcon />
              </div>
            </div>
          </li>
        ))}
      </ul>
      {(!isSinglePackage || (isSinglePackage && packages.length === 0)) && (
        <div className="mb-3 mt-1">
          <button
            className="btn btn-primary"
            type="button"
            onClick={addPackageHandler}
          >
            Add {packageEntity}
          </button>
        </div>
      )}
      {showPackageEditor && (
        <PackageEditWizard
          packageEntity={packageEntity}
          packageType={packageType}
          isEdit={isEdit}
          package={currentPackageCopy}
          onOk={okHander}
          onCancel={cancelHanlder}
        />
      )}
    </div>
  );
};

export default PackagesEditor;
