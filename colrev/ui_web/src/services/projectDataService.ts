import Project from "../models/project";

export default class ProjectDataService {
  public projectFromSettings = (project: Project, settingsProject: any) => {
    project.title = settingsProject.title;
    project.authors = settingsProject.authors;
    project.keywords = settingsProject.keywords;
    project.protocol = settingsProject.protocol;
    project.reviewType = settingsProject.review_type;
    project.idPattern = settingsProject.id_pattern;
    project.shareStatReq = settingsProject.share_stat_req;
    project.delayAutomatedProcessing =
      settingsProject.delay_automated_processing;
    project.curationUrl = settingsProject.curation_url;
    project.curatedMasterdata = settingsProject.curated_masterdata;
    project.curatedFields = settingsProject.curated_fields;
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
      id_pattern: project.idPattern,
      share_stat_req: project.shareStatReq,
      delay_automated_processing: project.delayAutomatedProcessing,
      curation_url: project.curationUrl,
      curated_masterdata: project.curatedMasterdata,
      curated_fields: project.curatedFields,
    };
    return settingsFileProject;
  };
}
