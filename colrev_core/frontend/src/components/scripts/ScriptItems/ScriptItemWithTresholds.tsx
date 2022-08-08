import ScripWithTresholds from "../../../models/scriptWithTresholds";

const ScriptItemWithTresholds: React.FC<{
  script: ScripWithTresholds;
  scriptChanged: any;
}> = ({ script, scriptChanged }) => {
  const endpointChangedHandler = (event: any) => {
    script.endpoint = event.target.value;
    scriptChanged();
  };

  const mergeTresholdChangedHandler = (event: any) => {
    script.mergeTreshold = event.target.value;
    scriptChanged();
  };

  const partitionTresholdChangedHandler = (event: any) => {
    script.partitionTreshold = event.target.value;
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
        <label htmlFor="mergeTreshold">Merge Threshold</label>
        <input
          className="form-control"
          type="text"
          id="mergeTreshold"
          value={script.mergeTreshold}
          onChange={mergeTresholdChangedHandler}
        />
      </div>
      <div className="mb-3">
        <label htmlFor="partitionTreshold">Partition Threshold</label>
        <input
          className="form-control"
          type="text"
          id="partitionTreshold"
          value={script.partitionTreshold}
          onChange={partitionTresholdChangedHandler}
        />
      </div>
    </div>
  );
};

export default ScriptItemWithTresholds;
