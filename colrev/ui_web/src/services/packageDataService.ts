import Package from "../models/package";

export default class PackageDataService {
  public packagesFromSettings = (settingsPackages: any) => {
    const packages: Package[] = [];

    for (const settingsPackage of settingsPackages) {
      const pkg = this.packageFromSettings(settingsPackage);

      // inner packages
      for (const [key, value] of Array.from(pkg.parameters)) {
        var isPackage = value["endpoint"] !== undefined;
        if (isPackage) {
          // new Package() to add the clone() method
          var innerPackage = this.packageFromSettings(value);
          pkg.parameters.set(key, innerPackage);
        }
      }

      packages.push(pkg);
    }

    return packages;
  };

  public packageFromSettings = (settingsPackage: any) => {
    const pkg = new Package();
    pkg.endpoint = settingsPackage.endpoint;

    if (!pkg.endpoint) {
      pkg.endpoint = "unknown";
    }

    const paramsMap = new Map(Object.entries(settingsPackage));
    paramsMap.delete("endpoint");
    pkg.parameters = paramsMap;

    return pkg;
  };

  public packagesToSettings = (packages: Package[]) => {
    const settingsPackages: any[] = [];

    for (const pkg of packages) {
      const settingsPackage = this.packageToSettings(pkg);

      // inner packages
      for (const [key, value] of Array.from(pkg.parameters)) {
        if (value) {
          var isPackage = value["endpoint"] !== undefined;
          if (isPackage) {
            // new Package() to add the clone() method
            var innerPackageSettings = this.packageToSettings(value);
            settingsPackage[key] = innerPackageSettings;
          }
        }
      }

      settingsPackages.push(settingsPackage);
    }

    return settingsPackages;
  };

  public packageToSettings = (pkg: Package) => {
    const paramsMap = new Map<string, any>();
    paramsMap.set("endpoint", pkg.endpoint);

    for (const [key, value] of Array.from(pkg.parameters)) {
      paramsMap.set(key, value);
    }

    const settingsPackage = Object.fromEntries(paramsMap);
    return settingsPackage;
  };
}
