export default class Project {
  public reviewType: string = "";
  public idPattern: string = "";
  public shareStatReq: string = "";
  public delayAutomatedProcessing: boolean = false;
  public curationUrl: string | null = null;
  public curatedMasterdata: boolean = false;
  public curatedFields: string[] = [];
}
