import Author from "./author";

export default class Project {
  public title: string = "";
  public authors: Author[] = [];
  public keywords: string[] = [];
  public protocol: string | null = null;
  public reviewType: string = "";
  public shareStatReq: string = "";
  public delayAutomatedProcessing: boolean = false;
  public colrevVersion: string = "";
}
