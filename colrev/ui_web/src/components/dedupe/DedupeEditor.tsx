import { useEffect, useState } from "react";
import Dedupe from "../../models/dedupe";
import Package from "../../models/package";
import PackagesEditor from "../packages/PackagesEditor";

const DedupeEditor: React.FC<{
  dedupe: Dedupe;
  dedupeChanged: any;
  options: any;
}> = ({ dedupe, dedupeChanged, options }) => {
  const [sameSourceMergesOptions, setSameSourceMergesOptions] = useState<
    string[]
  >([]);

  useEffect(() => {
    if (options) {
      setSameSourceMergesOptions(
        options.definitions.DedupeSettings.properties.same_source_merges.enum
      );
    }
  }, [options]);

  const sameSourceMergesChangedHandler = (event: any) => {
    const newDedupe = { ...dedupe, sameSourceMerges: event.target.value };
    dedupeChanged(newDedupe);
  };

  const dedupeScriptsChangedHandler = (scripts: Package[]) => {
    const newDedupe = { ...dedupe, scripts: scripts };
    dedupeChanged(newDedupe);
  };

  return (
    <div>
      <div className="mb-3">
        <label htmlFor="sameSourceMerges">Same Source Merges</label>
        <select
          className="form-select"
          aria-label="Select"
          id="sameSourceMerges"
          value={dedupe.sameSourceMerges ?? ""}
          onChange={sameSourceMergesChangedHandler}
        >
          {sameSourceMergesOptions.map((sameSourceMergesOption, index) => (
            <option key={index.toString()}>{sameSourceMergesOption}</option>
          ))}
        </select>
      </div>
      <div className="mb-3">
        <label>Scripts</label>
        <PackagesEditor
          packageEntity="Script"
          packageType="dedupe"
          packages={dedupe.scripts}
          packagesChanged={(scripts: Package[]) =>
            dedupeScriptsChangedHandler(scripts)
          }
        />
      </div>
    </div>
  );
};

export default DedupeEditor;
