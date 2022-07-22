const ExpanderItem: React.FC<{
  name: string;
  id: string;
  parentContainerId: string;
  show: boolean;
  children: any;
}> = ({ name, id, parentContainerId, show, children }) => {
  return (
    <div className="accordion-item">
      <h2 className="accordion-header" id={`${id}Heading`}>
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
