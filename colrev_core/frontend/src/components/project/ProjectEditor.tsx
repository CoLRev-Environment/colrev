import { useEffect, useState } from "react";
import Project from "../../models/project";
import FieldsEditor from "../fields/FieldsEditor";

const ProjectEditor: React.FC<{ project: Project; projectChanged: any }> = ({
  project,
  projectChanged,
}) => {
  const [reviewType, setReviewType] = useState<string>();
  const [idPattern, setIdPattern] = useState<string>();
  const [shareStatReq, setShareStatReq] = useState<string>();
  const [delayAutomatedProcessing, setDelayAutomatedProcessing] =
    useState<boolean>(false);
  const [curationUrl, setCurationUrl] = useState<string | null>(null);
  const [curatedMasterdata, setCuratedMasterdata] = useState<boolean>(false);

  useEffect(() => {
    if (project) {
      setReviewType(project.reviewType);
      setIdPattern(project.idPattern);
      setShareStatReq(project.shareStatReq);
      setDelayAutomatedProcessing(project.delayAutomatedProcessing);
      setCurationUrl(project.curationUrl);
      setCuratedMasterdata(project.curatedMasterdata);
    }
  }, [project]);

  const reviewTypeChangedHandler = (event: any) => {
    const newValue = event.target.value;
    //setReviewType(newValue);
    const newProject = { ...project, reviewType: newValue };
    projectChanged(newProject);
  };

  const idPatternChangedHandler = (event: any) => {
    const newProject = { ...project, idPattern: event.target.value };
    projectChanged(newProject);
  };

  const shareStatReqChangedHandler = (event: any) => {
    const newProject = { ...project, shareStatReq: event.target.value };
    projectChanged(newProject);
  };

  const delayAutomatedProcessingChangedHandler = () => {
    const newValue = !delayAutomatedProcessing;
    setDelayAutomatedProcessing(newValue);
    const newProject = {
      ...project,
      delayAutomatedProcessing: newValue,
    };
    projectChanged(newProject);
  };

  const curationUrlChangedHandler = (event: any) => {
    let newValue = event.target.value;

    if (!newValue) {
      newValue = null;
    }

    const newProject = { ...project, curationUrl: newValue };
    projectChanged(newProject);
  };

  const curatedMasterdataChangedHandler = () => {
    const newValue = !curatedMasterdata;
    setCuratedMasterdata(newValue);
    const newProject = {
      ...project,
      curatedMasterdata: newValue,
    };
    projectChanged(newProject);
  };

  const updateProjectCuratedFields = (newCuratedFields: string[]) => {
    const newProject = { ...project, curatedFields: newCuratedFields };
    projectChanged(newProject);
  };

  return (
    <div>
      <div className="mb-3">
        <label htmlFor="reviewType">Review Type</label>
        <input
          className="form-control"
          type="text"
          id="reviewType"
          value={reviewType ?? ""}
          onChange={reviewTypeChangedHandler}
        />
      </div>
      <div className="mb-3">
        <label
          htmlFor="idPattern"
          data-bs-toggle="tooltip"
          title="Specify the format of record identifiers (BibTex citation keys)."
        >
          ID Pattern
        </label>
        <input
          className="form-control"
          type="text"
          id="idPattern"
          value={idPattern ?? ""}
          onChange={idPatternChangedHandler}
        />
      </div>
      <div className="mb-3">
        <label htmlFor="shareStatReq">Share Stat Req</label>
        <input
          className="form-control"
          type="text"
          id="shareStatReq"
          value={shareStatReq ?? ""}
          onChange={shareStatReqChangedHandler}
        />
      </div>
      <div className="form-check form-switch mb-3">
        <input
          className="form-check-input"
          type="checkbox"
          id="delayAutomatedProcessing"
          checked={delayAutomatedProcessing}
          onChange={delayAutomatedProcessingChangedHandler}
        />
        <label className="form-check-label" htmlFor="delayAutomatedProcessing">
          Delay Automated Processing
        </label>
      </div>
      <div className="mb-3">
        <label htmlFor="curationUrl">Curation Url</label>
        <input
          className="form-control"
          type="text"
          id="curationUrl"
          value={curationUrl ?? ""}
          onChange={curationUrlChangedHandler}
        />
      </div>
      <div className="form-check form-switch mb-3">
        <input
          className="form-check-input"
          type="checkbox"
          id="curatedMasterdata"
          checked={curatedMasterdata}
          onChange={curatedMasterdataChangedHandler}
        />
        <label className="form-check-label" htmlFor="curatedMasterdata">
          Curated Masterdata
        </label>
      </div>
      <div className="mb-3">
        <FieldsEditor
          title="Curated Fields"
          fields={project.curatedFields}
          fieldsChanged={updateProjectCuratedFields}
        />
      </div>
    </div>
  );
};

export default ProjectEditor;
