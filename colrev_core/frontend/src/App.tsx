import React, { useEffect, useState } from "react";
import "./App.css";
import Project from "./models/project";
import ProjectEdit from "./components/project/ProjectEdit";
import ScriptsEdit from "./components/scripts/ScriptsEdit";
import Script from "./models/script";
import Settings from "./models/settings";
import dataService from "./services/dataService";
import Expander from "./components/common/Expander";
import ExpanderItem from "./components/common/ExpanderItem";

function App() {
  const [project, setProject] = useState<Project>();
  const [scripts, setScripts] = useState<Script[]>([]);
  const [isFileSaved, setIsFileSaved] = useState<boolean>(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setIsFileSaved(false);
    const settings = await dataService.getSettings();
    setProject(settings.project);
    setScripts(settings.data.scripts);
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
    settings.data.scripts = scripts;

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
        <h1 className="display-3 text-center my-4">Settings Editor</h1>
      </header>
      <div className="container" style={{ marginBottom: 100 }}>
        {project && (
          <>
            <Expander id="settingsExpander">
              <ExpanderItem
                name="Project"
                id="project"
                parentContainerId="settingsExpander"
                show={true}
              >
                <ProjectEdit
                  project={project}
                  projectChanged={onProjectChanged}
                />
              </ExpanderItem>
              <ExpanderItem
                name="Data"
                id="data"
                parentContainerId="settingsExpander"
                show={false}
              >
                <ScriptsEdit
                  scripts={scripts}
                  scriptsChanged={onScriptsChanged}
                />
              </ExpanderItem>
            </Expander>
            <div className="mb-3"></div>
            <div className="mb-3"></div>
            <div className="mb-3">
              <button
                className="btn btn-primary"
                type="button"
                onClick={onSave}
              >
                Save Settings
              </button>
            </div>
            {isFileSaved && (
              <div className="alert alert-success">Settings Saved</div>
            )}
          </>
        )}
      </div>
    </>
  );
}

export default App;
