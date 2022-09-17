import Prep from "../../models/prep";
import PrepRound from "../../models/prepRound";
import Script from "../../models/script";
import Expander from "../common/Expander";
import ExpanderItem from "../common/ExpanderItem";
import FiedlsEditor from "../fields/FieldsEditor";
import ScriptsEditor from "../scripts/ScriptsEditor";

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

  const sourcePrepScriptsChangedHandler = (
    scripts: Script[],
    prepRound: PrepRound
  ) => {
    prepRound.scripts = scripts;
    const newPrep = { ...prep };
    prepChanged(newPrep);
  };

  const mapPrepScriptsChangedHandler = (scripts: Script[]) => {
    const newPrep = { ...prep, manPrepScripts: scripts };
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
                <label>Prep Scripts</label>
                <ScriptsEditor
                  packageType="prep"
                  scripts={prepRound.scripts}
                  scriptsChanged={(scripts: Script[]) =>
                    sourcePrepScriptsChangedHandler(scripts, prepRound)
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
        <label>Man Prep Scripts</label>
        <ScriptsEditor
          packageType="prep_man"
          scripts={prep.manPrepScripts}
          scriptsChanged={(scripts: Script[]) =>
            mapPrepScriptsChangedHandler(scripts)
          }
        />
      </div>
    </div>
  );
};

export default PrepEditor;
