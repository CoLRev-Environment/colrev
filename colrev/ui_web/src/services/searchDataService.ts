import Search from "../models/search";

export default class SearchDataService {
  public searchFromSettings = (search: Search, settingsSearch: any) => {
    search.retrieveForthcoming = settingsSearch.retrieve_forthcoming;
  };

  public searchToSettings = (search: Search, settingsFile: any): any => {
    const settingsFileSearch = {
      ...settingsFile.search,
      retrieve_forthcoming: search.retrieveForthcoming,
    };
    return settingsFileSearch;
  };
}
