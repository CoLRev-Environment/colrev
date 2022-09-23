import DeleteIcon from "./icons/DeleteIcon";

const ExpanderItem: React.FC<{
  name: string;
  id: string;
  parentContainerId: string;
  show: boolean;
  hasDelete?: boolean;
  onDelete?: any;
  children: any;
}> = ({
  name,
  id,
  parentContainerId,
  show,
  hasDelete = false,
  onDelete = undefined,
  children,
}) => {
  return (
    <div className="accordion-item">
      <h2 className="accordion-header" id={`${id}Heading`}>
        <div className="d-flex align-items-center position-relative">
          <button
            className={"accordion-button " + (show ? "" : "collapsed")}
            type="button"
            data-bs-toggle="collapse"
            data-bs-target={`#${id}Collapse`}
            aria-expanded={show}
            aria-controls={`${id}Collapse`}
          >
            {name}
          </button>
          {hasDelete && (
            <div
              className="btn btn-danger btn-sm"
              style={{ position: "absolute", right: "3rem", zIndex: "10" }}
              onClick={onDelete}
            >
              <DeleteIcon />
            </div>
          )}
        </div>
      </h2>
      <div
        id={`${id}Collapse`}
        className={"accordion-collapse collapse " + (show ? "show" : "")}
        aria-labelledby={`${id}Heading`}
        data-bs-parent={`#${parentContainerId}`}
      >
        <div className="accordion-body">{children}</div>
      </div>
    </div>
  );
};

export default ExpanderItem;
