import Screen from "../models/screen";
import ScreenCriteria from "../models/screenCriteria";
import PackageDataService from "./packageDataService";

export default class ScreenDataService {
  private packageDataService = new PackageDataService();

  public screenFromSettings = (screen: Screen, settingsScreen: any) => {
    screen.explanation = settingsScreen.explanation;

    for (const propertName in settingsScreen.criteria) {
      const propertyValue = settingsScreen.criteria[propertName];

      const screenCriteria = new ScreenCriteria();
      screenCriteria.name = propertName;
      screenCriteria.explanation = propertyValue["explanation"];
      screenCriteria.comment = propertyValue["comment"];
      screenCriteria.criterionType = propertyValue["criterion_type"];

      screen.criteria.push(screenCriteria);
    }

    screen.packages = this.packageDataService.packagesFromSettings(
      settingsScreen.screen_package_endpoints
    );
  };

  public screenToSettings = (screen: Screen): any => {
    const settingsScreen = {
      explanation: screen.explanation,
      criteria: {},
      screen_package_endpoints: this.packageDataService.packagesToSettings(
        screen.packages
      ),
    };

    const paramsMap = new Map<string, any>();

    for (const screenCriteria of screen.criteria) {
      paramsMap.set(screenCriteria.name, {
        explanation: screenCriteria.explanation,
        comment: screenCriteria.comment,
        criterion_type: screenCriteria.criterionType,
      });
    }

    settingsScreen.criteria = Object.fromEntries(paramsMap);

    return settingsScreen;
  };
}
