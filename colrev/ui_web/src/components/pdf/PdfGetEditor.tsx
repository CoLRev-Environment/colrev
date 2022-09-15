import { useEffect, useState } from "react";
import PdfGet from "../../models/pdfGet";
import Script from "../../models/script";
import ScriptsEditor from "../scripts/ScriptsEditor";

const PdfGetEditor: React.FC<{
  pdfGet: PdfGet;
  pdfGetChanged: any;
}> = ({ pdfGet, pdfGetChanged }) => {
  const [
    pdfRequiredForScreenAndSynthesis,
    setPdfRequiredForScreenAndSynthesis,
  ] = useState<boolean>(true);
  const [renamePdfs, setRenamePdfs] = useState<boolean>(true);

  useEffect(() => {
    if (pdfGet) {
      setPdfRequiredForScreenAndSynthesis(
        pdfGet.pdfRequiredForScreenAndSynthesis
      );
      setRenamePdfs(pdfGet.renamePdfs);
    }
  }, [pdfGet]);

  const pdfPathTypeChangedHandler = (event: any) => {
    const newPdfGet = { ...pdfGet, pdfPathType: event.target.value };
    pdfGetChanged(newPdfGet);
  };

  const pdfRequiredForScreenAndSynthesisChangedHandler = () => {
    const newValue = !pdfRequiredForScreenAndSynthesis;
    setPdfRequiredForScreenAndSynthesis(newValue);
    const newPdfGet = {
      ...pdfGet,
      pdfRequiredForScreenAndSynthesis: newValue,
    };
    pdfGetChanged(newPdfGet);
  };

  const renamePdfsChangedHandler = () => {
    const newValue = !renamePdfs;
    setRenamePdfs(newValue);
    const newPdfGet = {
      ...pdfGet,
      renamePdfs: newValue,
    };
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
      <div className="form-check form-switch mb-3">
        <input
          className="form-check-input"
          type="checkbox"
          id="pdfRequiredForScreenAndSynthesis"
          checked={pdfRequiredForScreenAndSynthesis}
          onChange={pdfRequiredForScreenAndSynthesisChangedHandler}
        />
        <label
          className="form-check-label"
          htmlFor="pdfRequiredForScreenAndSynthesis"
        >
          Pdf Required for Screen and Synthesis
        </label>
      </div>
      <div className="form-check form-switch mb-3">
        <input
          className="form-check-input"
          type="checkbox"
          id="renamePdfs"
          checked={renamePdfs}
          onChange={renamePdfsChangedHandler}
        />
        <label className="form-check-label" htmlFor="renamePdfs">
          Rename Pdfs
        </label>
      </div>
      <div className="mb-3">
        <label>Scripts</label>
        <ScriptsEditor
          packageType="pdf_get_scripts"
          scripts={pdfGet.scripts}
          scriptsChanged={(scripts: Script[]) =>
            pdfGetScriptsChangedHandler(scripts)
          }
        />
      </div>
      <div className="mb-3">
        <label>Man PDF Get Scripts</label>
        <ScriptsEditor
          packageType="pdf_get_man_pdf_get_scripts"
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
