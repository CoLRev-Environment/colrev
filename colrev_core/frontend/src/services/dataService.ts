import Project from "../models/project";
import Settings from "../models/settings";
import httpService from "./httpService";
import config from "../config.json";

const apiEndpoint = config.apiEndpoint + "/api";

const getSettings = async (): Promise<Settings> => {
  const response = await httpService.get(`${apiEndpoint}/getSettings`);

  const settings = new Settings();
  settings.project = new Project();
  settings.project.title = response.data.project.title;
  settings.project.relevantFields = response.data.project.relevant_fields;
  settings.load = response.data.load;

  return Promise.resolve<Settings>(settings);
};

const saveSettings = async (settings: Settings): Promise<void> => {
  const settingsFile = {
    project: {
      title: settings.project.title,
      relevant_fields: settings.project.relevantFields,
    },
    load: settings.load,
  };

  await httpService.post(`${apiEndpoint}/saveSettings`, settingsFile, {
    headers: { "content-type": "application/json" },
  });

  return Promise.resolve();
};

const dataService = {
  getSettings,
  saveSettings,
};

export default dataService;
