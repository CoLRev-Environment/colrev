import React, { useEffect, useState } from "react";
import "../../App.css";
import Project from "../../models/project";
import ProjectEditor from "../project/ProjectEditor";
import Settings from "../../models/settings";
import dataService from "../../services/dataService";
import Expander from "../common/Expander";
import ExpanderItem from "../common/ExpanderItem";
import { KEY_S } from "keycode-js";
import SourcesEditor from "../sources/SourcesEditor";
import PrepEditor from "../prep/PrepEditor";
import Prep from "../../models/prep";
import { Tooltip } from "bootstrap";
import DedupeEditor from "../dedupe/DedupeEditor";
import Dedupe from "../../models/dedupe";
import Prescreen from "../../models/prescreen";
import PrescreenEditor from "../prescreen/PrescreenEditor";
import DataEditor from "../data/DataEditor";
import Data from "../../models/data";
import PdfGet from "../../models/pdfGet";
import PdfPrep from "../../models/pdfPrep";
import Screen from "../../models/screen";
import PdfGetEditor from "../pdf/PdfGetEditor";
import PdfPrepEditor from "../pdf/PdfPrepEditor";
import ScreenEditor from "../screen/ScreenEditor";
import Search from "../../models/search";
import SearchEditor from "../search/SearchEditor";
import Package from "../../models/package";
import { useParams } from "react-router-dom";

function SettingsEditor() {
  const supportedColrevSettingsVersion: string = "0.6.";

  const params = useParams();
  const openParam = params.open;
  const isOpenSources =
    openParam !== undefined &&
    openParam.toLowerCase() === "openSources".toLowerCase();

  const [isAppClosed, setIsAppClosed] = useState<boolean>(false);
  const [isAppError, setIsAppError] = useState<boolean>(false);
  const [isAppLoading, setIsAppLoading] = useState<boolean>(true);

  const [project, setProject] = useState<Project>(new Project());
  const [sources, setSources] = useState<Package[]>([]);
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

    try {
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
    } catch (error) {
      setIsAppError(true);
      return;
    }

    setIsAppLoading(false);
  };

  const onProjectChanged = (project: Project) => {
    setIsFileSaved(false);
    setProject(project);
  };

  const onSourcesChanged = (sources: Package[]) => {
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

  const onSave = async (commit?: boolean) => {
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
      await dataService.saveSettings(settings, commit);
      setIsFileSaved(true);
    } catch (error) {
      console.log(error);
      alert("Error saving file.");
    }
  };

  const onKeyDown = (e: any) => {
    if (e.ctrlKey && e.which === KEY_S) {
      e.preventDefault();
      onSave();
    }
  };

  const onClose = async () => {
    await dataService.shutdown();
    setIsAppClosed(true);
  };

  if (isAppClosed) {
    return (
      <div style={{ padding: "10px" }}>
        Application closed. You can now close this window.
      </div>
    );
  }

  if (isAppError) {
    return <div style={{ padding: "10px" }}>Application error.</div>;
  }

  if (isAppLoading) {
    return <div style={{ padding: "10px" }}>Loading...</div>;
  }

  const isOldFileVersion =
    project &&
    project.colrevVersion.indexOf(supportedColrevSettingsVersion) === -1;

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
        {isOldFileVersion && (
          <div className="alert alert-warning">
            Old settings.json version {project.colrevVersion} detected!
            Supported version is {supportedColrevSettingsVersion}
          </div>
        )}
        {project && (
          <>
            <Expander id="settingsExpander">
              <ExpanderItem
                name="Project"
                id="project"
                parentContainerId="settingsExpander"
                show={!isOpenSources}
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
                show={isOpenSources}
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
                <ScreenEditor
                  screen={screen}
                  screenChanged={onScreenChanged}
                  options={options}
                />
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
              <div
                className="btn-group"
                role="group"
                aria-label="Button group with nested dropdown"
              >
                <button
                  className="btn btn-primary"
                  type="button"
                  onClick={() => onSave(true)}
                >
                  Save and Commit Settings
                </button>
                <div className="btn-group" role="group">
                  <button
                    className="btn btn-primary dropdown-toggle"
                    data-bs-toggle="dropdown"
                    aria-expanded="false"
                  ></button>
                  <ul className="dropdown-menu">
                    <li>
                      <button
                        className="dropdown-item"
                        onClick={() => onSave()}
                      >
                        Save Settings
                      </button>
                    </li>
                  </ul>
                </div>
              </div>
              <button
                className="btn btn-primary ms-2"
                type="button"
                onClick={onClose}
              >
                Close
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

export default SettingsEditor;
