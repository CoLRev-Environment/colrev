import Prescreen from "../models/prescreen";
import PackageDataService from "./packageDataService";

export default class PrescreenDataService {
  private packageDataService = new PackageDataService();

  public prescreenFromSettings = (
    prescreen: Prescreen,
    settingsPrescreen: any
  ) => {
    prescreen.explanation = settingsPrescreen.explanation;
    prescreen.scripts = this.packageDataService.packagesFromSettings(
      settingsPrescreen.scripts
    );
  };

  public prescreenToSettings = (prescreen: Prescreen): any => {
    const settingsPrescreen = {
      explanation: prescreen.explanation,
      scripts: this.packageDataService.packagesToSettings(prescreen.scripts),
    };

    return settingsPrescreen;
  };
}
