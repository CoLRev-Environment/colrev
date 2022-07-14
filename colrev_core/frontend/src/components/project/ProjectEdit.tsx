import { useEffect, useState } from "react";
import Project from "../../models/project";

const ProjectEdit: React.FC<{ project: Project; projectChanged: any }> = ({
  project,
  projectChanged,
}) => {
  const [title, setTitle] = useState<string>();
  const [relevantFields, setRelevantFields] = useState<string[]>([]);

  useEffect(() => {
    if (project) {
      setTitle(project.title);
      setRelevantFields(project.relevantFields);
    }
  }, [project]);

  const titleChangeHandler = (event: any) => {
    const newTitle = event.target.value;
    //setTitle(newTitle);
    updateProjectTitle(newTitle);
  };

  const relevantFieldChangeHandler = (index: number, event: any) => {
    const newRelevantFields = relevantFields.map((item, i) =>
      i === index ? event.target.value : item
    );

    //setRelevantFields(newRelevantFields);
    updateProjectRelevantFields(newRelevantFields);
  };

  const deleteRelevantFieldHandler = (index: number) => {
    const newRelevantFields = relevantFields.filter((item, i) =>
      i === index ? false : true
    );

    //setRelevantFields(newRelevantFields);
    updateProjectRelevantFields(newRelevantFields);
  };

  const addNewRelevantFieldHandler = () => {
    const newRelevantFields = [...relevantFields, ""];
    //setRelevantFields(newRelevantFields);
    updateProjectRelevantFields(newRelevantFields);
  };

  const updateProjectTitle = (newTitle: string) => {
    const newProject = new Project();
    newProject.title = newTitle;
    newProject.relevantFields = relevantFields;
    projectChanged(newProject);
  };

  const updateProjectRelevantFields = (newRelevantFields: string[]) => {
    const newProject = new Project();
    newProject.title = title ?? "";
    newProject.relevantFields = newRelevantFields;
    projectChanged(newProject);
  };

  return (
    <div>
      <div className="card">
        <div className="card-header">Project</div>
        <div className="card-body">
          <div className="form-group">
            <label htmlFor="title">Title</label>
            <input
              className="form-control"
              type="text"
              id="title"
              value={title ?? ""}
              onChange={titleChangeHandler}
            />
          </div>
          <div className="form-group">
            <label htmlFor="title">Relevant Fields</label>
            <ul className="list-group">
              {relevantFields.map((relevantField: string, index: number) => (
                <li
                  className="d-flex justify-content-between align-items-center mb-2"
                  key={index.toString()}
                >
                  <input
                    className="form-control"
                    style={{ marginRight: 8 }}
                    type="text"
                    value={relevantField}
                    onChange={(event) =>
                      relevantFieldChangeHandler(index, event)
                    }
                  />
                  <button
                    className="btn btn-danger"
                    type="button"
                    onClick={() => deleteRelevantFieldHandler(index)}
                  >
                    X
                  </button>
                </li>
              ))}
            </ul>
            <button
              className="btn btn-primary"
              type="button"
              onClick={addNewRelevantFieldHandler}
            >
              Add
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProjectEdit;
