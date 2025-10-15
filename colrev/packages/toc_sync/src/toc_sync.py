#!/usr/bin/env python3
"""
General-purpose Markdown table-of-contents (TOC) creator/updater for journals.

What it does
------------
- Scans all *.md files in the current directory.
- Detects TOC files via YAML front matter with keys like:
    ---
    issn:
      - 0276-7783
      - 2162-9730
    include_forthcoming: true
    pdfs_dir: "/home/user/..."   # optional; used to add [PDF] links when available
    format: title_author_doi       # currently supported
    ---
- Fetches works from Crossref for **all** listed ISSNs via colrev's CrossrefAPI.
- Groups by Volume → Issue and renders sections as:
    ## Volume X - Number Y
    - **Title** — Authors; Year; pp. start--end — [doi:10.xxxx/...] (and optional [PDF])
- If include_forthcoming: true, items missing volume/issue render under a dedicated:
    ## Forthcoming
  section.
- Can also create a new TOC file interactively with `--new-toc`, and immediately updates it.

Requirements
------------
pip install colrev pyyaml
# optional (only for --new-toc)
pip install inquirer

Usage
-----
# Update/append TOCs in all *.md files with valid front matter
toc-sync

# Limit to a file/glob
toc-sync --only journal_toc.md
toc-sync --only "toc-*.md"

# Force a full rewrite (not just incremental insert at top)
toc-sync --rewrite

# Create a new TOC interactively (ISSN lookup via Crossref) and update it
toc-sync --new-toc \
  --out toc-mis-quarterly.md \
  --new-pdfs-dir "/home/user/papers" \
  --new-format title_author_doi \
  --new-include-forthcoming
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
import typing
from collections import defaultdict
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional
from typing import Tuple

import colrev.record.record

# Third-party
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # We'll check later and error nicely.

# colrev imports (installed with `pip install colrev`)
from colrev.packages.crossref.src.crossref_api import CrossrefAPI
from colrev.packages.crossref.src import crossref_api
from colrev.constants import Fields

# Optional interactive selector for --new-toc
try:
    import inquirer  # type: ignore
except Exception:  # pragma: no cover
    inquirer = None


# -----------------------------
# Special constants
# -----------------------------

# Internal bucket names for forthcoming items
FORTHCOMING_VOL = "__FORTHCOMING__"
FORTHCOMING_ISS = "__NA__"


# -----------------------------
# Utilities
# -----------------------------


def _safe(s: Any) -> str:
    return "" if s is None else str(s).strip()


def _slug(s: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", s.strip())
    s = re.sub(r"-+", "-", s).strip("-")
    return s.lower() or "journal"


def _authors_to_str(authors_field: str) -> str:
    # colrev records often provide "Lastname, First and Lastname2, First2"
    return _safe(authors_field)


def _sort_key_num_str(val: str) -> Tuple[int, str]:
    # Sort primarily numeric if possible (e.g., "45"), then lexicographically.
    try:
        return (0, f"{int(val):06d}")
    except Exception:
        return (1, (val or "~").lower())


def _pair_sort_key(vol: str, iss: str) -> Tuple[Tuple[int, str], Tuple[int, str]]:
    return (_sort_key_num_str(vol), _sort_key_num_str(iss))


# -----------------------------
# Grouping
# -----------------------------


@dataclass
class TocConfig:
    issns: List[str]
    include_forthcoming: bool = False
    pdfs_dir: Optional[Path] = None
    fmt: str = "title_author_doi"


def _group_records(
    records: List[colrev.record.record.Record], include_forthcoming: bool
) -> Dict[str, Dict[str, List[dict]]]:
    """Group by volume -> issue(number) -> list of records.

    If include_forthcoming is True, records missing volume/number are grouped into
    a dedicated "Forthcoming" section (internal keys FORTHCOMING_VOL/ISS).
    """
    grouped: Dict[str, Dict[str, List[dict]]] = defaultdict(lambda: defaultdict(list))
    seen_dois = set()

    for rec in records:
        data = rec.data  # colrev Record has .data
        doi = _safe(data.get(Fields.DOI, ""))
        if not doi or doi in seen_dois:
            continue
        seen_dois.add(doi)

        vol = _safe(data.get(Fields.VOLUME, ""))
        num = _safe(data.get(Fields.NUMBER, ""))

        if not vol or not num:
            if include_forthcoming:
                vol = FORTHCOMING_VOL
                num = FORTHCOMING_ISS
            else:
                continue

        grouped[vol][num].append(data)

    # Order volumes and issues
    ordered: Dict[str, Dict[str, List[dict]]] = OrderedDict()
    for vol in sorted(grouped.keys(), key=_sort_key_num_str, reverse=False):
        issue_map = grouped[vol]
        ordered_issue_map: Dict[str, List[dict]] = OrderedDict()
        for iss in sorted(issue_map.keys(), key=_sort_key_num_str, reverse=False):
            # Within each issue, sort by first page / title as fallback
            ordered_issue_map[iss] = sorted(
                issue_map[iss],
                key=lambda d: (
                    _safe(d.get(Fields.PAGES, "999999")),
                    _safe(d.get(Fields.TITLE, "")),
                ),
            )
        ordered[vol] = ordered_issue_map
    return ordered


# -----------------------------
# Markdown rendering
# -----------------------------


def _find_local_pdf(doi: str, pdfs_dir: Optional[Path]) -> Optional[str]:
    if not doi or not pdfs_dir:
        return None
    token = doi.replace("/", "_")  # Make a plausible filename token
    if not pdfs_dir.exists():
        return None
    matches = list(pdfs_dir.glob(f"**/*{token}*.pdf"))
    if matches:
        try:
            return os.path.relpath(matches[0], Path.cwd())
        except Exception:
            return str(matches[0])
    return None


def _record_to_md_line(d: dict, cfg: TocConfig) -> str:
    title = _safe(d.get(Fields.TITLE, "Untitled"))
    year = _safe(d.get(Fields.YEAR, ""))
    authors = _authors_to_str(d.get(Fields.AUTHOR, ""))
    doi = _safe(d.get(Fields.DOI, ""))
    url = _safe(d.get(Fields.URL, "")) or (f"https://doi.org/{doi}" if doi else "")
    pages = _safe(d.get(Fields.PAGES, ""))

    # Only format currently supported
    parts: List[str] = [f"**{title}**"]
    meta_bits: List[str] = []
    if authors:
        meta_bits.append(authors)
    if year:
        meta_bits.append(year)
    if pages:
        meta_bits.append(f"pp. {pages}")
    meta = "; ".join(meta_bits)
    if meta:
        parts.append(f" — {meta}")

    if url:
        if doi:
            parts.append(f" — [doi:{doi}]({url})")
        else:
            parts.append(f" — [link]({url})")

    pdf_rel = _find_local_pdf(doi, cfg.pdfs_dir)
    if pdf_rel:
        parts.append(f" — [PDF]({pdf_rel})")

    return "- " + "".join(parts)


def _iter_pairs_desc(
    grouped: Dict[str, Dict[str, List[dict]]],
) -> List[Tuple[str, str]]:
    pairs: List[Tuple[str, str]] = []
    for vol, issues in grouped.items():
        for iss in issues.keys():
            pairs.append((vol, iss))
    pairs.sort(key=lambda p: _pair_sort_key(*p))  # ASC
    pairs.reverse()  # DESC (newest first)
    return pairs


# -----------------------------
# Incremental update (insert at TOP after header)
# + always refresh Forthcoming; normalize legacy headings
# -----------------------------

# Accept both "## Volume X - Number Y" (plus common variants) and "## Forthcoming"
_HEADING_ISSUE_RE = re.compile(
    r"^##\s+Volume\s+(?P<vol>[^-]+?)\s*-\s*(?:Number|No\.|Nr\.|Issue)\s+(?P<iss>\S+)\s*$"
)
_HEADING_FORTHCOMING_RE = re.compile(r"^##\s+Forthcoming\s*$")


def _find_forthcoming_block(lines: List[str]) -> Optional[Tuple[int, int]]:
    """Return (start_idx, end_idx_exclusive) of the Forthcoming section, or None."""
    start = None
    for i, ln in enumerate(lines):
        if _HEADING_FORTHCOMING_RE.match(ln.strip()):
            start = i
            break
    if start is None:
        return None
    # Block ends at next "## " or EOF
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return (start, end)


# Treat legacy "## Volume Forthcoming - Number NA" as the Forthcoming section and normalize it
def _normalize_legacy_forthcoming(lines: List[str]) -> List[str]:
    out = []
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        m = _HEADING_ISSUE_RE.match(s)
        if m:
            vol = m.group("vol").strip().lower()
            iss = m.group("iss").strip().lower()
            if vol == "forthcoming" and iss in {"na", "n/a", "-", ""}:
                # Replace this heading with "## Forthcoming"
                out.append("## Forthcoming\n")
                i += 1
                # Copy everything until the next "## " heading
                while i < len(lines) and not lines[i].startswith("## "):
                    out.append(lines[i])
                    i += 1
                continue
        out.append(lines[i])
        i += 1
    return out


def _parse_existing_headings(
    lines: Iterable[str],
) -> Tuple[
    set[Tuple[str, str]], Optional[Tuple[Tuple[int, str], Tuple[int, str]]], bool
]:
    present: set[Tuple[str, str]] = set()
    latest_key: Optional[Tuple[Tuple[int, str], Tuple[int, str]]] = None
    has_forthcoming = False

    for ln in lines:
        s = ln.strip()
        if _HEADING_FORTHCOMING_RE.match(s):
            has_forthcoming = True
            continue
        m = _HEADING_ISSUE_RE.match(s)
        if not m:
            continue
        vol = m.group("vol").strip()
        iss = m.group("iss").strip()
        present.add((vol, iss))
        key = _pair_sort_key(vol, iss)
        if latest_key is None or key > latest_key:
            latest_key = key
    return present, latest_key, has_forthcoming


def _render_forthcoming_block(records: List[dict], cfg: TocConfig) -> List[str]:
    lines = ["## Forthcoming\n\n"]
    for d in records:
        lines.append(_record_to_md_line(d, cfg) + "\n")
    lines.append("\n")
    return lines


def _render_issue_block(
    vol: str, iss: str, items: List[dict], cfg: TocConfig
) -> List[str]:
    lines = [f"## Volume {vol} - Number {iss}\n\n"]
    for d in items:
        lines.append(_record_to_md_line(d, cfg) + "\n")
    lines.append("\n")
    return lines


def _write_forthcoming_section(
    f: typing.TextIO, records: List[dict], cfg: TocConfig
) -> None:
    f.write("## Forthcoming\n\n")
    for d in records:
        f.write(_record_to_md_line(d, cfg) + "\n")
    f.write("\n")


def _write_full_markdown(
    grouped: Dict[str, Dict[str, List[dict]]], out_path: Path, cfg: TocConfig
) -> None:
    # Preserve header before first "## ..." heading
    header_lines: List[str] = []
    if out_path.exists():
        with out_path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        lines = _normalize_legacy_forthcoming(lines)
        for ln in lines:
            if _HEADING_ISSUE_RE.match(ln.strip()) or _HEADING_FORTHCOMING_RE.match(
                ln.strip()
            ):
                break
            header_lines.append(ln)
    else:
        header_lines = ["# Journal Table of Contents\n\n"]

    with out_path.open("w", encoding="utf-8") as f:
        for ln in header_lines:
            f.write(ln)
        if header_lines and not header_lines[-1].endswith("\n"):
            f.write("\n")

        # 1) Forthcoming first (if any)
        if FORTHCOMING_VOL in grouped and FORTHCOMING_ISS in grouped[FORTHCOMING_VOL]:
            _write_forthcoming_section(
                f, grouped[FORTHCOMING_VOL][FORTHCOMING_ISS], cfg
            )

        # 2) Then numbered issues, newest first
        for vol, iss in _iter_pairs_desc(grouped):
            if vol == FORTHCOMING_VOL and iss == FORTHCOMING_ISS:
                continue
            f.write(f"## Volume {vol} - Number {iss}\n\n")
            for d in grouped[vol][iss]:
                f.write(_record_to_md_line(d, cfg) + "\n")
            f.write("\n")


def _append_incremental(
    grouped: Dict[str, Dict[str, List[dict]]], out_path: Path, cfg: TocConfig
) -> None:
    """
    Incremental update that:
      - Removes any existing 'Forthcoming' block and re-inserts a fresh one
      - Inserts strictly newer issues (vs. latest existing) right AFTER the header
      - Keeps existing content intact below the inserted block
    """
    if not out_path.exists():
        _write_full_markdown(grouped, out_path, cfg)
        return

    with out_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    lines = _normalize_legacy_forthcoming(lines)

    present_pairs, latest_existing, _has_forthcoming = _parse_existing_headings(lines)

    # ---- Build insertion block (to be placed after header)
    insertion: List[str] = []

    # 1) Always refresh Forthcoming (when configured and available)
    forthcoming_records = None
    if (
        cfg.include_forthcoming
        and FORTHCOMING_VOL in grouped
        and FORTHCOMING_ISS in grouped[FORTHCOMING_VOL]
    ):
        forthcoming_records = grouped[FORTHCOMING_VOL][FORTHCOMING_ISS]

    if forthcoming_records is not None:
        # Remove existing Forthcoming block (if any)
        rng = _find_forthcoming_block(lines)
        if rng is not None:
            start, end = rng
            del lines[start:end]
        # Add fresh forthcoming to insertion block
        insertion.extend(_render_forthcoming_block(forthcoming_records, cfg))

    # 2) Determine strictly newer numbered issues
    all_pairs_sorted: List[Tuple[str, str]] = []
    for vol, issues in grouped.items():
        for iss in issues.keys():
            if vol == FORTHCOMING_VOL and iss == FORTHCOMING_ISS:
                continue  # forthcoming handled above
            all_pairs_sorted.append((vol, iss))
    # sort ASC by (vol, iss)
    all_pairs_sorted.sort(key=lambda p: _pair_sort_key(*p))

    to_add: List[Tuple[str, str]] = []
    for vol, iss in all_pairs_sorted:
        if latest_existing is None:
            to_add.append((vol, iss))
            continue
        key = _pair_sort_key(vol, iss)
        if key > latest_existing:
            to_add.append((vol, iss))

    # Insert newer issues in NEWEST-FIRST order at the top
    to_add.sort(key=lambda p: _pair_sort_key(*p), reverse=True)

    for vol, iss in to_add:
        insertion.extend(_render_issue_block(vol, iss, grouped[vol][iss], cfg))

    # If nothing to insert, nothing to do
    if not insertion:
        return

    # ---- Find header end (first "## " or EOF if no headings yet)
    first_h2_idx = next(
        (i for i, ln in enumerate(lines) if ln.startswith("## ")), len(lines)
    )

    # Ensure header ends with a blank line
    if first_h2_idx == len(lines) or (
        first_h2_idx > 0 and not lines[first_h2_idx - 1].endswith("\n")
    ):
        pass  # we'll just splice raw; existing newlines are preserved

    new_lines = lines[:first_h2_idx] + insertion + lines[first_h2_idx:]

    out_path.write_text("".join(new_lines), encoding="utf-8")


# -----------------------------
# Crossref fetch
# -----------------------------


def fetch_records_for_issns(issns: List[str]) -> List[Any]:
    """Use colrev CrossrefAPI to iterate all works for the given ISSNs.
    We use the 'journals/{issn}/works' endpoint for each ISSN and merge.
    """
    all_records: List[Any] = []
    for issn in issns:
        issn = issn.strip()
        if not issn:
            continue
        url = f"https://api.crossref.org/journals/{issn}/works"
        api = CrossrefAPI(
            url=url, rerun=True
        )  # rerun=True => don't use incremental filter
        all_records.extend(list(api.get_records()))
    return all_records


# -----------------------------
# YAML front matter handling
# -----------------------------

_YAML_FENCE = re.compile(r"^---\s*$")


def read_yaml_front_matter(path: Path) -> Tuple[Optional[dict], int]:
    """Return (yaml_dict_or_None, end_line_index_of_front_matter_or_-1).
    If there is no front matter, returns (None, -1).
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if not lines or not _YAML_FENCE.match(lines[0]):
        return None, -1
    # find closing fence
    for i in range(1, len(lines)):
        if _YAML_FENCE.match(lines[i]):
            yaml_block = "".join(lines[1:i])
            try:
                data = yaml.safe_load(yaml_block) if yaml else None
            except Exception as e:  # pragma: no cover
                raise RuntimeError(f"YAML parse error in {path}: {e}")
            return (data or {}), i
    return None, -1


