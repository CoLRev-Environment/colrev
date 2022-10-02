import Package from "./package";
import ScreenCriteria from "./screenCriteria";

export default class Screen {
  public explanation: string | null = null;
  public criteria: ScreenCriteria[] = [];
  public packages: Package[] = [];
}
