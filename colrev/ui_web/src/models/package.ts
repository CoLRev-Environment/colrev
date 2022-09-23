export default class Package {
  public endpoint: string = "";
  public parameters: Map<string, any> = new Map<string, any>();

  public clone = (): Package => {
    const newPackage = new Package();
    newPackage.endpoint = this.endpoint;

    newPackage.parameters = new Map<string, any>();

    for (const [key, value] of Array.from(this.parameters)) {
      newPackage.parameters.set(key, value);
    }

    return newPackage;
  };
}
