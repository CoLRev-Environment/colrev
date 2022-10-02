import Prescreen from "../models/prescreen";
import PackageDataService from "./packageDataService";

export default class PrescreenDataService {
  private packageDataService = new PackageDataService();

  public prescreenFromSettings = (
    prescreen: Prescreen,
    settingsPrescreen: any
  ) => {
    prescreen.explanation = settingsPrescreen.explanation;
    prescreen.packages = this.packageDataService.packagesFromSettings(
      settingsPrescreen.prescreen_package_endpoints
    );
  };

  public prescreenToSettings = (prescreen: Prescreen): any => {
    const settingsPrescreen = {
      explanation: prescreen.explanation,
      prescreen_package_endpoints: this.packageDataService.packagesToSettings(
        prescreen.packages
      ),
    };

    return settingsPrescreen;
  };
}
