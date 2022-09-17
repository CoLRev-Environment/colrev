export default class Script {
  public endpoint: string = "";
  public parameters: Map<string, any> = new Map<string, any>();

  public clone = (): Script => {
    const newScript = new Script();
    newScript.endpoint = this.endpoint;

    newScript.parameters = new Map<string, any>();

    for (const [key, value] of Array.from(this.parameters)) {
      newScript.parameters.set(key, value);
    }

    return newScript;
  };
}
