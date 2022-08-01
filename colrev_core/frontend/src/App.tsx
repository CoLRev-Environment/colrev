import React, { useEffect, useState } from "react";
import "./App.css";
import Project from "./models/project";
import ProjectEditor from "./components/project/ProjectEditor";
import ScriptsEditor from "./components/scripts/ScriptsEditor";
import Script from "./models/script";
import Settings from "./models/settings";
import dataService from "./services/dataService";
import Expander from "./components/common/Expander";
import ExpanderItem from "./components/common/ExpanderItem";
import { KEY_S } from "keycode-js";
import SourcesEditor from "./components/sources/SourcesEditor";
import Source from "./models/source";
import PrepEditor from "./components/prep/PrepEditor";
import Prep from "./models/prep";

function App() {
  const [project, setProject] = useState<Project>(new Project());
  const [sources, setSources] = useState<Source[]>([]);
  const [prep, setPrep] = useState<Prep>(new Prep());
  const [scripts, setScripts] = useState<Script[]>([]);
  const [isFileSaved, setIsFileSaved] = useState<boolean>(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setIsFileSaved(false);
    const settings = await dataService.getSettings();
    setProject(settings.project);
    setSources(settings.sources);
    setPrep(settings.prep);
    setScripts(settings.data.scripts);
  };

  const onProjectChanged = (project: Project) => {
    setIsFileSaved(false);
    setProject(project);
  };

  const onSourcesChanged = (sources: Source[]) => {
    setIsFileSaved(false);
    setSources(sources);
  };

  const onPrepChanged = (prep: Prep) => {
    setIsFileSaved(false);
    setPrep(prep);
  };

  const onScriptsChanged = (scripts: Script[]) => {
    setIsFileSaved(false);
    setScripts(scripts);
  };

  const onSave = async () => {
    const settings = new Settings();
    settings.project = project;
    settings.sources = sources;
    settings.prep = prep;
    settings.data.scripts = scripts;

    setIsFileSaved(false);

    try {
      await dataService.saveSettings(settings);
      setIsFileSaved(true);
    } catch (error) {
      alert("Error saving file.");
    }
  };

  const onKeyDown = (e: any) => {
    if (e.ctrlKey && e.which === KEY_S) {
      e.preventDefault();
      onSave();
    }
  };

  return (
    <>
      <header>
        <h1 className="display-3 text-center my-4">Settings Editor</h1>
      </header>
      <div
        className="container"
        style={{ marginBottom: 100 }}
        onKeyDown={onKeyDown}
      >
        {project && (
          <>
            <Expander id="settingsExpander">
              <ExpanderItem
                name="Project"
                id="project"
                parentContainerId="settingsExpander"
                show={false}
              >
                <ProjectEditor
                  project={project}
                  projectChanged={onProjectChanged}
                />
              </ExpanderItem>
              <ExpanderItem
                name="Sources"
                id="sources"
                parentContainerId="settingsExpander"
                show={false}
              >
                <SourcesEditor
                  sources={sources}
                  sourcesChanged={onSourcesChanged}
                />
              </ExpanderItem>
              <ExpanderItem
                name="Prep"
                id="prep"
                parentContainerId="settingsExpander"
                show={true}
              >
                <PrepEditor prep={prep} prepChanged={onPrepChanged} />
              </ExpanderItem>
              <ExpanderItem
                name="Data"
                id="data"
                parentContainerId="settingsExpander"
                show={false}
              >
                <ScriptsEditor
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
