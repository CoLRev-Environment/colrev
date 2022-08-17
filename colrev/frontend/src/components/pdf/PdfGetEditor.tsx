import PdfGet from "../../models/pdfGet";
import Script from "../../models/script";
import ScriptsEditor from "../scripts/ScriptsEditor";

const PdfGetEditor: React.FC<{
  pdfGet: PdfGet;
  pdfGetChanged: any;
}> = ({ pdfGet, pdfGetChanged }) => {
  const pdfPathTypeChangedHandler = (event: any) => {
    const newPdfGet = { ...pdfGet, pdfPathType: event.target.value };
    pdfGetChanged(newPdfGet);
  };

  const pdfGetScriptsChangedHandler = (scripts: Script[]) => {
    const newPdfGet = { ...pdfGet, scripts: scripts };
    pdfGetChanged(newPdfGet);
  };

  const manPdfGetScriptsChangedHandler = (scripts: Script[]) => {
    const newPdfGet = { ...pdfGet, manPdfGetScripts: scripts };
    pdfGetChanged(newPdfGet);
  };

  return (
    <div>
      <div className="mb-3">
        <label htmlFor="pdfPathType">PDF Path Type</label>
        <input
          className="form-control"
          type="text"
          id="pdfPathType"
          value={pdfGet.pdfPathType}
          onChange={pdfPathTypeChangedHandler}
        />
      </div>
      <div className="mb-3">
        <label>Scripts</label>
        <ScriptsEditor
          id="pdfGetScripts"
          scripts={pdfGet.scripts}
          scriptsChanged={(scripts: Script[]) =>
            pdfGetScriptsChangedHandler(scripts)
          }
        />
      </div>
      <div className="mb-3">
        <label>Man PDF Get Scripts</label>
        <ScriptsEditor
          id="pdfGetManPdfGetScripts"
          scripts={pdfGet.manPdfGetScripts}
          scriptsChanged={(scripts: Script[]) =>
            manPdfGetScriptsChangedHandler(scripts)
          }
        />
      </div>
    </div>
  );
};

export default PdfGetEditor;
