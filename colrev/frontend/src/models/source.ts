import Script from "./script";

export default class Source {
  public filename: string = "";
  public searchType: string = "";
  public sourceName: string = "";
  public sourceIdentifier: string = "";
  public searchParameters: string = "";
  public searchScript: Script = new Script();
  public conversionScript: Script = new Script();
  public sourcePrepScripts: Script[] = [];
  public comment: string = "";
}
