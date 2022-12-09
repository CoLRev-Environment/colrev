import Package from "./package";

export default class PdfPrep {
  public keepBackupOfPdfs: boolean = true;
  public packages: Package[] = [];
  public manPdfPrepPackages: Package[] = [];
}
