import Author from "../../models/author";
import Expander from "../common/Expander";
import ExpanderItem from "../common/ExpanderItem";
import FiedlsEditor from "../fields/FieldsEditor";

const AuthorsEditor: React.FC<{ authors: Author[]; authorsChanged: any }> = ({
  authors,
  authorsChanged,
}) => {
  const authorsChangedHandler = () => {
    const newAuthors = [...authors];
    authorsChanged(newAuthors);
  };

  const deleteAuthorHandler = (author: Author) => {
    const newAuthors = authors.filter((s) => s !== author);
    authorsChanged(newAuthors);
  };

  const addAuthorHandler = () => {
    const newAuthor = new Author();
    newAuthor.name = "Author";
    const newAuthors = [...authors, newAuthor];
    authorsChanged(newAuthors);
  };

  const fieldChangedHandler = (fieldName: string, source: any, event: any) => {
    let newValue = event.target.value;

    if (
      (fieldName === "orcid" || fieldName === "affiliations") &&
      newValue === ""
    ) {
      newValue = null;
    }

    source[fieldName] = newValue;
    authorsChangedHandler();
  };

  const fieldChangedHandlerNewValue = (
    fieldName: string,
    source: any,
    newValue: any
  ) => {
    source[fieldName] = newValue;
    authorsChangedHandler();
  };

  return (
    <div className="mb-3">
      <label>Authors</label>
      <Expander id="authorsExpander">
        {authors.map((author, index) => (
          <ExpanderItem
            key={index.toString()}
            name={author.name}
            id={`author${index + 1}`}
            parentContainerId="authorsExpander"
            show={false}
            hasDelete={true}
            onDelete={() => deleteAuthorHandler(author)}
          >
            <div className="mb-3">
              <label htmlFor={`authorName${index + 1}`}>Name</label>
              <input
                className="form-control"
                type="text"
                id={`authorName${index + 1}`}
                value={author.name}
                onChange={(event) => fieldChangedHandler("name", author, event)}
              />
            </div>
            <div className="mb-3">
              <label htmlFor={`authorInitials${index + 1}`}>Initials</label>
              <input
                className="form-control"
                type="text"
                id={`authorInitials${index + 1}`}
                value={author.initials}
                onChange={(event) =>
                  fieldChangedHandler("initials", author, event)
                }
              />
            </div>
            <div className="mb-3">
              <label htmlFor={`authorEmail${index + 1}`}>Email</label>
              <input
                className="form-control"
                type="text"
                id={`authorEmail${index + 1}`}
                value={author.email}
                onChange={(event) =>
                  fieldChangedHandler("email", author, event)
                }
              />
            </div>
            <div className="mb-3">
              <label htmlFor={`authorOrcid${index + 1}`}>Orcid</label>
              <input
                className="form-control"
                type="text"
                id={`authorOrcid${index + 1}`}
                value={author.orcid ?? ""}
                onChange={(event) =>
                  fieldChangedHandler("orcid", author, event)
                }
              />
            </div>
            <div className="mb-3">
              <FiedlsEditor
                title="Contributions"
                fields={author.contributions}
                fieldsChanged={(newValue: any) =>
                  fieldChangedHandlerNewValue("contributions", author, newValue)
                }
              />
            </div>
            <div className="mb-3">
              <label htmlFor={`authorAffiliations${index + 1}`}>
                Affiliations
              </label>
              <input
                className="form-control"
                type="text"
                id={`authorAffiliations${index + 1}`}
                value={author.affiliations ?? ""}
                onChange={(event) =>
                  fieldChangedHandler("affiliations", author, event)
                }
              />
            </div>
            <div className="mb-3">
              <FiedlsEditor
                title="Funding"
                fields={author.funding}
                fieldsChanged={(newValue: any) =>
                  fieldChangedHandlerNewValue("funding", author, newValue)
                }
              />
            </div>
            <div className="mb-3">
              <FiedlsEditor
                title="Identifiers"
                fields={author.identifiers}
                fieldsChanged={(newValue: any) =>
                  fieldChangedHandlerNewValue("identifiers", author, newValue)
                }
              />
            </div>
          </ExpanderItem>
        ))}
      </Expander>
      <button
        className={"btn btn-primary" + (authors.length > 0 ? " mt-1" : "")}
        type="button"
        onClick={addAuthorHandler}
      >
        Add
      </button>
    </div>
  );
};

export default AuthorsEditor;
