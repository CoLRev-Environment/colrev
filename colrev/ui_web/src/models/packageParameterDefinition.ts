import { PackageParameterType } from "./packageParameterType";

export default class PackageParameterDefinition {
  public name: string = "param";
  public required: boolean = false;
  public tooltip: string = "";
  public type: PackageParameterType = PackageParameterType.String;
  public min: number = 0;
  public max: number = 999;
  public options: [] = [];
  public packageType: string = "";
}
