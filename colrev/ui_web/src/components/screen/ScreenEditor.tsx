import { useEffect, useState } from "react";
import Screen from "../../models/screen";
import Package from "../../models/package";
import PackagesEditor from "../packages/PackagesEditor";
import Expander from "../common/Expander";
import ExpanderItem from "../common/ExpanderItem";
import ScreenCriteria from "../../models/screenCriteria";

const ScreenEditor: React.FC<{
  screen: Screen;
  screenChanged: any;
  options: any;
}> = ({ screen, screenChanged, options }) => {
  const [explanation, setExplanation] = useState<string | null>(null);
  const [criterionTypeOptions, setCriterionTypeOptions] = useState<[]>([]);

  useEffect(() => {
    if (screen) {
      setExplanation(screen.explanation);
    }
    if (options) {
      setCriterionTypeOptions(
        options.definitions.ScreenCriterion.properties.criterion_type.enum
      );
    }
  }, [screen, options]);

  const explanationChangedHandler = (event: any) => {
    let newValue = event.target.value;

    if (!newValue) {
      newValue = null;
    }

    const newScreen = { ...screen, explanation: newValue };
    screenChanged(newScreen);
  };

  const getCriteriaUnqiqueName = (name: string, criteria: any) => {
    let newName = name;

    while (true) {
      let n = newName;
      const alreadyExists = screen.criteria.find(
        (c) => c.name === n && c !== criteria
      );
      if (alreadyExists) {
        newName = newName + "2";
      } else {
        break;
      }
    }

    return newName;
  };

  const deleteCriteriaHandler = (criteria: ScreenCriteria) => {
    const newCriterias = screen.criteria.filter((c) => c !== criteria);
    const newScreen = { ...screen, criteria: newCriterias };
    screenChanged(newScreen);
  };

  const addCriteriaRoundHandler = () => {
    const newCriteria = new ScreenCriteria();
    newCriteria.name = getCriteriaUnqiqueName("new", newCriteria);
    newCriteria.criterionType = criterionTypeOptions.at(0) ?? "";
    const newCriterias = [...screen.criteria, newCriteria];
    const newScreen = { ...screen, criteria: newCriterias };
    screenChanged(newScreen);
  };

  const criteriaFieldChangedHandler = (
    fieldName: string,
    criteria: any,
    event: any
  ) => {
    let newValue = event.target.value;

    if (fieldName === "name") {
      newValue = getCriteriaUnqiqueName(newValue, criteria);
    }

    criteria[fieldName] = newValue;

    const newScreen = { ...screen };
    screenChanged(newScreen);
  };

  const screenPackagesChangedHandler = (packages: Package[]) => {
    const newScreen = { ...screen, packages: packages };
    screenChanged(newScreen);
  };

  return (
    <div>
      <div className="mb-3">
        <label htmlFor="screenExplanation">Explanation</label>
        <input
          className="form-control"
          type="text"
          id="screenExplanation"
          value={explanation ?? ""}
          onChange={explanationChangedHandler}
        />
      </div>
      <div className="mb-3">
        <label>Criteria</label>
        <Expander id={`screenCriteriaExpander`}>
          {screen.criteria.map((crit, index) => (
            <ExpanderItem
              key={index.toString()}
              name={crit.name}
              id={`screenCriteria${index + 1}`}
              parentContainerId="screenCriteriaExpander"
              show={false}
              hasDelete={true}
              onDelete={() => deleteCriteriaHandler(crit)}
            >
              <div className="mb-3">
                <label>Name</label>
                <input
                  className="form-control"
                  type="text"
                  value={crit.name}
                  onChange={(event) =>
                    criteriaFieldChangedHandler("name", crit, event)
                  }
                />
              </div>
              <div className="mb-3">
                <label>Explanation</label>
                <input
                  className="form-control"
                  type="text"
                  value={crit.explanation}
                  onChange={(event) =>
                    criteriaFieldChangedHandler("explanation", crit, event)
                  }
                />
              </div>
              <div className="mb-3">
                <label>Comment</label>
                <input
                  className="form-control"
                  type="text"
                  value={crit.comment ?? ""}
                  onChange={(event) =>
                    criteriaFieldChangedHandler("comment", crit, event)
                  }
                />
              </div>
              <div className="mb-3">
                <label>Criterion Type</label>
                <select
                  className="form-select"
                  aria-label="Select"
                  value={crit.criterionType ?? ""}
                  onChange={(event) =>
                    criteriaFieldChangedHandler("criterionType", crit, event)
                  }
                >
                  {criterionTypeOptions.map((option, index) => (
                    <option key={index.toString()}>{option}</option>
                  ))}
                </select>
              </div>
            </ExpanderItem>
          ))}
        </Expander>
        <button
          className="btn btn-primary mt-1"
          type="button"
          onClick={addCriteriaRoundHandler}
        >
          Add
        </button>
      </div>
      <div className="mb-3">
        <label>Packages</label>
        <PackagesEditor
          packageEntity="Package"
          packageType="screen"
          packages={screen.packages}
          packagesChanged={(packages: Package[]) =>
            screenPackagesChangedHandler(packages)
          }
        />
      </div>
    </div>
  );
};

export default ScreenEditor;
