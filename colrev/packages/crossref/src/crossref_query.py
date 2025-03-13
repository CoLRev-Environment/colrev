import logging
import re
from typing import Dict
from typing import List
from typing import Optional

from search_query import AndQuery
from search_query import OrQuery
from search_query.query import Query


class WorksQueryParser:
    """Parser for extracting query components from API query strings."""

    FIELD_QUERIES = {
        "query.affiliation",
        "query.author",
        "query.bibliographic",
        "query.chair",
        "query.container-title",
        "query.contributor",
        "query.degree",
        "query.description",
        "query.editor",
        "query.event-acronym",
        "query.event-location",
        "query.event-name",
        "query.event-sponsor",
        "query.event-theme",
        "query.funder-name",
        "query.publisher-location",
        "query.publisher-name",
        "query.standards-body-acronym",
        "query.standards-body-name",
        "query.title",
        "query.translator",
    }

    QUERY_REGEX = re.compile(r"(\w+(?:\.\w+)?)=([^&]+)")

    def __init__(self, query_string: str):
        self.query_string = query_string
        self.parsed_queries: Dict[str, List[str]] = {}
        self.parse_query()

    def parse_query(self) -> None:
        """Parses the query string into structured components."""
        matches = self.QUERY_REGEX.findall(self.query_string)

        for field, value in matches:
            values = value.split("+")  # Convert "a+b" into an OR query
            values = [v.strip() for v in values if v.strip()]
            if field in self.parsed_queries:
                self.parsed_queries[field].extend(values)
            else:
                self.parsed_queries[field] = values

    def get_free_form_query(self) -> Optional[OrQuery]:
        """Returns the general search query as an OrQuery object."""
        if "query" in self.parsed_queries:
            terms = self.parsed_queries["query"]
            return OrQuery(terms) if len(terms) > 1 else OrQuery([terms[0]])
        return None

    def get_field_queries(self) -> Dict[str, OrQuery]:
        """Returns a dictionary of field queries as OrQuery objects."""
        return {
            field: (
                OrQuery(values, search_field=field)
                if len(values) > 1
                else OrQuery([values[0]], search_field=field)
            )
            for field, values in self.parsed_queries.items()
            if field in self.FIELD_QUERIES
        }

    def parse(self) -> Optional[AndQuery]:
        """Returns a combined AndQuery of all field queries."""
        field_queries = self.get_field_queries()
        if field_queries:
            return AndQuery(list(field_queries.values()), search_field="AB")
        return None

    def __repr__(self) -> str:
        return f"WorksQueryParser({self.parsed_queries})"


def parse(query: str, syntax_version: str, logger: logging.Logger) -> Query:
    if syntax_version == "crossref_1.0":
        assert query.startswith(
            "/works?query"
        ), f"Currently only support /works?query: {query}"

        # query.title=X&query.title=Y does not work as expected (the & is applied as OR)
        # https://api.crossref.org/works?query.title=microsourcing&query.title=Thailand

        query = query[len("/works?") :]

        return WorksQueryParser(query).parse()

    raise ValueError(f"Unsupported syntax version: {syntax_version}")


def serialize_query_object(query: Query) -> str:
    """Serializes a Query object into a properly formatted URL query string."""
    query_params = []
    # TODO : translate search_fields
    if query.search_field is None:
        query.search_field = "query"
    if isinstance(query, OrQuery):
        query_params.append(
            f"{query.search_field}={'+'.join([c.value for c in query.children])}"
        )
    elif isinstance(query, AndQuery):
        for subquery in query.children:
            query_params.append(serialize_query_object(subquery))
    else:
        query_params.append(f"{query.search_field}={query.value}")

    return "&".join(query_params)


def get_query_string(query: Query, syntax_version: str, logger: logging.Logger) -> str:
    if syntax_version == "crossref_1.0":
        search_fields = [q.search_field for q in query.children]
        if isinstance(query, AndQuery) and not len(search_fields) == len(
            set(search_fields)
        ):
            logger.warning(
                "Duplicate search fields detected in query. This may result in unexpected behavior (crossref runs OR instead of AND)."
            )

        return "/works?" + serialize_query_object(query)

    raise ValueError(f"Unsupported syntax version: {syntax_version}")
