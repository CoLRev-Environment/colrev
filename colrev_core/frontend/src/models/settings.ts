import Prep from "./prep";
import Project from "./project";
import Source from "./source";

export default class Settings {
  public project: Project = new Project();
  public sources: Source[] = [];
  public prep: Prep = new Prep();
  public data: any = {
    scripts: [],
  };
}
