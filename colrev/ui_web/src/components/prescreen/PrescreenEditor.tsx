import Prescreen from "../../models/prescreen";
import Package from "../../models/package";
import PackagesEditor from "../packages/PackagesEditor";

const PrescreenEditor: React.FC<{
  prescreen: Prescreen;
  prescreenChanged: any;
}> = ({ prescreen, prescreenChanged }) => {
  const explanationChangedHandler = (event: any) => {
    const newPrescreen = { ...prescreen, explanation: event.target.value };
    prescreenChanged(newPrescreen);
  };

  const prescreenScriptsChangedHandler = (scripts: Package[]) => {
    const newPrescreen = { ...prescreen, scripts: scripts };
    prescreenChanged(newPrescreen);
  };

  return (
    <div>
      <div className="mb-3">
        <label htmlFor="explanation">Explanation</label>
        <input
          className="form-control"
          type="text"
          id="explanation"
          value={prescreen.explanation}
          onChange={explanationChangedHandler}
        />
      </div>
      <div className="mb-3">
        <label>Scripts</label>
        <PackagesEditor
          packageEntity="Script"
          packageType="prescreen"
          packages={prescreen.scripts}
          packagesChanged={(scripts: Package[]) =>
            prescreenScriptsChangedHandler(scripts)
          }
        />
      </div>
    </div>
  );
};

export default PrescreenEditor;
