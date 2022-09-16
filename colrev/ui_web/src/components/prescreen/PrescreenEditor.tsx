import Prescreen from "../../models/prescreen";
import Script from "../../models/script";
import ScriptsEditor from "../scripts/ScriptsEditor";

const PrescreenEditor: React.FC<{
  prescreen: Prescreen;
  prescreenChanged: any;
}> = ({ prescreen, prescreenChanged }) => {
  const explanationChangedHandler = (event: any) => {
    const newPrescreen = { ...prescreen, explanation: event.target.value };
    prescreenChanged(newPrescreen);
  };

  const prescreenScriptsChangedHandler = (scripts: Script[]) => {
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
        <ScriptsEditor
          packageType="prescreen"
          scripts={prescreen.scripts}
          scriptsChanged={(scripts: Script[]) =>
            prescreenScriptsChangedHandler(scripts)
          }
        />
      </div>
    </div>
  );
};

export default PrescreenEditor;
