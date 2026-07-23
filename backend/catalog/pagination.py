from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Allows the frontend to request a page size (e.g. ?page_size=200 to pull
    a whole category in one call) while capping abuse."""
    page_size_query_param = "page_size"
    max_page_size = 200
