import Project from "../models/project";
import Settings from "../models/settings";
import httpService from "./httpService";
import config from "../config.json";
import Source from "../models/source";
import Script from "../models/script";
import Prep from "../models/prep";
import PrepRound from "../models/prepRound";

const apiEndpoint = config.apiEndpoint + "/api";

let settingsFile: any = {};

const getSettings = async (): Promise<Settings> => {
  const response = await httpService.get(`${apiEndpoint}/getSettings`);

  settingsFile = response.data;

  const settings = new Settings();

  settings.project = new Project();
  projectFromSettings(settings.project, settingsFile.project);

  for (const s of settingsFile.sources) {
    const source = new Source();
    sourceFromSettings(source, s);
    settings.sources.push(source);
  }

  settings.prep = new Prep();
  prepFromSettings(settings.prep, settingsFile.prep);

  settings.data = settingsFile.data;

  return Promise.resolve<Settings>(settings);
};

const saveSettings = async (settings: Settings): Promise<void> => {
  const newSettingsFile = {
    ...settingsFile,
    project: projectToSettings(settings.project),
    sources: [],
    prep: prepToSettings(settings.prep),
    data: settings.data,
  };

  for (const source of settings.sources) {
    const settingsFileSource = sourceToSettings(source);
    newSettingsFile.sources.push(settingsFileSource);
  }

  await httpService.post(`${apiEndpoint}/saveSettings`, newSettingsFile, {
    headers: { "content-type": "application/json" },
  });

  return Promise.resolve();
};

const projectFromSettings = (project: Project, settingsProject: any) => {
  project.reviewType = settingsProject.review_type;
  project.idPattern = settingsProject.id_pattern;
  project.shareStatReq = settingsProject.share_stat_req;
  project.delayAutomatedProcessing = settingsProject.delay_automated_processing;
  project.curationUrl = settingsProject.curation_url;
  project.curatedMasterdata = settingsProject.curated_masterdata;
  project.curatedFields = settingsProject.curated_fields;
};

const projectToSettings = (project: Project): any => {
  const settingsFileProject = {
    ...settingsFile.project,
    review_type: project.reviewType,
    id_pattern: project.idPattern,
    share_stat_req: project.shareStatReq,
    delay_automated_processing: project.delayAutomatedProcessing,
    curation_url: project.curationUrl,
    curated_masterdata: project.curatedMasterdata,
    curated_fields: project.curatedFields,
  };
  return settingsFileProject;
};

const sourceFromSettings = (source: Source, settingsSource: any) => {
  source.filename = settingsSource.filename;
  source.searchType = settingsSource.search_type;
  source.sourceName = settingsSource.source_name;
  source.sourceIdentifier = settingsSource.source_identifier;
  source.searchParameters = settingsSource.search_parameters;

  source.searchScript.endpoint = settingsSource.search_script.endpoint;
  source.conversionScript.endpoint = settingsSource.conversion_script.endpoint;

  for (const s of settingsSource.source_prep_scripts) {
    const script = new Script();
    script.endpoint = s.endpoint;
    source.sourcePrepScripts.push(script);
  }

  source.comment = settingsSource.comment;
};

const sourceToSettings = (source: Source): any => {
  const settingsFileSource = {
    filename: source.filename,
    search_type: source.searchType,
    source_name: source.sourceName,
    source_identifier: source.sourceIdentifier,
    search_parameters: source.searchParameters,

    search_script: {
      endpoint: source.searchScript.endpoint,
    },
    conversion_script: {
      endpoint: source.conversionScript.endpoint,
    },
    source_prep_scripts: [{}],
    comment: source.comment,
  };

  settingsFileSource.source_prep_scripts.pop();
  for (const script of source.sourcePrepScripts) {
    const settingsScript = { endpoint: script.endpoint };
    settingsFileSource.source_prep_scripts.push(settingsScript);
  }

  return settingsFileSource;
};

const prepFromSettings = (prep: Prep, settingsPrep: any) => {
  prep.fieldsToKeep = settingsPrep.fields_to_keep;

  for (const p of settingsPrep.prep_rounds) {
    const prepRound = new PrepRound();
    prepRound.name = p.name;
    prepRound.similarity = p.similarity;
    prepRound.scripts = p.scripts;
    prep.prepRounds.push(prepRound);
  }

  for (const s of settingsPrep.man_prep_scripts) {
    const script = new Script();
    script.endpoint = s.endpoint;
    prep.manPrepScripts.push(script);
  }
};

const prepToSettings = (prep: Prep): any => {
  const settingsFilePrep = {
    ...settingsFile.prep,
    fields_to_keep: prep.fieldsToKeep,
    prep_rounds: prep.prepRounds,
    man_prep_scripts: prep.manPrepScripts,
  };

  return settingsFilePrep;
};

const dataService = {
  getSettings,
  saveSettings,
};

export default dataService;
