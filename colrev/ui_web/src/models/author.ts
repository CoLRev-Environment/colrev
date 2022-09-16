export default class Author {
  public name: string = "";
  public initials: string = "";
  public email: string = "";
  public orcid: string | null = null;
  public contributions: string[] = [];
  public affiliations: string | null = null;
  public funding: string[] = [];
  public identifiers: string[] = [];
}
