import { useEffect, useState } from "react";
import Project from "../../models/project";
import FieldsEditor from "../fields/FieldsEditor";
import AuthorsEditor from "./AuthorsEditor";

const ProjectEditor: React.FC<{
  project: Project;
  projectChanged: any;
  options: any;
}> = ({ project, projectChanged, options }) => {
  const [title, setTitle] = useState<string>();
  const [protocol, setProtocol] = useState<string | null>(null);
  const [reviewType, setReviewType] = useState<string>();
  const [shareStatReq, setShareStatReq] = useState<string>();
  const [delayAutomatedProcessing, setDelayAutomatedProcessing] =
    useState<boolean>(false);

  const [shareStatReqOptions, setShareStatReqOptions] = useState<string[]>([]);

  useEffect(() => {
    if (project) {
      setTitle(project.title);
      setProtocol(project.protocol);
      setReviewType(project.reviewType);
      setShareStatReq(project.shareStatReq);
      setDelayAutomatedProcessing(project.delayAutomatedProcessing);

      if (options) {
        setShareStatReqOptions(
          options.definitions.ProjectSettings.properties.share_stat_req.enum
        );
      }
    }
  }, [project, options]);

  const titleChangedHandler = (event: any) => {
    const newValue = event.target.value;
    const newProject = { ...project, title: newValue };
    projectChanged(newProject);
  };

  const updateProjectAuthors = (newAuthors: string[]) => {
    const newProject = { ...project, authors: newAuthors };
    projectChanged(newProject);
  };

  const updateProjectKeywords = (newKeywords: string[]) => {
    const newProject = { ...project, keywords: newKeywords };
    projectChanged(newProject);
  };

  const protocolChangedHandler = (event: any) => {
    let newValue = event.target.value;

    if (!newValue) {
      newValue = null;
    }

    const newProject = { ...project, protocol: newValue };
    projectChanged(newProject);
  };

  const reviewTypeChangedHandler = (event: any) => {
    const newValue = event.target.value;
    const newProject = { ...project, reviewType: newValue };
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

  return (
    <div>
      <div className="mb-3">
        <label htmlFor="title">Title</label>
        <input
          className="form-control"
          type="text"
          id="title"
          value={title ?? ""}
          onChange={titleChangedHandler}
        />
      </div>
      <div className="mb-3">
        <AuthorsEditor
          authors={project.authors}
          authorsChanged={updateProjectAuthors}
        ></AuthorsEditor>
      </div>
      <div className="mb-3">
        <FieldsEditor
          title="Keywords"
          fields={project.keywords}
          fieldsChanged={updateProjectKeywords}
        />
      </div>
      <div className="mb-3">
        <label htmlFor="protocol">Protocol</label>
        <input
          className="form-control"
          type="text"
          id="protocol"
          value={protocol ?? ""}
          onChange={protocolChangedHandler}
        />
      </div>
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
        <label htmlFor="shareStatReq">Share Stat Req</label>
        <select
          className="form-select"
          aria-label="Select"
          id="shareStatReq"
          value={shareStatReq ?? ""}
          onChange={shareStatReqChangedHandler}
        >
          {shareStatReqOptions.map((shareStatReqOption, index) => (
            <option key={index.toString()}>{shareStatReqOption}</option>
          ))}
        </select>
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
    </div>
  );
};

export default ProjectEditor;
