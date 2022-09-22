import Package from "../../models/package";
import PackagesEditor from "../packages/PackagesEditor";

const SourcesEditor: React.FC<{ sources: Package[]; sourcesChanged: any }> = ({
  sources,
  sourcesChanged,
}) => {
  return (
    <>
      <div className="mb-3">
        <PackagesEditor
          packageEntity="Source"
          packageType="search_source"
          packages={sources}
          packagesChanged={(packages: Package[]) => sourcesChanged(packages)}
        />
      </div>
    </>
  );
};

export default SourcesEditor;
