import Project from "../models/project";
import Settings from "../models/settings";
import httpService from "./httpService";
import config from "../config.json";
import Prep from "../models/prep";
import PrepRound from "../models/prepRound";
import Dedupe from "../models/dedupe";
import Prescreen from "../models/prescreen";
import Data from "../models/data";
import PdfGet from "../models/pdfGet";
import PdfPrep from "../models/pdfPrep";
import Screen from "../models/screen";
import Search from "../models/search";
import PackageParameterType from "../models/packageParameterType";
import PackageParameterDefinition from "../models/packageParameterDefinition";
import Package from "../models/package";
import PackageDefinition from "../models/packageDefinition";

const apiEndpoint = config.apiEndpoint + "/api";

let settingsFile: any = {};

const getSettings = async (): Promise<Settings> => {
  const response = await httpService.get(`${apiEndpoint}/getSettings`);

  settingsFile = response.data;

  const settings = new Settings();

  settings.project = new Project();
  projectFromSettings(settings.project, settingsFile.project);

  settings.sources = packagesFromSettings(settingsFile.sources);

  settings.search = new Search();
  searchFromSettings(settings.search, settingsFile.search);

  settings.prep = new Prep();
  prepFromSettings(settings.prep, settingsFile.prep);

  settings.dedupe = new Dedupe();
  dedupeFromSettings(settings.dedupe, settingsFile.dedupe);

  settings.prescreen = new Prescreen();
  prescreenFromSettings(settings.prescreen, settingsFile.prescreen);

  settings.pdfGet = new PdfGet();
  pdfGetFromSettings(settings.pdfGet, settingsFile.pdf_get);

  settings.pdfPrep = new PdfPrep();
  pdfPrepFromSettings(settings.pdfPrep, settingsFile.pdf_prep);

  settings.screen = new Screen();
  screenFromSettings(settings.screen, settingsFile.screen);

  settings.data = new Data();
  dataFromSettings(settings.data, settingsFile.data);

  return Promise.resolve<Settings>(settings);
};

const saveSettings = async (settings: Settings): Promise<void> => {
  const newSettingsFile = {
    ...settingsFile,
    project: projectToSettings(settings.project),
    sources: [],
    search: searchToSettings(settings.search),
    prep: prepToSettings(settings.prep),
    dedupe: dedupeToSettings(settings.dedupe),
    prescreen: prescreenToSettings(settings.prescreen),
    pdf_get: pdfGetToSettings(settings.pdfGet),
    pdf_prep: pdfPrepToSettings(settings.pdfPrep),
    screen: screenToSettings(settings.screen),
    data: dataToSettings(settings.data),
  };

  newSettingsFile.sources = packagesToSettings(settings.sources);

  await httpService.post(`${apiEndpoint}/saveSettings`, newSettingsFile, {
    headers: { "content-type": "application/json" },
  });

  return Promise.resolve();
};

const projectFromSettings = (project: Project, settingsProject: any) => {
  project.title = settingsProject.title;
  project.authors = settingsProject.authors;
  project.keywords = settingsProject.keywords;
  project.protocol = settingsProject.protocol;
  project.reviewType = settingsProject.review_type;
  project.idPattern = settingsProject.id_pattern;
  project.shareStatReq = settingsProject.share_stat_req;
  project.delayAutomatedProcessing = settingsProject.delay_automated_processing;
  project.curationUrl = settingsProject.curation_url;
  project.curatedMasterdata = settingsProject.curated_masterdata;
  project.curatedFields = settingsProject.curated_fields;
  project.colrevVersion = settingsProject.colrev_version;
};

