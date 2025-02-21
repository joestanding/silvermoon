import math
from flask import request

def paginate_query(queryset, limit_default=20):
    # Get limit and page from query parameters, with safe defaults
    limit = int(request.args.get("limit", limit_default))
    page = int(request.args.get("page", 1))

    # Ensure limit and page are valid
    limit = max(1, min(limit, 100))
    page = max(1, page)

    # Compute pagination metadata
    total_records = queryset.count()
    total_pages = math.ceil(total_records / limit)
    skip = (page - 1) * limit

    # Fetch paginated results
    paginated_results = queryset.skip(skip).limit(limit)

    return paginated_results, total_records, total_pages, page, limit
