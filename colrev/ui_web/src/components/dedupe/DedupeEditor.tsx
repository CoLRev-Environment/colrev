import Dedupe from "../../models/dedupe";
import Script from "../../models/script";
import ScriptsEditor from "../scripts/ScriptsEditor";

const DedupeEditor: React.FC<{ dedupe: Dedupe; dedupeChanged: any }> = ({
  dedupe,
  dedupeChanged,
}) => {
  const sameSourceMergesChangedHandler = (event: any) => {
    const newDedupe = { ...dedupe, sameSourceMerges: event.target.value };
    dedupeChanged(newDedupe);
  };

  const dedupeScriptsChangedHandler = (scripts: Script[]) => {
    const newDedupe = { ...dedupe, scripts: scripts };
    dedupeChanged(newDedupe);
  };

  return (
    <div>
      <div className="mb-3">
        <label htmlFor="sameSourceMerges">Same Source Merges</label>
        <input
          className="form-control"
          type="text"
          id="sameSourceMerges"
          value={dedupe.sameSourceMerges}
          onChange={sameSourceMergesChangedHandler}
        />
      </div>
      <div className="mb-3">
        <label>Scripts</label>
        <ScriptsEditor
          packageType="dedupe"
          scripts={dedupe.scripts}
          scriptsChanged={(scripts: Script[]) =>
            dedupeScriptsChangedHandler(scripts)
          }
        />
      </div>
    </div>
  );
};

export default DedupeEditor;
