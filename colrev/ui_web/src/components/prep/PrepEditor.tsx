import Prep from "../../models/prep";
import PrepRound from "../../models/prepRound";
import Package from "../../models/package";
import Expander from "../common/Expander";
import ExpanderItem from "../common/ExpanderItem";
import FiedlsEditor from "../fields/FieldsEditor";
import PackagesEditor from "../packages/PackagesEditor";

const PrepEditor: React.FC<{ prep: Prep; prepChanged: any }> = ({
  prep,
  prepChanged,
}) => {
  const updateFieldsToKeep = (newFieldsToKeep: string[]) => {
    const newPrep = { ...prep, fieldsToKeep: newFieldsToKeep };
    prepChanged(newPrep);
  };

  const deletePrepRoundHandler = (prepRound: PrepRound) => {
    const newPrepRounds = prep.prepRounds.filter((p) => p !== prepRound);
    const newPrep = {
      ...prep,
      prepRounds: newPrepRounds,
    };
    prepChanged(newPrep);
  };

  const addPrepRoundHandler = () => {
    const newPrepRound = new PrepRound();
    newPrepRound.name = "new";
    const newPrepRounds = [...prep.prepRounds, newPrepRound];
    const newPrep = {
      ...prep,
      prepRounds: newPrepRounds,
    };
    prepChanged(newPrep);
  };

  const prepRoundfieldChangedHandler = (
    fieldName: string,
    prepRound: any,
    event: any
  ) => {
    const newValue = event.target.value;
    prepRound[fieldName] = newValue;
    const newPrep = { ...prep };
    prepChanged(newPrep);
  };

  const sourcePrepPackagesChangedHandler = (
    packages: Package[],
    prepRound: PrepRound
  ) => {
    prepRound.packages = packages;
    const newPrep = { ...prep };
    prepChanged(newPrep);
  };

  const manPrepPackagesChangedHandler = (packages: Package[]) => {
    const newPrep = { ...prep, manPrepPackages: packages };
    prepChanged(newPrep);
  };

  return (
    <div>
      <div className="mb-3">
        <FiedlsEditor
          title="Fields to Keep"
          fields={prep.fieldsToKeep}
          fieldsChanged={updateFieldsToKeep}
        />
      </div>
      <div className="mb-3">
        <label>Prep Rounds</label>
        <Expander id={`prepRoundsExpander`}>
          {prep.prepRounds.map((prepRound, index) => (
            <ExpanderItem
              key={index.toString()}
              name={prepRound.name}
              id={`prepRound${index + 1}`}
              parentContainerId="prepRoundsExpander"
              show={false}
              hasDelete={true}
              onDelete={() => deletePrepRoundHandler(prepRound)}
            >
              <div className="mb-3">
                <label htmlFor="name">Name</label>
                <input
                  className="form-control"
                  type="text"
                  id="name"
                  value={prepRound.name}
                  onChange={(event) =>
                    prepRoundfieldChangedHandler("name", prepRound, event)
                  }
                />
              </div>
              <div className="mb-3">
                <label htmlFor="similarity">Similarity</label>
                <input
                  className="form-control"
                  type="number"
                  id="similarity"
                  value={prepRound.similarity}
                  onChange={(event) =>
                    prepRoundfieldChangedHandler("similarity", prepRound, event)
                  }
                />
              </div>
              <div className="mb-3">
                <label>Prep Packages</label>
                <PackagesEditor
                  packageEntity="Package"
                  packageType="prep"
                  packages={prepRound.packages}
                  packagesChanged={(packages: Package[]) =>
                    sourcePrepPackagesChangedHandler(packages, prepRound)
                  }
                />
              </div>
            </ExpanderItem>
          ))}
        </Expander>
        <button
          className="btn btn-primary mt-1"
          type="button"
          onClick={addPrepRoundHandler}
        >
          Add
        </button>
      </div>
      <div className="mb-3">
        <label>Man Prep Packages</label>
        <PackagesEditor
          packageEntity="Package"
          packageType="prep_man"
          packages={prep.manPrepPackages}
          packagesChanged={(packages: Package[]) =>
            manPrepPackagesChangedHandler(packages)
          }
        />
      </div>
    </div>
  );
};

export default PrepEditor;
