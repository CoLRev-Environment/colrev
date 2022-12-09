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
    pdfGet.packages = this.packageDataService.packagesFromSettings(
      settingsPdfGet.pdf_get_package_endpoints
    );
    pdfGet.manPdfGetPackages = this.packageDataService.packagesFromSettings(
      settingsPdfGet.pdf_get_man_package_endpoints
    );
  };

  public pdfGetToSettings = (pdfGet: PdfGet): any => {
    const settingsPdfGet = {
      pdf_path_type: pdfGet.pdfPathType,
      pdf_required_for_screen_and_synthesis:
        pdfGet.pdfRequiredForScreenAndSynthesis,
      rename_pdfs: pdfGet.renamePdfs,
      pdf_get_package_endpoints: this.packageDataService.packagesToSettings(
        pdfGet.packages
      ),
      pdf_get_man_package_endpoints: this.packageDataService.packagesToSettings(
        pdfGet.manPdfGetPackages
      ),
    };

    return settingsPdfGet;
  };

  public pdfPrepFromSettings = (pdfPrep: PdfPrep, settingsPdfPrep: any) => {
    pdfPrep.keepBackupOfPdfs = settingsPdfPrep.keep_backup_of_pdfs;
    pdfPrep.packages = this.packageDataService.packagesFromSettings(
      settingsPdfPrep.pdf_prep_package_endpoints
    );
    pdfPrep.manPdfPrepPackages = this.packageDataService.packagesFromSettings(
      settingsPdfPrep.pdf_prep_man_package_endpoints
    );
  };

  public pdfPrepToSettings = (pdfPrep: PdfPrep): any => {
    const settingsPdfPrep = {
      keep_backup_of_pdfs: pdfPrep.keepBackupOfPdfs,
      pdf_prep_package_endpoints: this.packageDataService.packagesToSettings(
        pdfPrep.packages
      ),
      pdf_prep_man_package_endpoints:
        this.packageDataService.packagesToSettings(pdfPrep.manPdfPrepPackages),
    };

    return settingsPdfPrep;
  };
}
