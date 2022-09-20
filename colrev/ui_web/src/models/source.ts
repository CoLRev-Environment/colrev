import Package from "./package";
import SearchParameters from "./searchParameters";

export default class Source {
  public filename: string = "";
  public searchType: string = "";
  public sourceName: string = "";
  public sourceIdentifier: string = "";
  public searchParameters: SearchParameters = new SearchParameters();
  public loadConversionScript: Package = new Package();
  public comment: string = "";
}
