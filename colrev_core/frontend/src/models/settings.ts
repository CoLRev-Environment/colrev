import Project from "./project";

export default class Settings {
  public project: Project = new Project();
  public load: any = {
    criteria: [],
    scripts: [],
  };
}
