"""Errors the query guard returns to the model as readable text."""


class QueryRejectedError(Exception):
    """The query was refused before it reached Azure Data Explorer."""
