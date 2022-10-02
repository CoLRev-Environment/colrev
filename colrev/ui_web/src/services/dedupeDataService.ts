import Dedupe from "../models/dedupe";
import PackageDataService from "./packageDataService";

export default class DedupeDataService {
  private packageDataService: PackageDataService = new PackageDataService();

  public dedupeFromSettings = (dedupe: Dedupe, settingsDedupe: any) => {
    dedupe.sameSourceMerges = settingsDedupe.same_source_merges;
    dedupe.packages = this.packageDataService.packagesFromSettings(
      settingsDedupe.dedupe_package_endpoints
    );
  };

  public dedupeToSettings = (dedupe: Dedupe): any => {
    const settingsDedupe = {
      same_source_merges: dedupe.sameSourceMerges,
      dedupe_package_endpoints: this.packageDataService.packagesToSettings(
        dedupe.packages
      ),
    };

    return settingsDedupe;
  };
}
