from django.conf import settings
from rest_framework import pagination
from rest_framework.response import Response


class CrudKitPagination(pagination.PageNumberPagination):
    """
    Pagination for the CrudKit API.

    Uses page_size and page query parameters.
    Returns a response with next/previous links and a results field containing the data.
    """

    page_size = settings.REST_FRAMEWORK["PAGE_SIZE"]
    page_size_query_param = "page_size"
    max_page_size = 1000

    def get_paginated_response(self, data):
        return Response(
            {
                "count": self.page.paginator.count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "results": data,
                "page_size": self.get_page_size(self.request),
                "current_page": self.page.number,
                "total_pages": self.page.paginator.num_pages,
            }
        )
