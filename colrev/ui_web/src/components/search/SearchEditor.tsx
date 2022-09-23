import { useEffect, useState } from "react";
import Search from "../../models/search";

const SearchEditor: React.FC<{ search: Search; searchChanged: any }> = ({
  search,
  searchChanged,
}) => {
  const [retrieveForthcoming, setRetrieveForthcoming] = useState<boolean>(true);

  useEffect(() => {
    if (search) {
      setRetrieveForthcoming(search.retrieveForthcoming);
    }
  }, [search]);

  const retrieveForthcomingChangedHandler = () => {
    const newValue = !retrieveForthcoming;
    setRetrieveForthcoming(newValue);
    const newSearch = {
      ...search,
      retrieveForthcoming: newValue,
    };
    searchChanged(newSearch);
  };

  return (
    <div>
      <div className="form-check form-switch mb-3">
        <input
          className="form-check-input"
          type="checkbox"
          id="retrieveForthcoming"
          checked={retrieveForthcoming}
          onChange={retrieveForthcomingChangedHandler}
        />
        <label className="form-check-label" htmlFor="retrieveForthcoming">
          Retrieve Forthcoming
        </label>
      </div>
    </div>
  );
};

export default SearchEditor;
