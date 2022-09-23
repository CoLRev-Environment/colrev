import Data from "./data";
import Dedupe from "./dedupe";
import Package from "./package";
import PdfGet from "./pdfGet";
import PdfPrep from "./pdfPrep";
import Prep from "./prep";
import Prescreen from "./prescreen";
import Project from "./project";
import Screen from "./screen";
import Search from "./search";

export default class Settings {
  public project: Project = new Project();
  public sources: Package[] = [];
  public search: Search = new Search();
  public prep: Prep = new Prep();
  public dedupe: Dedupe = new Dedupe();
  public prescreen: Prescreen = new Prescreen();
  public pdfGet: PdfGet = new PdfGet();
  public pdfPrep: PdfPrep = new PdfPrep();
  public screen: Screen = new Screen();
  public data: Data = new Data();
}
