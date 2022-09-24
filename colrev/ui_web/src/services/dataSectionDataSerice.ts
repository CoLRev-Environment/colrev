import Data from "../models/data";
import PackageDataService from "./packageDataService";

export default class DataSectionDataService {
  private packageDataService: PackageDataService = new PackageDataService();

  public dataFromSettings = (data: Data, settingsData: any) => {
    data.scripts = this.packageDataService.packagesFromSettings(
      settingsData.scripts
    );
  };

  public dataToSettings = (data: Data): any => {
    const settingsData = {
      scripts: this.packageDataService.packagesToSettings(data.scripts),
    };

    return settingsData;
  };
}
