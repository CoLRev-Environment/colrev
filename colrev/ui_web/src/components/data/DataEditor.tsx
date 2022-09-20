import Data from "../../models/data";
import Package from "../../models/package";
import PackagesEditor from "../packages/PackagesEditor";

const DataEditor: React.FC<{
  data: Data;
  dataChanged: any;
}> = ({ data, dataChanged }) => {
  const dataScriptsChangedHandler = (scripts: Package[]) => {
    const newData = { ...data, scripts: scripts };
    dataChanged(newData);
  };

  return (
    <div>
      <div className="mb-3">
        <label>Scripts</label>
        <PackagesEditor
          packageEntity="Script"
          packageType="data"
          packages={data.scripts}
          packagesChanged={(scripts: Package[]) =>
            dataScriptsChangedHandler(scripts)
          }
        />
      </div>
    </div>
  );
};

export default DataEditor;
