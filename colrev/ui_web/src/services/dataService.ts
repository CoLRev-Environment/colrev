import Project from "../models/project";
import Settings from "../models/settings";
import httpService from "./httpService";
import config from "../config.json";
import Prep from "../models/prep";
import Dedupe from "../models/dedupe";
import Prescreen from "../models/prescreen";
import Data from "../models/data";
import PdfGet from "../models/pdfGet";
import PdfPrep from "../models/pdfPrep";
import Screen from "../models/screen";
import Search from "../models/search";
import PackageParameterType from "../models/packageParameterType";
import PackageParameterDefinition from "../models/packageParameterDefinition";
import PackageDefinition from "../models/packageDefinition";
import ProjectDataService from "./projectDataService";
import SearchDataService from "./searchDataService";
import PrepDataService from "./prepDataService";
import PackageDataService from "./packageDataService";
import DedupeDataService from "./dedupeDataService";
import PrescreenDataService from "./prescreenDataService";
import PdfDataService from "./pdfDataService";
import DataSectionDataService from "./dataSectionDataSerice";
import ScreenDataService from "./screenDataService";

const apiEndpoint = config.apiEndpoint + "/api";

let settingsFile: any = {};

const getSettings = async (): Promise<Settings> => {
  const response = await httpService.get(`${apiEndpoint}/getSettings`);

  settingsFile = response.data;

  const settings = new Settings();

  const packageDataService = new PackageDataService();
  const projectDataService = new ProjectDataService();
  const searchDataService = new SearchDataService();
  const prepDataService = new PrepDataService();
  const dedupeDataService = new DedupeDataService();
  const prescreenDataService = new PrescreenDataService();
  const pdfDataService = new PdfDataService();
  const screenDataService = new ScreenDataService();
  const dataSectionDataService = new DataSectionDataService();

  settings.project = new Project();
  projectDataService.projectFromSettings(
    settings.project,
    settingsFile.project
  );

  settings.sources = packageDataService.packagesFromSettings(
    settingsFile.sources
  );

  settings.search = new Search();
  searchDataService.searchFromSettings(settings.search, settingsFile.search);

  settings.prep = new Prep();
  prepDataService.prepFromSettings(settings.prep, settingsFile.prep);

  settings.dedupe = new Dedupe();
  dedupeDataService.dedupeFromSettings(settings.dedupe, settingsFile.dedupe);

  settings.prescreen = new Prescreen();
  prescreenDataService.prescreenFromSettings(
    settings.prescreen,
    settingsFile.prescreen
  );

  settings.pdfGet = new PdfGet();
  pdfDataService.pdfGetFromSettings(settings.pdfGet, settingsFile.pdf_get);

  settings.pdfPrep = new PdfPrep();
  pdfDataService.pdfPrepFromSettings(settings.pdfPrep, settingsFile.pdf_prep);

  settings.screen = new Screen();
  screenDataService.screenFromSettings(settings.screen, settingsFile.screen);

  settings.data = new Data();
  dataSectionDataService.dataFromSettings(settings.data, settingsFile.data);

  return Promise.resolve<Settings>(settings);
};

const saveSettings = async (
  settings: Settings,
  commit?: boolean
): Promise<void> => {
  const packageDataService = new PackageDataService();
  const projectDataService = new ProjectDataService();
  const searchDataService = new SearchDataService();
  const prepDataService = new PrepDataService();
  const dedupeDataService = new DedupeDataService();
  const prescreenDataService = new PrescreenDataService();
  const pdfDataService = new PdfDataService();
  const screenDataService = new ScreenDataService();
  const dataSectionDataService = new DataSectionDataService();

  const newSettingsFile = {
    ...settingsFile,
    project: projectDataService.projectToSettings(
      settings.project,
      settingsFile
    ),
    sources: [],
    search: searchDataService.searchToSettings(settings.search, settingsFile),
    prep: prepDataService.prepToSettings(settings.prep, settingsFile),
    dedupe: dedupeDataService.dedupeToSettings(settings.dedupe),
    prescreen: prescreenDataService.prescreenToSettings(settings.prescreen),
    pdf_get: pdfDataService.pdfGetToSettings(settings.pdfGet),
    pdf_prep: pdfDataService.pdfPrepToSettings(settings.pdfPrep),
    screen: screenDataService.screenToSettings(settings.screen),
    data: dataSectionDataService.dataToSettings(settings.data),
  };

  newSettingsFile.sources = packageDataService.packagesToSettings(
    settings.sources
  );

  let saveSettingsUrl = `${apiEndpoint}/saveSettings`;

  if (commit) {
    saveSettingsUrl += `?commitSelected=${commit}`;
  }

  await httpService.post(saveSettingsUrl, newSettingsFile, {
    headers: { "content-type": "application/json" },
  });

  return Promise.resolve();
};

