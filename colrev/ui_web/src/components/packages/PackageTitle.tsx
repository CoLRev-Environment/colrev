import PackageDefinition from "../../models/packageDefinition";

const PackageTitle: React.FC<{ packageDefinition: PackageDefinition }> = ({
  packageDefinition,
}) => {
  return (
    <div>
      {packageDefinition.description && (
        <div>
          {packageDefinition.name} - {packageDefinition.description}
        </div>
      )}
      {!packageDefinition.description && <div>{packageDefinition.name}</div>}
      <div style={{ fontSize: "0.8em" }}>{packageDefinition.endpoint}</div>
    </div>
  );
};

export default PackageTitle;
