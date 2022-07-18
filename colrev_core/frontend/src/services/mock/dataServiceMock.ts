import Project from "../../models/project";
import Script from "../../models/script";
import Settings from "../../models/settings";

const generateMockSettings = (): Settings => {
  const project = new Project();
  project.title = "A research project on topic X";
  project.relevantFields = ["context", "population"];

  const script1 = new Script();
  script1.endpoint = "data_formating";
  const script2 = new Script();
  script2.endpoint = "data_quality_measures";
  const scripts = [script1, script2];

  const settings = new Settings();
  settings.project = project;
  settings.load = {
    criteria: [],
    scripts: scripts,
  };

  return settings;
};

const dataServiceMock = {
  generateMockSettings,
};

export default dataServiceMock;
