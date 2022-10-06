import Project from "../models/project";

export default class ProjectDataService {
  public projectFromSettings = (project: Project, settingsProject: any) => {
    project.title = settingsProject.title;
    project.authors = settingsProject.authors;
    project.keywords = settingsProject.keywords;
    project.protocol = settingsProject.protocol;
    project.reviewType = settingsProject.review_type;
    project.shareStatReq = settingsProject.share_stat_req;
    project.delayAutomatedProcessing =
      settingsProject.delay_automated_processing;
    project.colrevVersion = settingsProject.colrev_version;
  };

  public projectToSettings = (project: Project, settingsFile: any): any => {
    const settingsFileProject = {
      ...settingsFile.project,
      title: project.title,
      authors: project.authors,
      keywords: project.keywords,
      protocol: project.protocol,
      review_type: project.reviewType,
      share_stat_req: project.shareStatReq,
      delay_automated_processing: project.delayAutomatedProcessing,
    };
    return settingsFileProject;
  };
}
