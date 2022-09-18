import React, { useEffect, useState } from "react";
import "./App.css";
import Project from "./models/project";
import ProjectEditor from "./components/project/ProjectEditor";
import Settings from "./models/settings";
import dataService from "./services/dataService";
import Expander from "./components/common/Expander";
import ExpanderItem from "./components/common/ExpanderItem";
import { KEY_S } from "keycode-js";
import SourcesEditor from "./components/sources/SourcesEditor";
import Source from "./models/source";
import PrepEditor from "./components/prep/PrepEditor";
import Prep from "./models/prep";
import { Tooltip } from "bootstrap";
import DedupeEditor from "./components/dedupe/DedupeEditor";
import Dedupe from "./models/dedupe";
import Prescreen from "./models/prescreen";
import PrescreenEditor from "./components/prescreen/PrescreenEditor";
import DataEditor from "./components/data/DataEditor";
import Data from "./models/data";
import PdfGet from "./models/pdfGet";
import PdfPrep from "./models/pdfPrep";
import Screen from "./models/screen";
import PdfGetEditor from "./components/pdf/PdfGetEditor";
import PdfPrepEditor from "./components/pdf/PdfPrepEditor";
import ScreenEditor from "./components/screen/ScreenEditor";
import Search from "./models/search";
import SearchEditor from "./components/search/SearchEditor";

function App() {
  const [project, setProject] = useState<Project>(new Project());
  const [sources, setSources] = useState<Source[]>([]);
  const [search, setSearch] = useState<Search>(new Search());
  const [prep, setPrep] = useState<Prep>(new Prep());
  const [dedupe, setDedupe] = useState<Dedupe>(new Dedupe());
  const [prescreen, setPrescreen] = useState<Prescreen>(new Prescreen());
  const [data, setData] = useState<Data>(new Data());
  const [pdfGet, setPdfGet] = useState<PdfGet>(new PdfGet());
  const [pdfPrep, setPdfPrep] = useState<PdfPrep>(new PdfPrep());
  const [screen, setScreen] = useState<Screen>(new Screen());
  const [isFileSaved, setIsFileSaved] = useState<boolean>(false);
  const [options, setOptions] = useState<any>();

  useEffect(() => {
    loadData();
    initTooltips();
  }, []);

  const initTooltips = () => {
    Array.from(document.querySelectorAll('[data-bs-toggle="tooltip"]')).forEach(
      (tooltipNode) => {
        if (!tooltipNode.hasAttribute("data-tooltip-initialized")) {
          new Tooltip(tooltipNode);
          tooltipNode.setAttribute("data-tooltip-initialized", "true");
        }
      }
    );
  };

  const loadData = async () => {
    setIsFileSaved(false);

    const options = await dataService.getOptions();
    setOptions(options);

    const settings = await dataService.getSettings();
    setProject(settings.project);
    setSources(settings.sources);
    setSearch(settings.search);
    setPrep(settings.prep);
    setDedupe(settings.dedupe);
    setPrescreen(settings.prescreen);
    setPdfGet(settings.pdfGet);
    setPdfPrep(settings.pdfPrep);
    setScreen(settings.screen);
    setData(settings.data);
  };

  const onProjectChanged = (project: Project) => {
    setIsFileSaved(false);
    setProject(project);
  };

  const onSourcesChanged = (sources: Source[]) => {
    setIsFileSaved(false);
    setSources(sources);
  };

  const onSearchChanged = (search: Search) => {
    setIsFileSaved(false);
    setSearch(search);
  };

  const onPrepChanged = (prep: Prep) => {
    setIsFileSaved(false);
    setPrep(prep);
  };

  const onDedupeChanged = (dedupe: Dedupe) => {
    setIsFileSaved(false);
    setDedupe(dedupe);
  };

  const onPrescreenChanged = (prescreen: Prescreen) => {
    setIsFileSaved(false);
    setPrescreen(prescreen);
  };

  const onPdfGetChanged = (pdfGet: PdfGet) => {
    setIsFileSaved(false);
    setPdfGet(pdfGet);
  };

  const onPdfPrepChanged = (pdfPrep: PdfPrep) => {
    setIsFileSaved(false);
    setPdfPrep(pdfPrep);
  };

  const onScreenChanged = (screen: Screen) => {
    setIsFileSaved(false);
    setScreen(screen);
  };

  const onDataChanged = (data: Data) => {
    setIsFileSaved(false);
    setData(data);
  };

  const onSave = async () => {
    const settings = new Settings();
    settings.project = project;
    settings.sources = sources;
    settings.search = search;
    settings.prep = prep;
    settings.dedupe = dedupe;
    settings.prescreen = prescreen;
    settings.pdfGet = pdfGet;
    settings.pdfPrep = pdfPrep;
    settings.screen = screen;
    settings.data = data;

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
                show={true}
              >
                <ProjectEditor
                  project={project}
                  projectChanged={onProjectChanged}
                  options={options}
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
                name="Search"
                id="search"
                parentContainerId="settingsExpander"
                show={false}
              >
                <SearchEditor search={search} searchChanged={onSearchChanged} />
              </ExpanderItem>
              <ExpanderItem
                name="Prep"
                id="prep"
                parentContainerId="settingsExpander"
                show={false}
              >
                <PrepEditor prep={prep} prepChanged={onPrepChanged} />
              </ExpanderItem>
              <ExpanderItem
                name="Dedupe"
                id="dedupe"
                parentContainerId="settingsExpander"
                show={false}
              >
                <DedupeEditor
                  dedupe={dedupe}
                  dedupeChanged={onDedupeChanged}
                  options={options}
                />
              </ExpanderItem>
              <ExpanderItem
                name="Prescreen"
                id="prescreen"
                parentContainerId="settingsExpander"
                show={false}
              >
                <PrescreenEditor
                  prescreen={prescreen}
                  prescreenChanged={onPrescreenChanged}
                />
              </ExpanderItem>
              <ExpanderItem
                name="PDF Get"
                id="pdfGet"
                parentContainerId="settingsExpander"
                show={false}
              >
                <PdfGetEditor
                  pdfGet={pdfGet}
                  pdfGetChanged={onPdfGetChanged}
                  options={options}
                />
              </ExpanderItem>
              <ExpanderItem
                name="PDF Prep"
                id="pdfPrep"
                parentContainerId="settingsExpander"
                show={false}
              >
                <PdfPrepEditor
                  pdfPrep={pdfPrep}
                  pdfPrepChanged={onPdfPrepChanged}
                />
              </ExpanderItem>
              <ExpanderItem
                name="Screen"
                id="screen"
                parentContainerId="settingsExpander"
                show={false}
              >
                <ScreenEditor screen={screen} screenChanged={onScreenChanged} />
              </ExpanderItem>
              <ExpanderItem
                name="Data"
                id="data"
                parentContainerId="settingsExpander"
                show={false}
              >
                <DataEditor
                  data={data}
                  dataChanged={onDataChanged}
                ></DataEditor>
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
