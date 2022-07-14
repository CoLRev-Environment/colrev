import React, { useState } from "react";
import "./App.css";
import Project from "./models/project";
import ProjectEdit from "./components/project/ProjectEdit";
import ScriptsEdit from "./components/scripts/ScriptsEdit";
import Script from "./models/script";
import Settings from "./models/settings";
import dataService from "./services/dataService";
import config from "./config.json";

function App() {
  const [project, setProject] = useState<Project>();
  const [scripts, setScripts] = useState<Script[]>([]);
  const [isFileSaved, setIsFileSaved] = useState<boolean>(false);

  const loadData = async () => {
    setIsFileSaved(false);
    const settings = await dataService.getSettings();
    setProject(settings.project);
    setScripts(settings.load.scripts);
  };

  const onProjectChanged = (project: Project) => {
    setIsFileSaved(false);
    setProject(project);
  };

  const onScriptsChanged = (scripts: Script[]) => {
    setIsFileSaved(false);
    setScripts(scripts);
  };

  const onSave = async () => {
    const settings = new Settings();
    settings.project = project ?? new Project();
    settings.load.scripts = scripts;

    setIsFileSaved(false);

    try {
      await dataService.saveSettings(settings);
      setIsFileSaved(true);
    } catch (error) {
      alert("Error saving file.");
    }
  };

  return (
    <>
      <header>
        <h1 className="display-3 text-center my-4">File Editor</h1>
      </header>
      <div className="container" style={{ marginBottom: 100 }}>
        <div className="mb-3 d-flex justify-content-between">
          <button className="btn btn-primary" type="button" onClick={loadData}>
            Load
          </button>
          <a
            className="align-self-center"
            href={config.apiEndpoint + "/data/settings.json"}
            target="_blank"
            rel="noreferrer"
          >
            Download File
          </a>
        </div>
        {project && (
          <>
            <div className="mb-3">
              <ProjectEdit
                project={project}
                projectChanged={onProjectChanged}
              />
            </div>
            <div className="mb-3">
              <ScriptsEdit
                scripts={scripts}
                scriptsChanged={onScriptsChanged}
              />
            </div>
            <div className="mb-3">
              <button
                className="btn btn-primary"
                type="button"
                onClick={onSave}
              >
                Save
              </button>
            </div>
            {isFileSaved && (
              <div className="alert alert-success">File Saved</div>
            )}
          </>
        )}
      </div>
    </>
  );
}

export default App;
