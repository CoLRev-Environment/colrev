import { useEffect, useState } from "react";
import Script from "../../models/script";
import Source from "../../models/source";
import ScriptEditor from "../scripts/ScriptEditor";
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
    <div>
      {sources.map((source, index) => (
        <div className="card mb-2" key={index.toString()}>
          <div className="card-header d-flex justify-content-between align-items-center">
            <span>Source {index + 1}</span>
            <button
              className="btn btn-danger"
              type="button"
              onClick={() => deleteSourceHandler(source)}
            >
              X
            </button>
          </div>
          <div className="card-body">
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
            <div className="card mb-3">
              <div className="card-header">
                <span>Search Script</span>
              </div>
              <div className="card-body">
                <ScriptEditor
                  script={source.searchScript}
                  scriptChanged={sourcesChangedHandler}
                />
              </div>
            </div>
            <div className="card mb-3">
              <div className="card-header">
                <span>Conversion Script</span>
              </div>
              <div className="card-body">
                <ScriptEditor
                  script={source.conversionScript}
                  scriptChanged={sourcesChangedHandler}
                />
              </div>
            </div>
            <div className="mb-3">
              <label>Source Prep Scripts</label>
              <ScriptsEditor
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
          </div>
        </div>
      ))}
      <button
        className="btn btn-primary"
        type="button"
        onClick={addSourceHandler}
      >
        Add
      </button>
    </div>
  );
};

export default SourcesEditor;
