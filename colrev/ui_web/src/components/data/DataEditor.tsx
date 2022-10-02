import Data from "../../models/data";
import Package from "../../models/package";
import PackagesEditor from "../packages/PackagesEditor";

const DataEditor: React.FC<{
  data: Data;
  dataChanged: any;
}> = ({ data, dataChanged }) => {
  const dataPackagesChangedHandler = (packages: Package[]) => {
    const newData = { ...data, packages: packages };
    dataChanged(newData);
  };

  return (
    <div>
      <div className="mb-3">
        <label>Packages</label>
        <PackagesEditor
          packageEntity="Package"
          packageType="data"
          packages={data.packages}
          packagesChanged={(packages: Package[]) =>
            dataPackagesChangedHandler(packages)
          }
        />
      </div>
    </div>
  );
};

export default DataEditor;
