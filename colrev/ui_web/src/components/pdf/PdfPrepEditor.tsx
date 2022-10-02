import PdfPrep from "../../models/pdfPrep";
import Package from "../../models/package";
import PackagesEditor from "../packages/PackagesEditor";

const PdfPrepEditor: React.FC<{
  pdfPrep: PdfPrep;
  pdfPrepChanged: any;
}> = ({ pdfPrep, pdfPrepChanged }) => {
  const pdfPrepPackagesChangedHandler = (packages: Package[]) => {
    const newPdfPrep = { ...pdfPrep, packages: packages };
    pdfPrepChanged(newPdfPrep);
  };

  const manPdfPrepPackagesChangedHandler = (packages: Package[]) => {
    const newPdfPrep = { ...pdfPrep, manPdfPrepPackages: packages };
    pdfPrepChanged(newPdfPrep);
  };

  return (
    <div>
      <div className="mb-3">
        <label>Packages</label>
        <PackagesEditor
          packageEntity="Package"
          packageType="pdf_prep"
          packages={pdfPrep.packages}
          packagesChanged={(packages: Package[]) =>
            pdfPrepPackagesChangedHandler(packages)
          }
        />
      </div>
      <div className="mb-3">
        <label>Man PDF Prep Packages</label>
        <PackagesEditor
          packageEntity="Package"
          packageType="pdf_prep_man"
          packages={pdfPrep.manPdfPrepPackages}
          packagesChanged={(packages: Package[]) =>
            manPdfPrepPackagesChangedHandler(packages)
          }
        />
      </div>
    </div>
  );
};

export default PdfPrepEditor;
