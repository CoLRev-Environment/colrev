import Data from "./data";
import Dedupe from "./dedupe";
import Prep from "./prep";
import Prescreen from "./prescreen";
import Project from "./project";
import Source from "./source";

export default class Settings {
  public project: Project = new Project();
  public sources: Source[] = [];
  public prep: Prep = new Prep();
  public dedupe: Dedupe = new Dedupe();
  public prescreen: Prescreen = new Prescreen();
  public data: Data = new Data();
}
