import Package from "./package";

export default class PdfGet {
  public pdfPathType: string = "";
  public pdfRequiredForScreenAndSynthesis: boolean = true;
  public renamePdfs: boolean = true;
  public packages: Package[] = [];
  public manPdfGetPackages: Package[] = [];
}
