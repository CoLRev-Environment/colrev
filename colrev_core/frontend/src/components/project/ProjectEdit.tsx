import { useEffect, useState } from "react";
import Project from "../../models/project";

const ProjectEdit: React.FC<{ project: Project; projectChanged: any }> = ({
  project,
  projectChanged,
}) => {
  const [title, setTitle] = useState<string>();
  const [curatedFields, setCuratedFields] = useState<string[]>([]);

  useEffect(() => {
    if (project) {
      setTitle(project.title);
      setCuratedFields(project.curatedFields);
    }
  }, [project]);

  const titleChangeHandler = (event: any) => {
    const newTitle = event.target.value;
    //setTitle(newTitle);
    updateProjectTitle(newTitle);
  };

  const curatedFieldChangeHandler = (index: number, event: any) => {
    const newCuratedFields = curatedFields.map((item, i) =>
      i === index ? event.target.value : item
    );

    //setCuratedFields(newCuratedFields);
    updateProjectCuratedFields(newCuratedFields);
  };

  const deleteCuratedFieldHandler = (index: number) => {
    const newCuratedFields = curatedFields.filter((item, i) =>
      i === index ? false : true
    );

    //setCuratedFields(newCuratedFields);
    updateProjectCuratedFields(newCuratedFields);
  };

  const addNewCuratedFieldHandler = () => {
    const newCuratedFields = [...curatedFields, ""];
    //setCuratedFields(newCuratedFields);
    updateProjectCuratedFields(newCuratedFields);
  };

  const updateProjectTitle = (newTitle: string) => {
    const newProject = new Project();
    newProject.title = newTitle;
    newProject.curatedFields = curatedFields;
    projectChanged(newProject);
  };

  const updateProjectCuratedFields = (newCuratedFields: string[]) => {
    const newProject = new Project();
    newProject.title = title ?? "";
    newProject.curatedFields = newCuratedFields;
    projectChanged(newProject);
  };

  return (
    <div>
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
        <label htmlFor="title">Curated Fields</label>
        <ul className="list-group">
          {curatedFields.map((curatedField: string, index: number) => (
            <li
              className="d-flex justify-content-between align-items-center mb-2"
              key={index.toString()}
            >
              <input
                className="form-control"
                style={{ marginRight: 8 }}
                type="text"
                value={curatedField}
                onChange={(event) => curatedFieldChangeHandler(index, event)}
              />
              <button
                className="btn btn-danger"
                type="button"
                onClick={() => deleteCuratedFieldHandler(index)}
              >
                X
              </button>
            </li>
          ))}
        </ul>
        <button
          className="btn btn-primary"
          type="button"
          onClick={addNewCuratedFieldHandler}
        >
          Add
        </button>
      </div>
    </div>
  );
};

export default ProjectEdit;
