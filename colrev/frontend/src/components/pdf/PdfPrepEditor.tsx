import PdfPrep from "../../models/pdfPrep";
import Script from "../../models/script";
import ScriptsEditor from "../scripts/ScriptsEditor";

const PdfPrepEditor: React.FC<{
  pdfPrep: PdfPrep;
  pdfPrepChanged: any;
}> = ({ pdfPrep, pdfPrepChanged }) => {
  const pdfPrepScriptsChangedHandler = (scripts: Script[]) => {
    const newPdfPrep = { ...pdfPrep, scripts: scripts };
    pdfPrepChanged(newPdfPrep);
  };

  const manPdfPrepScriptsChangedHandler = (scripts: Script[]) => {
    const newPdfPrep = { ...pdfPrep, manPdfPrepScripts: scripts };
    pdfPrepChanged(newPdfPrep);
  };

  return (
    <div>
      <div className="mb-3">
        <label>Scripts</label>
        <ScriptsEditor
          id="pdfPrepScripts"
          scripts={pdfPrep.scripts}
          scriptsChanged={(scripts: Script[]) =>
            pdfPrepScriptsChangedHandler(scripts)
          }
        />
      </div>
      <div className="mb-3">
        <label>Man PDF Prep Scripts</label>
        <ScriptsEditor
          id="pdfPrepManPdfPrepScripts"
          scripts={pdfPrep.manPdfPrepScripts}
          scriptsChanged={(scripts: Script[]) =>
            manPdfPrepScriptsChangedHandler(scripts)
          }
        />
      </div>
    </div>
  );
};

export default PdfPrepEditor;
