import Script from "./script";

export default class ScripWithTresholds extends Script {
  public mergeTreshold: number = 0.8;
  public partitionTreshold: number = 0.5;
}
