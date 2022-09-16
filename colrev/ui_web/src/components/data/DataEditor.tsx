import Data from "../../models/data";
import Script from "../../models/script";
import ScriptsEditor from "../scripts/ScriptsEditor";

const DataEditor: React.FC<{
  data: Data;
  dataChanged: any;
}> = ({ data, dataChanged }) => {
  const dataScriptsChangedHandler = (scripts: Script[]) => {
    const newData = { ...data, scripts: scripts };
    dataChanged(newData);
  };

  return (
    <div>
      <div className="mb-3">
        <label>Scripts</label>
        <ScriptsEditor
          packageType="data"
          scripts={data.scripts}
          scriptsChanged={(scripts: Script[]) =>
            dataScriptsChangedHandler(scripts)
          }
        />
      </div>
    </div>
  );
};

export default DataEditor;
