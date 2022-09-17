import { ScriptParameterType } from "./scriptParameterType";

export default class ScriptParameterDefinition {
  public name: string = "param";
  public required: boolean = false;
  public tooltip: string = "";
  public type: ScriptParameterType = ScriptParameterType.String;
  public min: number = 0;
  public max: number = 999;
}
