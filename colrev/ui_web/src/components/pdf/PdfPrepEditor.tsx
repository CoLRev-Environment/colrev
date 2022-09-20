import PdfPrep from "../../models/pdfPrep";
import Package from "../../models/package";
import PackagesEditor from "../packages/PackagesEditor";

const PdfPrepEditor: React.FC<{
  pdfPrep: PdfPrep;
  pdfPrepChanged: any;
}> = ({ pdfPrep, pdfPrepChanged }) => {
  const pdfPrepScriptsChangedHandler = (scripts: Package[]) => {
    const newPdfPrep = { ...pdfPrep, scripts: scripts };
    pdfPrepChanged(newPdfPrep);
  };

  const manPdfPrepScriptsChangedHandler = (scripts: Package[]) => {
    const newPdfPrep = { ...pdfPrep, manPdfPrepScripts: scripts };
    pdfPrepChanged(newPdfPrep);
  };

  return (
    <div>
      <div className="mb-3">
        <label>Scripts</label>
        <PackagesEditor
          packageEntity="Script"
          packageType="pdf_prep"
          packages={pdfPrep.scripts}
          packagesChanged={(scripts: Package[]) =>
            pdfPrepScriptsChangedHandler(scripts)
          }
        />
      </div>
      <div className="mb-3">
        <label>Man PDF Prep Scripts</label>
        <PackagesEditor
          packageEntity="Script"
          packageType="pdf_prep_man"
          packages={pdfPrep.manPdfPrepScripts}
          packagesChanged={(scripts: Package[]) =>
            manPdfPrepScriptsChangedHandler(scripts)
          }
        />
      </div>
    </div>
  );
};

export default PdfPrepEditor;