const projectToSettings = (project: Project): any => {
  const settingsFileProject = {
    ...settingsFile.project,
    title: project.title,
    authors: project.authors,
    keywords: project.keywords,
    protocol: project.protocol,
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

const searchFromSettings = (search: Search, settingsSearch: any) => {
  search.retrieveForthcoming = settingsSearch.retrieve_forthcoming;
};

const searchToSettings = (search: Search): any => {
  const settingsFileSearch = {
    ...settingsFile.search,
    retrieve_forthcoming: search.retrieveForthcoming,
  };
  return settingsFileSearch;
};

const prepFromSettings = (prep: Prep, settingsPrep: any) => {
  prep.fieldsToKeep = settingsPrep.fields_to_keep;

  for (const p of settingsPrep.prep_rounds) {
    const prepRound = new PrepRound();
    prepRound.name = p.name;
    prepRound.similarity = p.similarity;
    prepRound.scripts = packagesFromSettings(p.scripts);
    prep.prepRounds.push(prepRound);
  }

  prep.manPrepScripts = packagesFromSettings(settingsPrep.man_prep_scripts);
};

const prepToSettings = (prep: Prep): any => {
  const settingsFilePrep = {
    ...settingsFile.prep,
    fields_to_keep: prep.fieldsToKeep,
    prep_rounds: [],
    man_prep_scripts: packagesToSettings(prep.manPrepScripts),
  };

  for (const p of prep.prepRounds) {
    const prep_round = {
      name: p.name,
      similarity: p.similarity,
      scripts: packagesToSettings(p.scripts),
    };

    settingsFilePrep.prep_rounds.push(prep_round);
  }

  return settingsFilePrep;
};

const packagesFromSettings = (settingsPackages: any) => {
  const packages: Package[] = [];

  for (const settingsPackage of settingsPackages) {
    const pkg = packageFromSettings(settingsPackage);

    // inner packages
    for (const [key, value] of Array.from(pkg.parameters)) {
      var isPackage = value["endpoint"] !== undefined;
      if (isPackage) {
        // new Package() to add the clone() method
        var innerPackage = packageFromSettings(value);
        pkg.parameters.set(key, innerPackage);
      }
    }

    packages.push(pkg);
  }

  return packages;
};

const packageFromSettings = (settingsPackage: any) => {
  const pkg = new Package();
  pkg.endpoint = settingsPackage.endpoint;

  if (!pkg.endpoint) {
    pkg.endpoint = "unknown";
  }

  const paramsMap = new Map(Object.entries(settingsPackage));
  paramsMap.delete("endpoint");
  pkg.parameters = paramsMap;

  return pkg;
};

const packagesToSettings = (packages: Package[]) => {
  const settingsPackages: any[] = [];

  for (const pkg of packages) {
    const settingsPackage = packageToSettings(pkg);

    // inner packages
    for (const [key, value] of Array.from(pkg.parameters)) {
      if (value) {
        var isPackage = value["endpoint"] !== undefined;
        if (isPackage) {
          // new Package() to add the clone() method
          var innerPackageSettings = packageToSettings(value);
          settingsPackage[key] = innerPackageSettings;
        }
      }
    }

    settingsPackages.push(settingsPackage);
  }

  return settingsPackages;
};

const packageToSettings = (pkg: Package) => {
  const paramsMap = new Map<string, any>();
  paramsMap.set("endpoint", pkg.endpoint);

  for (const [key, value] of Array.from(pkg.parameters)) {
    paramsMap.set(key, value);
  }

  const settingsPackage = Object.fromEntries(paramsMap);
  return settingsPackage;
};

const dedupeFromSettings = (dedupe: Dedupe, settingsDedupe: any) => {
  dedupe.sameSourceMerges = settingsDedupe.same_source_merges;
  dedupe.scripts = packagesFromSettings(settingsDedupe.scripts);
};

const dedupeToSettings = (dedupe: Dedupe): any => {
  const settingsDedupe = {
    same_source_merges: dedupe.sameSourceMerges,
    scripts: packagesToSettings(dedupe.scripts),
  };

  return settingsDedupe;
};

const prescreenFromSettings = (
  prescreen: Prescreen,
  settingsPrescreen: any
) => {
  prescreen.explanation = settingsPrescreen.explanation;
  prescreen.scripts = packagesFromSettings(settingsPrescreen.scripts);
};

const prescreenToSettings = (prescreen: Prescreen): any => {
  const settingsPrescreen = {
    explanation: prescreen.explanation,
    scripts: packagesToSettings(prescreen.scripts),
  };

  return settingsPrescreen;
};

const pdfGetFromSettings = (pdfGet: PdfGet, settingsPdfGet: any) => {
  pdfGet.pdfPathType = settingsPdfGet.pdf_path_type;
  pdfGet.pdfRequiredForScreenAndSynthesis =
    settingsPdfGet.pdf_required_for_screen_and_synthesis;
  pdfGet.renamePdfs = settingsPdfGet.rename_pdfs;
  pdfGet.scripts = packagesFromSettings(settingsPdfGet.scripts);
  pdfGet.manPdfGetScripts = packagesFromSettings(
    settingsPdfGet.man_pdf_get_scripts
  );
};

const pdfGetToSettings = (pdfGet: PdfGet): any => {
  const settingsPdfGet = {
    pdf_path_type: pdfGet.pdfPathType,
    pdf_required_for_screen_and_synthesis:
      pdfGet.pdfRequiredForScreenAndSynthesis,
    rename_pdfs: pdfGet.renamePdfs,
    scripts: packagesToSettings(pdfGet.scripts),
    man_pdf_get_scripts: packagesToSettings(pdfGet.manPdfGetScripts),
  };

  return settingsPdfGet;
};

const pdfPrepFromSettings = (pdfPrep: PdfPrep, settingsPdfGet: any) => {
  pdfPrep.scripts = packagesFromSettings(settingsPdfGet.scripts);
  pdfPrep.manPdfPrepScripts = packagesFromSettings(
    settingsPdfGet.man_pdf_prep_scripts
  );
};

const pdfPrepToSettings = (pdfPrep: PdfPrep): any => {
  const settingsPdfPrep = {
    scripts: packagesToSettings(pdfPrep.scripts),
    man_pdf_prep_scripts: packagesToSettings(pdfPrep.manPdfPrepScripts),
  };

  return settingsPdfPrep;
};

const screenFromSettings = (screen: Screen, settingsScreen: any) => {
  screen.explanation = settingsScreen.explanation;
  screen.scripts = packagesFromSettings(settingsScreen.scripts);
};

const screenToSettings = (screen: Screen): any => {
  const settingsScreen = {
    explanation: screen.explanation,
    criteria: {},
    scripts: packagesToSettings(screen.scripts),
  };

  return settingsScreen;
};

const dataFromSettings = (data: Data, settingsData: any) => {
  data.scripts = packagesFromSettings(settingsData.scripts);
};

const dataToSettings = (data: Data): any => {
  const settingsData = {
    scripts: packagesToSettings(data.scripts),
  };

  return settingsData;
};

const getOptions = async (): Promise<any> => {
  const response = await httpService.get(`${apiEndpoint}/getOptions`);
  return response.data;
};

const getScriptDefinitions = async (
  packageType: string
): Promise<PackageDefinition[]> => {
  const response = await httpService.get(
    `${apiEndpoint}/getScripts?packageType=${packageType}`
  );

  const scriptDefinitions: PackageDefinition[] = [];

  for (const property in response.data) {
    const scriptDefinition = new PackageDefinition();
    scriptDefinition.name = property;

    const propertyValues = response.data[property];
    scriptDefinition.description = propertyValues.description;
    scriptDefinition.endpoint = propertyValues.endpoint;

    scriptDefinitions.push(scriptDefinition);
  }

  return Promise.resolve<PackageDefinition[]>(scriptDefinitions);
};

const getScriptParameterDefinitions = async (
  packageType: string,
  packageIdentifier: string
): Promise<PackageParameterDefinition[]> => {
  const response = await httpService.get(
    `${apiEndpoint}/getScriptDetails?packageType=${packageType}&packageIdentifier=${packageIdentifier}&endpointVersion=1.0`
  );

  const scriptParameterDefinitions: PackageParameterDefinition[] = [];

  const paramsMap = new Map(Object.entries(response.data.properties));

  for (const [key, value] of Array.from<any>(paramsMap)) {
    const param = new PackageParameterDefinition();
    param.name = key;
    param.tooltip = value.tooltip;

    if (value.enum) {
      param.type = PackageParameterType.Options;
      param.options = value.enum;
    } else {
      param.type = getScriptParameterType(value.type);
    }

    param.min = value.min;
    param.max = value.max;

    param.scriptType = value.script_type;

    scriptParameterDefinitions.push(param);
  }

  return Promise.resolve<PackageParameterDefinition[]>(
    scriptParameterDefinitions
  );
};

const getScriptParameterType = (
  parameterType: string
): PackageParameterType => {
  let scriptParameterType = PackageParameterType.Unknown;

  switch (parameterType) {
    case "integer":
      scriptParameterType = PackageParameterType.Int;
      break;
    case "float":
      scriptParameterType = PackageParameterType.Float;
      break;
    case "boolean":
      scriptParameterType = PackageParameterType.Boolean;
      break;
    case "path":
    case "string":
      scriptParameterType = PackageParameterType.String;
      break;
    case "array":
      scriptParameterType = PackageParameterType.StringList;
      break;
    case "script":
      scriptParameterType = PackageParameterType.Script;
      break;
    case "script_array":
      //scriptParameterType = PackageParameterType.ScriptList;
      scriptParameterType = PackageParameterType.Script;
      break;
  }

  return scriptParameterType;
};

const dataService = {
  getSettings,
  saveSettings,
  getOptions,
  getPackageDefinitions: getScriptDefinitions,
  getPackageParameterDefinitions: getScriptParameterDefinitions,
};

export default dataService;
