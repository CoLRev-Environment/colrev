import ScriptWithLanguageScope from "../../../models/scriptWithLanguageScope";
import FiedlsEditor from "../../fields/FieldsEditor";

const ScriptItemWithLanguageScope: React.FC<{
  script: ScriptWithLanguageScope;
  scriptChanged: any;
}> = ({ script, scriptChanged }) => {
  const endpointChangedHandler = (event: any) => {
    script.endpoint = event.target.value;
    scriptChanged();
  };

  const languageScopeChangedHandler = (newFields: string[]) => {
    script.languageScope = newFields;
    scriptChanged();
  };

  return (
    <div>
      <div className="mb-3">
        <label htmlFor="endpoint">Endpoint</label>
        <input
          className="form-control"
          type="text"
          id="endpoint"
          value={script.endpoint}
          onChange={endpointChangedHandler}
        />
      </div>
      <div className="mb-3">
        <FiedlsEditor
          title="Language Scope"
          fields={script.languageScope}
          fieldsChanged={languageScopeChangedHandler}
        />
      </div>
    </div>
  );
};

export default ScriptItemWithLanguageScope;
