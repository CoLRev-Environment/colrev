import Script from "./script";

export default class PdfGet {
  public pdfPathType: string = "";
  public pdfRequiredForScreenAndSynthesis: boolean = true;
  public renamePdfs: boolean = true;
  public scripts: Script[] = [];
  public manPdfGetScripts: Script[] = [];
}
