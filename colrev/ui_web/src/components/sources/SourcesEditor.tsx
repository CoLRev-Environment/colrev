import Script from "../../models/script";
import Source from "../../models/source";
import Expander from "../common/Expander";
import ExpanderItem from "../common/ExpanderItem";
import ScriptsEditor from "../scripts/ScriptsEditor";

const SourcesEditor: React.FC<{ sources: Source[]; sourcesChanged: any }> = ({
  sources,
  sourcesChanged,
}) => {
  const sourcesChangedHandler = () => {
    const newSources = [...sources];
    sourcesChanged(newSources);
  };

  const deleteSourceHandler = (source: Source) => {
    const newSources = sources.filter((s) => s !== source);
    sourcesChanged(newSources);
  };

  const addSourceHandler = () => {
    const newSources = [...sources, new Source()];
    sourcesChanged(newSources);
  };

  const fieldChangedHandler = (fieldName: string, source: any, event: any) => {
    const newValue = event.target.value;
    source[fieldName] = newValue;
    sourcesChangedHandler();
  };

  const sourcePrepScriptsChangedHandler = (
    scripts: Script[],
    source: Source
  ) => {
    source.sourcePrepScripts = scripts;
    sourcesChangedHandler();
  };

  return (
    <div className="mb-3">
      <Expander id="sourcesExpander">
        {sources.map((source, index) => (
          <ExpanderItem
            key={index.toString()}
            name={source.filename}
            id={`source${index + 1}`}
            parentContainerId="sourcesExpander"
            show={false}
            hasDelete={true}
            onDelete={() => deleteSourceHandler(source)}
          >
            <div className="mb-3">
              <label htmlFor="filename">Filename</label>
              <input
                className="form-control"
                type="text"
                id="filename"
                value={source.filename}
                onChange={(event) =>
                  fieldChangedHandler("filename", source, event)
                }
              />
            </div>
            <div className="mb-3">
              <label htmlFor="searchType">Search Type</label>
              <input
                className="form-control"
                type="text"
                id="searchType"
                value={source.searchType}
                onChange={(event) =>
                  fieldChangedHandler("searchType", source, event)
                }
              />
            </div>
            <div className="mb-3">
              <label htmlFor="sourceName">Source Name</label>
              <input
                className="form-control"
                type="text"
                id="sourceName"
                value={source.sourceName}
                onChange={(event) =>
                  fieldChangedHandler("sourceName", source, event)
                }
              />
            </div>
            <div className="mb-3">
              <label htmlFor="sourceIdentifier">Source Identifier</label>
              <input
                className="form-control"
                type="text"
                id="sourceIdentifier"
                value={source.sourceIdentifier}
                onChange={(event) =>
                  fieldChangedHandler("sourceIdentifier", source, event)
                }
              />
            </div>
            <div className="mb-3">
              <label htmlFor="searchParameters">Search Parameters</label>
              <input
                className="form-control"
                type="text"
                id="searchParameters"
                value={source.searchParameters}
                onChange={(event) =>
                  fieldChangedHandler("searchParameters", source, event)
                }
              />
            </div>
            <div className="mb-3">
              <label>Search Script</label>
              <ScriptsEditor
                id="sourceSearchScript"
                isSingleScript={true}
                scripts={[source.searchScript]}
                scriptsChanged={(scripts: Script[]) => {
                  source.searchScript = scripts[0];
                  sourcesChangedHandler();
                }}
              />
            </div>
            <div className="mb-3">
              <label>Conversion Script</label>
              <ScriptsEditor
                id="sourceConversionScript"
                isSingleScript={true}
                scripts={[source.conversionScript]}
                scriptsChanged={(scripts: Script[]) => {
                  source.conversionScript = scripts[0];
                  sourcesChangedHandler();
                }}
              />
            </div>
            <div className="mb-3">
              <label>Source Prep Scripts</label>
              <ScriptsEditor
                id="sourcePrepScripts"
                scripts={source.sourcePrepScripts}
                scriptsChanged={(scripts: Script[]) =>
                  sourcePrepScriptsChangedHandler(scripts, source)
                }
              />
            </div>
            <div className="mb-3">
              <label htmlFor="comment">Comment</label>
              <input
                className="form-control"
                type="text"
                id="comment"
                value={source.comment}
                onChange={(event) =>
                  fieldChangedHandler("comment", source, event)
                }
              />
            </div>
          </ExpanderItem>
        ))}
      </Expander>
      <button
        className="btn btn-primary mt-1"
        type="button"
        onClick={addSourceHandler}
      >
        Add
      </button>
    </div>
  );
};

export default SourcesEditor;
