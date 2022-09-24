import Dedupe from "../models/dedupe";
import PackageDataService from "./packageDataService";

export default class DedupeDataService {
  private packageDataService: PackageDataService = new PackageDataService();

  public dedupeFromSettings = (dedupe: Dedupe, settingsDedupe: any) => {
    dedupe.sameSourceMerges = settingsDedupe.same_source_merges;
    dedupe.scripts = this.packageDataService.packagesFromSettings(
      settingsDedupe.scripts
    );
  };

  public dedupeToSettings = (dedupe: Dedupe): any => {
    const settingsDedupe = {
      same_source_merges: dedupe.sameSourceMerges,
      scripts: this.packageDataService.packagesToSettings(dedupe.scripts),
    };

    return settingsDedupe;
  };
}
