import { useEffect, useState } from "react";
import PdfGet from "../../models/pdfGet";
import Package from "../../models/package";
import PackagesEditor from "../packages/PackagesEditor";

const PdfGetEditor: React.FC<{
  pdfGet: PdfGet;
  pdfGetChanged: any;
  options: any;
}> = ({ pdfGet, pdfGetChanged, options }) => {
  const [
    pdfRequiredForScreenAndSynthesis,
    setPdfRequiredForScreenAndSynthesis,
  ] = useState<boolean>(true);

  const [renamePdfs, setRenamePdfs] = useState<boolean>(true);

  const [pdfPathTypeOptions, setPdfPathTypeOptions] = useState<string[]>([]);

  useEffect(() => {
    if (pdfGet) {
      setPdfRequiredForScreenAndSynthesis(
        pdfGet.pdfRequiredForScreenAndSynthesis
      );
      setRenamePdfs(pdfGet.renamePdfs);
    }

    if (options) {
      setPdfPathTypeOptions(
        options.definitions.PDFGetSettings.properties.pdf_path_type.enum
      );
    }
  }, [pdfGet, options]);

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

  const pdfGetPackagesChangedHandler = (packages: Package[]) => {
    const newPdfGet = { ...pdfGet, packages: packages };
    pdfGetChanged(newPdfGet);
  };

  const manPdfGetPackagesChangedHandler = (packages: Package[]) => {
    const newPdfGet = { ...pdfGet, manPdfGetPackages: packages };
    pdfGetChanged(newPdfGet);
  };

  return (
    <div>
      <div className="mb-3">
        <label htmlFor="pdfPathType">PDF Path Type</label>
        <select
          className="form-select"
          aria-label="Select"
          id="pdfPathType"
          value={pdfGet.pdfPathType ?? ""}
          onChange={pdfPathTypeChangedHandler}
        >
          {pdfPathTypeOptions.map((pdfPathTypeOption, index) => (
            <option key={index.toString()}>{pdfPathTypeOption}</option>
          ))}
        </select>
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
          PDF Required for Screen and Synthesis
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
          Rename PDFs
        </label>
      </div>
      <div className="mb-3">
        <label>Packages</label>
        <PackagesEditor
          packageEntity="Package"
          packageType="pdf_get"
          packages={pdfGet.packages}
          packagesChanged={(packages: Package[]) =>
            pdfGetPackagesChangedHandler(packages)
          }
        />
      </div>
      <div className="mb-3">
        <label>Man PDF Get Packages</label>
        <PackagesEditor
          packageEntity="Package"
          packageType="pdf_get_man"
          packages={pdfGet.manPdfGetPackages}
          packagesChanged={(packages: Package[]) =>
            manPdfGetPackagesChangedHandler(packages)
          }
        />
      </div>
    </div>
  );
};

export default PdfGetEditor;