def is_toc_file(meta: Optional[dict]) -> bool:
    if not isinstance(meta, dict):
        return False
    if "issn" not in meta:
        return False
    issn = meta.get("issn")
    return isinstance(issn, list) and all(isinstance(x, (str, int)) for x in issn)


def cfg_from_meta(meta: dict) -> TocConfig:
    issns = [str(x).strip() for x in meta.get("issn", []) if str(x).strip()]
    include_forthcoming = bool(meta.get("include_forthcoming", False))
    pdfs_dir_val = meta.get("pdfs_dir")
    pdfs_dir = Path(str(pdfs_dir_val)) if pdfs_dir_val else None
    fmt = str(meta.get("format", "title_author_doi")).strip() or "title_author_doi"
    return TocConfig(
        issns=issns, include_forthcoming=include_forthcoming, pdfs_dir=pdfs_dir, fmt=fmt
    )


# -----------------------------
# New TOC creation (interactive)
# -----------------------------


def create_new_toc(
    out_path: Optional[str] = None,
    include_forthcoming: bool = True,
    pdfs_dir: Optional[str] = None,
    fmt: str = "title_author_doi",
) -> Optional[Path]:
    if inquirer is None:
        print(
            "ERROR: python-inquirer is not installed. Please `pip install inquirer`.",
            file=sys.stderr,
        )
        return None

    j_name = input("Enter journal name to lookup the ISSN: ").strip()
    if not j_name:
        print("Aborted: empty journal name.", file=sys.stderr)
        return None

    url = "https://api.crossref.org/journals?query=" + j_name.replace(" ", "+")
    endpoint = crossref_api.Endpoint(url)

    items = list(endpoint)
    if not items:
        print("No journals found for that query.", file=sys.stderr)
        return None

    choices = []
    for x in items:
        title = x.get(Fields.TITLE) or x.get("title") or "<untitled>"
        issn = x.get("ISSN") or []
        if isinstance(issn, (str, int)):
            issn = [str(issn)]
        choices.append({str(title): issn})

    questions = [
        inquirer.List(
            Fields.JOURNAL,
            message="Select journal:",
            choices=choices,
        )
    ]
    answers = inquirer.prompt(questions)
    if not answers:
        print("Selection cancelled.", file=sys.stderr)
        return None

    sel_map = answers[Fields.JOURNAL]
    journal_title = list(sel_map.keys())[0]
    issn_list = list(sel_map.values())[0]

    # Determine output filename
    if out_path:
        md_path = Path(out_path)
    else:
        md_path = Path(f"{_slug(journal_title)}.md")

    # Write initial Markdown with YAML front matter and Forthcoming heading
    md_path.write_text(
        "---\n"
        "issn:\n"
        + "".join([f"    - {i}\n" for i in issn_list])
        + f"include_forthcoming: {str(include_forthcoming).lower()}\n"
        + (f'pdfs_dir: "{pdfs_dir}"\n' if pdfs_dir else "")
        + f"format: {fmt}\n"
        "---\n\n"
        f"# {journal_title} (table of content)\n\n"
        "> Generated by [toc-sync](https://colrev-environment.github.io/colrev/"
        "manual/packages/colrev.toc_sync.html) package.  \n"
        "> To update, run `toc-sync` in this directory.\n\n"
        "## Forthcoming\n",
        encoding="utf-8",
    )

    print(f"Created new TOC file: {md_path}")
    return md_path


