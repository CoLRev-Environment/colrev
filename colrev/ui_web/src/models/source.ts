import Script from "./script";
import SearchParameters from "./searchParameters";

export default class Source {
  public filename: string = "";
  public searchType: string = "";
  public sourceName: string = "";
  public sourceIdentifier: string = "";
  public searchParameters: SearchParameters = new SearchParameters();
  public loadConversionScript: Script = new Script();
  public comment: string = "";
}