const getOptions = async (): Promise<any> => {
  const response = await httpService.get(`${apiEndpoint}/getOptions`);
  return response.data;
};

const getPackageDefinitions = async (
  packageType: string
): Promise<PackageDefinition[]> => {
  const response = await httpService.get(
    `${apiEndpoint}/getPackages?PackageEndpointType=${packageType}`
  );

  const packageDefinitions: PackageDefinition[] = [];

  for (const property in response.data) {
    const packageDefinition = new PackageDefinition();
    packageDefinition.name = property;

    const propertyValues = response.data[property];
    packageDefinition.description = propertyValues.description;
    packageDefinition.endpoint = propertyValues.endpoint;

    packageDefinitions.push(packageDefinition);
  }

  return Promise.resolve<PackageDefinition[]>(packageDefinitions);
};

const getPackageParameterDefinitions = async (
  packageType: string,
  packageIdentifier: string
): Promise<PackageParameterDefinition[]> => {
  const response = await httpService.get(
    `${apiEndpoint}/getPackageDetails?PackageEndpointType=${packageType}&PackageIdentifier=${packageIdentifier}&EndpointVersion=1.0`
  );

  const packageParameterDefinitions: PackageParameterDefinition[] = [];

  if (!response.data.properties)
    return Promise.resolve<PackageParameterDefinition[]>(
      packageParameterDefinitions
    );

  const paramsMap = new Map(Object.entries(response.data.properties));

  for (const [key, value] of Array.from<any>(paramsMap)) {
    if (key === "endpoint") {
      continue;
    }

    const param = new PackageParameterDefinition();
    param.name = key;
    param.tooltip = value.tooltip;

    if (value.enum) {
      param.type = PackageParameterType.Options;
      param.options = value.enum;
    } else {
      param.type = getPackageParameterType(value.type);
    }

    param.min = value.min;
    param.max = value.max;

    param.packageType = value.package_endpoint_type;

    packageParameterDefinitions.push(param);
  }

  return Promise.resolve<PackageParameterDefinition[]>(
    packageParameterDefinitions
  );
};

const getPackageParameterType = (
  parameterType: string
): PackageParameterType => {
  let packageParameterType = PackageParameterType.Unknown;

  switch (parameterType) {
    case "integer":
      packageParameterType = PackageParameterType.Int;
      break;
    case "float":
      packageParameterType = PackageParameterType.Float;
      break;
    case "boolean":
      packageParameterType = PackageParameterType.Boolean;
      break;
    case "path":
    case "string":
      packageParameterType = PackageParameterType.String;
      break;
    case "array":
      packageParameterType = PackageParameterType.StringList;
      break;
    case "package_endpoint":
      packageParameterType = PackageParameterType.Package;
      break;
  }

  return packageParameterType;
};

const shutdown = async (): Promise<any> => {
  const response = await httpService.get(`${apiEndpoint}/shutdown`);
  return Promise.resolve(response.data);
};

const dataService = {
  getSettings,
  saveSettings,
  getOptions,
  getPackageDefinitions,
  getPackageParameterDefinitions,
  shutdown,
};

export default dataService;
