import Prep from "../models/prep";
import PrepRound from "../models/prepRound";
import PackageDataService from "./packageDataService";

export default class PrepDataService {
  private packageDataService: PackageDataService = new PackageDataService();

  public prepFromSettings = (prep: Prep, settingsPrep: any) => {
    prep.fieldsToKeep = settingsPrep.fields_to_keep;

    for (const p of settingsPrep.prep_rounds) {
      const prepRound = new PrepRound();
      prepRound.name = p.name;
      prepRound.similarity = p.similarity;
      prepRound.packages = this.packageDataService.packagesFromSettings(
        p.prep_package_endpoints
      );
      prep.prepRounds.push(prepRound);
    }

    prep.manPrepPackages = this.packageDataService.packagesFromSettings(
      settingsPrep.prep_man_package_endpoints
    );
  };

  public prepToSettings = (prep: Prep, settingsFile: any): any => {
    const settingsFilePrep = {
      ...settingsFile.prep,
      fields_to_keep: prep.fieldsToKeep,
      prep_rounds: [],
      prep_man_package_endpoints: this.packageDataService.packagesToSettings(
        prep.manPrepPackages
      ),
    };

    for (const p of prep.prepRounds) {
      const prep_round = {
        name: p.name,
        similarity: p.similarity,
        prep_package_endpoints: this.packageDataService.packagesToSettings(
          p.packages
        ),
      };

      settingsFilePrep.prep_rounds.push(prep_round);
    }

    return settingsFilePrep;
  };
}
