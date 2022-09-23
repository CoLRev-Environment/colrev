import Author from "./author";

export default class Project {
  public title: string = "";
  public authors: Author[] = [];
  public keywords: string[] = [];
  public protocol: string | null = null;
  public reviewType: string = "";
  public idPattern: string = "";
  public shareStatReq: string = "";
  public delayAutomatedProcessing: boolean = false;
  public curationUrl: string | null = null;
  public curatedMasterdata: boolean = false;
  public curatedFields: string[] = [];
  public colrevVersion: string = "";
}
