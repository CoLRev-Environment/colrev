import Project from "../models/project";
import Settings from "../models/settings";
import httpService from "./httpService";
import config from "../config.json";

const apiEndpoint = config.apiEndpoint + "/api";

let settingsFile: any = {};

const getSettings = async (): Promise<Settings> => {
  const response = await httpService.get(`${apiEndpoint}/getSettings`);

  settingsFile = response.data;

  const settings = new Settings();

  settings.project = new Project();
  settings.project.reviewType = settingsFile.project.review_type;
  settings.project.idPattern = settingsFile.project.id_pattern;
  settings.project.shareStatReq = settingsFile.project.share_stat_req;
  settings.project.delayAutomatedProcessing =
    settingsFile.project.delay_automated_processing;
  settings.project.curationUrl = settingsFile.project.curation_url;
  settings.project.curatedMasterdata = settingsFile.project.curated_masterdata;
  settings.project.curatedFields = settingsFile.project.curated_fields;

  settings.data = settingsFile.data;

  return Promise.resolve<Settings>(settings);
};

const saveSettings = async (settings: Settings): Promise<void> => {
  const newSettingsFile = {
    ...settingsFile,

    project: {
      ...settingsFile.project,
      review_type: settings.project.reviewType,
      id_pattern: settings.project.idPattern,
      share_stat_req: settings.project.shareStatReq,
      delay_automated_processing: settings.project.delayAutomatedProcessing,
      curation_url: settings.project.curationUrl,
      curated_masterdata: settings.project.curatedMasterdata,
      curated_fields: settings.project.curatedFields,
    },

    data: settings.data,
  };

  await httpService.post(`${apiEndpoint}/saveSettings`, newSettingsFile, {
    headers: { "content-type": "application/json" },
  });

  return Promise.resolve();
};

const dataService = {
  getSettings,
  saveSettings,
};

export default dataService;
