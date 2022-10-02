import Data from "../models/data";
import PackageDataService from "./packageDataService";

export default class DataSectionDataService {
  private packageDataService: PackageDataService = new PackageDataService();

  public dataFromSettings = (data: Data, settingsData: any) => {
    data.packages = this.packageDataService.packagesFromSettings(
      settingsData.data_package_endpoints
    );
  };

  public dataToSettings = (data: Data): any => {
    const settingsData = {
      data_package_endpoints: this.packageDataService.packagesToSettings(
        data.packages
      ),
    };

    return settingsData;
  };
}
