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
      prepRound.scripts = this.packageDataService.packagesFromSettings(
        p.scripts
      );
      prep.prepRounds.push(prepRound);
    }

    prep.manPrepScripts = this.packageDataService.packagesFromSettings(
      settingsPrep.man_prep_scripts
    );
  };

  public prepToSettings = (prep: Prep, settingsFile: any): any => {
    const settingsFilePrep = {
      ...settingsFile.prep,
      fields_to_keep: prep.fieldsToKeep,
      prep_rounds: [],
      man_prep_scripts: this.packageDataService.packagesToSettings(
        prep.manPrepScripts
      ),
    };

    for (const p of prep.prepRounds) {
      const prep_round = {
        name: p.name,
        similarity: p.similarity,
        scripts: this.packageDataService.packagesToSettings(p.scripts),
      };

      settingsFilePrep.prep_rounds.push(prep_round);
    }

    return settingsFilePrep;
  };
}