# -----------------------------
# Main processing
# -----------------------------


def process_file(md_path: Path, only_append: bool = True) -> None:
    meta, _ = read_yaml_front_matter(md_path)
    if not is_toc_file(meta):
        return
    cfg = cfg_from_meta(meta or {})

    try:
        records = fetch_records_for_issns(cfg.issns)
    except Exception as e:
        print(
            f"ERROR: Failed to fetch Crossref records for {md_path.name}: {e}",
            file=sys.stderr,
        )
        return

    grouped = _group_records(records, include_forthcoming=cfg.include_forthcoming)
    if not grouped:
        print(
            f"WARNING: No records grouped for {md_path.name} (skipping)",
            file=sys.stderr,
        )
        return

    try:
        if only_append:
            _append_incremental(grouped, md_path, cfg)
        else:
            _write_full_markdown(grouped, md_path, cfg)
    except Exception as e:
        print(
            f"ERROR: Failed to write Markdown for {md_path.name}: {e}", file=sys.stderr
        )
        return

    print(f"Updated TOC: {md_path}")


def main() -> None:
    if yaml is None:
        print(
            "ERROR: pyyaml not installed. Please `pip install pyyaml`.", file=sys.stderr
        )
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Update or create journal TOC markdown files from Crossref"
    )
    parser.add_argument(
        "--only",
        default=None,
        help="Process only this file or glob (e.g., 'misq.md' or 'toc-*.md')",
    )
    parser.add_argument(
        "--rewrite",
        action="store_true",
        help="Rewrite full TOC instead of incremental insert-at-top",
    )

    # New TOC creation options
    parser.add_argument(
        "--new-toc",
        action="store_true",
        help="Interactively create a new TOC markdown file (ISSN lookup via Crossref)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output path for --new-toc (defaults to <journal>.md)",
    )
    parser.add_argument(
        "--new-pdfs-dir",
        default=None,
        help="Optional pdfs_dir to set in new TOC front matter",
    )
    parser.add_argument(
        "--new-format",
        default="title_author_doi",
        help="Front matter format for new TOC (default: title_author_doi)",
    )
    parser.add_argument(
        "--new-include-forthcoming",
        action="store_true",
        default=True,
        help="Include a Forthcoming section in new TOC (default: true)",
    )

    args = parser.parse_args()

    # If the user wants to create a new TOC,
    # do that first, then immediately update it (full write)
    if args.new_toc:
        created = create_new_toc(
            out_path=args.out,
            include_forthcoming=args.new_include_forthcoming,
            pdfs_dir=args.new_pdfs_dir,
            fmt=args.new_format,
        )
        if created is not None:
            process_file(created, only_append=False)  # full write on first creation
        return

    # Otherwise update/append existing TOCs
    paths: List[Path]
    if args.only:
        paths = [Path(p) for p in glob.glob(args.only)]
    else:
        paths = [p for p in Path.cwd().glob("*.md")]

    if not paths:
        print("No markdown files found.")
        return

    processed_any = False
    for p in paths:
        try:
            meta, _ = read_yaml_front_matter(p)
        except Exception as e:
            print(f"WARNING: Skipping {p}: {e}", file=sys.stderr)
            continue
        if is_toc_file(meta):
            process_file(p, only_append=(not args.rewrite))
            processed_any = True

    if not processed_any:
        print("No TOC markdown files detected (need YAML front matter with 'issn:').")


if __name__ == "__main__":
    main()
