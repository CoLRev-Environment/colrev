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
  settings.project.curatedFields = response.data.project.curated_fields;
  settings.data = response.data.data;

  return Promise.resolve<Settings>(settings);
};

const saveSettings = async (settings: Settings): Promise<void> => {
  const settingsFile = {
    project: {
      title: settings.project.title,
      curated_fields: settings.project.curatedFields,
    },
    data: settings.data,
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
