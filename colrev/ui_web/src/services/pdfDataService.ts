import PdfGet from "../models/pdfGet";
import PdfPrep from "../models/pdfPrep";
import PackageDataService from "./packageDataService";

export default class PdfDataService {
  private packageDataService: PackageDataService = new PackageDataService();

  public pdfGetFromSettings = (pdfGet: PdfGet, settingsPdfGet: any) => {
    pdfGet.pdfPathType = settingsPdfGet.pdf_path_type;
    pdfGet.pdfRequiredForScreenAndSynthesis =
      settingsPdfGet.pdf_required_for_screen_and_synthesis;
    pdfGet.renamePdfs = settingsPdfGet.rename_pdfs;
    pdfGet.scripts = this.packageDataService.packagesFromSettings(
      settingsPdfGet.scripts
    );
    pdfGet.manPdfGetScripts = this.packageDataService.packagesFromSettings(
      settingsPdfGet.man_pdf_get_scripts
    );
  };

  public pdfGetToSettings = (pdfGet: PdfGet): any => {
    const settingsPdfGet = {
      pdf_path_type: pdfGet.pdfPathType,
      pdf_required_for_screen_and_synthesis:
        pdfGet.pdfRequiredForScreenAndSynthesis,
      rename_pdfs: pdfGet.renamePdfs,
      scripts: this.packageDataService.packagesToSettings(pdfGet.scripts),
      man_pdf_get_scripts: this.packageDataService.packagesToSettings(
        pdfGet.manPdfGetScripts
      ),
    };

    return settingsPdfGet;
  };

  public pdfPrepFromSettings = (pdfPrep: PdfPrep, settingsPdfGet: any) => {
    pdfPrep.scripts = this.packageDataService.packagesFromSettings(
      settingsPdfGet.scripts
    );
    pdfPrep.manPdfPrepScripts = this.packageDataService.packagesFromSettings(
      settingsPdfGet.man_pdf_prep_scripts
    );
  };

  public pdfPrepToSettings = (pdfPrep: PdfPrep): any => {
    const settingsPdfPrep = {
      scripts: this.packageDataService.packagesToSettings(pdfPrep.scripts),
      man_pdf_prep_scripts: this.packageDataService.packagesToSettings(
        pdfPrep.manPdfPrepScripts
      ),
    };

    return settingsPdfPrep;
  };
}
