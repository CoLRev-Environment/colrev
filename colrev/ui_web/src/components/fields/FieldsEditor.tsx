import DeleteIcon from "../common/icons/DeleteIcon";

const FiedlsEditor: React.FC<{
  title: string;
  fields: string[];
  fieldsChanged: any;
}> = ({ title, fields, fieldsChanged }) => {
  const fieldChangedHandler = (index: number, event: any) => {
    const newFields = fields.map((item, i) =>
      i === index ? event.target.value : item
    );
    fieldsChanged(newFields);
  };

  const deleteFieldHandler = (index: number) => {
    const newFields = fields.filter((item, i) => (i === index ? false : true));
    fieldsChanged(newFields);
  };

  const addFieldHandler = () => {
    const newFields = [...fields, ""];
    fieldsChanged(newFields);
  };

  return (
    <div>
      <label>{title}</label>
      <ul className="list-group">
        {fields.map((field: string, index: number) => (
          <li
            className="d-flex justify-content-between align-items-center mb-2"
            key={index.toString()}
          >
            <input
              className="form-control"
              style={{ marginRight: 8 }}
              type="text"
              value={field}
              onChange={(event) => fieldChangedHandler(index, event)}
            />
            <button
              className="btn btn-danger btn-sm"
              type="button"
              onClick={() => deleteFieldHandler(index)}
            >
              <DeleteIcon />
            </button>
          </li>
        ))}
      </ul>
      <button
        className="btn btn-primary"
        type="button"
        onClick={addFieldHandler}
      >
        Add
      </button>
    </div>
  );
};

export default FiedlsEditor;
