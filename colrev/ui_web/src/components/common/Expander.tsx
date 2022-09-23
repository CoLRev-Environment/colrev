const Expander: React.FC<{ id: string; children: any }> = ({
  id,
  children,
}) => {
  return (
    <div className="accordion" id={id}>
      {children}
    </div>
  );
};

export default Expander;
